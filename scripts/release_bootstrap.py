#!/usr/bin/env python3
"""Fail-closed preflight for Factory v1.x publications."""
from __future__ import annotations

import hashlib
import json
import re
import sys
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
DECISION_EVIDENCE_RE = re.compile(
    r'^<!-- factory-human-decision (\{[^\n]*\}) -->'
)
DECISION_INTENT_RE = re.compile(r"<!--\s*factory-human-decision\b")
DECISION_COMMAND_RE = re.compile(r"^/decidir ([A-D])$")
MAIN_TARGET_RE = re.compile(r"\bmain@([0-9a-f]{40})\b")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DECISION_BOT = "github-actions[bot]"
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
RELEASE_GATE_CATEGORIES = {"release-1.0.0", "factory-release"}
MAX_INPUT = 1_000_000
MAX_COMMENT_BODY = 20_000


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


def _validate_v2_maintenance_decision(
    *,
    body: str,
    comments: Any,
    owner: str,
    expected: str,
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
    if (
        not isinstance(option_a, dict)
        or "publicar" not in str(option_a.get("label", "")).casefold()
    ):
        raise ReleaseBootstrapError("Opción A debe identificar inequívocamente publicación.")

    targets = MAIN_TARGET_RE.findall(str(gate.get("context", "")))
    if len(targets) != 1 or targets[0] != expected:
        raise ReleaseBootstrapError(
            "Puerta v2 debe ligar un único main@SHA al expected_sha."
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
        if not isinstance(comment_body, str) or len(comment_body) > MAX_COMMENT_BODY:
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

    if commands != ["A"]:
        raise ReleaseBootstrapError(
            "Decisión v2 requiere un único /decidir A explícito del OWNER."
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
    if not (expected == current == branch_sha == v1_sha):
        raise ReleaseBootstrapError("expected_sha, github.sha, HEAD y v1 deben coincidir.")

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
        raise ReleaseBootstrapError("Puerta creada por actor no confiable.")
    body = gate.get("body")
    gate_result = classify_body(body if isinstance(body, str) else "")
    category = gate_result.get("category") if gate_result.get("status") == "gate" else None
    if category not in RELEASE_GATE_CATEGORIES:
        raise ReleaseBootstrapError("Issue indicado no es puerta de release válida.")

    closed_by = gate.get("closed_by")
    if v1_0_0_exists:
        if category != "factory-release":
            raise ReleaseBootstrapError("Mantenimiento v1.x requiere puerta factory-release.")
        if closed_by == owner:
            if _latest_owner_approval(gate.get("comments"), owner) != expected:
                raise ReleaseBootstrapError(
                    "La aprobación legacy del dueño corresponde a otro SHA."
                )
        elif closed_by == DECISION_BOT:
            _validate_v2_maintenance_decision(
                body=body if isinstance(body, str) else "",
                comments=gate.get("comments"),
                owner=owner,
                expected=expected,
            )
        else:
            raise ReleaseBootstrapError(
                "Puerta de mantenimiento debe cerrar por OWNER legacy o bot v2."
            )
    else:
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
