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
    "factory-release",
    "go-live",
}
REQUIRED = {"category", "context", "options", "recommendation", "safe_default"}
OPTIONAL_SIMPLE = {
    "title_simple",
    "summary_simple",
    "why_recommended",
    "blocks",
}
OPTIONAL_OPTION = {
    "effect",
    "pros",
    "cons",
    "risk",
    "cost",
    "reversible",
}
OPTION_ID_RE = re.compile(r"^[A-D]$")
RISK_VALUES = {"low", "medium", "high"}
MAX_EVENT_CHARS = 200_000
MAX_ISSUE_BODY_CHARS = 65_536
MAX_LIST_ITEMS = 5


class GateValidationError(ValueError):
    pass


def _result(
    status: str,
    category: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    result = {"status": status, "category": category}
    if reason is not None:
        result["reason"] = reason
    return result


def _line(value: Any, field: str, max_len: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise GateValidationError(f"{field} debe ser texto.")
    normalized = value.strip()
    if (
        (not normalized and not allow_empty)
        or len(normalized) > max_len
        or "\n" in value
        or "\r" in value
    ):
        suffix = "0" if allow_empty else "1"
        raise GateValidationError(
            f"{field} debe ser texto de una línea, {suffix}..{max_len} caracteres."
        )
    return normalized


def _short_text(value: Any, field: str, max_len: int, max_lines: int) -> str:
    if not isinstance(value, str):
        raise GateValidationError(f"{field} debe ser texto.")
    normalized = value.strip()
    if not normalized or len(normalized) > max_len or "\r" in value:
        raise GateValidationError(
            f"{field} debe contener 1..{max_len} caracteres."
        )
    if len(normalized.split("\n")) > max_lines:
        raise GateValidationError(
            f"{field} debe contener como máximo {max_lines} líneas."
        )
    return normalized


def _line_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_LIST_ITEMS:
        raise GateValidationError(
            f"{field} debe contener entre 1 y {MAX_LIST_ITEMS} elementos."
        )
    return [_line(item, field, 180) for item in value]


def _validate_simple_root(raw: dict[str, Any], normalized: dict[str, Any]) -> None:
    if "title_simple" in raw:
        normalized["title_simple"] = _line(
            raw["title_simple"], "title_simple", 180
        )
    if "summary_simple" in raw:
        normalized["summary_simple"] = _short_text(
            raw["summary_simple"], "summary_simple", 600, 3
        )
    if "why_recommended" in raw:
        normalized["why_recommended"] = _line(
            raw["why_recommended"], "why_recommended", 300
        )
    if "blocks" in raw:
        normalized["blocks"] = _line(raw["blocks"], "blocks", 300)


def _validate_option(item: Any, seen: set[str]) -> dict[str, Any]:
    allowed = {"id", "label"} | OPTIONAL_OPTION
    if not isinstance(item, dict) or not {"id", "label"}.issubset(item):
        raise GateValidationError(
            "Cada option debe contener al menos id y label."
        )
    if not set(item).issubset(allowed):
        raise GateValidationError(
            "Cada option contiene campos no permitidos."
        )

    option_id = _line(item["id"], "option.id", 1)
    label = _line(item["label"], "option.label", 240)
    if not OPTION_ID_RE.fullmatch(option_id) or option_id in seen:
        raise GateValidationError("option.id debe ser único y usar A..D.")
    seen.add(option_id)

    normalized: dict[str, Any] = {"id": option_id, "label": label}
    if "effect" in item:
        normalized["effect"] = _line(item["effect"], "option.effect", 300)
    if "pros" in item:
        normalized["pros"] = _line_list(item["pros"], "option.pros")
    if "cons" in item:
        normalized["cons"] = _line_list(item["cons"], "option.cons")
    if "risk" in item:
        risk = _line(item["risk"], "option.risk", 16)
        if risk not in RISK_VALUES:
            raise GateValidationError(
                "option.risk debe ser low, medium o high."
            )
        normalized["risk"] = risk
    if "cost" in item:
        normalized["cost"] = _line(
            item["cost"], "option.cost", 120, allow_empty=True
        )
    if "reversible" in item:
        if type(item["reversible"]) is not bool:
            raise GateValidationError("option.reversible debe ser booleano.")
        normalized["reversible"] = item["reversible"]
    return normalized


def validate_gate(raw: Any) -> dict[str, Any]:
    allowed = REQUIRED | OPTIONAL_SIMPLE
    if (
        not isinstance(raw, dict)
        or not REQUIRED.issubset(raw)
        or not set(raw).issubset(allowed)
    ):
        raise GateValidationError(
            "La puerta requiere category, context, options, recommendation y "
            "safe_default; solo admite además los campos simples documentados."
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

    normalized_options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in options:
        normalized_options.append(_validate_option(item, seen))

    recommendation = _line(raw["recommendation"], "recommendation", 1)
    safe_default = _line(raw["safe_default"], "safe_default", 1)
    if recommendation not in seen or safe_default not in seen:
        raise GateValidationError(
            "recommendation y safe_default deben referir una option existente."
        )

    normalized: dict[str, Any] = {
        "category": category,
        "context": context,
        "options": normalized_options,
        "recommendation": recommendation,
        "safe_default": safe_default,
    }
    _validate_simple_root(raw, normalized)
    return normalized


def classify_body(body: str, *, include_reason: bool = False) -> dict[str, Any]:
    if not isinstance(body, str):
        raise GateValidationError("El cuerpo del Issue debe ser texto.")

    def invalid(reason: str) -> dict[str, Any]:
        # Los motivos se construyen exclusivamente desde errores de esquema,
        # nunca desde campos ni valores proporcionados en el marker.
        return _result(
            "invalid-gate",
            reason=reason if include_reason else None,
        )

    marker_intent = MARKER_NAME in body
    if len(body) > MAX_ISSUE_BODY_CHARS:
        return invalid("El cuerpo supera el límite permitido.") if marker_intent else _result("no-gate")

    matches = MARKER_RE.findall(body)
    if not matches:
        return invalid("Marker de puerta incompleto o malformado.") if marker_intent else _result("no-gate")
    if len(matches) != 1:
        return invalid("Debe existir exactamente un marker de puerta.")

    try:
        raw = json.loads(matches[0])
    except json.JSONDecodeError:
        return invalid("El JSON del marker es inválido.")
    try:
        gate = validate_gate(raw)
    except GateValidationError as exc:
        return invalid(str(exc))

    return _result("gate", gate["category"])


def classify_event_text(
    payload: str, *, include_reason: bool = False
) -> dict[str, Any]:
    if not isinstance(payload, str) or len(payload) > MAX_EVENT_CHARS:
        return _result(
            "invalid-gate",
            reason="Evento de GitHub fuera de límites." if include_reason else None,
        )

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
    return classify_body(
        body if isinstance(body, str) else "",
        include_reason=include_reason,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "github"), default="json")
    args = parser.parse_args()

    payload = sys.stdin.read(MAX_EVENT_CHARS + 1)
    try:
        result = classify_event_text(payload, include_reason=args.format == "github")
    except GateValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.format == "github":
        print(f"status={result['status']}")
        print(f"category={result['category'] or ''}")
        print(f"reason={result.get('reason', '')}")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
