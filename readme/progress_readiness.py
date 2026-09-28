"""Cálculo puro y determinista de Progress + Readiness para README Contract v1."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

CONTRACT_ID = "factory.progress-readiness.v1"
APPLICABILITY = {"APPLICABLE", "NOT_APPLICABLE"}
FRESHNESS = {"CURRENT", "STALE", "UNKNOWN"}
SIGNAL_STATES = {"DEMONSTRATED", "PARTIAL", "NOT_DEMONSTRATED", "UNKNOWN"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
BLOCKER_STATUSES = {"OPEN", "CLOSED"}


class ProgressReadinessError(ValueError):
    """Input incompatible con Progress + Readiness v1."""


def calculate_progress_readiness(payload: Any) -> dict[str, Any]:
    """Normaliza evidencia y calcula métricas explicables para un target."""
    raw = _object(payload, {"target", "dimensions", "blockers"}, "payload")
    target = _target(raw["target"])
    dimensions = sorted((_dimension(row) for row in _list(raw["dimensions"], "dimensions")), key=lambda row: row["id"])
    blockers = sorted((_blocker(row) for row in _list(raw["blockers"], "blockers")), key=lambda row: row["id"])
    _unique(dimensions, "dimension")
    _unique(blockers, "blocker")

    totals = {"progress": 0.0, "readiness": 0.0, "weight": 0.0}
    freshness_values: list[str] = []
    evidence: set[str] = set()
    for dimension in dimensions:
        if dimension["applicability"] == "NOT_APPLICABLE":
            continue
        totals["weight"] += dimension["weight"]
        totals["progress"] += dimension["weight"] * dimension["progress_percent"] / 100.0
        totals["readiness"] += dimension["weight"] * dimension["readiness_percent"] / 100.0
        for milestone in dimension["milestones"]:
            freshness_values.append(milestone["freshness"])
            for metric in ("progress", "readiness"):
                evidence.update(milestone[metric]["evidence_refs"])
    for blocker in blockers:
        evidence.update(blocker["evidence_refs"])

    freshness = _freshness(freshness_values)
    progress = _percent(totals["progress"], totals["weight"])
    readiness = _percent(totals["readiness"], totals["weight"])
    critical = [row for row in blockers if row["severity"] == "CRITICAL" and row["status"] == "OPEN"]
    return {
        "contract": CONTRACT_ID,
        "target": target,
        "baseline_fingerprint": _baseline(target, dimensions),
        "progress": {"percent": progress, "status": _status(progress, freshness, "COMPLETE")},
        "readiness": {
            "percent": readiness,
            "status": "BLOCKED" if critical else _status(readiness, freshness, "READY"),
        },
        "dimensions": dimensions,
        "critical_blockers": critical,
        "blockers": blockers,
        "evidence_freshness": freshness,
        "evidence_refs": sorted(evidence),
    }


def compare_snapshots(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    """Emite tendencia solo cuando target y denominador conservan el mismo baseline."""
    for name, payload in (("previous", previous), ("current", current)):
        if not isinstance(payload, Mapping) or payload.get("contract") != CONTRACT_ID:
            raise ProgressReadinessError(f"{name} no es payload calculado compatible.")
        required = {"baseline_fingerprint", "progress", "readiness", "dimensions", "critical_blockers"}
        if not required <= set(payload):
            raise ProgressReadinessError(f"{name} está incompleto.")
    if previous["baseline_fingerprint"] != current["baseline_fingerprint"]:
        return {"kind": "REBASELINE", "progress_delta": None, "readiness_delta": None, "causes": ["target_or_scope_changed"]}

    before = {row["id"]: row for row in previous["dimensions"]}
    after = {row["id"]: row for row in current["dimensions"]}
    causes = [
        f"{dimension_id}:{metric}:{before[dimension_id][metric]}->{after[dimension_id][metric]}"
        for dimension_id in sorted(after)
        for metric in ("progress_percent", "readiness_percent")
        if before[dimension_id][metric] != after[dimension_id][metric]
    ]
    old_blockers = {row["id"] for row in previous["critical_blockers"]}
    new_blockers = {row["id"] for row in current["critical_blockers"]}
    causes += [f"blocker_opened:{item}" for item in sorted(new_blockers - old_blockers)]
    causes += [f"blocker_closed:{item}" for item in sorted(old_blockers - new_blockers)]
    return {
        "kind": "DELTA",
        "progress_delta": _delta(previous["progress"]["percent"], current["progress"]["percent"]),
        "readiness_delta": _delta(previous["readiness"]["percent"], current["readiness"]["percent"]),
        "causes": causes,
    }


def _target(value: Any) -> dict[str, str]:
    raw = _object(value, {"id", "label", "version", "scope"}, "target")
    return {key: _text(raw[key], f"target.{key}") for key in ("id", "label", "version", "scope")}


def _dimension(value: Any) -> dict[str, Any]:
    raw = _object(value, {"id", "label", "weight", "applicability", "milestones"}, "dimension")
    applicability = _enum(raw["applicability"], APPLICABILITY, "dimension.applicability")
    milestones = sorted((_milestone(row) for row in _list(raw["milestones"], "dimension.milestones")), key=lambda row: row["id"])
    _unique(milestones, "milestone")
    if applicability == "APPLICABLE" and not milestones:
        raise ProgressReadinessError("dimensión aplicable requiere al menos un hito.")
    if applicability == "NOT_APPLICABLE" and milestones:
        raise ProgressReadinessError("dimensión NOT_APPLICABLE no admite hitos.")

    milestone_weight = sum(row["weight"] for row in milestones)
    def metric_percent(metric: str) -> float | None:
        score = sum(row["weight"] * row[metric]["effective_value"] for row in milestones)
        return _percent(score, milestone_weight)
    return {
        "id": _text(raw["id"], "dimension.id"),
        "label": _text(raw["label"], "dimension.label"),
        "weight": _positive(raw["weight"], "dimension.weight"),
        "applicability": applicability,
        "progress_percent": metric_percent("progress"),
        "readiness_percent": metric_percent("readiness"),
        "milestones": milestones,
    }


def _milestone(value: Any) -> dict[str, Any]:
    raw = _object(value, {"id", "label", "weight", "freshness", "progress", "readiness"}, "milestone")
    freshness = _enum(raw["freshness"], FRESHNESS, "milestone.freshness")
    return {
        "id": _text(raw["id"], "milestone.id"),
        "label": _text(raw["label"], "milestone.label"),
        "weight": _positive(raw["weight"], "milestone.weight"),
        "freshness": freshness,
        "progress": _signal(raw["progress"], "milestone.progress", freshness),
        "readiness": _signal(raw["readiness"], "milestone.readiness", freshness),
    }


def _signal(value: Any, field: str, freshness: str) -> dict[str, Any]:
    raw = _object(value, {"state", "value", "evidence_refs"}, field)
    state = _enum(raw["state"], SIGNAL_STATES, f"{field}.state")
    number = _ratio(raw["value"], f"{field}.value")
    evidence = sorted({_text(ref, f"{field}.evidence_refs") for ref in _list(raw["evidence_refs"], f"{field}.evidence_refs")})
    if state == "DEMONSTRATED" and number != 1.0:
        raise ProgressReadinessError(f"{field}: DEMONSTRATED requiere value=1.")
    if state in {"NOT_DEMONSTRATED", "UNKNOWN"} and number != 0.0:
        raise ProgressReadinessError(f"{field}: {state} requiere value=0.")
    if state == "PARTIAL" and not 0.0 < number < 1.0:
        raise ProgressReadinessError(f"{field}: PARTIAL requiere 0 < value < 1.")
    if state in {"DEMONSTRATED", "PARTIAL"} and freshness == "CURRENT" and not evidence:
        raise ProgressReadinessError(f"{field}: señal positiva CURRENT requiere evidence_refs.")
    effective = number if freshness == "CURRENT" and state != "UNKNOWN" else 0.0
    return {"state": state, "value": number, "effective_value": effective, "evidence_refs": evidence}


def _blocker(value: Any) -> dict[str, Any]:
    raw = _object(value, {"id", "severity", "status", "evidence_refs"}, "blocker")
    return {
        "id": _text(raw["id"], "blocker.id"),
        "severity": _enum(raw["severity"], SEVERITIES, "blocker.severity"),
        "status": _enum(raw["status"], BLOCKER_STATUSES, "blocker.status"),
        "evidence_refs": sorted({_text(ref, "blocker.evidence_refs") for ref in _list(raw["evidence_refs"], "blocker.evidence_refs")}),
    }


def _baseline(target: Mapping[str, str], dimensions: list[dict[str, Any]]) -> str:
    scope = {
        "target": {key: target[key] for key in ("id", "version", "scope")},
        "dimensions": [{
            "id": row["id"], "weight": row["weight"], "applicability": row["applicability"],
            "milestones": [{"id": item["id"], "weight": item["weight"]} for item in row["milestones"]],
        } for row in dimensions],
    }
    encoded = json.dumps(scope, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _freshness(values: list[str]) -> str:
    if not values or "UNKNOWN" in values:
        return "UNKNOWN"
    return "STALE" if "STALE" in values else "CURRENT"


def _status(percent: float | None, freshness: str, complete: str) -> str:
    if percent is None:
        return "UNKNOWN"
    return complete if percent == 100.0 and freshness == "CURRENT" else "BUILDING"


def _percent(score: float, weight: float) -> float | None:
    return None if weight <= 0 else round(100.0 * score / weight, 2)


def _delta(before: float | None, after: float | None) -> float | None:
    return None if before is None or after is None else round(after - before, 2)


def _object(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProgressReadinessError(f"{field} debe contener exactamente: {', '.join(sorted(keys))}.")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProgressReadinessError(f"{field} debe ser lista.")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ProgressReadinessError(f"{field} debe ser texto.")
    cleaned = " ".join(value.split())
    if not cleaned or len(cleaned) > 240:
        raise ProgressReadinessError(f"{field} inválido.")
    return cleaned


def _enum(value: Any, allowed: set[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ProgressReadinessError(f"{field} fuera del contrato.")
    return value


def _positive(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ProgressReadinessError(f"{field} debe ser numérico finito > 0.")
    return float(value)


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ProgressReadinessError(f"{field} debe estar entre 0 y 1.")
    return float(value)


def _unique(rows: list[dict[str, Any]], field: str) -> None:
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ProgressReadinessError(f"{field} id duplicado.")


__all__ = ["CONTRACT_ID", "ProgressReadinessError", "calculate_progress_readiness", "compare_snapshots"]
