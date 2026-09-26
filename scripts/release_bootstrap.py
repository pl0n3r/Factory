#!/usr/bin/env python3
"""Fail-closed preflight for Factory v1.x publications."""
from __future__ import annotations

import json
import re
import sys
from typing import Any

from seguridad.puertas_humanas import classify_body

REPOSITORY = "pl0n3r/factory"
REQUIRED_ISSUES = tuple(str(n) for n in range(1, 15)) + ("54", "83")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
APPROVAL_NAME = "factory-release-approval"
APPROVAL_RE = re.compile(r"<!--\s*factory-release-approval\s+(\{.*?\})\s*-->", re.DOTALL)
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
    if gate.get("closed_by") != owner:
        raise ReleaseBootstrapError("Puerta debe ser cerrada por el dueño.")
    body = gate.get("body")
    gate_result = classify_body(body if isinstance(body, str) else "")
    category = gate_result.get("category") if gate_result.get("status") == "gate" else None
    if category not in RELEASE_GATE_CATEGORIES:
        raise ReleaseBootstrapError("Issue indicado no es puerta de release válida.")
    if v1_0_0_exists and category != "factory-release":
        raise ReleaseBootstrapError("Mantenimiento v1.x requiere puerta factory-release.")
    if not v1_0_0_exists and category != "release-1.0.0":
        raise ReleaseBootstrapError("Primer release requiere puerta release-1.0.0.")
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
