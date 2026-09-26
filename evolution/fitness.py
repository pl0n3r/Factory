"""Fitness Engine: comparación multidimensional contra baseline sin score mágico."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from evolution.constitution import PROTECTED_INVARIANTS


FITNESS_VERSION = 1
DIRECTIONS = {"higher", "lower"}
MAX_DIMENSIONS = 64
_DIMENSION = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class FitnessError(ValueError):
    """Vector o comparación de fitness inválidos."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalize_value(value: Any, dimension: str) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FitnessError(f"{dimension}: value debe ser número finito o null")
    if isinstance(value, float) and not math.isfinite(value):
        raise FitnessError(f"{dimension}: value debe ser finito")
    return value


def _normalize_vector(value: Any, name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not value:
        raise FitnessError(f"{name}: vector vacío o inválido")
    if len(value) > MAX_DIMENSIONS:
        raise FitnessError(f"{name}: demasiadas dimensiones")

    normalized: dict[str, dict[str, Any]] = {}
    for raw_dimension, raw_metric in value.items():
        if (
            not isinstance(raw_dimension, str)
            or _DIMENSION.fullmatch(raw_dimension) is None
        ):
            raise FitnessError(f"{name}: dimensión inválida")
        if (
            not isinstance(raw_metric, dict)
            or set(raw_metric) != {"value", "direction"}
        ):
            raise FitnessError(f"{name}.{raw_dimension}: métrica inválida")
        direction = raw_metric["direction"]
        if direction not in DIRECTIONS:
            raise FitnessError(f"{name}.{raw_dimension}: direction inválida")
        normalized[raw_dimension] = {
            "value": _normalize_value(raw_metric["value"], raw_dimension),
            "direction": direction,
        }
    return dict(sorted(normalized.items()))


def _normalize_protected(value: Any) -> tuple[str, ...]:
    constitutional = set(PROTECTED_INVARIANTS)
    if value is None:
        return tuple(sorted(constitutional))
    if (
        not isinstance(value, (list, tuple, set))
        or not value
        or not all(
            isinstance(item, str) and _DIMENSION.fullmatch(item) is not None
            for item in value
        )
    ):
        raise FitnessError("protected_dimensions inválidas")
    requested = set(value)
    if not constitutional.issubset(requested):
        raise FitnessError(
            "protected_dimensions no puede debilitar invariantes constitucionales"
        )
    return tuple(sorted(requested))


def _dimension_status(
    baseline: float | int | None,
    candidate: float | int | None,
    direction: str,
) -> tuple[str, float | int | None]:
    if baseline is None or candidate is None:
        return "unknown", None
    delta = candidate - baseline
    if delta == 0:
        return "equal", 0
    if direction == "higher":
        return ("improved" if delta > 0 else "regressed"), delta
    return ("improved" if delta < 0 else "regressed"), delta


def compare_fitness(
    *,
    baseline: Any,
    candidate: Any,
    protected_dimensions: Any = None,
) -> dict[str, Any]:
    """Compara candidate vs baseline por dimensión, sin colapsar a un score."""
    base = _normalize_vector(baseline, "baseline")
    cand = _normalize_vector(candidate, "candidate")
    protected = set(_normalize_protected(protected_dimensions))
    dimensions = sorted(set(base) | set(cand) | protected)

    comparisons: dict[str, dict[str, Any]] = {}
    comparable = 0
    missing: list[str] = []
    improved: list[str] = []
    regressed: list[str] = []
    protected_regressions: list[str] = []

    for dimension in dimensions:
        base_metric = base.get(dimension)
        cand_metric = cand.get(dimension)
        directions = {
            metric["direction"]
            for metric in (base_metric, cand_metric)
            if metric is not None
        }
        if len(directions) > 1:
            raise FitnessError(f"{dimension}: direction no coincide")
        direction = next(iter(directions)) if directions else None
        base_value = base_metric["value"] if base_metric is not None else None
        cand_value = cand_metric["value"] if cand_metric is not None else None
        if direction is None:
            status, delta = "unknown", None
        else:
            status, delta = _dimension_status(base_value, cand_value, direction)
        is_protected = dimension in protected

        comparisons[dimension] = {
            "baseline": base_value,
            "candidate": cand_value,
            "direction": direction,
            "protected": is_protected,
            "status": status,
            "delta": delta,
        }
        if status == "unknown":
            missing.append(dimension)
            continue
        comparable += 1
        if status == "improved":
            improved.append(dimension)
        elif status == "regressed":
            regressed.append(dimension)
            if is_protected:
                protected_regressions.append(dimension)

    total = len(dimensions)
    confidence = comparable / total
    if protected_regressions:
        claim = "blocked"
    elif missing:
        claim = "inconclusive"
    elif regressed:
        claim = "mixed"
    elif improved:
        claim = "improved"
    else:
        claim = "equal"

    result = {
        "version": FITNESS_VERSION,
        "dimensions": comparisons,
        "protected_dimensions": sorted(protected),
        "protected_regressions": protected_regressions,
        "missing_dimensions": missing,
        "confidence": {
            "comparable": comparable,
            "total": total,
            "ratio": round(confidence, 6),
        },
        "claim": claim,
        "can_claim_improvement": claim == "improved",
    }
    result["fingerprint"] = _stable_hash(result)
    return result
