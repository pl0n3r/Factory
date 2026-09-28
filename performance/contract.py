"""Performance Contract v1: límites y evidencia por proyecto, sin umbrales globales."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import math
import re
from typing import Any

VERSION = 1
UNITS = {"ms", "s", "bytes", "kb", "mb", "count", "rps", "rpm", "percent", "ratio"}
OPERATORS = {"lte", "gte"}
ALLOWED_ACTIONS = {"observe", "diagnose", "benchmark", "create_work_item", "measure_before_after"}
ESCALATION_CONDITIONS = {
    "cost_change", "architecture_change", "consistency_risk", "business_semantics",
    "destructive_migration", "sensitive_data", "capacity_budget",
}
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|session[_-]?(?:id|key)?)\b\s*[:=]"
    r"|bearer\s+[A-Za-z0-9._~+/-]{8,})"
)
MAX_SURFACES, MAX_METRICS, MAX_SECONDS, MAX_SAMPLES = 50, 100, 31_536_000, 10_000_000


class PerformanceContractError(ValueError):
    """Contrato de rendimiento inválido."""


def validate_performance_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Valida y normaliza un Performance Contract v1 de forma determinista."""
    _reject_sensitive(payload)
    _exact(payload, {"version", "project", "surfaces"}, "contract")
    if payload["version"] != VERSION:
        raise PerformanceContractError("version debe ser 1.")
    project = _identifier(payload["project"], "project")
    raw_surfaces = payload["surfaces"]
    if not isinstance(raw_surfaces, list) or not raw_surfaces or len(raw_surfaces) > MAX_SURFACES:
        raise PerformanceContractError("surfaces debe ser lista no vacía y acotada.")
    seen, surfaces = set(), []
    for raw in raw_surfaces:
        _exact(raw, {"id", "label", "metrics"}, "surface")
        surface_id = _identifier(raw["id"], "surface.id")
        if surface_id in seen:
            raise PerformanceContractError("surface.id duplicado.")
        seen.add(surface_id)
        surfaces.append({
            "id": surface_id,
            "label": _text(raw["label"], "surface.label"),
            "metrics": _metrics(raw["metrics"]),
        })
    surfaces.sort(key=lambda row: row["id"])
    return {"version": VERSION, "project": project, "surfaces": surfaces}


def canonical_performance_contract(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        validate_performance_contract(payload),
        ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True,
    )


def _metrics(raw_metrics: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_metrics, list) or not raw_metrics or len(raw_metrics) > MAX_METRICS:
        raise PerformanceContractError("metrics debe ser lista no vacía y acotada.")
    seen, result = set(), []
    for raw in raw_metrics:
        _exact(raw, {
            "id", "label", "baseline", "budget", "window", "freshness", "evidence",
            "allowed_actions", "escalation_conditions",
        }, "metric")
        metric_id = _identifier(raw["id"], "metric.id")
        if metric_id in seen:
            raise PerformanceContractError("metric.id duplicado.")
        seen.add(metric_id)
        baseline, budget = _measurement(raw["baseline"], "baseline"), _budget(raw["budget"])
        if baseline["unit"] != budget["unit"]:
            raise PerformanceContractError("baseline y budget usan unidades incompatibles.")
        result.append({
            "id": metric_id, "label": _text(raw["label"], "metric.label"),
            "baseline": baseline, "budget": budget, "window": _window(raw["window"]),
            "freshness": _freshness(raw["freshness"]), "evidence": _evidence(raw["evidence"]),
            "allowed_actions": _catalog(raw["allowed_actions"], ALLOWED_ACTIONS, "allowed_actions"),
            "escalation_conditions": _catalog(
                raw["escalation_conditions"], ESCALATION_CONDITIONS, "escalation_conditions"
            ),
        })
    result.sort(key=lambda row: row["id"])
    return result


def _measurement(raw: Any, label: str) -> dict[str, Any]:
    _exact(raw, {"value", "unit", "observed_at"}, label)
    return {"value": _number(raw["value"], f"{label}.value"), "unit": _enum(raw["unit"], UNITS, f"{label}.unit"),
            "observed_at": _timestamp(raw["observed_at"], f"{label}.observed_at")}


def _budget(raw: Any) -> dict[str, Any]:
    _exact(raw, {"operator", "value", "unit"}, "budget")
    return {"operator": _enum(raw["operator"], OPERATORS, "budget.operator"),
            "value": _number(raw["value"], "budget.value"), "unit": _enum(raw["unit"], UNITS, "budget.unit")}


def _window(raw: Any) -> dict[str, int]:
    _exact(raw, {"duration_seconds", "min_samples"}, "window")
    return {"duration_seconds": _bounded_int(raw["duration_seconds"], "window.duration_seconds", MAX_SECONDS),
            "min_samples": _bounded_int(raw["min_samples"], "window.min_samples", MAX_SAMPLES)}


def _freshness(raw: Any) -> dict[str, int]:
    _exact(raw, {"max_age_seconds"}, "freshness")
    return {"max_age_seconds": _bounded_int(raw["max_age_seconds"], "freshness.max_age_seconds", MAX_SECONDS)}


def _evidence(raw: Any) -> dict[str, str]:
    _exact(raw, {"source", "ref", "observed_at"}, "evidence")
    return {"source": _identifier(raw["source"], "evidence.source"), "ref": _reference(raw["ref"], "evidence.ref"),
            "observed_at": _timestamp(raw["observed_at"], "evidence.observed_at")}


def _exact(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise PerformanceContractError(f"{label} contiene campos faltantes o no permitidos.")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise PerformanceContractError(f"{label} inválido.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PerformanceContractError(f"{label} debe ser texto.")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 160:
        raise PerformanceContractError(f"{label} vacío o fuera de límites.")
    return normalized


def _number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1e15:
        raise PerformanceContractError(f"{label} debe ser número finito y acotado.")
    return value


def _bounded_int(value: Any, label: str, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > high:
        raise PerformanceContractError(f"{label} fuera de límites.")
    return value


def _enum(value: Any, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise PerformanceContractError(f"{label} fuera del catálogo.")
    return value


def _catalog(value: Any, allowed: set[str], label: str) -> list[str]:
    if (not isinstance(value, list) or len(value) > len(allowed)
            or not all(isinstance(item, str) for item in value) or len(value) != len(set(value))):
        raise PerformanceContractError(f"{label} debe ser lista única y acotada.")
    if any(item not in allowed for item in value):
        raise PerformanceContractError(f"{label} contiene valor fuera del catálogo.")
    return sorted(value)


def _reference(value: Any, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise PerformanceContractError(f"{label} inválida.")
    return value


def _timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise PerformanceContractError(f"{label} debe ser ISO-8601 con zona.")
    parsed = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(parsed)
    except ValueError as exc:
        raise PerformanceContractError(f"{label} debe ser ISO-8601 con zona.") from exc
    if timestamp.tzinfo is None:
        raise PerformanceContractError(f"{label} debe incluir zona horaria.")
    return timestamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _reject_sensitive(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_sensitive(key)
            _reject_sensitive(item)
    elif isinstance(value, list):
        for item in value:
            _reject_sensitive(item)
    elif isinstance(value, str) and _SENSITIVE.search(value):
        raise PerformanceContractError("entrada contiene forma sensible no permitida.")
