"""Causal evidence contract for Factory Lab promotions."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


EVIDENCE_VERSION = 1
EVIDENCE_CLASSES = (
    "observational",
    "quasi_experimental",
    "controlled_shadow",
)
IMPACT_LEVELS = ("low", "medium", "high")
MIN_SAMPLE_BY_IMPACT = {"low": 2, "medium": 4, "high": 8}
_EVIDENCE_RANK = {
    "observational": 1,
    "quasi_experimental": 2,
    "controlled_shadow": 3,
}
_REQUIRED_RANK = {"low": 1, "medium": 2, "high": 3}
_STRENGTH = {0: "insufficient", 1: "weak", 2: "moderate", 3: "strong"}
_METRIC = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


class ExperimentEvidenceError(ValueError):
    """Invalid or non-reproducible experiment evidence."""


def _stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 over JSON-safe evidence."""
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _line(value: Any, field: str, max_len: int = 240) -> str:
    """Validate a bounded, non-empty one-line identifier."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_len
        or "\n" in value
        or "\r" in value
    ):
        raise ExperimentEvidenceError(f"{field} debe ser texto de una línea")
    return value.strip()


def _positive_int(value: Any, field: str) -> int:
    """Validate a positive sample size without accepting booleans."""
    if type(value) is not int or value <= 0:
        raise ExperimentEvidenceError(f"{field} debe ser entero positivo")
    return value


def _strings(
    value: Any,
    field: str,
    *,
    allow_empty: bool,
    metric_names: bool = False,
) -> tuple[str, ...]:
    """Normalize bounded string collections without duplicates."""
    if not isinstance(value, (list, tuple)):
        raise ExperimentEvidenceError(f"{field} debe ser lista")
    if (not allow_empty and not value) or len(value) > 32:
        raise ExperimentEvidenceError(f"{field} tiene cardinalidad inválida")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ExperimentEvidenceError(f"{field} contiene valores inválidos")
    normalized = tuple(item.strip() for item in value)
    if len(set(normalized)) != len(normalized):
        raise ExperimentEvidenceError(f"{field} contiene duplicados")
    if metric_names and any(_METRIC.fullmatch(item) is None for item in normalized):
        raise ExperimentEvidenceError(f"{field} contiene métricas inválidas")
    return tuple(sorted(normalized))


def evaluate_experiment_evidence(declaration: Any) -> dict[str, Any]:
    """Evaluate causal strength without collapsing product metrics into a score."""
    required = {
        "baseline",
        "treatment",
        "protected_metrics",
        "evidence_class",
        "impact",
        "baseline_sample_size",
        "treatment_sample_size",
        "confounders",
        "simultaneous_changes",
    }
    if not isinstance(declaration, dict) or set(declaration) != required:
        raise ExperimentEvidenceError(
            "declaration incompleta o con campos extra"
        )

    baseline = _line(declaration["baseline"], "baseline")
    treatment = _line(declaration["treatment"], "treatment")
    if baseline == treatment:
        raise ExperimentEvidenceError("baseline y treatment deben diferir")

    protected = _strings(
        declaration["protected_metrics"],
        "protected_metrics",
        allow_empty=False,
        metric_names=True,
    )
    evidence_class = _line(declaration["evidence_class"], "evidence_class")
    if evidence_class not in EVIDENCE_CLASSES:
        raise ExperimentEvidenceError("evidence_class no admitida")
    impact = _line(declaration["impact"], "impact")
    if impact not in IMPACT_LEVELS:
        raise ExperimentEvidenceError("impact no admitido")

    baseline_n = _positive_int(
        declaration["baseline_sample_size"],
        "baseline_sample_size",
    )
    treatment_n = _positive_int(
        declaration["treatment_sample_size"],
        "treatment_sample_size",
    )
    confounders = _strings(
        declaration["confounders"],
        "confounders",
        allow_empty=True,
    )
    simultaneous = _strings(
        declaration["simultaneous_changes"],
        "simultaneous_changes",
        allow_empty=True,
    )

    observed_sample = min(baseline_n, treatment_n)
    minimum_sample = MIN_SAMPLE_BY_IMPACT[impact]
    raw_rank = _EVIDENCE_RANK[evidence_class]
    effective_rank = max(
        0,
        raw_rank - (1 if confounders or simultaneous else 0),
    )
    reasons: list[str] = []
    if observed_sample < minimum_sample:
        reasons.append("sample_below_risk_minimum")
    if effective_rank < _REQUIRED_RANK[impact]:
        reasons.append("causal_strength_below_impact_requirement")

    status = "supported" if not reasons else "insufficient_evidence"
    result = {
        "version": EVIDENCE_VERSION,
        "baseline": baseline,
        "treatment": treatment,
        "protected_metrics": list(protected),
        "evidence_class": evidence_class,
        "impact": impact,
        "sample": {
            "baseline": baseline_n,
            "treatment": treatment_n,
            "observed_minimum": observed_sample,
            "required_minimum": minimum_sample,
        },
        "confounders": list(confounders),
        "simultaneous_changes": list(simultaneous),
        "claim_strength": _STRENGTH[effective_rank],
        "status": status,
        "reasons": reasons,
        "promotion_allowed": status == "supported",
    }
    result["fingerprint"] = _stable_hash(result)
    return result


def validate_experiment_evidence(
    declaration: Any,
    result: Any,
) -> dict[str, Any]:
    """Recompute source evidence and require exact equality."""
    expected = evaluate_experiment_evidence(declaration)
    if not isinstance(result, dict) or result != expected:
        raise ExperimentEvidenceError(
            "resultado causal no coincide con evidencia fuente"
        )
    return expected
