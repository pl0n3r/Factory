#!/usr/bin/env python3
"""Sincroniza invalid-gate sin sobrescribir etiquetas de otros escritores."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from urllib.parse import quote

from puertas_humanas import (
    FACTORY_RELEASE_TARGET_RE,
    MARKER_RE,
    GateValidationError,
    gate_authority_contract_from_body,
    gate_target_identity_from_body,
    validate_gate,
)

MARKER = "<!-- factory-invalid-gate -->"
OWNED = "<!-- factory-invalid-gate-owner:bot -->"
BOT = "github-actions[bot]"
BLOCKED = "estado: bloqueado"
AVAILABLE = "estado: disponible"
COMPLETED = "estado: completado"
DECISION_LABEL = "decisión: dueño"
TRUSTED_ISSUE_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
DUPLICATE_MARKER = "<!-- factory-human-gate-duplicate"
DECISION_RE = re.compile(r'^<!-- factory-human-decision (\{[^\n]*\}) -->')
RELEASE_REARM_RE = re.compile(
    r"<!--\s*factory-release-rearm\s+(\{[^\n]*\})\s*-->"
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class GateConflictError(ValueError):
    """Estado ambiguo: la reconciliación no debe ejecutar mutaciones sensibles."""


def gh_api(method: str, path: str, payload: dict | None = None):
    command = ["gh", "api"]
    if method == "GET" and ("per_page=" in path):
        command += ["--paginate", "--slurp"]
    if method != "GET":
        command += ["--method", method]
    command.append(path)
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        capture_output=True,
        text=True,
        check=True,
    )
    value = json.loads(result.stdout) if result.stdout.strip() else None
    if method == "GET" and "per_page=" in path:
        # --slurp devuelve una lista de páginas (cada página es una lista).
        return [item for page in value for item in page]
    return value


def issue_labels(api, base: str) -> set[str]:
    return {label["name"] for label in api("GET", base)["labels"]}


def comments_for(api, base: str) -> list[dict]:
    return api("GET", f"{base}/comments?per_page=100")


def bot_comment(api, base: str) -> dict | None:
    return next(
        (
            comment for comment in comments_for(api, base)
            if comment.get("user", {}).get("login") == BOT
            and comment.get("body", "").startswith(MARKER)
        ),
        None,
    )


def last_block_actor(api, base: str) -> str | None:
    events = api("GET", f"{base}/events?per_page=100")
    relevant = (
        event for event in reversed(events)
        if event.get("label", {}).get("name") == BLOCKED
        and event.get("event") in ("labeled", "unlabeled")
    )
    last = next(relevant, None)
    if last is None or last["event"] != "labeled":
        return None
    return last.get("actor", {}).get("login")


def add_label(api, base: str, label: str) -> None:
    api("POST", f"{base}/labels", {"labels": [label]})


def remove_label(api, base: str, label: str) -> None:
    api("DELETE", f"{base}/labels/{quote(label, safe='')}")


def sync_invalid(api, repository: str, issue: int, reason: str) -> None:
    base = f"repos/{repository}/issues/{issue}"
    labels = issue_labels(api, base)
    existing = bot_comment(api, base)
    # Un bloqueo previo del dueño no se reclama como propio.
    if BLOCKED in labels:
        owned = bool(
            existing and OWNED in existing["body"]
            and last_block_actor(api, base) == BOT
        )
    else:
        # Solo se cambian las etiquetas de estado; no PATCH de toda la lista.
        for label in labels:
            if label.startswith("estado: "):
                remove_label(api, base, label)
        add_label(api, base, BLOCKED)
        owned = True

    message = (
        f"{MARKER}\n"
        + (f"{OWNED}\n" if owned else "")
        + f"⛔ Puerta humana inválida. Motivo de validación: {reason}"
    )
    if existing:
        if existing["body"] != message:
            api("PATCH", f"repos/{repository}/issues/comments/{existing['id']}", {"body": message})
    else:
        api("POST", f"{base}/comments", {"body": message})


def _restore_valid(api, repository: str, issue: int) -> None:
    base = f"repos/{repository}/issues/{issue}"
    comment = bot_comment(api, base)
    if not comment or OWNED not in comment["body"]:
        return
    if BLOCKED not in issue_labels(api, base):
        return
    # Además del marker, comprobar el último actor que aplicó el bloqueo actual.
    if last_block_actor(api, base) != BOT:
        return
    remove_label(api, base, BLOCKED)
    # Nunca reemplazar etiquetas ajenas, ni restaurar si otro agente puso estado.
    if not any(
        name.startswith("estado: ") for name in issue_labels(api, base)
    ):
        add_label(api, base, AVAILABLE)


def _decision_evidence(api, base: str) -> tuple[str, str] | None:
    found: set[tuple[str, str]] = set()
    for comment in comments_for(api, base):
        if comment.get("user", {}).get("login") != BOT:
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        match = DECISION_RE.match(body)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise GateConflictError(
                "Existe evidencia de decisión inválida en una puerta equivalente."
            ) from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"gate_sha256", "option", "version"}
            or payload.get("version") != 2
            or payload.get("option") not in {"A", "B", "C", "D"}
            or not isinstance(payload.get("gate_sha256"), str)
            or not SHA256_RE.fullmatch(payload["gate_sha256"])
        ):
            raise GateConflictError(
                "Existe evidencia de decisión incompatible en una puerta equivalente."
            )
        found.add((payload["option"], payload["gate_sha256"]))
    if len(found) > 1:
        raise GateConflictError(
            "Existen decisiones humanas contradictorias en una puerta equivalente."
        )
    return next(iter(found), None)


def _trusted_gate_candidate(candidate: dict) -> bool:
    """Acepta humanos confiables o el release-rearm exacto creado por Actions."""
    if candidate.get("author_association") in TRUSTED_ISSUE_ASSOCIATIONS:
        return True

    user = candidate.get("user")
    body = candidate.get("body")
    if (
        not isinstance(user, dict)
        or user.get("login") != BOT
        or user.get("type") != "Bot"
        or not isinstance(body, str)
    ):
        return False

    gate_markers = MARKER_RE.findall(body)
    rearm_markers = RELEASE_REARM_RE.findall(body)
    if len(gate_markers) != 1 or len(rearm_markers) != 1:
        return False

    try:
        gate = validate_gate(json.loads(gate_markers[0]))
        rearm = json.loads(rearm_markers[0])
    except (GateValidationError, json.JSONDecodeError, TypeError):
        return False

    if gate.get("category") != "factory-release":
        return False
    target = FACTORY_RELEASE_TARGET_RE.search(gate.get("context", ""))
    if target is None:
        return False

    if (
        not isinstance(rearm, dict)
        or set(rearm) != {"version", "source_issue", "sha"}
        or type(rearm.get("version")) is not int
        or rearm["version"] != 1
        or type(rearm.get("source_issue")) is not int
        or rearm["source_issue"] <= 0
        or not isinstance(rearm.get("sha"), str)
        or SHA_RE.fullmatch(rearm["sha"]) is None
        or rearm["sha"] != target.group(2).lower()
    ):
        return False

    return True


def _target_issues(api, repository: str, target_identity: str) -> list[dict]:
    candidates = api(
        "GET", f"repos/{repository}/issues?state=all&per_page=100"
    )
    equivalent: list[dict] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or "pull_request" in candidate:
            continue
        if not _trusted_gate_candidate(candidate):
            continue
        body = candidate.get("body")
        if not isinstance(body, str):
            continue
        try:
            candidate_identity = gate_target_identity_from_body(body)
        except (GateValidationError, ValueError):
            continue
        if candidate_identity == target_identity:
            equivalent.append(candidate)
    return sorted(equivalent, key=lambda item: item.get("number", 0))


def _mark_duplicate(api, repository: str, issue: dict, canonical: int) -> None:
    number = issue["number"]
    base = f"repos/{repository}/issues/{number}"
    labels = issue_labels(api, base)
    if DECISION_LABEL in labels:
        remove_label(api, base, DECISION_LABEL)
    for label in labels:
        if label.startswith("estado: "):
            remove_label(api, base, label)
    add_label(api, base, COMPLETED)

    marker = f"{DUPLICATE_MARKER} canonical={canonical} -->"
    if not any(
        comment.get("user", {}).get("login") == BOT
        and isinstance(comment.get("body"), str)
        and comment["body"].startswith(marker)
        for comment in comments_for(api, base)
    ):
        api(
            "POST",
            f"{base}/comments",
            {
                "body": (
                    f"{marker}\n"
                    f"♻️ Puerta equivalente reconciliada hacia #{canonical}; "
                    "no se materializó ninguna decisión."
                )
            },
        )
    api(
        "PATCH",
        base,
        {"state": "closed", "state_reason": "duplicate"},
    )


def reconcile_gate(api, repository: str, issue: int) -> bool:
    """Conserva una única puerta abierta por identidad y devuelve si es canónica."""
    base = f"repos/{repository}/issues/{issue}"
    current = api("GET", base)
    if (
        not isinstance(current, dict)
        or current.get("state") != "open"
        or "pull_request" in current
        or not isinstance(current.get("body"), str)
    ):
        return False

    try:
        target_identity = gate_target_identity_from_body(current["body"])
        authority_contract = gate_authority_contract_from_body(current["body"])
    except (GateValidationError, ValueError):
        return False

    equivalent = _target_issues(api, repository, target_identity)
    if issue not in {item.get("number") for item in equivalent}:
        # Si GitHub todavía no refleja el Issue en el listado, no enrutar.
        return False

    for candidate in equivalent:
        body = candidate.get("body")
        if not isinstance(body, str):
            raise GateConflictError(
                "Una puerta equivalente perdió su contrato de autoridad."
            )
        try:
            candidate_contract = gate_authority_contract_from_body(body)
        except (GateValidationError, ValueError) as exc:
            raise GateConflictError(
                "Una puerta equivalente tiene contrato inválido."
            ) from exc
        if candidate_contract != authority_contract:
            raise GateConflictError(
                "Puertas del mismo target contienen contratos de autoridad distintos."
            )

    open_equivalent = [
        item for item in equivalent if item.get("state") == "open"
    ]
    if not open_equivalent:
        return False
    canonical = min(item["number"] for item in open_equivalent)

    evidence: list[tuple[int, tuple[str, str]]] = []
    for candidate in equivalent:
        candidate_base = f"repos/{repository}/issues/{candidate['number']}"
        found = _decision_evidence(api, candidate_base)
        if found is not None:
            evidence.append((candidate["number"], found))

    if len({value for _, value in evidence}) > 1:
        raise GateConflictError(
            "Puertas equivalentes contienen decisiones incompatibles."
        )
    if any(number != canonical for number, _ in evidence):
        raise GateConflictError(
            "Una puerta duplicada ya contiene decisión; se requiere reconciliación manual."
        )

    for candidate in open_equivalent:
        if candidate["number"] != canonical:
            _mark_duplicate(api, repository, candidate, canonical)

    return issue == canonical


def sync_valid(api, repository: str, issue: int) -> bool:
    _restore_valid(api, repository, issue)
    return reconcile_gate(api, repository, issue)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("invalid", "valid"))
    args = parser.parse_args()
    repository = os.environ["REPOSITORIO"]
    issue = int(os.environ["ISSUE"])
    if args.action == "invalid":
        sync_invalid(gh_api, repository, issue, os.environ["REASON"])
    else:
        canonical = sync_valid(gh_api, repository, issue)
        print(f"canonical={str(canonical).lower()}")


if __name__ == "__main__":
    main()
