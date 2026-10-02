#!/usr/bin/env python3
"""Runtime acotado del watchdog 4C: inputs canónicos + alertas GitHub propias."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.unattended_guards import GuardDecision
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
REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"
)
ALERT_MARKER_RE = re.compile(
    r"<!--\s*factory-unattended-watchdog-alert\s+(\{.*?\})\s*-->",
    re.DOTALL,
)
ALERT_TITLE = "[AUTO][WATCHDOG]"
API_ORIGIN = "https://api.github.com"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PAGES = 10


class RuntimeValidationError(ValueError):
    """Contrato runtime inválido o fuera del límite permitido."""


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


def _normalize_open_alerts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise RuntimeValidationError("invalid_open_alerts")
    result: dict[str, int] = {}
    for fingerprint, issue_number in value.items():
        if (
            not isinstance(fingerprint, str)
            or FINGERPRINT_RE.fullmatch(fingerprint) is None
            or isinstance(issue_number, bool)
            or not isinstance(issue_number, int)
            or issue_number <= 0
        ):
            raise RuntimeValidationError("invalid_open_alert")
        result[fingerprint] = issue_number
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

    close = (
        tuple(sorted(number for fp, number in current.items() if fp not in active))
        if decision.action == "ALLOW"
        else ()
    )
    return decision, AlertPlan(
        action=decision.action,
        authority=decision.authority,
        create=create,
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
    reasons = "\n".join(f"- \`{reason}\`" for reason in spec.reasons) or "- \`none\`"
    return (
        f"{_alert_marker(spec.fingerprint)}\n"
        "## Watchdog desatendido\n\n"
        f"Severidad: **{spec.severity}**\n\n"
        f"Código: \`{spec.code}\`\n\n"
        f"Fingerprint: \`{spec.fingerprint}\`\n\n"
        f"Evidencia 4C: \`{spec.evidence_fingerprint}\`\n\n"
        f"### Razones\n{reasons}\n\n"
        "Esta alerta pertenece exclusivamente al runtime unattended-watchdog. "
        "No concede autoridad nueva ni implica go-live, gasto o datos reales.\n"
    )


class GitHubIssueClient:
    """Cliente mínimo; solo lista Issues y muta alertas con marker propio."""

    def __init__(self, token: str, repository: str):
        if not isinstance(token, str) or not token:
            raise RuntimeValidationError("missing_github_token")
        if not isinstance(repository, str) or REPOSITORY_RE.fullmatch(repository) is None:
            raise RuntimeValidationError("invalid_repository")
        self.token = token
        self.repository = repository

    def _request(self, method: str, path: str, payload: object | None = None) -> object:
        if not path.startswith(f"/repos/{self.repository}/"):
            raise RuntimeValidationError("github_path_outside_repository")
        body = None
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Factory-Unattended-Watchdog/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(API_ORIGIN + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeValidationError("github_response_too_large")
                return json.loads(raw.decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeValidationError("github_request_failed") from exc

    def list_owned_alerts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for page in range(1, MAX_PAGES + 1):
            query = urlencode({"state": "open", "per_page": 100, "page": page})
            payload = self._request(
                "GET", f"/repos/{self.repository}/issues?{query}"
            )
            if not isinstance(payload, list):
                raise RuntimeValidationError("github_issues_invalid")
            for issue in payload:
                if not isinstance(issue, dict) or "pull_request" in issue:
                    continue
                body = issue.get("body")
                number = issue.get("number")
                if not isinstance(body, str) or not isinstance(number, int):
                    continue
                match = ALERT_MARKER_RE.search(body)
                if match is None:
                    continue
                try:
                    marker = json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
                if (
                    not isinstance(marker, dict)
                    or set(marker) != {"version", "fingerprint"}
                    or marker["version"] != 1
                    or not isinstance(marker["fingerprint"], str)
                    or FINGERPRINT_RE.fullmatch(marker["fingerprint"]) is None
                ):
                    continue
                fingerprint = marker["fingerprint"]
                if fingerprint in result and result[fingerprint] != number:
                    raise RuntimeValidationError("duplicate_owned_alert_fingerprint")
                result[fingerprint] = number
            if len(payload) < 100:
                return result
        raise RuntimeValidationError("github_issue_listing_truncated")

    def create_alert(self, spec: AlertSpec) -> None:
        self._request(
            "POST",
            f"/repos/{self.repository}/issues",
            {
                "title": f"{ALERT_TITLE} {spec.severity} {spec.fingerprint[:12]}",
                "body": alert_body(spec),
            },
        )

    def close_alert(self, issue_number: int) -> None:
        self._request(
            "PATCH",
            f"/repos/{self.repository}/issues/{issue_number}",
            {"state": "closed", "state_reason": "completed"},
        )


def apply_plan(client: GitHubIssueClient, plan: AlertPlan) -> None:
    for spec in plan.create:
        client.create_alert(spec)
    for issue_number in plan.close:
        client.close_alert(issue_number)


def read_json(path: str | None) -> object:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _plan_json(decision: WatchdogDecision, plan: AlertPlan) -> dict[str, object]:
    return {
        "action": plan.action,
        "authority": plan.authority,
        "create": [asdict(item) for item in plan.create],
        "close": list(plan.close),
        "interrupt_owner": decision.interrupt_owner,
        "evidence_fingerprint": plan.evidence_fingerprint,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/unattended-watchdog.json")
    parser.add_argument("--input")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config_payload = read_json(args.config)
    runtime_input = read_json(args.input)
    if not isinstance(runtime_input, dict):
        runtime_input = {}

    token = os.environ.get("GH_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    try:
        client = GitHubIssueClient(token, repository)
        open_alerts = client.list_owned_alerts()
        decision, plan = evaluate_runtime(
            config_payload,
            runtime_input.get("guard"),
            runtime_input.get("evidence"),
            open_alerts,
        )
        print(json.dumps(_plan_json(decision, plan), sort_keys=True))
        if not args.dry_run:
            apply_plan(client, plan)
        return 0
    except RuntimeValidationError as exc:
        print(json.dumps({"action": "BLOCKED", "reason": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
