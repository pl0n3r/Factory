#!/usr/bin/env python3
"""Sonar Watch: lectura Sonar read-only e Issues AUTO idempotentes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quality.contract import QualityContractError, validate_quality_contract
from quality.sonar import factory_project_catalog, normalize_sonar_snapshot
from quality.status import derive_quality_health

AUTO_PREFIX = "[AUTO] Sonar"
MARKER_PREFIX = "<!-- factory-sonar-watch "
_SONAR_PAGE_SIZE = 500
_MAX_SONAR_ISSUES = 10_000
_GITHUB_PAGE_SIZE = 50
_MAX_GITHUB_ISSUES = 10_000
_MAX_GITHUB_ISSUE_PAGES = (_MAX_GITHUB_ISSUES // _GITHUB_PAGE_SIZE) + 1
_MAX_GITHUB_COMMENTS = 1_000
_MAX_GITHUB_COMMENT_PAGES = (_MAX_GITHUB_COMMENTS // _GITHUB_PAGE_SIZE) + 1
SENSITIVE = re.compile(
    r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)"
    r"\s*[:=]|bearer\s+[A-Za-z0-9._~+/-]{8,}"
)
_SONAR_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_ORIGIN_URL = re.compile(
    r"^https://sonarcloud\.io/project/overview\?id=[A-Za-z0-9_.:-]{1,160}$"
)
CONFIG_PATH = ROOT / "quality/sonar-watch-config.json"
_FACTORY_REPOS = {
    "brvtal": "pl0n3r/brvtal",
    "condor": "pl0n3r/Condor",
    "controlbot": "pl0n3r/ControlBot",
    "factory": "pl0n3r/Factory",
    "factoryrunner": "pl0n3r/FactoryRunner",
    "grindflow": "pl0n3r/GrindFlow",
}
_FACTORY_SONAR_KEYS = {
    "brvtal": "pl0n3r_brvtal",
    "condor": "pl0n3r_Condor",
    "controlbot": "pl0n3r_factory-control",
    "factory": "pl0n3r_factory",
    "factoryrunner": "pl0n3r_FactoryRunner",
    "grindflow": "pl0n3r_GrindFlow",
}
_CONFIG_FIELDS = {"version", "provenance", "projects"}
_PROVENANCE_FIELDS = {"issue", "observed_at", "policy"}
_PROJECT_CONFIG_FIELDS = {"project", "sonar_key", "github_repo", "contract"}
_ALLOWED_AUTOSCAN_VALUES = {"true": "automatic", "false": "ci"}


class SonarWatchError(ValueError):
    """El watcher no puede demostrar una operación segura."""


def issue_marker(project: str, signal: str) -> str:
    fingerprint = hashlib.sha256(f"{project}|{signal}".encode()).hexdigest()[:24]
    payload = {"fingerprint": fingerprint, "project": project, "signal": signal, "version": 1}
    return MARKER_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":")) + " -->"


def _safe(value: Any, label: str) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SonarWatchError(f"{label} inválido.") from exc
    if len(encoded.encode()) > 500_000 or SENSITIVE.search(encoded):
        raise SonarWatchError(f"{label} contiene forma sensible.")


def _detail_lines(signal: dict[str, Any]) -> list[str]:
    details = signal.get("details")
    if not isinstance(details, dict):
        raise SonarWatchError("details Sonar inválidos.")
    if signal["signal"] == "quality_gate":
        return [
            f"- QG `{row.get('metric')}`: actual=`{row.get('actual')}`, "
            f"threshold=`{row.get('threshold')}`"
            for row in details.get("failed_conditions", [])
            if isinstance(row, dict)
        ] or ["- sin detalle adicional"]
    if signal["signal"] == "ce_task" and details.get("error_message"):
        return [f"- CE: {details['error_message']}"]
    if signal["signal"] == "historical_debt":
        rows = [
            f"- `{row.get('type')}/{row.get('severity')}`: "
            f"{row.get('count')} abiertos; oldest={row.get('oldest_age_days')}d"
            for row in details.get("counts", [])
            if isinstance(row, dict)
        ]
        rows += [f"- umbral excedido: `{item}`" for item in details.get("exceeded", [])]
        return rows or ["- sin detalle adicional"]
    return ["- sin detalle adicional"]


def _origin_url(sonar_key: str) -> str:
    if not isinstance(sonar_key, str) or _SONAR_KEY.fullmatch(sonar_key) is None:
        raise SonarWatchError("sonar_key inválido.")
    return f"https://sonarcloud.io/project/overview?id={sonar_key}"


def _validate_origin_url(origin_url: str) -> None:
    if not isinstance(origin_url, str) or _ORIGIN_URL.fullmatch(origin_url) is None:
        raise SonarWatchError("origin_url Sonar inválida.")


def render_issue_body(
    project: str,
    signal: dict[str, Any],
    health: dict[str, Any],
    origin: str,
    origin_url: str,
) -> str:
    _validate_origin_url(origin_url)
    _safe(signal, "signal")
    freshness = signal["freshness"]
    refs = "\n".join(f"- `{ref}`" for ref in signal["evidence_refs"]) or "- ninguna"
    classes = ", ".join(f"`{item}`" for item in health.get("work_item_classes", [])) or "`none`"
    return (
        f"{issue_marker(project, signal['signal'])}\n## Sonar Watch\n\n"
        f"Proyecto: `{project}`  \nSeñal: `{signal['signal']}`  \n"
        f"Estado: `{signal['status']}`  \nRazón: `{signal['reason']}`  \n"
        f"Freshness: `{freshness['state']}` "
        f"(age={freshness['age_seconds']}, max={freshness['max_age_seconds']})  \n"
        f"Origen: [`{origin}`]({origin_url})  \n"
        f"Clases correctivas Quality Health: {classes}\n\n"
        f"### Evidencia\n\n{refs}\n\n### Detalle\n\n"
        + "\n".join(_detail_lines(signal))
        + "\n\nEste Issue es administrado automáticamente por Factory Sonar Watch. "
        "No implica escritura sobre Sonar.\n"
    )


def sync_project(
    *, contract, snapshot, observed_at, project_ref, origin_ref, origin_url, issues
):
    if not isinstance(origin_url, str) or _ORIGIN_URL.fullmatch(origin_url) is None:
        raise SonarWatchError("origin_url Sonar inválida.")
    evidence = normalize_sonar_snapshot(contract, snapshot, observed_at=observed_at)
    health = derive_quality_health(
        contract, [], [], observed_at=observed_at, project_ref=project_ref,
        sonar_evidence=evidence,
    )
    sonar = health.get("external_dimensions", {}).get("sonar")
    if not isinstance(sonar, dict) or sonar.get("recalculated") is not False:
        raise SonarWatchError("Quality Health no proyectó Sonar canónicamente.")
    projected = {row["signal"]: row for row in sonar["signals"]}
    operations = []
    for signal in evidence["signals"]:
        canonical = projected.get(signal["signal"])
        if canonical is None or canonical["status"] != signal["status"]:
            raise SonarWatchError("proyección Sonar incoherente.")
        marker = issue_marker(evidence["project"], signal["signal"])
        matches = issues.find(marker)
        if len(matches) > 1:
            raise SonarWatchError("Issues AUTO duplicados para la misma señal.")
        current = matches[0] if matches else None
        if signal["status"] == "NOT_APPLICABLE":
            if current is not None and current["state"] != "closed":
                source_ref = signal["details"].get("source_ref")
                comment_marker = (
                    "<!-- factory-sonar-watch-not-applicable "
                    + json.dumps(
                        {
                            "project": evidence["project"],
                            "signal": signal["signal"],
                            "version": 1,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + " -->"
                )
                comment = (
                    f"{comment_marker}\n"
                    f"ℹ️ Sonar Watch: la señal `{signal['signal']}` pasa a "
                    f"`NOT_APPLICABLE` por `{signal['reason']}` "
                    f"según `{source_ref}`. Se cierra sin tratarla como PASS."
                )
                issues.comment_once(
                    current["number"],
                    marker=comment_marker,
                    body=comment,
                )
                issues.update(
                    current["number"],
                    title=current["title"],
                    body=current["body"],
                    state="closed",
                )
                operations.append({
                    "action": "closed_not_applicable",
                    "signal": signal["signal"],
                })
            continue
        fresh_pass = signal["status"] == "PASS" and signal["freshness"]["state"] == "CURRENT"
        if fresh_pass:
            if current is not None and current["state"] != "closed":
                issues.update(current["number"], title=current["title"], body=current["body"], state="closed")
                operations.append({"action": "closed", "signal": signal["signal"]})
            continue
        title = f"{AUTO_PREFIX} {evidence['project']}: {signal['signal']}"
        body = render_issue_body(
            evidence["project"], signal, sonar, origin_ref, origin_url
        )
        if current is None:
            issues.create(title=title, body=body)
            action = "created"
        else:
            issues.update(current["number"], title=title, body=body, state="open")
            action = "updated"
        operations.append({"action": action, "signal": signal["signal"]})
    return operations


class HttpJson:
    def __init__(self, *, token: str, base_url: str, read_only: bool = False):
        self.token, self.base_url, self.read_only = token, base_url.rstrip("/"), read_only

    def request(self, path: str, *, method: str = "GET", payload: Any = None) -> Any:
        if self.read_only and method != "GET":
            raise SonarWatchError("Sonar Watch solo permite GET contra Sonar.")
        headers = {"Accept": "application/json", "User-Agent": "factory-sonar-watch/1"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read(1_000_001)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise SonarWatchError("falló una API remota.") from exc
        if len(raw) > 1_000_000:
            raise SonarWatchError("respuesta remota excede tamaño máximo.")
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise SonarWatchError("respuesta remota no es JSON.") from exc


class GitHubIssues:
    def __init__(self, *, repository: str, token: str):
        self.repository = repository
        self.http = HttpJson(token=token, base_url="https://api.github.com")

    def find(self, marker: str):
        found = []
        scanned = 0
        for page in range(1, _MAX_GITHUB_ISSUE_PAGES + 1):
            rows = self.http.request(
                f"/repos/{self.repository}/issues?"
                + urlencode({"state": "all", "per_page": _GITHUB_PAGE_SIZE, "page": page})
            )
            if not isinstance(rows, list) or len(rows) > _GITHUB_PAGE_SIZE:
                raise SonarWatchError("respuesta GitHub Issues inválida.")
            scanned += len(rows)
            if scanned > _MAX_GITHUB_ISSUES:
                raise SonarWatchError("paginación GitHub Issues excede límite seguro.")
            for row in rows:
                if "pull_request" not in row and marker in (row.get("body") or ""):
                    found.append({
                        "number": row["number"], "title": row["title"],
                        "body": row.get("body") or "", "state": row["state"],
                    })
            if len(rows) < _GITHUB_PAGE_SIZE:
                return found
        raise SonarWatchError("paginación GitHub Issues excede límite seguro.")

    def create(self, *, title: str, body: str):
        self.http.request(
            f"/repos/{self.repository}/issues", method="POST",
            payload={"title": title, "body": body},
        )

    def update(self, number: int, *, title: str, body: str, state: str):
        self.http.request(
            f"/repos/{self.repository}/issues/{number}", method="PATCH",
            payload={"title": title, "body": body, "state": state},
        )

    def comment(self, number: int, *, body: str):
        self.http.request(
            f"/repos/{self.repository}/issues/{number}/comments", method="POST",
            payload={"body": body},
        )

    def comment_once(self, number: int, *, marker: str, body: str) -> bool:
        scanned = 0
        for page in range(1, _MAX_GITHUB_COMMENT_PAGES + 1):
            rows = self.http.request(
                f"/repos/{self.repository}/issues/{number}/comments?"
                + urlencode({
                    "per_page": _GITHUB_PAGE_SIZE,
                    "page": page,
                })
            )
            if not isinstance(rows, list) or len(rows) > _GITHUB_PAGE_SIZE:
                raise SonarWatchError("respuesta GitHub Comments inválida.")
            scanned += len(rows)
            if scanned > _MAX_GITHUB_COMMENTS:
                raise SonarWatchError(
                    "paginación GitHub Comments excede límite seguro."
                )
            if any(
                isinstance(row, dict) and marker in (row.get("body") or "")
                for row in rows
            ):
                return False
            if len(rows) < _GITHUB_PAGE_SIZE:
                self.comment(number, body=body)
                return True
        raise SonarWatchError(
            "paginación GitHub Comments excede límite seguro."
        )


class SonarApi:
    def __init__(self, *, token: str):
        self.token = token
        self.http = HttpJson(
            token=token,
            base_url="https://sonarcloud.io",
            read_only=True,
        )

    def get(self, path: str, params: dict[str, Any]):
        return self.http.request(
            path + "?" + urlencode(params),
            method="GET",
        )

    def preflight_visibility(self, projects: list[dict[str, Any]]) -> dict[str, str]:
        expected: dict[str, str] = {}
        for cfg in projects:
            contract = cfg.get("contract")
            sonar = contract.get("sonar") if isinstance(contract, dict) else None
            visibility = (
                sonar.get("expected_visibility")
                if isinstance(sonar, dict)
                else None
            )
            if visibility not in {"public", "private"}:
                raise SonarWatchError(
                    "expected_visibility Sonar ausente o ambiguo."
                )
            expected[cfg["project"]] = visibility

        if any(value == "private" for value in expected.values()) and not self.token:
            raise SonarWatchError(
                "contrato Sonar privado sin SONAR_TOKEN; "
                "se aborta antes de cualquier request Sonar."
            )

        observed: dict[str, str] = {}
        for cfg in projects:
            component = self.get(
                "/api/components/show",
                {"component": cfg["sonar_key"]},
            )
            row = component.get("component")
            if not isinstance(row, dict):
                raise SonarWatchError("components/show devolvió shape inválido.")
            visibility = row.get("visibility")
            if visibility not in {"public", "private"}:
                raise SonarWatchError("visibilidad Sonar ausente o ambigua.")
            observed[cfg["project"]] = visibility
        return observed

    @staticmethod
    def analysis_method_from_settings(payload: Any) -> str:
        settings = payload.get("settings") if isinstance(payload, dict) else None
        if not isinstance(settings, list) or len(settings) != 1:
            raise SonarWatchError(
                "sonar.autoscan.enabled debe devolver exactamente un setting."
            )
        row = settings[0]
        if not isinstance(row, dict) or row.get("key") != "sonar.autoscan.enabled":
            raise SonarWatchError("setting sonar.autoscan.enabled inválido.")
        value = row.get("value")
        if not isinstance(value, str) or value not in _ALLOWED_AUTOSCAN_VALUES:
            raise SonarWatchError(
                "sonar.autoscan.enabled debe ser exactamente true o false."
            )
        return _ALLOWED_AUTOSCAN_VALUES[value]

    def _paged(self, path, *, key_name, key, result_name, extra=None):
        rows, page, total = [], 1, None
        while True:
            params = {key_name: key, "ps": _SONAR_PAGE_SIZE, "p": page, **(extra or {})}
            payload = self.get(path, params)
            batch, paging = payload.get(result_name), payload.get("paging")
            if not isinstance(batch, list) or not isinstance(paging, dict):
                raise SonarWatchError("paginación Sonar inválida.")
            candidate = paging.get("total")
            if (
                type(candidate) is not int or candidate < 0 or candidate > _MAX_SONAR_ISSUES
                or paging.get("pageIndex") != page or paging.get("pageSize") != _SONAR_PAGE_SIZE
            ):
                raise SonarWatchError("paginación Sonar incoherente.")
            total = candidate if total is None else total
            if candidate != total:
                raise SonarWatchError("total Sonar cambió durante paginación.")
            rows.extend(batch)
            if len(rows) > total:
                raise SonarWatchError("Sonar devolvió filas excedentes.")
            if len(rows) == total:
                return rows
            if not batch or len(batch) < _SONAR_PAGE_SIZE:
                raise SonarWatchError("Sonar truncó filas antes del total.")
            page += 1

    def _all_issues(self, key):
        return {"issues": self._paged(
            "/api/issues/search", key_name="componentKeys", key=key,
            result_name="issues", extra={"resolved": "false"},
        )}

    def _all_hotspots(self, key):
        return {"hotspots": self._paged(
            "/api/hotspots/search", key_name="projectKey", key=key,
            result_name="hotspots", extra={"status": "TO_REVIEW"},
        )}

    def snapshot(
        self,
        cfg: dict[str, Any],
        *,
        observed_at: str,
        component: dict[str, Any] | None = None,
    ):
        key = cfg["sonar_key"]
        component = component or self.get(
            "/api/components/show",
            {"component": key},
        )
        qg = self.get("/api/qualitygates/project_status", {"projectKey": key})
        analyses = self.get("/api/project_analyses/search", {"project": key, "ps": 1})
        ce = self.get("/api/ce/component", {"component": key})
        measures = self.get(
            "/api/measures/component",
            {"component": key, "metricKeys": "coverage,ncloc"},
        )
        settings = self.get(
            "/api/settings/values",
            {"component": key, "keys": "sonar.autoscan.enabled"},
        )
        return _snapshot_from_api(
            cfg["project"], observed_at, qg, analyses, ce, measures, settings,
            component, self._all_issues(key), self._all_hotspots(key),
        )


def _snapshot_from_api(project, observed_at, qg, analyses, ce, measures, settings, component, issues, hotspots):
    status = qg.get("projectStatus", {})
    conditions = [{
        "metric": row.get("metricKey"), "status": row.get("status"),
        "actual": row.get("actualValue"), "threshold": row.get("errorThreshold"),
    } for row in status.get("conditions", [])]
    analysis_rows = analyses.get("analyses", [])
    coverage = any(
        row.get("metric") == "coverage"
        for row in measures.get("component", {}).get("measures", [])
    )
    debt = []
    for row in issues.get("issues", []):
        kind = {"BUG": "bug", "VULNERABILITY": "vulnerability"}.get(row.get("type"))
        if kind:
            debt.append({
                "type": kind, "severity": row.get("severity", "INFO"),
                "opened_at": row.get("creationDate"),
                "evidence_ref": f"sonar:{project}:issue:{row.get('key', 'unknown')}",
            })
    for row in hotspots.get("hotspots", []):
        if (
            not isinstance(row, dict) or row.get("status") != "TO_REVIEW"
            or row.get("vulnerabilityProbability") not in {"HIGH", "MEDIUM", "LOW"}
            or not isinstance(row.get("key"), str) or not row["key"]
            or not isinstance(row.get("creationDate"), str)
        ):
            raise SonarWatchError("Security Hotspot Sonar inválido.")
        debt.append({
            "type": "hotspot", "severity": row["vulnerabilityProbability"],
            "opened_at": row["creationDate"],
            "evidence_ref": f"sonar:{project}:hotspot:{row['key']}",
        })
    current = ce.get("current")
    method = None if not analysis_rows else SonarApi.analysis_method_from_settings(settings)
    return {
        "project": project, "snapshot_at": observed_at,
        "quality_gate": {"status": status.get("status"), "conditions": conditions},
        "analysis": None if not analysis_rows else {
            "analyzed_at": analysis_rows[0].get("date"),
            "method": method,
            "coverage_available": coverage,
        },
        "ce_task": None if not current else {
            "status": current.get("status"), "error_message": current.get("errorMessage"),
        },
        "organization": None,
        "visibility": component.get("component", {}).get("visibility"),
        "debt": debt,
        "evidence_refs": [f"sonar:{project}:snapshot:{_compact_time(observed_at)}"],
    }


def _compact_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SonarWatchError("observed_at inválido.") from exc
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_runtime_config(path: Path = CONFIG_PATH) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SonarWatchError("configuración Sonar versionada ilegible o inválida.") from exc
    if not isinstance(payload, dict) or set(payload) != _CONFIG_FIELDS or payload.get("version") != 1:
        raise SonarWatchError("configuración Sonar versionada fuera de contrato.")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != _PROVENANCE_FIELDS:
        raise SonarWatchError("provenance Sonar inválida.")
    for field in _PROVENANCE_FIELDS:
        if not isinstance(provenance[field], str) or not provenance[field].strip():
            raise SonarWatchError("provenance Sonar incompleta.")
    projects = payload.get("projects")
    expected = set(factory_project_catalog())
    if not isinstance(projects, list) or len(projects) != len(expected):
        raise SonarWatchError("config debe cubrir exactamente los seis proyectos Factory.")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for cfg in projects:
        if not isinstance(cfg, dict) or set(cfg) != _PROJECT_CONFIG_FIELDS:
            raise SonarWatchError("config de proyecto incompleta.")
        project = cfg["project"]
        if project not in expected or project in seen:
            raise SonarWatchError("config contiene proyecto duplicado o fuera del catálogo.")
        seen.add(project)
        if cfg["github_repo"] != _FACTORY_REPOS[project]:
            raise SonarWatchError("github_repo no coincide con el catálogo Factory.")
        if (
            not isinstance(cfg["sonar_key"], str)
            or cfg["sonar_key"] != _FACTORY_SONAR_KEYS[project]
            or not _SONAR_KEY.fullmatch(cfg["sonar_key"])
        ):
            raise SonarWatchError("sonar_key no coincide con el catálogo Factory.")
        try:
            contract = validate_quality_contract(cfg["contract"])
        except QualityContractError as exc:
            raise SonarWatchError("Quality Contract Sonar inválido.") from exc
        if contract["project"] != project or "sonar" not in contract:
            raise SonarWatchError("Quality Contract no corresponde al proyecto o carece de Sonar.")
        normalized.append({
            "project": project,
            "sonar_key": cfg["sonar_key"],
            "github_repo": cfg["github_repo"],
            "contract": contract,
        })
    if seen != expected or len({cfg["sonar_key"] for cfg in normalized}) != len(normalized):
        raise SonarWatchError("config Sonar no cubre el catálogo de forma única.")
    return normalized


def run_live() -> int:
    token, gh_token = os.getenv("SONAR_TOKEN", ""), os.getenv("GH_TOKEN", "")
    repository = os.getenv("GITHUB_REPOSITORY", "")
    if not gh_token or not repository:
        raise SonarWatchError("configuración runtime incompleta.")
    projects = load_runtime_config()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    sonar = SonarApi(token=token)
    components = sonar.preflight_visibility(projects)
    github = GitHubIssues(repository=repository, token=gh_token)
    operations = []
    for cfg in projects:
        operations += sync_project(
            contract=cfg["contract"],
            snapshot=sonar.snapshot(
                cfg,
                observed_at=now,
                component={"component": {"visibility": components[cfg["project"]]}},
            ),
            observed_at=now,
            project_ref=cfg["github_repo"],
            origin_ref=f"sonar:{cfg['project']}",
            origin_url=_origin_url(cfg["sonar_key"]),
            issues=github,
        )
    print(json.dumps({"operations": operations}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_live())
    except SonarWatchError as exc:
        print(f"sonar-watch: {exc}", file=sys.stderr)
        raise SystemExit(2)
