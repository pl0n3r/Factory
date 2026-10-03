#!/usr/bin/env python3
"""Fail-closed preflight for Factory v1.x publications."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timedelta
from typing import Any

from seguridad.puertas_humanas import (
    GateValidationError,
    MARKER_RE,
    classify_body,
    validate_gate,
)

REPOSITORY = "pl0n3r/factory"
REQUIRED_ISSUES = tuple(str(n) for n in range(1, 15)) + ("54", "83")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
APPROVAL_NAME = "factory-release-approval"
APPROVAL_RE = re.compile(r"<!--\s*factory-release-approval\s+(\{.*?\})\s*-->", re.DOTALL)
DECISION_BOT = "github-actions[bot]"
DECISION_COMMAND_RE = re.compile(r"^/decidir ([A-D])$")
DECISION_INTENT_RE = re.compile(r"<!--\s*factory-human-decision\b")
DECISION_EVIDENCE_RE = re.compile(
    r'^<!--\s*factory-human-decision\s+(\{[^\n]*\})\s*-->'
)
MAIN_TARGET_RE = re.compile(r"\bmain@([0-9a-f]{40})\b")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
RELEASE_GATE_CATEGORIES = {"release-1.0.0", "factory-release"}
REARM_RE = re.compile(
    r"<!--\s*factory-release-rearm\s+(\{[^\n]*\})\s*-->"
)
REARM_INTENT_RE = re.compile(r"<!--\s*factory-release-rearm\b")
RELEASE_WINDOW_RE = re.compile(
    r"<!--\s*factory-release-window\s+(\{[^\n]*\})\s*-->"
)
RELEASE_WINDOW_INTENT_RE = re.compile(r"<!--\s*factory-release-window\b")
MAX_REARM_DEPTH = 8
MAX_RELEASE_WINDOW_MINUTES = 120
MAX_INPUT = 1_000_000
MAX_COMMENT_BODY = 20_000
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
EXPECTED_MODES = {"exact", "latest"}
REQUIRED_EXACT_MAIN_CHECKS = ("ci", "sonar", "codeql", "watchdog")
RELEASE_MACHINERY_EXACT_PATHS = frozenset(
    {
        "scripts/release_bootstrap.py",
        "scripts/reusable_release_preflight.py",
        "scripts/reusable_permission_compat.py",
        "scripts/verificar_ruleset_v1.py",
        "template/.github/workflows/release.yml",
    }
)


class ReleaseBootstrapError(ValueError):
    pass


def _string(value: Any, field: str, limit: int = 500) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ReleaseBootstrapError(f"{field} inválido.")
    return value


def _sha(value: Any, field: str) -> str:
    text = _string(value, field, 40).lower()
    if SHA_RE.fullmatch(text) is None:
        raise ReleaseBootstrapError(f"{field} debe ser SHA-1 de 40 hex.")
    return text


def _canonical_time(value: Any, field: str) -> datetime:
    text = _string(value, field, 40)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseBootstrapError(f"{field} inválido.") from exc
    if parsed.tzinfo is None:
        raise ReleaseBootstrapError(f"{field} requiere zona horaria.")
    return parsed


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseBootstrapError(f"Marker contiene clave duplicada: {key}.")
        result[key] = value
    return result


def _marker_payload(
    body: str,
    *,
    marker_re: re.Pattern[str],
    intent_re: re.Pattern[str],
    name: str,
) -> dict[str, Any] | None:
    matches = marker_re.findall(body)
    if not matches:
        if intent_re.search(body):
            raise ReleaseBootstrapError(f"Marker {name} incompleto.")
        return None
    if len(matches) != 1:
        raise ReleaseBootstrapError(f"Marker {name} ambiguo.")
    try:
        raw = json.loads(matches[0], object_pairs_hook=_unique_json_object)
    except json.JSONDecodeError as exc:
        raise ReleaseBootstrapError(f"Marker {name} inválido.") from exc
    if not isinstance(raw, dict):
        raise ReleaseBootstrapError(f"Marker {name} inválido.")
    return raw


def _latest_owner_approval(comments: Any, owner: str) -> str:
    if not isinstance(comments, list):
        raise ReleaseBootstrapError("Comentarios de aprobación inválidos.")
    approvals: list[str] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if login != owner or comment.get("author_association") != "OWNER":
            continue
        body = comment.get("body")
        if not isinstance(body, str) or len(body) > MAX_COMMENT_BODY:
            continue
        matches = APPROVAL_RE.findall(body)
        if APPROVAL_NAME in body and len(matches) != 1:
            raise ReleaseBootstrapError("Marker de aprobación del dueño inválido.")
        if not matches:
            continue
        try:
            raw = json.loads(matches[0])
        except json.JSONDecodeError as exc:
            raise ReleaseBootstrapError("Aprobación del dueño contiene JSON inválido.") from exc
        if not isinstance(raw, dict) or set(raw) != {"sha"}:
            raise ReleaseBootstrapError("Aprobación del dueño debe contener solo sha.")
        approvals.append(_sha(raw["sha"], "approval.sha"))
    if not approvals:
        raise ReleaseBootstrapError("Falta aprobación explícita del dueño.")
    return approvals[-1]


def _normalized_gate_snapshot(body: str) -> tuple[dict[str, Any], str]:
    matches = MARKER_RE.findall(body)
    if len(matches) != 1:
        raise ReleaseBootstrapError("Puerta humana ambigua o inválida.")
    try:
        raw = json.loads(matches[0])
        gate = validate_gate(raw)
    except (json.JSONDecodeError, GateValidationError) as exc:
        raise ReleaseBootstrapError("Puerta humana inválida.") from exc
    canonical = json.dumps(
        gate,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return gate, fingerprint


def _release_gate_target(body: str) -> str:
    gate, _ = _normalized_gate_snapshot(body)
    if gate.get("category") != "factory-release":
        raise ReleaseBootstrapError("Origen de rearmado no es factory-release.")
    targets = MAIN_TARGET_RE.findall(str(gate.get("context", "")))
    if len(targets) != 1:
        raise ReleaseBootstrapError("Origen de rearmado sin main@SHA único.")
    return _sha(targets[0], "gate.target_sha")


def _release_gate_version(body: str) -> str:
    gate, _ = _normalized_gate_snapshot(body)
    if gate.get("category") != "factory-release":
        raise ReleaseBootstrapError("Puerta por versión requiere factory-release.")
    option_a = next(
        (item for item in gate.get("options", []) if item.get("id") == "A"),
        None,
    )
    label = str(option_a.get("label", "")).strip() if isinstance(option_a, dict) else ""
    match = re.fullmatch(r"Publicar Factory v?([0-9]+\.[0-9]+\.[0-9]+)", label)
    if match is None:
        raise ReleaseBootstrapError(
            "Puerta por versión requiere opción A 'Publicar Factory X.Y.Z'."
        )
    return match.group(1)


def _is_release_machinery_path(path: str) -> bool:
    if path in RELEASE_MACHINERY_EXACT_PATHS:
        return True
    if path.startswith(".github/workflows/"):
        filename = path.rsplit("/", 1)[-1].casefold()
        return "release" in filename and filename.endswith((".yml", ".yaml"))
    return False


def _validate_latest_release_context(
    *,
    body: str,
    expected: str,
    current_version: Any,
    changed_files: Any,
    exact_main_checks: Any,
) -> None:
    version = _string(current_version, "current_version", 64)
    if VERSION_RE.fullmatch(version) is None:
        raise ReleaseBootstrapError("current_version inválida.")
    if _release_gate_version(body) != version:
        raise ReleaseBootstrapError(
            "La versión aprobada por la puerta no coincide con config/version.json."
        )

    gate_sha = _release_gate_target(body)
    if not isinstance(changed_files, list):
        raise ReleaseBootstrapError("changed_files_since_gate inválido.")
    normalized_files = [
        _string(path, "changed_files_since_gate[]", 500)
        for path in changed_files
    ]
    if gate_sha != expected:
        protected = sorted(
            path for path in normalized_files if _is_release_machinery_path(path)
        )
        if protected:
            raise ReleaseBootstrapError(
                "La maquinaria de release cambió desde la puerta; requiere una puerta nueva: "
                + ", ".join(protected)
            )

    if (
        not isinstance(exact_main_checks, dict)
        or set(exact_main_checks) != set(REQUIRED_EXACT_MAIN_CHECKS)
    ):
        raise ReleaseBootstrapError("Evidencia exact-main incompleta.")
    red = [
        name
        for name in REQUIRED_EXACT_MAIN_CHECKS
        if exact_main_checks.get(name) != "success"
    ]
    if red:
        raise ReleaseBootstrapError(
            "Checks exact-main no están todos en success: " + ", ".join(red)
        )


def _rearm_marker(body: str, target_sha: str) -> int:
    raw = _marker_payload(
        body,
        marker_re=REARM_RE,
        intent_re=REARM_INTENT_RE,
        name="factory-release-rearm",
    )
    if (
        not isinstance(raw, dict)
        or set(raw) != {"version", "source_issue", "sha"}
        or raw.get("version") != 1
        or type(raw.get("source_issue")) is not int
        or raw["source_issue"] < 1
        or _sha(raw.get("sha"), "rearm.sha") != target_sha
    ):
        raise ReleaseBootstrapError("Origen de rearmado inválido.")
    return raw["source_issue"]


def _release_window(
    body: str,
    target_sha: str,
    *,
    created_at: Any = None,
    current_at: Any = None,
) -> None:
    raw = _marker_payload(
        body,
        marker_re=RELEASE_WINDOW_RE,
        intent_re=RELEASE_WINDOW_INTENT_RE,
        name="factory-release-window",
    )
    if (
        not isinstance(raw, dict)
        or set(raw) != {"version", "sha", "opened_at", "expires_at"}
        or raw.get("version") != 1
        or _sha(raw.get("sha"), "window.sha") != target_sha
    ):
        raise ReleaseBootstrapError("Ventana de rearmado inválida.")
    opened = _canonical_time(raw["opened_at"], "window.opened_at")
    expires = _canonical_time(raw["expires_at"], "window.expires_at")
    if (
        expires <= opened
        or expires - opened > timedelta(minutes=MAX_RELEASE_WINDOW_MINUTES)
    ):
        raise ReleaseBootstrapError("Ventana de rearmado fuera de límites.")
    if created_at is not None:
        created = _canonical_time(created_at, "gate.created_at")
        if created < opened or created >= expires:
            raise ReleaseBootstrapError(
                "Puerta rearmada fue creada fuera de su ventana."
            )
    if current_at is not None:
        current = _canonical_time(current_at, "now")
        if current < opened or current >= expires:
            raise ReleaseBootstrapError(
                "Puerta rearmada fuera de su ventana vigente."
            )


def _validate_rearmed_bot_gate(
    *,
    gate: dict[str, Any],
    expected: str,
    owner: str,
    now: Any,
    sources: Any,
    allow_target_drift: bool = False,
    require_current_window: bool = True,
) -> None:
    user = gate.get("user")
    if not isinstance(user, dict) or user.get("login") != DECISION_BOT:
        raise ReleaseBootstrapError("Puerta creada por actor no confiable.")

    body = gate.get("body")
    if not isinstance(body, str):
        raise ReleaseBootstrapError("Puerta rearmada sin body válido.")
    target_sha = _release_gate_target(body)
    if target_sha != expected and not allow_target_drift:
        raise ReleaseBootstrapError(
            "Puerta rearmada corresponde a otro SHA."
        )
    next_issue = _rearm_marker(body, target_sha)
    _release_window(
        body,
        target_sha,
        created_at=gate.get("created_at"),
        current_at=now if require_current_window else None,
    )

    if not isinstance(sources, list) or not sources:
        raise ReleaseBootstrapError("Falta provenance de rearmado.")
    if len(sources) > MAX_REARM_DEPTH:
        raise ReleaseBootstrapError("Cadena de rearmado excede el límite.")

    seen: set[int] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ReleaseBootstrapError("Fuente de rearmado inválida.")
        number = source.get("number")
        if type(number) is not int or number < 1 or number != next_issue:
            raise ReleaseBootstrapError("Cadena de rearmado no coincide.")
        if number in seen:
            raise ReleaseBootstrapError("Cadena de rearmado cíclica.")
        seen.add(number)

        source_body = source.get("body")
        if not isinstance(source_body, str):
            raise ReleaseBootstrapError("Fuente de rearmado sin body válido.")
        source_target = _release_gate_target(source_body)
        source_user = source.get("user")
        source_login = (
            source_user.get("login") if isinstance(source_user, dict) else None
        )
        association = source.get("author_association")

        if source_login == owner and association == "OWNER":
            if index != len(sources) - 1:
                raise ReleaseBootstrapError(
                    "Cadena de rearmado contiene evidencia sobrante."
                )
            return

        if source_login != DECISION_BOT:
            raise ReleaseBootstrapError(
                "Cadena de rearmado no termina en una puerta del OWNER."
            )
        next_issue = _rearm_marker(source_body, source_target)
        _release_window(
            source_body,
            source_target,
            created_at=source.get("created_at"),
        )

    raise ReleaseBootstrapError(
        "Cadena de rearmado no termina en una puerta del OWNER."
    )


def _v2_release_intent(gate: dict[str, Any]) -> bool:
    if gate.get("closed_by") == DECISION_BOT:
        return True
    comments = gate.get("comments")
    if not isinstance(comments, list):
        return False
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        if DECISION_INTENT_RE.search(body) or DECISION_COMMAND_RE.fullmatch(body):
            return True
    return False


def _validate_v2_maintenance_decision(
    *,
    body: str,
    comments: Any,
    owner: str,
    expected: str,
    allow_target_drift: bool = False,
) -> None:
    gate, gate_sha256 = _normalized_gate_snapshot(body)
    if gate.get("category") != "factory-release":
        raise ReleaseBootstrapError("Decisión v2 solo válida para factory-release.")
    if gate.get("safe_default") != "B":
        raise ReleaseBootstrapError("Puerta v2 debe conservar safe_default B.")

    option_a = next(
        (item for item in gate.get("options", []) if item.get("id") == "A"),
        None,
    )
    option_a_label = (
        str(option_a.get("label", "")).strip().casefold()
        if isinstance(option_a, dict)
        else ""
    )
    if not (
        option_a_label == "publicar"
        or option_a_label.startswith("publicar ")
    ):
        raise ReleaseBootstrapError("Opción A debe identificar inequívocamente publicación.")

    targets = MAIN_TARGET_RE.findall(str(gate.get("context", "")))
    if len(targets) != 1 or (
        targets[0] != expected and not allow_target_drift
    ):
        raise ReleaseBootstrapError(
            "Puerta v2 debe ligar un único main@SHA compatible con el modo solicitado."
        )

    if not isinstance(comments, list):
        raise ReleaseBootstrapError("Comentarios de decisión inválidos.")

    commands: list[str] = []
    journals: list[tuple[str, str]] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        comment_body = comment.get("body")
        if not isinstance(comment_body, str):
            continue
        if len(comment_body) > MAX_COMMENT_BODY:
            if DECISION_INTENT_RE.search(comment_body):
                raise ReleaseBootstrapError("Journal v2 excede el límite permitido.")
            continue

        command = DECISION_COMMAND_RE.fullmatch(comment_body)
        if (
            login == owner
            and comment.get("author_association") == "OWNER"
            and command is not None
        ):
            commands.append(command.group(1))

        journal_intents = DECISION_INTENT_RE.findall(comment_body)
        if not journal_intents:
            continue
        if len(journal_intents) != 1:
            raise ReleaseBootstrapError("Journal v2 ambiguo.")
        if login != DECISION_BOT:
            raise ReleaseBootstrapError("Journal v2 no puede ser aportado por un actor humano.")
        evidence = DECISION_EVIDENCE_RE.match(comment_body)
        if evidence is None:
            raise ReleaseBootstrapError("Journal v2 malformado.")
        try:
            raw = json.loads(evidence.group(1))
        except json.JSONDecodeError as exc:
            raise ReleaseBootstrapError("Journal v2 contiene JSON inválido.") from exc
        if (
            not isinstance(raw, dict)
            or set(raw) != {"gate_sha256", "option", "version"}
            or raw.get("version") != 2
            or raw.get("option") != "A"
            or not isinstance(raw.get("gate_sha256"), str)
            or SHA256_RE.fullmatch(raw["gate_sha256"]) is None
        ):
            raise ReleaseBootstrapError("Journal v2 incompatible.")
        journals.append((raw["option"], raw["gate_sha256"]))

    if not commands or any(option != "A" for option in commands):
        raise ReleaseBootstrapError(
            "Decisión v2 requiere /decidir A explícito del OWNER sin opciones contradictorias."
        )
    if len(journals) != 1:
        raise ReleaseBootstrapError("Debe existir exactamente un journal v2 del bot.")
    if journals[0] != ("A", gate_sha256):
        raise ReleaseBootstrapError("Journal v2 no corresponde al gate vigente.")


def validate_payload(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ReleaseBootstrapError("Payload inválido.")
    repository = _string(payload.get("repository"), "repository")
    owner = _string(payload.get("repository_owner"), "repository_owner")
    actor = _string(payload.get("actor"), "actor")
    event_name = _string(payload.get("event_name"), "event_name")
    branch = _string(payload.get("default_branch"), "default_branch")
    ref = _string(payload.get("ref"), "ref")
    expected_mode = payload.get("expected_mode", "exact")
    if expected_mode not in EXPECTED_MODES:
        raise ReleaseBootstrapError("expected_mode inválido.")
    expected = _sha(payload.get("expected_sha"), "expected_sha")
    current = _sha(payload.get("current_sha"), "current_sha")
    branch_sha = _sha(payload.get("default_branch_sha"), "default_branch_sha")
    v1_sha = _sha(payload.get("v1_sha"), "v1_sha")
    v1_0_0_exists = payload.get("v1_0_0_exists")
    if not isinstance(v1_0_0_exists, bool):
        raise ReleaseBootstrapError("v1_0_0_exists debe ser booleano.")

    if repository.casefold() != REPOSITORY.casefold() or owner != REPOSITORY.split("/", 1)[0]:
        raise ReleaseBootstrapError("Bootstrap solo permitido en pl0n3r/factory.")
    if actor != owner:
        raise ReleaseBootstrapError("Bootstrap requiere al propietario del repositorio.")
    if event_name != "workflow_dispatch" or ref != f"refs/heads/{branch}":
        raise ReleaseBootstrapError("Bootstrap solo acepta workflow_dispatch en default branch.")
    if not (expected == current == branch_sha):
        raise ReleaseBootstrapError("expected_sha, github.sha y HEAD deben coincidir.")
    if not v1_0_0_exists and v1_sha != expected:
        raise ReleaseBootstrapError(
            "Primer bootstrap requiere v1 en el SHA exacto aprobado."
        )

    issues = payload.get("issues")
    if not isinstance(issues, dict):
        raise ReleaseBootstrapError("Estados de Issues inválidos.")
    for number in REQUIRED_ISSUES:
        issue = issues.get(number)
        if not isinstance(issue, dict) or issue.get("state") != "closed":
            raise ReleaseBootstrapError(f"Issue #{number} debe estar cerrado.")

    gate = payload.get("gate")
    if not isinstance(gate, dict) or gate.get("state") != "closed":
        raise ReleaseBootstrapError("Puerta de release debe estar cerrada.")
    if gate.get("author_association") not in TRUSTED_ASSOCIATIONS:
        _validate_rearmed_bot_gate(
            gate=gate,
            expected=expected,
            owner=owner,
            now=payload.get("now"),
            sources=payload.get("rearm_sources"),
            allow_target_drift=expected_mode == "latest",
            require_current_window=expected_mode != "latest",
        )
    body = gate.get("body")
    gate_result = classify_body(body if isinstance(body, str) else "")
    category = gate_result.get("category") if gate_result.get("status") == "gate" else None
    if category not in RELEASE_GATE_CATEGORIES:
        raise ReleaseBootstrapError("Issue indicado no es puerta de release válida.")

    closed_by = gate.get("closed_by")
    if v1_0_0_exists:
        if category != "factory-release":
            raise ReleaseBootstrapError("Mantenimiento v1.x requiere puerta factory-release.")
        if _v2_release_intent(gate):
            if closed_by != DECISION_BOT:
                raise ReleaseBootstrapError("Puerta v2 debe cerrar por el bot de decisión.")
            gate_body = body if isinstance(body, str) else ""
            _validate_v2_maintenance_decision(
                body=gate_body,
                comments=gate.get("comments"),
                owner=owner,
                expected=expected,
                allow_target_drift=expected_mode == "latest",
            )
            if expected_mode == "latest":
                _validate_latest_release_context(
                    body=gate_body,
                    expected=expected,
                    current_version=payload.get("current_version"),
                    changed_files=payload.get("changed_files_since_gate"),
                    exact_main_checks=payload.get("exact_main_checks"),
                )
        else:
            if expected_mode == "latest":
                raise ReleaseBootstrapError(
                    "expected_sha=latest requiere una puerta v2 por versión."
                )
            if closed_by != owner:
                raise ReleaseBootstrapError("Puerta legacy debe ser cerrada por el dueño.")
            if _latest_owner_approval(gate.get("comments"), owner) != expected:
                raise ReleaseBootstrapError(
                    "La aprobación legacy del dueño corresponde a otro SHA."
                )
    else:
        if expected_mode == "latest":
            raise ReleaseBootstrapError(
                "expected_sha=latest solo está permitido para mantenimiento v1.x."
            )
        if category != "release-1.0.0":
            raise ReleaseBootstrapError("Primer release requiere puerta release-1.0.0.")
        if closed_by != owner:
            raise ReleaseBootstrapError("Primer release debe ser cerrado por el dueño.")
        if _latest_owner_approval(gate.get("comments"), owner) != expected:
            raise ReleaseBootstrapError("La aprobación del dueño corresponde a otro SHA.")
    return {"status": "ready", "sha": expected}


def main() -> int:
    raw = sys.stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        print("ERROR: payload demasiado grande.", file=sys.stderr)
        return 2
    try:
        result = validate_payload(json.loads(raw))
    except (json.JSONDecodeError, ReleaseBootstrapError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
