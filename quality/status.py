"""Quality Health v1: estado común para Readiness y Factory Queue."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any

from performance.status import PerformanceStatusError, readiness_projection as performance_projection
from quality.contract import validate_quality_contract
from recovery.status import RecoveryStatusError, project_recovery_readiness

HEALTH_STATES = frozenset({"PASS", "DEGRADED", "UNKNOWN", "BLOCKED"})
GATE_STATES = frozenset({"PASS", "FAIL", "UNKNOWN", "STALE"})
WORK_ITEM_CLASSES = frozenset({
    "quality_gate_failed", "quality_evidence_missing", "quality_evidence_stale",
    "quality_evidence_unknown", "quality_regression_flaky",
    "quality_regression_unverified", "quality_regression_unresolved",
    "quality_performance_degraded", "quality_performance_unknown",
    "quality_performance_blocked", "quality_recovery_degraded",
    "quality_recovery_unknown", "quality_recovery_blocked",
})
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_PROJECT_REF = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SENSITIVE = re.compile(
    r"(?i)(?:\b(?:password|passwd|secret|token|api[_-]?key|authorization|cookie)"
    r"\b\s*[:=]|bearer\s+[A-Za-z0-9._~+/-]{8,})"
)


class QualityStatusError(ValueError):
    """Quality Health no puede demostrarse de forma segura."""


def derive_quality_health(
    contract: Any,
    gate_evidence: Any,
    regressions: Any,
    *,
    observed_at: str,
    project_ref: str,
    performance_status: Mapping[str, Any] | None = None,
    recovery_health: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deriva un único estado Quality sin ejecutar ni recalcular dimensiones externas."""
    _safe((gate_evidence, regressions))
    quality = validate_quality_contract(contract)
    now = _time(observed_at, "observed_at")
    project_ref = _project_ref(project_ref)
    required = _required_gates(quality)
    rows = _gate_rows(gate_evidence, required, now, quality["evidence_freshness_seconds"])

    states: list[str] = []
    reasons: list[str] = []
    classes: list[str] = []
    refs: set[str] = set()
    ages: list[int] = []

    for key, meta in required.items():
        row = rows.get(key)
        surface, gate = key
        label = f"{surface}:{gate}"
        if row is None:
            states.append("UNKNOWN"); reasons.append(f"gate_missing:{label}")
            classes.append("quality_evidence_missing")
            continue
        refs.add(row["evidence_ref"]); ages.append(row["age_seconds"])
        if row["stale"] or row["status"] == "STALE":
            states.append("UNKNOWN"); reasons.append(f"gate_stale:{label}")
            classes.append("quality_evidence_stale")
        elif row["status"] == "UNKNOWN":
            states.append("UNKNOWN"); reasons.append(f"gate_unknown:{label}")
            classes.append("quality_evidence_unknown")
        elif row["status"] == "FAIL":
            states.append("BLOCKED" if meta["criticality"] == "critical" else "DEGRADED")
            reasons.append(f"gate_failed:{label}"); classes.append("quality_gate_failed")

    for regression in _regressions(regressions, project_ref, required):
        refs.update(regression["provenance"])
        surface = regression["surface"]
        classification = regression["classification"]
        if classification == "VERIFIED":
            continue
        if classification == "FLAKY":
            states.append("DEGRADED"); reasons.append(f"regression_flaky:{surface}")
            classes.append("quality_regression_flaky")
        elif classification == "OBSERVED":
            states.append("UNKNOWN"); reasons.append(f"regression_unverified:{surface}")
            classes.append("quality_regression_unverified")
        elif classification == "REPRODUCED":
            critical = any(
                meta["criticality"] == "critical"
                for (candidate, _), meta in required.items()
                if candidate == surface
            )
            states.append("BLOCKED" if critical else "DEGRADED")
            reasons.append(f"regression_unresolved:{surface}")
            classes.append("quality_regression_unresolved")

    external = _external_dimensions(
        quality, performance_status, recovery_health, states, reasons, classes, refs
    )
    state = _highest_state(states)
    freshness_state = "DEGRADED" if any(
        item.startswith(("gate_missing:", "gate_stale:", "gate_unknown:"))
        or item in {"performance_missing", "recovery_missing",
                    "performance_unknown", "recovery_unknown"}
        for item in reasons
    ) else "CURRENT"
    return {
        "version": 1,
        "project": quality["project"],
        "project_ref": project_ref,
        "state": state,
        "observed_at": _iso(now),
        "reasons": sorted(set(reasons)) or ["quality_evidence_current"],
        "freshness": {
            "state": freshness_state,
            "max_age_seconds": quality["evidence_freshness_seconds"],
            "oldest_age_seconds": max(ages) if ages else None,
        },
        "required_gates": [
            {"surface": surface, "gate": gate, **meta}
            for (surface, gate), meta in sorted(required.items())
        ],
        "external_dimensions": external,
        "evidence_refs": sorted(refs),
        "work_item_classes": sorted(set(classes)),
        "authority": "unchanged",
        "execute_actions": False,
        "parallel_queue": False,
    }


def quality_work_item_classes(health: Mapping[str, Any]) -> list[str]:
    _health_contract(health)
    classes = health.get("work_item_classes")
    if not isinstance(classes, list) or any(item not in WORK_ITEM_CLASSES for item in classes):
        raise QualityStatusError("Quality Health contiene clase no canónica.")
    return sorted(set(classes))


def readiness_projection(health: Mapping[str, Any]) -> dict[str, Any]:
    _health_contract(health)
    classes = quality_work_item_classes(health)
    state = health["state"]
    return {
        "version": 1,
        "dimension": "quality",
        "quality_health": state,
        "ready": state in {"PASS", "DEGRADED"},
        "critical_blocker": state in {"UNKNOWN", "BLOCKED"},
        "reasons": list(health.get("reasons", [])),
        "evidence_refs": list(health.get("evidence_refs", [])),
        "work_item_classes": classes,
        "source": "quality_health_v1",
        "recalculated": False,
    }


def _required_gates(contract: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (surface["id"], gate): {"criticality": surface["criticality"]}
        for surface in contract["surfaces"]
        for gate in surface["required_gates"]
    }


def _gate_rows(value: Any, required, now: datetime, max_age: int):
    if not isinstance(value, list):
        raise QualityStatusError("gate_evidence debe ser lista.")
    result = {}
    for raw in value:
        row = _closed(raw, {"surface", "gate", "status", "observed_at", "evidence_ref"}, "gate")
        key = (row["surface"], row["gate"])
        if key not in required or key in result or row["status"] not in GATE_STATES:
            raise QualityStatusError("gate evidence fuera del contrato.")
        seen = _time(row["observed_at"], "gate.observed_at")
        age = int((now - seen).total_seconds())
        if age < 0:
            raise QualityStatusError("gate evidence temporal inválida.")
        result[key] = {
            "status": row["status"], "evidence_ref": _ref(row["evidence_ref"]),
            "age_seconds": age, "stale": age > max_age,
        }
    return result


def _regressions(value: Any, project_ref: str, required):
    if not isinstance(value, list):
        raise QualityStatusError("regressions debe ser lista.")
    surfaces = {surface for surface, _ in required}
    result = []
    for raw in value:
        row = _closed(
            raw,
            {"version", "regression_id", "project", "surface", "signature",
             "classification", "flaky", "reproduced", "pass_evidence_eligible",
             "guardrail_material", "provenance", "fingerprint"},
            "regression",
        )
        classification = row["classification"]
        coherent = (
            (classification == "VERIFIED" and row["pass_evidence_eligible"] is True
             and row["reproduced"] is True and row["flaky"] is False)
            or (classification == "FLAKY" and row["pass_evidence_eligible"] is False
                and row["flaky"] is True)
            or (classification == "REPRODUCED" and row["pass_evidence_eligible"] is False
                and row["reproduced"] is True and row["flaky"] is False)
            or (classification == "OBSERVED" and row["pass_evidence_eligible"] is False
                and row["reproduced"] is False and row["flaky"] is False)
        )
        if (
            row["version"] != 1 or row["project"] != project_ref
            or row["surface"] not in surfaces or not coherent
        ):
            raise QualityStatusError("regression evidence incoherente.")
        provenance = row["provenance"]
        if not isinstance(provenance, list) or not provenance:
            raise QualityStatusError("regression provenance inválida.")
        result.append({**row, "provenance": [_ref(item) for item in provenance]})
    return result


def _external_dimensions(quality, performance_status, recovery_health, states, reasons, classes, refs):
    result = {}
    required = quality["dimensions"]
    if required["performance"]["required"]:
        if performance_status is None:
            states.append("UNKNOWN"); reasons.append("performance_missing")
            classes.append("quality_performance_unknown")
        else:
            try:
                projected = performance_projection(performance_status)
            except PerformanceStatusError as exc:
                raise QualityStatusError("performance status inválido.") from exc
            if projected["project"] != quality["project"]:
                raise QualityStatusError("performance project incoherente.")
            result["performance"] = _external("performance", projected["status"], projected, states, reasons, classes)
            refs.update(_refs(projected.get("evidence_refs", [])))
    if required["recovery"]["required"]:
        if recovery_health is None:
            states.append("UNKNOWN"); reasons.append("recovery_missing")
            classes.append("quality_recovery_unknown")
        else:
            if not isinstance(recovery_health, Mapping) or recovery_health.get("project") != quality["project"]:
                raise QualityStatusError("recovery project incoherente.")
            try:
                projected = project_recovery_readiness(recovery_health, critical=True)
            except RecoveryStatusError as exc:
                raise QualityStatusError("recovery health inválido.") from exc
            result["recovery"] = _external("recovery", projected["recovery_health"], projected, states, reasons, classes)
    return result


def _external(name, status, payload, states, reasons, classes):
    mapped = {"HEALTHY": "PASS", "DEGRADED": "DEGRADED", "UNKNOWN": "UNKNOWN", "BLOCKED": "BLOCKED"}
    if status not in mapped:
        raise QualityStatusError(f"{name} status inválido.")
    if mapped[status] != "PASS":
        states.append(mapped[status]); reasons.append(f"{name}_{status.lower()}")
        classes.append(f"quality_{name}_{status.lower()}")
    return {
        "status": status, "source": payload.get("source"),
        "reasons": list(payload.get("reasons", [])),
        "evidence_refs": list(payload.get("evidence_refs", [])),
        "work_item_classes": list(payload.get("work_item_classes", [])),
        "recalculated": False,
    }


def _highest_state(states: list[str]) -> str:
    order = {"PASS": 0, "DEGRADED": 1, "UNKNOWN": 2, "BLOCKED": 3}
    return max(states or ["PASS"], key=order.__getitem__)


def _health_contract(health: Mapping[str, Any]) -> None:
    if (
        not isinstance(health, Mapping) or health.get("version") != 1
        or health.get("state") not in HEALTH_STATES
        or health.get("authority") != "unchanged"
        or health.get("execute_actions") is not False
        or health.get("parallel_queue") is not False
    ):
        raise QualityStatusError("Quality Health contract inválido.")


def _closed(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise QualityStatusError(f"{label} contiene campos faltantes o no permitidos.")
    return value


def _refs(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise QualityStatusError("evidence_refs inválidas.")
    return [_ref(item) for item in value]


def _ref(value: Any) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None or _SENSITIVE.search(value):
        raise QualityStatusError("evidence ref inválida o sensible.")
    return value


def _project_ref(value: Any) -> str:
    if not isinstance(value, str) or _PROJECT_REF.fullmatch(value) is None:
        raise QualityStatusError("project_ref inválido.")
    return value


def _time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise QualityStatusError(f"{label} inválido.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QualityStatusError(f"{label} inválido.") from exc
    if parsed.tzinfo is None:
        raise QualityStatusError(f"{label} inválido.")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise QualityStatusError("Quality evidence debe ser JSON finito.") from exc
    if len(encoded.encode()) > 100_000 or _SENSITIVE.search(encoded):
        raise QualityStatusError("Quality evidence contiene forma sensible no permitida.")
