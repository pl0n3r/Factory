#!/usr/bin/env python3
"""Runtime acotado del watchdog 4C: inputs canónicos + alertas GitHub propias."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.parse import urlencode

from scripts.unattended_global_idle import (
    CANONICAL_REPOSITORIES,
    evaluate_global_idle_snapshot,
)
from scripts.unattended_guards import (
    GuardDecision,
    evaluate_global_idle_guard,
    evaluate_unattended_guards,
)
from scripts.unattended_kill_switch import evaluate_unattended_kill_switch
from scripts.unattended_state_source import project_state_presence
from scripts.unattended_watchdog import WatchdogDecision, evaluate_unattended_watchdog

CONFIG_FIELDS = frozenset(
    {
        "ready_without_dispatch_minutes",
        "reservation_stale_minutes",
        "state_stale_minutes",
    }
)
GUARD_FIELDS = frozenset(
    {"action", "authority", "pause_allowed", "reasons", "evidence_fingerprint"}
)
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_REPOSITORY = "pl0n3r/Factory"
REPOSITORY_API_PREFIX = "/repos/pl0n3r/Factory/"
READ_REPOSITORY_API_PREFIXES = tuple(
    f"/repos/{repository}/" for repository in CANONICAL_REPOSITORIES
)
ALERT_MARKER_START_RE = re.compile(r"<!--\s*factory-unattended-watchdog-alert\b")
ALERT_MARKER_RE = re.compile(
    r"<!--\s*factory-unattended-watchdog-alert\s+(\{.*?\})\s*-->",
    re.DOTALL,
)
ALERT_TITLE = "[AUTO][WATCHDOG]"
API_HOST = "api.github.com"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "unattended-watchdog.json"
MAX_STDIN_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
COLLECTION_PAGE_SIZE = 50
MAX_PAGES = 20
OWNED_ALERT_CREATOR = "github-actions[bot]"
READY_WORK_LABELS = frozenset({"estado: disponible", "status: available"})
RESERVED_WORK_LABELS = frozenset({"estado: reservado", "status: reserved"})
REVIEW_WORK_LABELS = frozenset({"estado: en revisión", "status: in review"})
ACTIVE_WORK_LABELS = READY_WORK_LABELS | RESERVED_WORK_LABELS | REVIEW_WORK_LABELS


class RuntimeValidationError(ValueError):
    """Contrato runtime inválido o fuera del límite permitido."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeValidationError("duplicate_json_key")
        result[key] = value
    return result


@dataclass(frozen=True)
class AlertSpec:
    fingerprint: str
    severity: str
    code: str
    reasons: tuple[str, ...]
    evidence_fingerprint: str


@dataclass(frozen=True)
class AlertPlan:
    action: str
    authority: str
    create: tuple[AlertSpec, ...]
    reopen: tuple[tuple[int, AlertSpec], ...]
    close: tuple[int, ...]
    evidence_fingerprint: str


def _closed(mapping: object, fields: frozenset[str], label: str) -> dict[str, object]:
    if not isinstance(mapping, dict) or set(mapping) != fields:
        raise RuntimeValidationError(f"invalid_{label}_shape")
    return mapping


def normalize_config(payload: object) -> dict[str, int]:
    row = _closed(payload, CONFIG_FIELDS, "config")
    result: dict[str, int] = {}
    for key in sorted(CONFIG_FIELDS):
        value = row[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RuntimeValidationError(f"invalid_{key}")
        result[key] = value
    return result


def guard_from_payload(payload: object) -> GuardDecision | None:
    try:
        row = _closed(payload, GUARD_FIELDS, "guard")
    except RuntimeValidationError:
        return None
    reasons = row["reasons"]
    if not isinstance(reasons, list):
        return None
    return GuardDecision(
        action=row["action"],
        authority=row["authority"],
        pause_allowed=row["pause_allowed"],
        reasons=tuple(reasons),
        evidence_fingerprint=row["evidence_fingerprint"],
    )


def _normalize_open_alerts(value: object) -> dict[str, tuple[int, str]]:
    if not isinstance(value, dict):
        raise RuntimeValidationError("invalid_open_alerts")
    result: dict[str, tuple[int, str]] = {}
    for fingerprint, raw in value.items():
        if not isinstance(fingerprint, str) or FINGERPRINT_RE.fullmatch(fingerprint) is None:
            raise RuntimeValidationError("invalid_open_alert")
        if isinstance(raw, int) and not isinstance(raw, bool):
            number, state = raw, "open"
        elif isinstance(raw, dict) and set(raw) == {"number", "state"}:
            number, state = raw["number"], raw["state"]
        else:
            raise RuntimeValidationError("invalid_open_alert")
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or number <= 0
            or state not in {"open", "closed"}
        ):
            raise RuntimeValidationError("invalid_open_alert")
        result[fingerprint] = (number, state)
    return result


def evaluate_runtime(
    config_payload: object,
    guard_payload: object,
    evidence_payload: object,
    open_alerts: object,
) -> tuple[WatchdogDecision, AlertPlan]:
    """Invoca 4C sin recalcular su política y deriva solo efectos de alertas propias."""
    current = _normalize_open_alerts(open_alerts)
    try:
        config = normalize_config(config_payload)
    except RuntimeValidationError:
        config = config_payload

    guard = guard_from_payload(guard_payload)
    evidence = copy.deepcopy(evidence_payload)
    if isinstance(evidence, dict):
        evidence["already_alerted_fingerprints"] = sorted(current)

    decision = evaluate_unattended_watchdog(guard, config, evidence)
    active = {incident.fingerprint: incident for incident in decision.incidents}

    create = tuple(
        AlertSpec(
            fingerprint=incident.fingerprint,
            severity=incident.severity,
            code=incident.code,
            reasons=incident.reasons,
            evidence_fingerprint=decision.evidence_fingerprint,
        )
        for incident in decision.incidents
        if incident.fingerprint in decision.new_alert_fingerprints
        and incident.fingerprint not in current
    )
    reopen = tuple(
        (
            current[incident.fingerprint][0],
            AlertSpec(
                fingerprint=incident.fingerprint,
                severity=incident.severity,
                code=incident.code,
                reasons=incident.reasons,
                evidence_fingerprint=decision.evidence_fingerprint,
            ),
        )
        for incident in decision.incidents
        if incident.fingerprint in current
        and current[incident.fingerprint][1] == "closed"
    )

    evidence_reconcilable = decision.daily_summary.state_freshness == "fresh"
    close = (
        tuple(sorted(
            alert[0]
            for fp, alert in current.items()
            if alert[1] == "open" and fp not in active
        ))
        if evidence_reconcilable
        else ()
    )
    return decision, AlertPlan(
        action=decision.action,
        authority=decision.authority,
        create=create,
        reopen=reopen,
        close=close,
        evidence_fingerprint=decision.evidence_fingerprint,
    )


def _alert_marker(fingerprint: str) -> str:
    payload = json.dumps(
        {"version": 1, "fingerprint": fingerprint},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"<!-- factory-unattended-watchdog-alert {payload} -->"


def alert_body(spec: AlertSpec) -> str:
    reasons = "\n".join(f"- `{reason}`" for reason in spec.reasons) or "- `none`"
    return (
        f"{_alert_marker(spec.fingerprint)}\n"
        "## Watchdog desatendido\n\n"
        f"Severidad: **{spec.severity}**\n\n"
        f"Código: `{spec.code}`\n\n"
        f"Fingerprint: `{spec.fingerprint}`\n\n"
        f"Evidencia 4C: `{spec.evidence_fingerprint}`\n\n"
        f"### Razones\n{reasons}\n\n"
        "Esta alerta pertenece exclusivamente al runtime unattended-watchdog. "
        "No concede autoridad nueva ni implica go-live, gasto o datos reales.\n"
    )


def parse_owned_alert(issue: object) -> tuple[str, int, str] | None:
    """Reconoce solo alertas creadas por este workflow; nunca Issues ajenos."""
    if not isinstance(issue, dict) or "pull_request" in issue:
        return None
    body = issue.get("body")
    title = issue.get("title")
    number = issue.get("number")
    state = issue.get("state", "open")
    user = issue.get("user")
    if (
        not isinstance(body, str)
        or not isinstance(title, str)
        or not title.startswith(ALERT_TITLE + " ")
        or isinstance(number, bool)
        or not isinstance(number, int)
        or number <= 0
        or state not in {"open", "closed"}
        or not isinstance(user, dict)
        or user.get("login") != "github-actions[bot]"
    ):
        return None
    starts = ALERT_MARKER_START_RE.findall(body)
    markers = ALERT_MARKER_RE.findall(body)
    if len(starts) != 1 or len(markers) != 1:
        return None
    try:
        marker = json.loads(markers[0], object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, RuntimeValidationError):
        return None
    if (
        not isinstance(marker, dict)
        or set(marker) != {"version", "fingerprint"}
        or type(marker["version"]) is not int
        or marker["version"] != 1
        or not isinstance(marker["fingerprint"], str)
        or FINGERPRINT_RE.fullmatch(marker["fingerprint"]) is None
    ):
        return None
    return marker["fingerprint"], number, state


RequestJson = Callable[[str, str, object | None], object]


def _https_json_request(
    token: str,
    method: str,
    path: str,
    payload: object | None,
) -> object:
    """Transport fijo: GET en repos canónicos; mutaciones solo en Factory."""
    if method == "GET":
        if not any(path.startswith(prefix) for prefix in READ_REPOSITORY_API_PREFIXES):
            raise RuntimeValidationError("github_path_outside_repository")
    elif not path.startswith(REPOSITORY_API_PREFIX):
        raise RuntimeValidationError("github_path_outside_repository")
    body = None if payload is None else json.dumps(payload, separators=(",", ":"))
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Factory-Unattended-Watchdog/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPSConnection(API_HOST, timeout=15)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeValidationError("github_response_too_large")
        if response.status < 200 or response.status >= 300:
            raise RuntimeValidationError("github_request_failed")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeValidationError("github_response_invalid_json") from exc
    except RuntimeValidationError:
        raise
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise RuntimeValidationError("github_request_failed") from exc
    finally:
        connection.close()


class GitHubIssueClient:
    """Cliente mínimo; solo lista Issues y muta alertas con marker propio."""

    def __init__(
        self,
        token: str,
        repository: str,
        request_json: RequestJson | None = None,
    ):
        if not isinstance(token, str) or not token:
            raise RuntimeValidationError("missing_github_token")
        if repository != CANONICAL_REPOSITORY:
            raise RuntimeValidationError("invalid_repository")
        self.token = token
        self.repository = CANONICAL_REPOSITORY
        self._transport = request_json

    def _request(self, method: str, path: str, payload: object | None = None) -> object:
        if method == "GET":
            if not any(path.startswith(prefix) for prefix in READ_REPOSITORY_API_PREFIXES):
                raise RuntimeValidationError("github_path_outside_repository")
        elif not path.startswith(REPOSITORY_API_PREFIX):
            raise RuntimeValidationError("github_path_outside_repository")
        if self._transport is not None:
            return self._transport(method, path, payload)
        return _https_json_request(self.token, method, path, payload)

    @staticmethod
    def _repository_prefix(repository: str) -> str:
        if repository not in CANONICAL_REPOSITORIES:
            raise RuntimeValidationError("github_repository_outside_canonical_set")
        return f"/repos/{repository}/"

    def repository_activity(self, repository: str, now: str) -> dict[str, object]:
        """Resume inventario read-only de un repo canónico para el proof global."""
        prefix = self._repository_prefix(repository)
        ready = False
        reserved = False
        reviewing = False
        ambiguous = False
        for page in range(1, MAX_PAGES + 1):
            query = urlencode(
                {"state": "open", "per_page": COLLECTION_PAGE_SIZE, "page": page}
            )
            payload = self._request("GET", f"{prefix}issues?{query}")
            if not isinstance(payload, list):
                raise RuntimeValidationError("github_issues_invalid")
            for issue in payload:
                if not isinstance(issue, dict):
                    raise RuntimeValidationError("github_issue_invalid")
                if "pull_request" in issue:
                    continue
                labels = issue.get("labels")
                if not isinstance(labels, list):
                    raise RuntimeValidationError("github_issue_labels_invalid")
                names: set[str] = set()
                for label in labels:
                    if not isinstance(label, dict) or not isinstance(label.get("name"), str):
                        raise RuntimeValidationError("github_issue_label_invalid")
                    names.add(label["name"])
                active = names & ACTIVE_WORK_LABELS
                ready = ready or bool(active & READY_WORK_LABELS)
                reserved = reserved or bool(active & RESERVED_WORK_LABELS)
                reviewing = reviewing or bool(active & REVIEW_WORK_LABELS)
                ambiguous = ambiguous or len(active) > 1
            if len(payload) < COLLECTION_PAGE_SIZE:
                return {
                    "repository": repository,
                    "freshness": "fresh",
                    "ready": ready,
                    "reserved": reserved,
                    "reviewing": reviewing,
                    "ambiguous": ambiguous,
                    "source_ref": f"github:{repository}#issues:{now}",
                }
        raise RuntimeValidationError("github_issue_listing_truncated")

    def global_idle_proof(self, now: str) -> dict[str, object]:
        snapshot = {
            "version": 1,
            "repositories": [
                self.repository_activity(repository, now)
                for repository in CANONICAL_REPOSITORIES
            ],
        }
        return evaluate_global_idle_snapshot(snapshot)

    def get_issue(self, issue_number: int) -> dict[str, object]:
        if isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number <= 0:
            raise RuntimeValidationError("invalid_issue_number")
        payload = self._request("GET", f"{REPOSITORY_API_PREFIX}issues/{issue_number}")
        if not isinstance(payload, dict):
            raise RuntimeValidationError("github_issue_invalid")
        return payload

    def list_open_work_items(self) -> list[dict[str, object]]:
        """Lista Issues abiertos que representan frentes activos observables."""
        result: list[dict[str, object]] = []
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"state": "open", "per_page": COLLECTION_PAGE_SIZE, "page": page})
            payload = self._request(
                "GET", f"{REPOSITORY_API_PREFIX}issues?{query}"
            )
            if not isinstance(payload, list):
                raise RuntimeValidationError("github_issues_invalid")
            for issue in payload:
                if not isinstance(issue, dict) or "pull_request" in issue:
                    continue
                if str(issue.get("title", "")).startswith(ALERT_TITLE):
                    continue
                labels = issue.get("labels")
                if not isinstance(labels, list):
                    continue
                names = {
                    label.get("name")
                    for label in labels
                    if isinstance(label, dict) and isinstance(label.get("name"), str)
                }
                if names & ACTIVE_WORK_LABELS:
                    result.append(issue)
            if len(payload) < COLLECTION_PAGE_SIZE:
                return result
        raise RuntimeValidationError("github_issue_listing_truncated")

    def list_issue_comments(self, issue_number: int) -> list[dict[str, object]]:
        """Lee comentarios del Issue activo; nunca escribe."""
        if isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number <= 0:
            raise RuntimeValidationError("invalid_issue_number")
        result: list[dict[str, object]] = []
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"per_page": COLLECTION_PAGE_SIZE, "page": page})
            payload = self._request(
                "GET", f"{REPOSITORY_API_PREFIX}issues/{issue_number}/comments?{query}"
            )
            if not isinstance(payload, list):
                raise RuntimeValidationError("github_comments_invalid")
            result.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < COLLECTION_PAGE_SIZE:
                return result
        raise RuntimeValidationError("github_comment_listing_truncated")

    def get_branch_head(self, issue_number: int) -> str:
        """Resuelve exclusivamente trabajo/issue-N para un Issue validado."""
        if isinstance(issue_number, bool) or not isinstance(issue_number, int) or issue_number <= 0:
            raise RuntimeValidationError("invalid_issue_number")
        branch = f"trabajo/issue-{issue_number}"
        payload = self._request(
            "GET", f"{REPOSITORY_API_PREFIX}git/ref/heads/{branch}"
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("object"), dict):
            raise RuntimeValidationError("github_branch_invalid")
        sha = payload["object"].get("sha")
        if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise RuntimeValidationError("github_branch_sha_invalid")
        return sha

    def list_owned_alerts(self) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for page in range(1, MAX_PAGES + 1):
            query = urlencode(
                {
                    "state": "all",
                    "creator": OWNED_ALERT_CREATOR,
                    "per_page": COLLECTION_PAGE_SIZE,
                    "page": page,
                }
            )
            payload = self._request(
                "GET", f"{REPOSITORY_API_PREFIX}issues?{query}"
            )
            if not isinstance(payload, list):
                raise RuntimeValidationError("github_issues_invalid")
            for issue in payload:
                owned = parse_owned_alert(issue)
                if owned is None:
                    continue
                fingerprint, number, state = owned
                if fingerprint in result and result[fingerprint]["number"] != number:
                    raise RuntimeValidationError("duplicate_owned_alert_fingerprint")
                result[fingerprint] = {"number": number, "state": state}
            if len(payload) < COLLECTION_PAGE_SIZE:
                return result
        raise RuntimeValidationError("github_issue_listing_truncated")

    @staticmethod
    def _labels(spec: AlertSpec) -> list[str]:
        if spec.severity in {"S1", "S2"}:
            return ["tipo: incidente", "prioridad: crítica", "estado: disponible", "rol: sre"]
        return ["tipo: calidad", "prioridad: alta", "estado: bloqueado", "rol: sre"]

    def create_alert(self, spec: AlertSpec) -> None:
        self._request(
            "POST",
            f"{REPOSITORY_API_PREFIX}issues",
            {
                "title": f"{ALERT_TITLE} {spec.severity} {spec.fingerprint[:12]}",
                "body": alert_body(spec),
                "labels": self._labels(spec),
            },
        )

    def reopen_alert(self, issue_number: int, spec: AlertSpec) -> None:
        self._request(
            "PATCH",
            f"{REPOSITORY_API_PREFIX}issues/{issue_number}",
            {
                "state": "open",
                "title": f"{ALERT_TITLE} {spec.severity} {spec.fingerprint[:12]}",
                "body": alert_body(spec),
                "labels": self._labels(spec),
            },
        )

    def close_alert(self, issue_number: int) -> None:
        self._request(
            "PATCH",
            f"{REPOSITORY_API_PREFIX}issues/{issue_number}",
            {"state": "closed", "state_reason": "completed"},
        )


def apply_plan(client: GitHubIssueClient, plan: AlertPlan) -> None:
    for spec in plan.create:
        client.create_alert(spec)
    for issue_number, spec in plan.reopen:
        client.reopen_alert(issue_number, spec)
    for issue_number in plan.close:
        client.close_alert(issue_number)


def _canonical_blocked_guard() -> GuardDecision:
    """Obtiene BLOCKED desde el core 4B; no fabrica una decisión permissiva."""
    return evaluate_unattended_guards(None, {}, {}, {})


def _guard_payload(decision: GuardDecision) -> dict[str, object]:
    return {
        "action": decision.action,
        "authority": decision.authority,
        "pause_allowed": decision.pause_allowed,
        "reasons": list(decision.reasons),
        "evidence_fingerprint": decision.evidence_fingerprint,
    }


def _idle_github_evidence(now: str) -> dict[str, object]:
    """Representa inventario Factory vacío sin inventar sesión, heartbeat o capacidad."""
    return {
        "now": now,
        "presence": {
            "version": 1,
            "source": "factory-github-inventory",
            "observed_at": now,
            "sessions": [],
            "capacity": {
                "known_slots": 0,
                "eligible_free_slots": 0,
                "degraded_slots": 0,
                "freshness": "unknown",
            },
        },
        "work_ready": False,
        "ready_since": None,
        "next_dispatch_planned": False,
        "reservation": None,
        "state": {
            "work_identity": "pl0n3r/Factory#idle",
            "repository": CANONICAL_REPOSITORY,
            "branch": None,
            "head_sha": None,
            "reservation_id": None,
            "risk": "low",
            "severity": "S3",
            "evidence": ["github_inventory:no_active_work_items"],
            "last_state": "idle",
            "next_action": "re-run dispatcher when canonical work appears",
            "blockers": [],
            "updated_at": now,
        },
        "incidents": [],
        "already_alerted_fingerprints": [],
        "active_fronts": [],
        "human_gates": [],
        "integrated": [],
        "reverted": [],
        "next_actions": ["re-run dispatcher when canonical work appears"],
    }


def collect_github_input(
    client: GitHubIssueClient,
    config_payload: object,
    now: str,
) -> dict[str, object]:
    """Lee GitHub y proyecta STATE/Presence solo mediante la fuente canónica #775."""
    guard_payload = _guard_payload(_canonical_blocked_guard())
    try:
        cfg = normalize_config(config_payload)
        candidates: list[object] = []
        active_fronts: list[str] = []
        ready_observed = False
        active_work_observed = False
        for issue in client.list_open_work_items():
            number = issue.get("number")
            if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                raise RuntimeValidationError("github_issue_invalid")
            labels = issue.get("labels")
            names = {
                label.get("name")
                for label in labels
                if isinstance(labels, list)
                and isinstance(label, dict)
                and isinstance(label.get("name"), str)
            }
            if "estado: disponible" in names:
                ready_observed = True
                continue
            active_work_observed = True
            comments = client.list_issue_comments(number)
            projection = project_state_presence(
                repository=client.repository,
                issue_number=number,
                comments=comments,
                now=now,
                state_stale_minutes=cfg["state_stale_minutes"],
                reservation_stale_minutes=cfg["reservation_stale_minutes"],
            )
            if projection.state is not None:
                projection = project_state_presence(
                    repository=client.repository,
                    issue_number=number,
                    comments=comments,
                    now=now,
                    state_stale_minutes=cfg["state_stale_minutes"],
                    reservation_stale_minutes=cfg["reservation_stale_minutes"],
                    branch_head_sha=client.get_branch_head(number),
                )
            if projection.state is not None:
                active_fronts.append(str(projection.state["work_identity"]))
            if projection.status == "READY" and projection.state is not None:
                candidates.append(projection)

        if ready_observed:
            return {"guard": guard_payload, "evidence": None}
        if not candidates:
            if active_work_observed:
                return {"guard": guard_payload, "evidence": None}
            evidence = _idle_github_evidence(now)
            proof = client.global_idle_proof(now)
            if proof["idle_global"] is True:
                evidence["global_idle"] = proof
                guard_payload = _guard_payload(evaluate_global_idle_guard(proof))
            return {"guard": guard_payload, "evidence": evidence}
        if len(candidates) != 1:
            return {"guard": guard_payload, "evidence": None}

        projection = candidates[0]
        state = projection.state
        assert isinstance(state, dict)
        return {
            "guard": guard_payload,
            "evidence": {
                "now": now,
                "presence": projection.presence,
                "work_ready": False,
                "ready_since": None,
                "next_dispatch_planned": False,
                "reservation": None,
                "state": state,
                "incidents": [],
                "already_alerted_fingerprints": [],
                "active_fronts": sorted(set(active_fronts)),
                "human_gates": [],
                "integrated": [],
                "reverted": [],
                "next_actions": [str(state["next_action"])],
            },
        }
    except (RuntimeValidationError, TypeError, ValueError, KeyError):
        return {"guard": guard_payload, "evidence": None}


def load_config() -> object:
    """Carga únicamente la configuración versionada en la ruta fija de Factory."""
    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
        return json.loads(raw, object_pairs_hook=_unique_json_object)
    except (OSError, json.JSONDecodeError, RuntimeValidationError):
        return None


def read_stdin_json(stream=None) -> object:
    """Lee una entrada offline acotada desde stdin, nunca desde una ruta controlable."""
    source = sys.stdin if stream is None else stream
    try:
        raw = source.read(MAX_STDIN_BYTES + 1)
    except (OSError, AttributeError):
        return None
    if not isinstance(raw, str) or len(raw) > MAX_STDIN_BYTES:
        return None
    try:
        return json.loads(raw, object_pairs_hook=_unique_json_object)
    except (json.JSONDecodeError, RuntimeValidationError):
        return None


def _plan_json(decision: WatchdogDecision, plan: AlertPlan) -> dict[str, object]:
    return {
        "action": plan.action,
        "authority": plan.authority,
        "create": [asdict(item) for item in plan.create],
        "reopen": [number for number, _ in plan.reopen],
        "close": list(plan.close),
        "interrupt_owner": decision.interrupt_owner,
        "evidence_fingerprint": plan.evidence_fingerprint,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-stdin", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config_payload = load_config()
    runtime_input = read_stdin_json() if args.input_stdin else None

    token = os.environ.get("GH_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    try:
        client = GitHubIssueClient(token, repository)
        open_alerts = client.list_owned_alerts()
        if not args.input_stdin:
            now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            runtime_input = collect_github_input(client, config_payload, now)
        if not isinstance(runtime_input, dict):
            runtime_input = {}
        decision, plan = evaluate_runtime(
            config_payload,
            runtime_input.get("guard"),
            runtime_input.get("evidence"),
            open_alerts,
        )
        if not args.dry_run:
            switch = evaluate_unattended_kill_switch(client.get_issue(767))
            if switch.global_pause:
                print(json.dumps({
                    "action": "BLOCKED",
                    "authority": "unchanged",
                    "reason": f"kill_switch:{switch.reason}",
                    "create": [],
                    "reopen": [],
                    "close": [],
                }, sort_keys=True))
                return 1
            apply_plan(client, plan)
        print(json.dumps(_plan_json(decision, plan), sort_keys=True))
        return 0
    except RuntimeValidationError as exc:
        print(json.dumps({"action": "BLOCKED", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
