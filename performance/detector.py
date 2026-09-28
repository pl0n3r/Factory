"""Detección determinista de regresiones contra Performance Contract v1."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import math
import re
from typing import Any

from performance.contract import validate_performance_contract

CLASSIFICATIONS = {"PERF_INFO", "PERF_REVIEW", "PERF_DEGRADATION", "PERF_INCIDENT"}
SEVERITIES = {"info", "low", "medium", "high", "critical"}
_VALUE_ERROR = "value debe ser número finito y acotado."
BOTTLENECKS = {
    "database", "backend", "frontend", "infrastructure",
    "sre", "data", "architecture", "unknown",
}
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_SENSITIVE_REF = re.compile(
    r"(?:"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bgithub_pat_[A-Za-z0-9_]{10,}\b|"
    r"\bsk-[A-Za-z0-9]{20,}\b|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    r")",
    re.IGNORECASE,
)


class PerformanceDetectionError(ValueError):
    """Observación de rendimiento inválida."""


def detect_performance(
    contract: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    evaluated_at: str,
) -> dict[str, Any]:
    """Compara evidencia con la métrica exacta sin ejecutar remediación."""
    canonical = validate_performance_contract(contract)
    obs = _observation(observation)
    now = _time(evaluated_at, "evaluated_at")
    metric = _metric(canonical, obs)
    if metric is None:
        return _unknown(canonical["project"], obs, now)

    if obs["unit"] != metric["baseline"]["unit"]:
        raise PerformanceDetectionError("observation.unit incompatible con contrato.")

    observed_time = _parse(obs["observed_at"])
    age = int((now - observed_time).total_seconds())
    reasons: list[str] = []
    if age < 0:
        reasons.append("future_evidence")
    if age > metric["freshness"]["max_age_seconds"]:
        reasons.append("stale")
    if obs["sample_count"] < metric["window"]["min_samples"]:
        reasons.append("insufficient_samples")
    if obs["window_seconds"] < metric["window"]["duration_seconds"]:
        reasons.append("insufficient_window")

    if not reasons:
        state = "CURRENT"
    elif reasons == ["stale"]:
        state = "STALE"
    else:
        state = "INSUFFICIENT"
    breach = (
        obs["value"] > metric["budget"]["value"]
        if metric["budget"]["operator"] == "lte"
        else obs["value"] < metric["budget"]["value"]
    )
    if state != "CURRENT":
        classification = "PERF_REVIEW"
    elif not breach:
        classification = "PERF_INFO"
    elif obs["severity"] == "critical" and obs["operational_impact"]:
        classification = "PERF_INCIDENT"
    else:
        classification = "PERF_DEGRADATION"

    return _result(
        canonical["project"], obs, metric, classification, state,
        sorted(reasons), breach, max(age, 0),
    )


def _result(
    project: str,
    obs: dict[str, Any],
    metric: dict[str, Any],
    classification: str,
    state: str,
    reasons: list[str],
    breach: bool,
    age: int,
) -> dict[str, Any]:
    return {
        "version": 1,
        "project": project,
        "surface": obs["surface"],
        "metric": obs["metric"],
        "classification": classification,
        "evidence_state": state,
        "reasons": reasons,
        "breach": breach,
        "baseline": metric["baseline"],
        "budget": metric["budget"],
        "observed": {
            "value": obs["value"], "unit": obs["unit"],
            "observed_at": obs["observed_at"],
            "sample_count": obs["sample_count"],
            "window_seconds": obs["window_seconds"],
        },
        "delta": obs["value"] - metric["baseline"]["value"],
        "freshness": {
            "age_seconds": age,
            "max_age_seconds": metric["freshness"]["max_age_seconds"],
        },
        "identity": {"sha": obs["sha"], "release": obs["release"]},
        "severity": obs["severity"],
        "operational_impact": obs["operational_impact"],
        "bottleneck": obs["bottleneck"],
        "evidence_ref": obs["evidence_ref"],
        "allowed_actions": metric["allowed_actions"],
        "escalation_conditions": metric["escalation_conditions"],
    }


def _unknown(project: str, obs: dict[str, Any], now: datetime) -> dict[str, Any]:
    age = max(0, int((now - _parse(obs["observed_at"])).total_seconds()))
    return {
        "version": 1, "project": project, "surface": obs["surface"],
        "metric": obs["metric"], "classification": "PERF_REVIEW",
        "evidence_state": "UNKNOWN", "reasons": ["unknown_contract_identity"],
        "breach": None, "baseline": None, "budget": None,
        "observed": {
            "value": obs["value"], "unit": obs["unit"],
            "observed_at": obs["observed_at"],
            "sample_count": obs["sample_count"],
            "window_seconds": obs["window_seconds"],
        },
        "delta": None,
        "freshness": {"age_seconds": age, "max_age_seconds": None},
        "identity": {"sha": obs["sha"], "release": obs["release"]},
        "severity": obs["severity"], "operational_impact": obs["operational_impact"],
        "bottleneck": obs["bottleneck"], "evidence_ref": obs["evidence_ref"],
        "allowed_actions": [], "escalation_conditions": [],
    }


def _metric(contract: dict[str, Any], obs: dict[str, Any]) -> dict[str, Any] | None:
    if obs["project"] != contract["project"]:
        return None
    for surface in contract["surfaces"]:
        if surface["id"] == obs["surface"]:
            return next((m for m in surface["metrics"] if m["id"] == obs["metric"]), None)
    return None


def _observation(raw: Any) -> dict[str, Any]:
    fields = {
        "version", "project", "surface", "metric", "value", "unit",
        "observed_at", "window_seconds", "sample_count", "severity",
        "operational_impact", "bottleneck", "evidence_ref", "sha", "release",
    }
    if not isinstance(raw, Mapping) or set(raw) != fields or raw["version"] != 1:
        raise PerformanceDetectionError("observation no coincide con contrato v1.")
    if type(raw["operational_impact"]) is not bool:
        raise PerformanceDetectionError("operational_impact debe ser booleano.")
    return {
        "version": 1,
        "project": _match(raw["project"], _ID, "project"),
        "surface": _match(raw["surface"], _ID, "surface"),
        "metric": _match(raw["metric"], _ID, "metric"),
        "value": _number(raw["value"]),
        "unit": _match(raw["unit"], _ID, "unit"),
        "observed_at": _time(raw["observed_at"], "observed_at").isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z"),
        "window_seconds": _positive(raw["window_seconds"], "window_seconds"),
        "sample_count": _positive(raw["sample_count"], "sample_count"),
        "severity": _enum(raw["severity"], SEVERITIES, "severity"),
        "operational_impact": raw["operational_impact"],
        "bottleneck": _enum(raw["bottleneck"], BOTTLENECKS, "bottleneck"),
        "evidence_ref": _evidence_ref(raw["evidence_ref"]),
        "sha": _nullable(raw["sha"], _SHA, "sha"),
        "release": _nullable(raw["release"], _RELEASE, "release"),
    }


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise PerformanceDetectionError(f"{label} debe ser ISO-8601 con zona.")
    try:
        parsed = _parse(value)
    except ValueError as exc:
        raise PerformanceDetectionError(f"{label} debe ser ISO-8601 con zona.") from exc
    if parsed.tzinfo is None:
        raise PerformanceDetectionError(f"{label} debe incluir zona horaria.")
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PerformanceDetectionError(_VALUE_ERROR)
    if isinstance(value, float) and not math.isfinite(value):
        raise PerformanceDetectionError(_VALUE_ERROR)
    if abs(value) > 1e15:
        raise PerformanceDetectionError(_VALUE_ERROR)
    return value


def _positive(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 31_536_000:
        raise PerformanceDetectionError(f"{label} fuera de límites.")
    return value


def _match(value: Any, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise PerformanceDetectionError(f"{label} inválido.")
    return value


def _nullable(value: Any, pattern: re.Pattern[str], label: str) -> str | None:
    return None if value is None else _match(value, pattern, label)


def _evidence_ref(value: Any) -> str:
    ref = _match(value, _REF, "evidence_ref")
    if _SENSITIVE_REF.search(ref):
        raise PerformanceDetectionError(
            "evidence_ref contiene forma sensible no permitida."
        )
    return ref


def _enum(value: Any, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise PerformanceDetectionError(f"{label} fuera del catálogo.")
    return value
