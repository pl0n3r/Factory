"""Pure fail-closed compatibility contract for GitHub Actions permission envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LEVEL_RANK = {"none": 0, "read": 1, "write": 2}
ALLOWED_SCOPES = frozenset(
    {
        "actions",
        "attestations",
        "checks",
        "contents",
        "deployments",
        "discussions",
        "id-token",
        "issues",
        "models",
        "packages",
        "pages",
        "pull-requests",
        "security-events",
        "statuses",
    }
)


def _normalize_envelope(kind: str, value: object) -> tuple[dict[str, str], list[str]]:
    if not isinstance(value, Mapping):
        return {}, [f"{kind}:envelope_not_mapping"]

    normalized: dict[str, str] = {}
    errors: list[str] = []
    for raw_scope, raw_level in value.items():
        if not isinstance(raw_scope, str) or raw_scope not in ALLOWED_SCOPES:
            errors.append(f"{kind}:unknown_scope:{raw_scope!s}")
            continue
        if not isinstance(raw_level, str) or raw_level not in LEVEL_RANK:
            errors.append(f"{kind}:invalid_level:{raw_scope}:{raw_level!s}")
            continue
        normalized[raw_scope] = raw_level
    return normalized, sorted(errors)


def compare_permissions(required: object, granted: object) -> dict[str, Any]:
    """Return a deterministic compatibility result; malformed inputs fail closed."""
    required_map, required_errors = _normalize_envelope("reusable", required)
    granted_map, granted_errors = _normalize_envelope("caller", granted)
    errors = sorted(required_errors + granted_errors)
    if errors:
        return {
            "compatible": False,
            "reason": "invalid_contract",
            "missing": [],
            "errors": errors,
        }

    missing = []
    for scope in sorted(required_map):
        required_level = required_map[scope]
        granted_level = granted_map.get(scope, "none")
        if LEVEL_RANK[granted_level] < LEVEL_RANK[required_level]:
            missing.append(
                {
                    "scope": scope,
                    "required": required_level,
                    "granted": granted_level,
                }
            )

    return {
        "compatible": not missing,
        "reason": "compatible" if not missing else "insufficient_permissions",
        "missing": missing,
        "errors": [],
    }


def compare_callers(required: object, callers: object) -> dict[str, Any]:
    """Require every named caller to satisfy the same reusable envelope."""
    if not isinstance(callers, Mapping) or not callers:
        return {
            "compatible": False,
            "reason": "invalid_contract",
            "callers": [],
            "errors": ["callers:non_empty_mapping_required"],
        }

    entries = []
    errors = []
    for raw_name in sorted(callers, key=lambda item: str(item)):
        if not isinstance(raw_name, str) or not raw_name.strip():
            errors.append(f"callers:invalid_name:{raw_name!s}")
            continue
        result = compare_permissions(required, callers[raw_name])
        entries.append({"caller": raw_name, **result})

    if errors:
        return {
            "compatible": False,
            "reason": "invalid_contract",
            "callers": entries,
            "errors": sorted(errors),
        }

    compatible = all(entry["compatible"] for entry in entries)
    return {
        "compatible": compatible,
        "reason": "compatible" if compatible else "caller_incompatible",
        "callers": entries,
        "errors": [],
    }
