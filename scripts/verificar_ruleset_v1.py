#!/usr/bin/env python3
"""Valida que el canal mayor v1 siga protegido por un ruleset activo."""
from __future__ import annotations

import json
import sys
from typing import Any


MAX_INPUT = 1_000_000
MAX_RULESETS = 500
V1_REF = "refs/tags/v1"
REQUIRED_RULES = frozenset({"creation", "update", "deletion"})


class RulesetValidationError(ValueError):
    """El estado de rulesets no demuestra protección suficiente para v1."""


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 500:
        raise RulesetValidationError(f"{field} debe ser una lista acotada.")
    if any(not isinstance(item, str) for item in value):
        raise RulesetValidationError(f"{field} contiene valores inválidos.")
    return value


def _rule_types(value: Any) -> set[str]:
    if not isinstance(value, list) or len(value) > 100:
        raise RulesetValidationError("rules debe ser una lista acotada.")
    result: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise RulesetValidationError("rules contiene una entrada inválida.")
        rule_type = item.get("type")
        if not isinstance(rule_type, str) or not rule_type:
            raise RulesetValidationError("rules contiene un tipo inválido.")
        result.add(rule_type)
    return result


def _protects_v1(ruleset: dict[str, Any]) -> bool:
    if ruleset.get("target") != "tag" or ruleset.get("enforcement") != "active":
        return False

    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        raise RulesetValidationError("conditions inválido.")
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        raise RulesetValidationError("conditions.ref_name inválido.")

    includes = _string_list(ref_name.get("include"), "conditions.ref_name.include")
    excludes = _string_list(ref_name.get("exclude"), "conditions.ref_name.exclude")
    if V1_REF not in includes or V1_REF in excludes:
        return False

    return REQUIRED_RULES.issubset(_rule_types(ruleset.get("rules")))


def validate_rulesets(payload: Any) -> dict[str, int | str]:
    """Devuelve evidencia mínima si algún ruleset protege v1; si no, falla cerrado."""
    if not isinstance(payload, list) or len(payload) > MAX_RULESETS:
        raise RulesetValidationError("El payload de rulesets debe ser una lista acotada.")

    valid_ids: list[int] = []
    for ruleset in payload:
        if not isinstance(ruleset, dict):
            raise RulesetValidationError("Ruleset inválido.")
        identifier = ruleset.get("id")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 1:
            raise RulesetValidationError("Ruleset sin id válido.")
        if _protects_v1(ruleset):
            valid_ids.append(identifier)

    if not valid_ids:
        raise RulesetValidationError(
            "No existe un ruleset activo de tags que proteja refs/tags/v1 "
            "contra creación, actualización y borrado."
        )

    return {"status": "protected", "ruleset_id": min(valid_ids)}


def main() -> int:
    raw = sys.stdin.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        print("ERROR: payload de rulesets demasiado grande.", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
        result = validate_rulesets(payload)
    except (json.JSONDecodeError, RulesetValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
