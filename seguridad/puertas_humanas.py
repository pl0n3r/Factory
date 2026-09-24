#!/usr/bin/env python3
"""Clasifica escalaciones que sí requieren decisión del dueño."""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

MARKER_NAME = "factory-human-gate"
MARKER_RE = re.compile(
    r"<!--\s*factory-human-gate\s+(\{.*?\})\s*-->",
    re.DOTALL,
)
CATEGORIES = {
    "product-direction",
    "brand",
    "money",
    "legal",
    "real-customer-data",
    "release-1.0.0",
    "go-live",
}
REQUIRED = {"category", "context", "options", "recommendation", "safe_default"}
OPTION_ID_RE = re.compile(r"^[A-D]$")
MAX_EVENT_CHARS = 200_000
MAX_ISSUE_BODY_CHARS = 65_536


class GateValidationError(ValueError):
    pass


def _result(status: str, category: str | None = None) -> dict[str, Any]:
    return {"status": status, "category": category}


def _line(value: Any, field: str, max_len: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_len
        or "\n" in value
        or "\r" in value
    ):
        raise GateValidationError(
            f"{field} debe ser texto de una línea, 1..{max_len} caracteres."
        )
    return value.strip()


def validate_gate(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != REQUIRED:
        raise GateValidationError(
            "La puerta debe contener exactamente category, context, options, "
            "recommendation y safe_default."
        )

    category = _line(raw["category"], "category", 80)
    if category not in CATEGORIES:
        raise GateValidationError(
            "category no pertenece a la lista cerrada de decisiones del dueño."
        )

    context = _line(raw["context"], "context", 500)
    options = raw["options"]
    if not isinstance(options, list) or not 2 <= len(options) <= 4:
        raise GateValidationError("options debe contener entre 2 y 4 opciones.")

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in options:
        if not isinstance(item, dict) or set(item) != {"id", "label"}:
            raise GateValidationError(
                "Cada option debe contener exactamente id y label."
            )
        option_id = _line(item["id"], "option.id", 1)
        label = _line(item["label"], "option.label", 240)
        if not OPTION_ID_RE.fullmatch(option_id) or option_id in seen:
            raise GateValidationError("option.id debe ser único y usar A..D.")
        seen.add(option_id)
        normalized.append({"id": option_id, "label": label})

    recommendation = _line(raw["recommendation"], "recommendation", 1)
    safe_default = _line(raw["safe_default"], "safe_default", 1)
    if recommendation not in seen or safe_default not in seen:
        raise GateValidationError(
            "recommendation y safe_default deben referir una option existente."
        )

    return {
        "category": category,
        "context": context,
        "options": normalized,
        "recommendation": recommendation,
        "safe_default": safe_default,
    }


def classify_body(body: str) -> dict[str, Any]:
    if not isinstance(body, str):
        raise GateValidationError("El cuerpo del Issue debe ser texto.")

    marker_intent = MARKER_NAME in body
    if len(body) > MAX_ISSUE_BODY_CHARS:
        return _result("invalid-gate") if marker_intent else _result("no-gate")

    matches = MARKER_RE.findall(body)
    if not matches:
        return _result("invalid-gate") if marker_intent else _result("no-gate")
    if len(matches) != 1:
        return _result("invalid-gate")

    try:
        raw = json.loads(matches[0])
        gate = validate_gate(raw)
    except (json.JSONDecodeError, GateValidationError):
        return _result("invalid-gate")

    return _result("gate", gate["category"])


def classify_event_text(payload: str) -> dict[str, Any]:
    if not isinstance(payload, str) or len(payload) > MAX_EVENT_CHARS:
        return _result("invalid-gate")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise GateValidationError(
            "Evento de GitHub contiene JSON inválido."
        ) from exc

    issue = event.get("issue") if isinstance(event, dict) else None
    if not isinstance(issue, dict):
        raise GateValidationError("El evento no contiene un Issue.")

    body = issue.get("body")
    return classify_body(body if isinstance(body, str) else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "github"), default="json")
    args = parser.parse_args()

    payload = sys.stdin.read(MAX_EVENT_CHARS + 1)
    try:
        result = classify_event_text(payload)
    except GateValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "github":
        print(f"status={result['status']}")
        print(f"category={result['category'] or ''}")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
