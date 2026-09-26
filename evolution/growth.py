"""Growth engine: detect real capability gaps and propose validated candidates."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from evolution.constitution import validate_candidate


GROWTH_VERSION = 1
MAX_CAPABILITIES = 128
MAX_EVIDENCE = 32
_TOKEN = re.compile(r"[a-z0-9]+")


class GrowthError(ValueError):
    """Invalid capability inventory or gap request."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_capability(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GrowthError("capability debe ser texto no vacío")
    folded = unicodedata.normalize("NFKD", value.casefold().strip())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    tokens = _TOKEN.findall(ascii_text)
    if not tokens:
        raise GrowthError("capability no contiene identificador útil")
    return "-".join(tokens)


def _evidence(value: Any) -> list[str]:
    if (
        not isinstance(value, (list, tuple))
        or not 1 <= len(value) <= MAX_EVIDENCE
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise GrowthError("evidence debe contener 1..32 referencias no vacías")
    return sorted(set(item.strip() for item in value))


def _inventory(value: Any) -> dict[str, str]:
    if not isinstance(value, (list, tuple, set)) or len(value) > MAX_CAPABILITIES:
        raise GrowthError("available_capabilities inválido o excesivo")
    result: dict[str, str] = {}
    for item in value:
        canonical = canonical_capability(item)
        result.setdefault(canonical, item.strip())
    return dict(sorted(result.items()))


def detect_capability_gap(
    *,
    required_capability: Any,
    available_capabilities: Any,
) -> dict[str, Any]:
    """Return a deterministic gap record, reusing equivalent capabilities."""
    required = canonical_capability(required_capability)
    available = _inventory(available_capabilities)
    equivalent = available.get(required)
    result = {
        "version": GROWTH_VERSION,
        "required": required,
        "gap": equivalent is None,
        "reuse": equivalent,
        "available": sorted(available),
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def compile_growth_candidate(
    *,
    gap: Any,
    evidence: Any,
    expected_value: Any,
) -> dict[str, Any] | None:
    """Compile a Constitution-valid candidate only for a demonstrated gap."""
    if not isinstance(gap, dict) or set(gap) != {
        "version",
        "required",
        "gap",
        "reuse",
        "available",
        "fingerprint",
    }:
        raise GrowthError("gap inválido")
    expected_gap = dict(gap)
    fingerprint = expected_gap.pop("fingerprint")
    if fingerprint != _stable_hash(expected_gap):
        raise GrowthError("gap fingerprint no coincide")
    if gap["gap"] is not True:
        return None
    if not isinstance(expected_value, str) or not expected_value.strip():
        raise GrowthError("expected_value debe ser texto no vacío")

    sources = _evidence(evidence)
    required = gap["required"]
    capability_id = f"capability_{hashlib.sha256(required.encode()).hexdigest()[:16]}"
    value = {
        "version": GROWTH_VERSION,
        "capability": required,
        "status": "candidate",
        "expected_value": expected_value.strip(),
        "lineage": {
            "gap_fingerprint": fingerprint,
            "evidence": sources,
        },
    }
    candidate = {
        "version": 1,
        "changes": [
            {
                "path": f"evolution_state.heuristics.{capability_id}",
                "operation": "add",
                "value": value,
            }
        ],
        "evidence": sources,
        "rollback": {"reversible": True, "strategy": "revert"},
    }
    candidate_fingerprint = validate_candidate(candidate)
    return {
        "version": GROWTH_VERSION,
        "capability_id": capability_id,
        "capability": required,
        "expected_value": expected_value.strip(),
        "candidate": candidate,
        "candidate_fingerprint": candidate_fingerprint,
        "lineage": value["lineage"],
    }
