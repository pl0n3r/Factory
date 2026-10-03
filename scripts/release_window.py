#!/usr/bin/env python3
"""Ventana fail-closed para releases Factory exact-SHA.

Este módulo es puro: recibe snapshots GitHub ya recolectados por workflows y
devuelve decisiones estructuradas. No hace red ni muta GitHub por sí mismo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seguridad.puertas_humanas import GateValidationError, MARKER_RE, validate_gate

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
TARGET_RE = re.compile(
    r"\b(?:Factory\s+)?v?(\d+\.\d+\.\d+)\b.*?\bmain@([0-9a-f]{40})\b",
    re.IGNORECASE,
)
WINDOW_RE = re.compile(
    r"<!--\s*factory-release-window\s+(\{[^\n]*\})\s*-->"
)
WINDOW_INTENT_RE = re.compile(r"<!--\s*factory-release-window\b")
DECISION_RE = re.compile(
    r"<!--\s*factory-human-decision\s+(\{[^\n]*\})\s*-->"
)
EXECUTED_RE = re.compile(
    r"<!--\s*factory-release-executed\s+(\{[^\n]*\})\s*-->"
)
EXCEPTION_RE = re.compile(
    r"<!--\s*factory-release-freeze-exception\s+(\{[^\n]*\})\s*-->"
)
ACTIONS_BOT = "github-actions[bot]"
MAX_ROWS = 200
MAX_COMMENTS = 300
DEFAULT_TTL_MINUTES = 60


class ReleaseWindowError(ValueError):
    """Evidencia ambigua/inválida: no se debe ampliar autoridad."""


def _canonical_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ReleaseWindowError(f"{field} inválido.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseWindowError(f"{field} inválido.") from exc
    if parsed.tzinfo is None:
        raise ReleaseWindowError(f"{field} requiere timezone.")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ReleaseWindowError(f"{field} inválido.")
    normalized = value.lower()
    if SHA_RE.fullmatch(normalized) is None:
        raise ReleaseWindowError(f"{field} inválido.")
    return normalized


def _semver(value: Any) -> str:
    if not isinstance(value, str) or SEMVER_RE.fullmatch(value) is None:
        raise ReleaseWindowError("version inválida.")
    return value


def _gate_fingerprint(gate: dict[str, Any]) -> str:
    canonical = json.dumps(
        validate_gate(gate),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gate_from_body(body: Any) -> tuple[dict[str, Any], str, str] | None:
    if not isinstance(body, str):
        return None
    matches = MARKER_RE.findall(body)
    if not matches:
        return None
    if len(matches) != 1:
        raise ReleaseWindowError("Puerta humana ambigua.")
    try:
        raw = json.loads(matches[0])
        gate = validate_gate(raw)
    except (json.JSONDecodeError, GateValidationError) as exc:
        raise ReleaseWindowError("Puerta humana inválida.") from exc
    if gate["category"] != "factory-release":
        return None
    match = TARGET_RE.search(gate["context"])
    if match is None:
        raise ReleaseWindowError("factory-release sin target exacto.")
    return gate, _semver(match.group(1)), _sha(match.group(2), "gate.sha")


def _window_from_body(body: str, target_sha: str) -> dict[str, Any] | None:
    matches = WINDOW_RE.findall(body)
    intent = WINDOW_INTENT_RE.search(body) is not None
    if not matches:
        if intent:
            raise ReleaseWindowError("Marker release-window incompleto.")
        return None
    if len(matches) != 1:
        raise ReleaseWindowError("Marker release-window ambiguo.")
    try:
        raw = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise ReleaseWindowError("Marker release-window inválido.") from exc
    if not isinstance(raw, dict) or set(raw) != {
        "version", "sha", "opened_at", "expires_at"
    }:
        raise ReleaseWindowError("Schema release-window inválido.")
    if raw["version"] != 1 or _sha(raw["sha"], "window.sha") != target_sha:
        raise ReleaseWindowError("release-window no coincide con el target.")
    opened = _canonical_time(raw["opened_at"], "opened_at")
    expires = _canonical_time(raw["expires_at"], "expires_at")
    if expires <= opened or expires - opened > timedelta(minutes=120):
        raise ReleaseWindowError("Ventana release fuera de límites.")
    return {
        "opened_at": opened,
        "expires_at": expires,
        "sha": target_sha,
    }


def _comments(row: dict[str, Any]) -> list[dict[str, Any]]:
    comments = row.get("comments", [])
    if not isinstance(comments, list) or len(comments) > MAX_COMMENTS:
        raise ReleaseWindowError("Comentarios de gate inválidos.")
    return [item for item in comments if isinstance(item, dict)]


def _decision_a(
    comments: list[dict[str, Any]],
    gate_fingerprint: str,
) -> bool:
    journals: list[tuple[str, str]] = []
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != ACTIONS_BOT:
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        matches = DECISION_RE.findall(body)
        if not matches:
            continue
        if len(matches) != 1:
            raise ReleaseWindowError("Journal de decisión ambiguo.")
        try:
            raw = json.loads(matches[0])
        except json.JSONDecodeError as exc:
            raise ReleaseWindowError("Journal de decisión inválido.") from exc
        if not isinstance(raw, dict) or set(raw) != {
            "gate_sha256", "option", "version"
        }:
            raise ReleaseWindowError("Schema de decisión inválido.")
        if (
            raw["version"] != 2
            or raw["option"] not in {"A", "B"}
            or not isinstance(raw["gate_sha256"], str)
        ):
            raise ReleaseWindowError("Journal de decisión incompatible.")
        journals.append((raw["option"], raw["gate_sha256"]))
    if not journals:
        return False
    option, fingerprint = journals[-1]
    return option == "A" and fingerprint == gate_fingerprint


def _execution(
    comments: list[dict[str, Any]],
    target_sha: str,
) -> dict[str, Any] | None:
    found: list[dict[str, Any]] = []
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("login") != ACTIONS_BOT:
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        for match in EXECUTED_RE.findall(body):
            try:
                raw = json.loads(match)
            except json.JSONDecodeError as exc:
                raise ReleaseWindowError("Marker executed inválido.") from exc
            if not isinstance(raw, dict) or set(raw) != {
                "version", "sha", "run_id", "executed_at"
            }:
                raise ReleaseWindowError("Schema executed inválido.")
            if (
                raw["version"] != 1
                or _sha(raw["sha"], "executed.sha") != target_sha
                or type(raw["run_id"]) is not int
                or raw["run_id"] < 1
            ):
                raise ReleaseWindowError("Marker executed incompatible.")
            _canonical_time(raw["executed_at"], "executed_at")
            found.append(raw)
    if not found:
        return None
    unique = {(item["sha"], item["run_id"]) for item in found}
    if len(unique) != 1:
        raise ReleaseWindowError("Ejecución terminal ambigua.")
    return found[-1]


def gate_records(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ReleaseWindowError("Snapshot de Issues inválido.")
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        issue = row.get("issue")
        if not isinstance(issue, dict):
            continue
        body = issue.get("body")
        if not isinstance(body, str) or WINDOW_INTENT_RE.search(body) is None:
            continue
        gate_info = _gate_from_body(body)
        if gate_info is None:
            raise ReleaseWindowError("release-window sin puerta factory-release.")
        gate, version, target_sha = gate_info
        number = issue.get("number")
        state = issue.get("state")
        if type(number) is not int or number < 1 or state not in {"open", "closed"}:
            raise ReleaseWindowError("Issue de release inválido.")
        comments = _comments(row)
        fingerprint = _gate_fingerprint(gate)
        records.append({
            "number": number,
            "state": state,
            "title": str(issue.get("title") or ""),
            "updated_at": issue.get("updated_at"),
            "gate": gate,
            "fingerprint": fingerprint,
            "version": version,
            "sha": target_sha,
            "window": _window_from_body(body, target_sha),
            "approved_a": _decision_a(comments, fingerprint),
            "executed": _execution(comments, target_sha),
        })
    return sorted(records, key=lambda item: item["number"])


def _latest_by_version(records: list[dict[str, Any]], version: str) -> dict[str, Any] | None:
    matches = [item for item in records if item["version"] == version]
    return max(matches, key=lambda item: item["number"], default=None)


def freeze_gate(records: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    active: list[dict[str, Any]] = []
    for record in records:
        window = record["window"]
        if window is None or record["executed"] is not None:
            continue
        if now > window["expires_at"]:
            continue
        if record["state"] == "open" or record["approved_a"]:
            active.append(record)
    return max(active, key=lambda item: item["number"], default=None)


def _critical_exception(pr: Any, work_issue: Any) -> bool:
    if not isinstance(pr, dict) or not isinstance(work_issue, dict):
        return False
    body = pr.get("body")
    if not isinstance(body, str):
        return False
    matches = EXCEPTION_RE.findall(body)
    if len(matches) != 1:
        return False
    try:
        raw = json.loads(matches[0])
    except json.JSONDecodeError:
        return False
    if raw != {"version": 1, "reason": "critical-repair", "issue": work_issue.get("number")}:
        return False
    labels = work_issue.get("labels", [])
    names = {
        item.get("name")
        for item in labels
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    return (
        work_issue.get("state") == "open"
        and "prioridad: crítica" in names
    )


def check_pull_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReleaseWindowError("Payload PR inválido.")
    now = _canonical_time(payload.get("now"), "now")
    records = gate_records(payload.get("gates"))
    active = freeze_gate(records, now)
    if active is None:
        return {"allowed": True, "reason": "no_active_release_window"}
    if _critical_exception(payload.get("pr"), payload.get("work_issue")):
        return {
            "allowed": True,
            "reason": "critical_repair_exception",
            "gate_issue": active["number"],
            "sha": active["sha"],
        }
    return {
        "allowed": False,
        "reason": "factory_release_window_active",
        "gate_issue": active["number"],
        "sha": active["sha"],
        "expires_at": _iso(active["window"]["expires_at"]),
    }


def _render_gate(version: str, sha: str, now: datetime, *, source_issue: int) -> dict[str, Any]:
    expires = now + timedelta(minutes=DEFAULT_TTL_MINUTES)
    gate = {
        "category": "factory-release",
        "context": (
            f"Autorizar Factory v{version} exclusivamente para main@{sha}. "
            f"Puerta rearmada desde #{source_issue}; la decisión anterior no se hereda."
        ),
        "title_simple": f"Publicar Factory {version}",
        "summary_simple": (
            f"Factory {version} requiere una decisión nueva para el HEAD exacto {sha[:8]}."
        ),
        "why_recommended": (
            "El candidato debe revalidarse sobre el HEAD actual antes de cualquier publicación."
        ),
        "blocks": "Factory@v1 no cambia sin una decisión exact-SHA nueva.",
        "options": [
            {
                "id": "A",
                "label": f"Publicar Factory {version}",
                "effect": f"Autorizar exclusivamente main@{sha} mediante el bootstrap protegido.",
                "risk": "medium",
                "reversible": True,
            },
            {
                "id": "B",
                "label": "No publicar todavía",
                "effect": "Mantener Factory@v1 sin cambios.",
                "risk": "low",
                "reversible": True,
            },
        ],
        "recommendation": "A",
        "safe_default": "B",
    }
    normalized = validate_gate(gate)
    marker = json.dumps(
        normalized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    window = json.dumps(
        {
            "version": 1,
            "sha": sha,
            "opened_at": _iso(now),
            "expires_at": _iso(expires),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    rearm = json.dumps(
        {
            "version": 1,
            "source_issue": source_issue,
            "sha": sha,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    body = (
        f"Factory **{version}** requiere una decisión nueva para el HEAD exacto:\n\n"
        f"`{sha}`\n\n"
        "La autorización anterior quedó stale y **no** se transporta. "
        "Un mensaje genérico como `sigue` no autoriza publicar.\n\n"
        "Responde explícitamente `/decidir A` o `/decidir B`.\n\n"
        f"<!-- factory-human-gate {marker} -->\n"
        f"<!-- factory-release-window {window} -->\n"
        f"<!-- factory-release-rearm {rearm} -->"
    )
    return {
        "title": f"decisión en espera: Factory v{version} sobre HEAD exacto {sha[:8]}",
        "body": body,
        "labels": [
            "tipo: infraestructura",
            "decisión: dueño",
            "prioridad: crítica",
            "rol: infraestructura",
            "rol: sre",
            "rol: seguridad",
        ],
        "expires_at": _iso(expires),
    }


def plan_rearm(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReleaseWindowError("Payload push inválido.")
    now = _canonical_time(payload.get("now"), "now")
    main_sha = _sha(payload.get("main_sha"), "main_sha")
    version = _semver(payload.get("version"))
    records = gate_records(payload.get("gates"))
    latest = _latest_by_version(records, version)
    if latest is None:
        return {"action": "none", "reason": "no_prior_release_gate"}
    if latest["sha"] == main_sha:
        return {"action": "none", "reason": "current_head_already_has_gate"}
    if latest["executed"] is not None:
        return {"action": "none", "reason": "latest_release_executed"}
    if latest["state"] == "closed" and not latest["approved_a"]:
        return {"action": "none", "reason": "latest_gate_not_approved"}
    # Open stale gates and approved-A stale gates both need a fresh exact-SHA gate.
    gate = _render_gate(version, main_sha, now, source_issue=latest["number"])
    return {
        "action": "create_gate",
        "source_issue": latest["number"],
        "source_sha": latest["sha"],
        "sha": main_sha,
        "version": version,
        **gate,
    }


def plan_execution(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ReleaseWindowError("Payload workflow_run inválido.")
    if payload.get("conclusion") != "success":
        return {"action": "none", "reason": "release_run_not_successful"}
    now = _canonical_time(payload.get("now"), "now")
    head_sha = _sha(payload.get("head_sha"), "head_sha")
    run_id = payload.get("run_id")
    if type(run_id) is not int or run_id < 1:
        raise ReleaseWindowError("run_id inválido.")
    records = gate_records(payload.get("gates"))
    matches = [
        item for item in records
        if item["sha"] == head_sha and item["approved_a"]
    ]
    if not matches:
        return {"action": "none", "reason": "no_approved_gate_for_run_sha"}
    gate = max(matches, key=lambda item: item["number"])
    if gate["executed"] is not None:
        return {"action": "none", "reason": "execution_already_recorded"}
    marker = json.dumps(
        {
            "version": 1,
            "sha": head_sha,
            "run_id": run_id,
            "executed_at": _iso(now),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "action": "mark_executed",
        "issue": gate["number"],
        "sha": head_sha,
        "comment": (
            f"<!-- factory-release-executed {marker} -->\n"
            f"✅ Release Factory ejecutada y self-test publicado terminal-success "
            f"para `{head_sha}` (run `{run_id}`)."
        ),
    }


def approved_unexecuted(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        raise ReleaseWindowError("Payload summary inválido.")
    records = gate_records(payload.get("gates"))
    by_version: dict[str, dict[str, Any]] = {}
    for record in records:
        previous = by_version.get(record["version"])
        if previous is None or record["number"] > previous["number"]:
            by_version[record["version"]] = record
    pending = [
        item for item in by_version.values()
        if item["approved_a"] and item["executed"] is None
    ]
    if not pending:
        return None
    gate = max(pending, key=lambda item: item["number"])
    updated_at = gate.get("updated_at")
    return {
        "issue": gate["number"],
        "version": gate["version"],
        "sha": gate["sha"],
        "updated_at": updated_at,
    }


def _read_payload() -> Any:
    raw = sys.stdin.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ReleaseWindowError("Payload demasiado grande.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReleaseWindowError("JSON inválido.") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("pr-check", "push", "workflow-run", "summary"),
    )
    args = parser.parse_args()
    try:
        payload = _read_payload()
        if args.mode == "pr-check":
            result = check_pull_request(payload)
        elif args.mode == "push":
            result = plan_rearm(payload)
        elif args.mode == "workflow-run":
            result = plan_execution(payload)
        else:
            result = approved_unexecuted(payload)
    except ReleaseWindowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.mode == "pr-check" and not result.get("allowed", False):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
