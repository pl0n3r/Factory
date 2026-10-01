#!/usr/bin/env python3
"""Materializa una decisión humana explícita sin ejecutar su efecto."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Any
from puertas_humanas import (
    MARKER_RE,
    classify_body,
    gate_authority_contract_from_body,
    gate_target_identity_from_body,
    validate_gate,
)

AUTHORIZED = {"OWNER"}
COMMAND_RE = re.compile(r"^/decidir ([A-D])$")
DECISION_LABEL = "decisión: dueño"
COMPLETED = "estado: completado"
STATUS_PREFIX = "estado: "
BOT = "github-actions[bot]"
EVIDENCE_RE = re.compile(
    r'^<!-- factory-human-decision (\{[^\n]*\}) -->'
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_EVENT_CHARS = 200_000


class DecisionError(ValueError):
    """Entrada o estado no confiable; no se debe mutar nada."""


def gh_api(method: str, path: str, payload: dict | None = None):
    command = ["gh", "api"]
    if method == "GET" and "per_page=" in path:
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
        return [item for page in value for item in page]
    return value


def _comment_command(event: dict[str, Any]) -> str | None:
    issue = event.get("issue")
    comment = event.get("comment")
    if not isinstance(issue, dict) or not isinstance(comment, dict):
        return None
    if "pull_request" in issue:
        return None
    association = comment.get("author_association")
    user = comment.get("user")
    if association not in AUTHORIZED:
        return None
    if not isinstance(user, dict) or user.get("type") == "Bot":
        return None
    body = comment.get("body")
    if not isinstance(body, str):
        return None
    match = COMMAND_RE.fullmatch(body)
    return match.group(1) if match else None


def _gate_snapshot(body: str) -> tuple[set[str], str]:
    classified = classify_body(body)
    if classified.get("status") != "gate":
        raise DecisionError("El Issue no contiene una puerta humana válida.")
    matches = MARKER_RE.findall(body)
    if len(matches) != 1:
        raise DecisionError("La puerta humana no es inequívoca.")
    try:
        raw = json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise DecisionError("El marker de puerta es inválido.") from exc
    gate = validate_gate(raw)
    canonical = json.dumps(
        gate,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    gate_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {item["id"] for item in gate["options"]}, gate_sha256


def _labels(issue: dict[str, Any]) -> set[str]:
    result = set()
    for item in issue.get("labels", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            result.add(item["name"])
        elif isinstance(item, str):
            result.add(item)
    return result


def _evidence_body(option: str, gate_sha256: str) -> str:
    marker = json.dumps(
        {"gate_sha256": gate_sha256, "option": option, "version": 2},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        f"<!-- factory-human-decision {marker} -->\n"
        f"✅ Decisión humana registrada: opción **{option}**. "
        "Este journal permite completar/reintentar la materialización sin "
        "ejecutar el efecto de la opción ni ampliar autoridad."
    )


def _existing_evidence(api, base: str) -> tuple[str, str] | None:
    found: set[tuple[str, str]] = set()
    for comment in api("GET", f"{base}/comments?per_page=100"):
        if comment.get("user", {}).get("login") != BOT:
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        match = EVIDENCE_RE.match(body)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise DecisionError("Existe evidencia de decisión inválida.") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"gate_sha256", "option", "version"}
            or payload.get("version") != 2
            or payload.get("option") not in {"A", "B", "C", "D"}
            or not isinstance(payload.get("gate_sha256"), str)
            or not SHA256_RE.fullmatch(payload["gate_sha256"])
        ):
            raise DecisionError("Existe evidencia de decisión incompatible o inválida.")
        found.add((payload["option"], payload["gate_sha256"]))
    if len(found) > 1:
        raise DecisionError("Existen decisiones humanas contradictorias.")
    return next(iter(found), None)


def _open_target_gate_numbers(
    api,
    repository: str,
    issue_number: int,
    target_identity: str,
    authority_contract: str,
) -> list[int] | None:
    result: list[int] = []
    for candidate in api(
        "GET", f"repos/{repository}/issues?state=all&per_page=100"
    ):
        if not isinstance(candidate, dict) or "pull_request" in candidate:
            continue
        number = candidate.get("number")
        body = candidate.get("body")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or not isinstance(body, str)
        ):
            continue
        try:
            candidate_target = gate_target_identity_from_body(body)
        except ValueError:
            continue
        if candidate_target != target_identity:
            continue
        try:
            candidate_contract = gate_authority_contract_from_body(body)
        except ValueError:
            return None
        if candidate_contract != authority_contract:
            return None

        if number != issue_number:
            candidate_base = f"repos/{repository}/issues/{number}"
            try:
                evidence = _existing_evidence(api, candidate_base)
            except DecisionError:
                return None
            if evidence is not None:
                return None

        if candidate.get("state") == "open":
            result.append(number)
    return sorted(set(result))


def _gate_is_unambiguous(
    api,
    repository: str,
    issue_number: int,
    target_identity: str,
    authority_contract: str,
) -> bool:
    numbers = _open_target_gate_numbers(
        api,
        repository,
        issue_number,
        target_identity,
        authority_contract,
    )
    return numbers == [issue_number]


def materialize_decision(
    event: dict[str, Any],
    api,
    repository: str,
) -> bool:
    """Aplica únicamente la materialización de la decisión; nunca su efecto."""
    option = _comment_command(event)
    if option is None:
        return False

    event_repo = event.get("repository")
    if (
        isinstance(event_repo, dict)
        and isinstance(event_repo.get("full_name"), str)
        and event_repo["full_name"] != repository
    ):
        return False

    event_issue = event.get("issue")
    number = event_issue.get("number") if isinstance(event_issue, dict) else None
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        return False
    event_body = event_issue.get("body")
    if not isinstance(event_body, str):
        return False
    try:
        event_options, event_gate_sha256 = _gate_snapshot(event_body)
        event_target = gate_target_identity_from_body(event_body)
        event_contract = gate_authority_contract_from_body(event_body)
    except (DecisionError, ValueError):
        return False
    if option not in event_options:
        return False

    base = f"repos/{repository}/issues/{number}"
    issue = api("GET", base)
    if not isinstance(issue, dict) or issue.get("state") != "open":
        return False
    if "pull_request" in issue:
        return False

    labels = _labels(issue)
    body = issue.get("body")
    if not isinstance(body, str):
        return False
    try:
        options, gate_sha256 = _gate_snapshot(body)
        live_target = gate_target_identity_from_body(body)
        live_contract = gate_authority_contract_from_body(body)
    except (DecisionError, ValueError):
        return False
    if (
        option not in options
        or gate_sha256 != event_gate_sha256
        or live_target != event_target
        or live_contract != event_contract
        or not _gate_is_unambiguous(
            api, repository, number, event_target, event_contract
        )
    ):
        return False

    existing = _existing_evidence(api, base)
    expected_evidence = (option, event_gate_sha256)
    if existing is not None and existing != expected_evidence:
        return False

    # Inicio normal: la cola canónica debe seguir presente. Recovery solo
    # puede reanudar un journal v2 ligado a ESTA MISMA puerta y opción.
    if DECISION_LABEL not in labels and existing != expected_evidence:
        return False

    if existing is None:
        issue = api("GET", base)
        if not isinstance(issue, dict) or issue.get("state") != "open":
            return False
        labels = _labels(issue)
        if DECISION_LABEL not in labels:
            return False
        live_body = issue.get("body")
        if not isinstance(live_body, str):
            return False
        try:
            live_options, live_gate_sha256 = _gate_snapshot(live_body)
            live_target = gate_target_identity_from_body(live_body)
            live_contract = gate_authority_contract_from_body(live_body)
        except (DecisionError, ValueError):
            return False
        if (
            option not in live_options
            or live_gate_sha256 != event_gate_sha256
            or live_target != event_target
            or live_contract != event_contract
            or not _gate_is_unambiguous(
                api, repository, number, event_target, event_contract
            )
        ):
            return False
        api(
            "POST",
            f"{base}/comments",
            {"body": _evidence_body(option, event_gate_sha256)},
        )
        existing = expected_evidence

    # Revalidar la identidad completa del gate antes de la transición final.
    issue = api("GET", base)
    if not isinstance(issue, dict) or issue.get("state") != "open":
        return False
    live_body = issue.get("body")
    if not isinstance(live_body, str):
        return False
    try:
        live_options, live_gate_sha256 = _gate_snapshot(live_body)
    except (DecisionError, ValueError):
        return False
    if (
        option not in live_options
        or live_gate_sha256 != event_gate_sha256
        or existing != expected_evidence
    ):
        return False

    labels = _labels(issue)
    if DECISION_LABEL not in labels and existing != expected_evidence:
        return False

    # Última fotografía inmediatamente antes del único write final.
    issue = api("GET", base)
    if not isinstance(issue, dict) or issue.get("state") != "open":
        return False
    final_body = issue.get("body")
    if not isinstance(final_body, str):
        return False
    try:
        final_options, final_gate_sha256 = _gate_snapshot(final_body)
        final_target = gate_target_identity_from_body(final_body)
        final_contract = gate_authority_contract_from_body(final_body)
    except (DecisionError, ValueError):
        return False
    if (
        option not in final_options
        or final_gate_sha256 != event_gate_sha256
        or final_target != event_target
        or final_contract != event_contract
        or existing != expected_evidence
        or not _gate_is_unambiguous(
            api, repository, number, event_target, event_contract
        )
    ):
        return False

    labels = _labels(issue)
    if DECISION_LABEL not in labels and existing != expected_evidence:
        return False

    final_labels = sorted(
        label
        for label in labels
        if label != DECISION_LABEL and not label.startswith(STATUS_PREFIX)
    )
    final_labels.append(COMPLETED)

    api(
        "PATCH",
        base,
        {
            "state": "closed",
            "state_reason": "completed",
            "labels": final_labels,
        },
    )
    return True


def main() -> int:
    payload = sys.stdin.read(MAX_EVENT_CHARS + 1)
    if len(payload) > MAX_EVENT_CHARS:
        return 0
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return 0
    if not isinstance(event, dict):
        return 0
    repository = os.environ.get("REPOSITORIO", "")
    if not repository:
        print("REPOSITORIO requerido.", file=sys.stderr)
        return 2
    try:
        changed = materialize_decision(event, gh_api, repository)
    except (DecisionError, subprocess.CalledProcessError) as exc:
        print(f"Decisión no materializada: {exc}", file=sys.stderr)
        return 1
    print("decision_materialized=true" if changed else "decision_materialized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
