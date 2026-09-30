#!/usr/bin/env python3
"""Watcher Sonar: lectura read-only + Issues AUTO idempotentes en Factory."""
from __future__ import annotations

import base64
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

from quality.sonar import factory_project_catalog, normalize_sonar_snapshot
from quality.status import derive_quality_health

AUTO_PREFIX = "[AUTO] Sonar"
MARKER_PREFIX = "<!-- factory-sonar-watch "
_SENSITIVE = re.compile(
    r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)"
    r"\s*[:=]|bearer\s+[A-Za-z0-9._~+/-]{8,}"
)
_MAX_GITHUB_ISSUE_PAGES = 100
_MAX_SONAR_ISSUES = 10_000
_SONAR_PAGE_SIZE = 500


class SonarWatchError(ValueError):
    """Fallo seguro del watcher."""


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def _safe_json(value: Any, label: str) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SonarWatchError(f"{label} inválido.") from exc
    if len(encoded.encode()) > 500_000 or _SENSITIVE.search(encoded):
        raise SonarWatchError(f"{label} contiene forma sensible.")
    return value


def _fingerprint(project: str, signal: str) -> str:
    return hashlib.sha256(f"{project}|{signal}".encode()).hexdigest()[:24]


def issue_marker(project: str, signal: str) -> str:
    payload = {
        "fingerprint": _fingerprint(project, signal),
        "project": project,
        "signal": signal,
        "version": 1,
    }
    return MARKER_PREFIX + json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ) + " -->"


def _fresh_current(signal: dict[str, Any]) -> bool:
    freshness = signal.get("freshness")
    return (
        signal.get("status") == "PASS"
        and isinstance(freshness, dict)
        and freshness.get("state") == "CURRENT"
    )


def _detail_lines(signal: dict[str, Any]) -> list[str]:
    details = signal.get("details")
    if not isinstance(details, dict):
        raise SonarWatchError("details Sonar inválidos.")
    name = signal["signal"]
    lines: list[str] = []
    if name == "quality_gate":
        for row in details.get("failed_conditions", []):
            if not isinstance(row, dict):
                raise SonarWatchError("condición QG inválida.")
            lines.append(
                f"- QG `{row.get('metric')}`: actual=`{row.get('actual')}`, "
                f"threshold=`{row.get('threshold')}`"
            )
    elif name == "ce_task" and details.get("error_message"):
        lines.append(f"- CE: {details['error_message']}")
    elif name == "historical_debt":
        for row in details.get("counts", []):
            if not isinstance(row, dict):
                raise SonarWatchError("deuda Sonar inválida.")
            lines.append(
                f"- `{row.get('type')}/{row.get('severity')}`: "
                f"{row.get('count')} abiertos; oldest={row.get('oldest_age_days')}d"
            )
        for item in details.get("exceeded", []):
            lines.append(f"- umbral excedido: `{item}`")
    return lines or ["- sin detalle adicional"]


def render_issue_body(
    *,
    project: str,
    signal: dict[str, Any],
    health_sonar: dict[str, Any],
    origin_ref: str,
) -> str:
    _safe_json(signal, "signal")
    marker = issue_marker(project, signal["signal"])
    freshness = signal["freshness"]
    refs = signal["evidence_refs"]
    classes = health_sonar.get("work_item_classes", [])
    detail = "\n".join(_detail_lines(signal))
    refs_text = "\n".join(f"- `{ref}`" for ref in refs) or "- ninguna"
    classes_text = ", ".join(f"`{item}`" for item in classes) or "`none`"
    return (
        f"{marker}\n"
        "## Sonar Watch\n\n"
        f"Proyecto: `{project}`  \n"
        f"Señal: `{signal['signal']}`  \n"
        f"Estado: `{signal['status']}`  \n"
        f"Razón: `{signal['reason']}`  \n"
        f"Freshness: `{freshness['state']}` "
        f"(age={freshness['age_seconds']}, max={freshness['max_age_seconds']})  \n"
        f"Origen: `{origin_ref}`  \n"
        f"Clases correctivas Quality Health: {classes_text}\n\n"
        "### Evidencia\n\n"
        f"{refs_text}\n\n"
        "### Detalle\n\n"
        f"{detail}\n\n"
        "Este Issue es administrado automáticamente por Factory Sonar Watch. "
        "No implica una acción de escritura sobre Sonar.\n"
    )


def sync_project(
    *,
    contract: dict[str, Any],
    snapshot: dict[str, Any],
    observed_at: str,
    project_ref: str,
    origin_ref: str,
    issues: Any,
) -> list[dict[str, Any]]:
    """Normaliza Sonar, pasa por Quality Health y sincroniza un Issue por señal."""
    evidence = normalize_sonar_snapshot(contract, snapshot, observed_at=observed_at)
    health = derive_quality_health(
        contract,
        [],
        [],
        observed_at=observed_at,
        project_ref=project_ref,
        sonar_evidence=evidence,
    )
    sonar_health = health.get("external_dimensions", {}).get("sonar")
    if not isinstance(sonar_health, dict) or sonar_health.get("recalculated") is not False:
        raise SonarWatchError("Quality Health no proyectó Sonar canónicamente.")

    project = evidence["project"]
    projected = {row["signal"]: row for row in sonar_health["signals"]}
    operations: list[dict[str, Any]] = []
    for signal in evidence["signals"]:
        canonical = projected.get(signal["signal"])
        if canonical is None or canonical["status"] != signal["status"]:
            raise SonarWatchError("proyección Sonar incoherente.")
        marker = issue_marker(project, signal["signal"])
        matches = issues.find(marker)
        if len(matches) > 1:
            raise SonarWatchError(
                "existen Issues AUTO duplicados para la misma señal."
            )
        current = matches[0] if matches else None

        if _fresh_current(signal):
            if current is not None and current["state"] != "closed":
                issues.update(
                    current["number"],
                    title=current["title"],
                    body=current["body"],
                    state="closed",
                )
                operations.append(
                    {"action": "closed", "signal": signal["signal"]}
                )
            continue

        title = f"{AUTO_PREFIX} {project}: {signal['signal']}"
        body = render_issue_body(
            project=project,
            signal=signal,
            health_sonar=sonar_health,
            origin_ref=origin_ref,
        )
        if current is None:
            issues.create(title=title, body=body)
            operations.append(
                {"action": "created", "signal": signal["signal"]}
            )
        else:
            issues.update(
                current["number"], title=title, body=body, state="open"
            )
            operations.append(
                {"action": "updated", "signal": signal["signal"]}
            )
    return operations


class HttpJson:
    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        auth: str = "bearer",
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.auth = auth

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: Any = None,
    ) -> Any:
        url = self.base_url + path
        headers = {
            "Accept": "application/json",
            "User-Agent": "factory-sonar-watch/1",
        }
        if self.token:
            if self.auth == "basic":
                encoded = base64.b64encode(
                    f"{self.token}:".encode()
                ).decode()
                headers["Authorization"] = f"Basic {encoded}"
            elif self.auth == "bearer":
                headers["Authorization"] = f"Bearer {self.token}"
            else:
                raise SonarWatchError("esquema de autenticación inválido.")
        data = None if payload is None else _json_bytes(payload)
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=20) as response:
                raw = response.read(1_000_001)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise SonarWatchError("falló una lectura/API remota.") from exc
        if len(raw) > 1_000_000:
            raise SonarWatchError("respuesta remota excede tamaño máximo.")
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise SonarWatchError("respuesta remota no es JSON.") from exc


class GitHubIssues:
    def __init__(self, *, repository: str, token: str):
        self.repository = repository
        self.http = HttpJson(
            token=token,
            base_url="https://api.github.com",
            auth="bearer",
        )

    def find(self, marker: str) -> list[dict[str, Any]]:
        found = []
        for page in range(1, _MAX_GITHUB_ISSUE_PAGES + 1):
            rows = self.http.request(
                f"/repos/{self.repository}/issues?"
                + urlencode({"state": "all", "per_page": 100, "page": page})
            )
            if not isinstance(rows, list):
                raise SonarWatchError("respuesta GitHub Issues inválida.")
            for row in rows:
                if "pull_request" in row:
                    continue
                if (
                    marker in (row.get("body") or "")
                    and (row.get("user") or {}).get("login") == "github-actions[bot]"
                ):
                    found.append({
                        "number": row["number"],
                        "title": row["title"],
                        "body": row.get("body") or "",
                        "state": row["state"],
                    })
            if len(rows) < 100:
                return found
        raise SonarWatchError(
            "paginación GitHub Issues excede límite seguro."
        )

    def create(self, *, title: str, body: str) -> None:
        self.http.request(
            f"/repos/{self.repository}/issues",
            method="POST",
            payload={"title": title, "body": body},
        )

    def update(
        self,
        number: int,
        *,
        title: str,
        body: str,
        state: str,
    ) -> None:
        self.http.request(
            f"/repos/{self.repository}/issues/{number}",
            method="PATCH",
            payload={"title": title, "body": body, "state": state},
        )


class SonarApi:
    def __init__(self, *, token: str):
        self.http = HttpJson(
            token=token,
            base_url="https://sonarcloud.io",
            auth="basic",
        )

    def get(self, path: str, params: dict[str, Any]) -> Any:
        return self.http.request(path + "?" + urlencode(params))

    def _paged_search(
        self,
        path: str,
        *,
        key_name: str,
        key: str,
        result_name: str,
        extra: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        page = 1
        total: int | None = None
        while True:
            params = {
                key_name: key,
                "ps": _SONAR_PAGE_SIZE,
                "p": page,
            }
            params.update(extra or {})
            payload = self.get(path, params)
            if not isinstance(payload, dict):
                raise SonarWatchError("respuesta Sonar paginada inválida.")
            rows = payload.get(result_name)
            paging = payload.get("paging")
            if not isinstance(rows, list) or not isinstance(paging, dict):
                raise SonarWatchError("paginación Sonar inválida.")
            candidate_total = paging.get("total")
            page_index = paging.get("pageIndex")
            page_size = paging.get("pageSize")
            if (
                type(candidate_total) is not int
                or candidate_total < 0
                or candidate_total > _MAX_SONAR_ISSUES
                or page_index != page
                or page_size != _SONAR_PAGE_SIZE
            ):
                raise SonarWatchError("paginación Sonar incoherente.")
            if total is None:
                total = candidate_total
            elif candidate_total != total:
                raise SonarWatchError("total Sonar cambió durante paginación.")
            collected.extend(rows)
            if len(collected) > total:
                raise SonarWatchError("Sonar devolvió filas excedentes.")
            if len(collected) == total:
                return collected
            if not rows or len(rows) < _SONAR_PAGE_SIZE:
                raise SonarWatchError("Sonar truncó filas antes del total.")
            page += 1

    def _all_issues(self, key: str) -> dict[str, Any]:
        return {
            "issues": self._paged_search(
                "/api/issues/search",
                key_name="componentKeys",
                key=key,
                result_name="issues",
                extra={"resolved": "false"},
            )
        }

    def _all_hotspots(self, key: str) -> dict[str, Any]:
        return {
            "hotspots": self._paged_search(
                "/api/hotspots/search",
                key_name="projectKey",
                key=key,
                result_name="hotspots",
                extra={"status": "TO_REVIEW"},
            )
        }

    def snapshot(
        self,
        cfg: dict[str, Any],
        *,
        observed_at: str,
    ) -> dict[str, Any]:
        key = cfg["sonar_key"]
        project = cfg["project"]
        qg = self.get(
            "/api/qualitygates/project_status",
            {"projectKey": key},
        )
        analyses = self.get(
            "/api/project_analyses/search",
            {"project": key, "ps": 1},
        )
        ce = self.get("/api/ce/component", {"component": key})
        measures = self.get(
            "/api/measures/component",
            {"component": key, "metricKeys": "coverage,ncloc"},
        )
        autoscan = self.get(
            "/api/autoscan/activation",
            {"projectKey": key},
        )
        component = self.get(
            "/api/components/show",
            {"component": key},
        )
        issues = self._all_issues(key)
        hotspots = self._all_hotspots(key)
        return _snapshot_from_api(
            project,
            observed_at,
            qg,
            analyses,
            ce,
            measures,
            autoscan,
            component,
            issues,
            hotspots,
        )


def _snapshot_from_api(
    project,
    observed_at,
    qg,
    analyses,
    ce,
    measures,
    autoscan,
    component,
    issues,
    hotspots,
):
    project_status = qg.get("projectStatus", {})
    qg_conditions = [
        {
            "metric": row.get("metricKey"),
            "status": row.get("status"),
            "actual": row.get("actualValue"),
            "threshold": row.get("errorThreshold"),
        }
        for row in project_status.get("conditions", [])
    ]
    analysis_rows = analyses.get("analyses", [])
    measure_rows = measures.get("component", {}).get("measures", [])
    coverage = any(
        row.get("metric") == "coverage" for row in measure_rows
    )
    current = ce.get("current")
    visibility = component.get("component", {}).get("visibility")
    debt = []
    for row in issues.get("issues", []):
        kind = {
            "BUG": "bug",
            "VULNERABILITY": "vulnerability",
        }.get(row.get("type"))
        if kind is None:
            continue
        debt.append({
            "type": kind,
            "severity": row.get("severity", "INFO"),
            "opened_at": row.get("creationDate"),
            "evidence_ref": (
                f"sonar:{project}:issue:{row.get('key', 'unknown')}"
            ),
        })
    for row in hotspots.get("hotspots", []):
        if (
            not isinstance(row, dict)
            or row.get("status") != "TO_REVIEW"
            or row.get("vulnerabilityProbability") not in {"HIGH", "MEDIUM", "LOW"}
            or not isinstance(row.get("key"), str)
            or not row["key"]
            or not isinstance(row.get("creationDate"), str)
        ):
            raise SonarWatchError("Security Hotspot Sonar inválido.")
        debt.append({
            "type": "hotspot",
            "severity": row["vulnerabilityProbability"],
            "opened_at": row["creationDate"],
            "evidence_ref": (
                f"sonar:{project}:hotspot:{row['key']}"
            ),
        })
    return {
        "project": project,
        "snapshot_at": observed_at,
        "quality_gate": {
            "status": project_status.get("status"),
            "conditions": qg_conditions,
        },
        "analysis": None if not analysis_rows else {
            "analyzed_at": analysis_rows[0].get("date"),
            "method": (
                "automatic"
                if autoscan.get("enable") is True
                else "ci"
            ),
            "coverage_available": coverage,
        },
        "ce_task": None if not current else {
            "status": current.get("status"),
            "error_message": current.get("errorMessage"),
        },
        "organization": None,
        "visibility": visibility,
        "debt": debt,
        "evidence_refs": [
            f"sonar:{project}:snapshot:{_compact_time(observed_at)}"
        ],
    }


def _compact_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise SonarWatchError("observed_at inválido.") from exc
    return parsed.astimezone(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )


def run_live() -> int:
    token = os.environ.get("SONAR_TOKEN", "")
    gh_token = os.environ.get("GH_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    raw_config = os.environ.get("SONAR_WATCH_CONFIG_JSON", "")
    if not token or not gh_token or not repository or not raw_config:
        raise SonarWatchError("configuración runtime incompleta.")
    try:
        config = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        raise SonarWatchError(
            "SONAR_WATCH_CONFIG_JSON inválido."
        ) from exc
    projects = config.get("projects")
    if not isinstance(projects, list):
        raise SonarWatchError("config.projects debe ser lista.")
    expected = set(factory_project_catalog())
    actual = {
        row.get("project")
        for row in projects
        if isinstance(row, dict)
    }
    if actual != expected or len(projects) != len(expected):
        raise SonarWatchError(
            "config debe cubrir exactamente los seis proyectos Factory."
        )

    now = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")
    sonar = SonarApi(token=token)
    gh = GitHubIssues(repository=repository, token=gh_token)
    operations = []
    for cfg in projects:
        if not isinstance(cfg, dict):
            raise SonarWatchError("config de proyecto inválida.")
        contract = cfg.get("contract")
        project_ref = cfg.get("github_repo")
        sonar_key = cfg.get("sonar_key")
        if (
            not isinstance(contract, dict)
            or not isinstance(project_ref, str)
            or not isinstance(sonar_key, str)
            or not sonar_key
        ):
            raise SonarWatchError("config de proyecto incompleta.")
        snapshot = sonar.snapshot(cfg, observed_at=now)
        operations.extend(sync_project(
            contract=contract,
            snapshot=snapshot,
            observed_at=now,
            project_ref=project_ref,
            origin_ref=f"sonar:{cfg['project']}",
            issues=gh,
        ))
    print(json.dumps({"operations": operations}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_live())
    except SonarWatchError as exc:
        print(f"sonar-watch: {exc}", file=sys.stderr)
        raise SystemExit(2)
