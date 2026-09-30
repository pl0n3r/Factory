#!/usr/bin/env python3
"""Materializa una decisión humana explícita sin ejecutar su efecto."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any
from urllib.parse import quote

from puertas_humanas import (
    MARKER_RE,
    classify_body,
    validate_gate,
)

AUTHORIZED = {"OWNER", "MEMBER", "COLLABORATOR"}
COMMAND_RE = re.compile(r"^/decidir ([A-D])$")
DECISION_LABEL = "decisión: dueño"
COMPLETED = "estado: completado"
STATUS_PREFIX = "estado: "
BOT = "github-actions[bot]"
EVIDENCE_RE = re.compile(
    r'^<!-- factory-human-decision (\{[^\n]*\}) -->'
)
MAX_EVENT_CHARS = 200_000


class DecisionError(ValueError):
    """Entrada o estado no confiable; no se debe mutar nada."""


def gh_api(method: str, path: str, payload: dict | None = None):
    command = ["gh", "api"]
    if method == "GET" and "?per_page=" in path:
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
    if method == "GET" and "?per_page=" in path:
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


def _gate_options(body: str) -> set[str]:
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
    return {item["id"] for item in gate["options"]}


def _labels(issue: dict[str, Any]) -> set[str]:
    result = set()
    for item in issue.get("labels", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            result.add(item["name"])
        elif isinstance(item, str):
            result.add(item)
    return result


def _evidence_body(option: str) -> str:
    marker = json.dumps(
        {"option": option, "version": 1},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        f"<!-- factory-human-decision {marker} -->\n"
        f"✅ Decisión humana materializada: opción **{option}**. "
        "Este registro no ejecuta el efecto de la opción ni amplía autoridad."
    )


def _existing_evidence(api, base: str) -> str | None:
    found: set[str] = set()
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
            or set(payload) != {"option", "version"}
            or payload.get("version") != 1
            or payload.get("option") not in {"A", "B", "C", "D"}
        ):
            raise DecisionError("Existe evidencia de decisión inválida.")
        found.add(payload["option"])
    if len(found) > 1:
        raise DecisionError("Existen decisiones humanas contradictorias.")
    return next(iter(found), None)


def _remove_label(api, base: str, label: str) -> None:
    api("DELETE", f"{base}/labels/{quote(label, safe='')}")


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

    base = f"repos/{repository}/issues/{number}"
    issue = api("GET", base)
    if not isinstance(issue, dict) or issue.get("state") != "open":
        return False
    if "pull_request" in issue:
        return False

    labels = _labels(issue)
    if DECISION_LABEL not in labels:
        return False

    body = issue.get("body")
    if not isinstance(body, str):
        return False
    try:
        options = _gate_options(body)
    except (DecisionError, ValueError):
        return False
    if option not in options:
        return False

    existing = _existing_evidence(api, base)
    if existing is not None and existing != option:
        return False
    if existing is None:
        api("POST", f"{base}/comments", {"body": _evidence_body(option)})

    # Releer estado antes de mutar labels para fallar cerrado ante carreras.
    issue = api("GET", base)
    if not isinstance(issue, dict) or issue.get("state") != "open":
        return False
    labels = _labels(issue)
    if DECISION_LABEL not in labels:
        return False

    _remove_label(api, base, DECISION_LABEL)
    for label in sorted(labels):
        if label.startswith(STATUS_PREFIX) and label != COMPLETED:
            _remove_label(api, base, label)
    if COMPLETED not in labels:
        api("POST", f"{base}/labels", {"labels": [COMPLETED]})

    api(
        "PATCH",
        base,
        {"state": "closed", "state_reason": "completed"},
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
