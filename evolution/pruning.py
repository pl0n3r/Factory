"""Pruning engine: evidence-based retirement candidates with lineage."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from evolution.growth import MAX_EVIDENCE, canonical_capability


PRUNING_VERSION = 1
MIN_AGE_DAYS = 90
MAX_USAGE_COUNT = 1
MAX_VALUE_SCORE = 0.25
PROTECTED_CAPABILITIES = frozenset(
    set(PROTECTED_INVARIANTS)
    | {
        "constitution",
        "human-gates",
        "rollback",
        "audit-trail",
    }
)


class PruningError(ValueError):
    """Invalid pruning evidence or protected capability request."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _evidence(value: Any) -> list[str]:
    if (
        not isinstance(value, (list, tuple))
        or not 1 <= len(value) <= MAX_EVIDENCE
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise PruningError("evidence debe contener 1..32 referencias no vacías")
    return sorted(set(item.strip() for item in value))


def _metric_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise PruningError(f"{field} debe ser entero >= 0")
    return value


def _value_score(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PruningError("value_score debe ser número 0..1")
    if isinstance(value, float) and not math.isfinite(value):
        raise PruningError("value_score debe ser número finito 0..1")
    if value < 0 or value > 1:
        raise PruningError("value_score debe ser número 0..1")
    return value


def evaluate_pruning(
    *,
    capability: Any,
    usage_count: Any,
    age_days: Any,
    value_score: Any,
    evidence: Any,
    protected: bool = False,
    parent_fingerprint: Any = None,
) -> dict[str, Any]:
    """Evaluate whether entropy is sufficient for a reversible prune candidate."""
    canonical = canonical_capability(capability)
    if protected is not True and protected is not False:
        raise PruningError("protected debe ser boolean")
    if protected or canonical in PROTECTED_CAPABILITIES:
        raise PruningError("capability protegida no puede podarse")

    usage = _metric_int(usage_count, "usage_count")
    age = _metric_int(age_days, "age_days")
    score = _value_score(value_score)
    sources = _evidence(evidence)

    if parent_fingerprint is not None and (
        not isinstance(parent_fingerprint, str)
        or len(parent_fingerprint) != 64
        or any(char not in "0123456789abcdef" for char in parent_fingerprint)
    ):
        raise PruningError("parent_fingerprint inválido")

    criteria = {
        "usage_low": usage <= MAX_USAGE_COUNT,
        "old_enough": age >= MIN_AGE_DAYS,
        "value_low": score <= MAX_VALUE_SCORE,
    }
    eligible = all(criteria.values()) and len(sources) >= 2

    result = {
        "version": PRUNING_VERSION,
        "capability": canonical,
        "eligible": eligible,
        "criteria": criteria,
        "metrics": {
            "usage_count": usage,
            "age_days": age,
            "value_score": score,
        },
        "evidence": sources,
        "lineage": {
            "parent_fingerprint": parent_fingerprint,
            "history_preserved": True,
        },
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def compile_pruning_candidate(evaluation: Any) -> dict[str, Any] | None:
    """Compile a retirement candidate without deleting history or protected state."""
    if not isinstance(evaluation, dict) or set(evaluation) != {
        "version",
        "capability",
        "eligible",
        "criteria",
        "metrics",
        "evidence",
        "lineage",
        "fingerprint",
    }:
        raise PruningError("evaluation inválida")
    expected = dict(evaluation)
    fingerprint = expected.pop("fingerprint")
    if fingerprint != _stable_hash(expected):
        raise PruningError("evaluation fingerprint no coincide")
    if evaluation["capability"] in PROTECTED_CAPABILITIES:
        raise PruningError("capability protegida no puede podarse")
    if evaluation["eligible"] is not True:
        return None

    prune_id = f"prune_{hashlib.sha256(evaluation['capability'].encode()).hexdigest()[:16]}"
    value = {
        "version": PRUNING_VERSION,
        "capability": evaluation["capability"],
        "status": "prune-candidate",
        "criteria": evaluation["criteria"],
        "metrics": evaluation["metrics"],
        "lineage": {
            **evaluation["lineage"],
            "evaluation_fingerprint": fingerprint,
            "evidence": evaluation["evidence"],
        },
    }
    candidate = {
        "version": 1,
        "changes": [
            {
                "path": f"evolution_state.heuristics.{prune_id}",
                "operation": "add",
                "value": value,
            }
        ],
        "evidence": evaluation["evidence"],
        "rollback": {"reversible": True, "strategy": "restore_baseline"},
    }
    candidate_fingerprint = validate_candidate(candidate)
    return {
        "version": PRUNING_VERSION,
        "prune_id": prune_id,
        "capability": evaluation["capability"],
        "candidate": candidate,
        "candidate_fingerprint": candidate_fingerprint,
        "lineage": value["lineage"],
    }
