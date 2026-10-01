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
SONAR_SIGNAL_STATES = GATE_STATES | {"NOT_APPLICABLE"}
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
    sonar_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deriva un único estado Quality sin ejecutar ni recalcular dimensiones externas."""
    _safe((gate_evidence, regressions, performance_status, recovery_health, sonar_evidence))
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
    sonar = _sonar_dimension(
        quality, sonar_evidence, states, reasons, classes, refs, ages
    )
    if sonar is not None:
        external["sonar"] = sonar
    state = _highest_state(states)
    freshness_classes = {
        "quality_evidence_missing",
        "quality_evidence_stale",
        "quality_evidence_unknown",
    }
    freshness_state = "DEGRADED" if (
        any(
            item.startswith(("gate_missing:", "gate_stale:", "gate_unknown:"))
            or item in {
                "performance_missing", "recovery_missing", "sonar_missing",
                "performance_unknown", "recovery_unknown",
            }
            for item in reasons
        )
        or any(item in freshness_classes for item in classes)
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



_SONAR_SIGNALS = frozenset({
    "quality_gate", "analysis_freshness", "ce_task", "organization_line_usage",
    "visibility", "analysis_method", "coverage", "historical_debt",
})
_SONAR_FAIL_STATES = {
    "quality_gate": "BLOCKED",
    "ce_task": "BLOCKED",
    "organization_line_usage": "DEGRADED",
    "visibility": "DEGRADED",
    "analysis_method": "DEGRADED",
    "coverage": "DEGRADED",
    "analysis_freshness": "DEGRADED",
    "historical_debt": "DEGRADED",
}


def _sonar_dimension(quality, evidence, states, reasons, classes, refs, ages):
    configured = "sonar" in quality
    if not configured:
        if evidence is not None:
            raise QualityStatusError("sonar evidence fuera del contrato.")
        return None
    if evidence is None:
        states.append("UNKNOWN")
        reasons.append("sonar_missing")
        classes.append("quality_evidence_missing")
        return {
            "status": "UNKNOWN", "source": "sonar_evidence_v1",
            "reasons": ["sonar_missing"], "evidence_refs": [],
            "work_item_classes": ["quality_evidence_missing"],
            "signals": [], "recalculated": False,
        }

    row = _closed(
        evidence,
        {
            "version", "project", "observed_at", "snapshot_freshness",
            "signals", "authority", "execute_actions",
        },
        "sonar",
    )
    if (
        row["version"] != 1 or row["project"] != quality["project"]
        or row["authority"] != "read_only" or row["execute_actions"] is not False
    ):
        raise QualityStatusError("sonar evidence contract inválido.")

    _time(row["observed_at"], "sonar.observed_at")
    snapshot = _closed(
        row["snapshot_freshness"],
        {"state", "age_seconds", "max_age_seconds"},
        "sonar.snapshot_freshness",
    )
    _freshness(snapshot, "sonar.snapshot_freshness")
    if snapshot["state"] not in {"CURRENT", "STALE"}:
        raise QualityStatusError("sonar snapshot freshness inválida.")

    raw_signals = row["signals"]
    if not isinstance(raw_signals, list) or len(raw_signals) != len(_SONAR_SIGNALS):
        raise QualityStatusError("sonar signals inválidas.")

    seen = set()
    projected = []
    local_states = []
    local_reasons = []
    local_classes = []
    local_refs = set()
    for raw in raw_signals:
        signal = _closed(
            raw,
            {
                "signal", "status", "reason", "observed_at", "freshness",
                "evidence_refs", "details",
            },
            "sonar.signal",
        )
        name = signal["signal"]
        status = signal["status"]
        if name not in _SONAR_SIGNALS or name in seen or status not in SONAR_SIGNAL_STATES:
            raise QualityStatusError("sonar signal fuera del contrato.")
        seen.add(name)
        reason = _ref(signal["reason"])
        freshness = _closed(
            signal["freshness"],
            {"state", "age_seconds", "max_age_seconds"},
            "sonar.signal.freshness",
        )
        age = _freshness(freshness, "sonar.signal.freshness")
        freshness_state = freshness["state"]
        if (status == "STALE") != (freshness_state == "STALE"):
            raise QualityStatusError("sonar stale incoherente.")
        if freshness_state == "UNKNOWN" and status != "UNKNOWN":
            raise QualityStatusError("sonar unknown incoherente.")
        if status in {"PASS", "FAIL"} and freshness_state != "CURRENT":
            raise QualityStatusError("sonar status/freshness incoherente.")
        observed = signal["observed_at"]
        if freshness_state == "UNKNOWN":
            if observed is not None:
                raise QualityStatusError("sonar observed_at incoherente.")
        else:
            if observed is None:
                raise QualityStatusError("sonar observed_at faltante.")
            _time(observed, "sonar.signal.observed_at")
        if snapshot["state"] == "STALE" and status not in {"STALE", "NOT_APPLICABLE"}:
            raise QualityStatusError("sonar snapshot stale incoherente.")
        signal_refs = _refs(signal["evidence_refs"])
        _validate_sonar_applicability(
            quality, name, status, reason, signal_refs
        )
        refs.update(signal_refs)
        local_refs.update(signal_refs)
        if age is not None:
            ages.append(age)

        projected.append({
            "signal": name, "status": status, "reason": reason,
            "freshness": dict(freshness), "evidence_refs": signal_refs,
        })
        if status in {"PASS", "NOT_APPLICABLE"}:
            continue
        reason_key = f"sonar:{name}:{reason}"
        reasons.append(reason_key)
        local_reasons.append(reason_key)
        if status == "STALE":
            states.append("UNKNOWN"); local_states.append("UNKNOWN")
            classes.append("quality_evidence_stale")
            local_classes.append("quality_evidence_stale")
        elif status == "UNKNOWN":
            states.append("UNKNOWN"); local_states.append("UNKNOWN")
            classes.append("quality_evidence_unknown")
            local_classes.append("quality_evidence_unknown")
        else:
            health_state = _SONAR_FAIL_STATES[name]
            states.append(health_state); local_states.append(health_state)
            classes.append("quality_gate_failed")
            local_classes.append("quality_gate_failed")

    if seen != _SONAR_SIGNALS:
        raise QualityStatusError("sonar signals incompletas.")
    return {
        "status": _highest_state(local_states),
        "source": "sonar_evidence_v1",
        "reasons": sorted(set(local_reasons)),
        "evidence_refs": sorted(local_refs),
        "work_item_classes": sorted(set(local_classes)),
        "signals": sorted(projected, key=lambda item: item["signal"]),
        "recalculated": False,
    }


def _validate_sonar_applicability(
    quality: Mapping[str, Any],
    signal: str,
    status: str,
    reason: str,
    evidence_refs: list[str],
) -> None:
    sonar = quality["sonar"]
    applicability = sonar.get("applicability")
    policy = (
        applicability.get(signal)
        if isinstance(applicability, Mapping)
        and signal in {"coverage", "organization_line_usage"}
        else None
    )
    if status == "NOT_APPLICABLE":
        if not isinstance(policy, Mapping) or policy.get("state") != "not_applicable":
            raise QualityStatusError(
                "sonar NOT_APPLICABLE requiere autorización explícita del contrato."
            )
        if reason != policy.get("reason") or policy.get("source_ref") not in evidence_refs:
            raise QualityStatusError(
                "sonar NOT_APPLICABLE no coincide con razón/provenance del contrato."
            )
        return
    if isinstance(policy, Mapping) and policy.get("state") == "not_applicable":
        raise QualityStatusError(
            "sonar evidence contradice aplicabilidad explícita del contrato."
        )


def _freshness(value: Mapping[str, Any], label: str) -> int | None:
    state = value["state"]
    age = value["age_seconds"]
    max_age = value["max_age_seconds"]
    if state not in {"CURRENT", "STALE", "UNKNOWN"}:
        raise QualityStatusError(f"{label}.state inválido.")
    if type(max_age) is not int or max_age <= 0:
        raise QualityStatusError(f"{label}.max_age_seconds inválido.")
    if state == "UNKNOWN":
        if age is not None:
            raise QualityStatusError(f"{label}.age_seconds incoherente.")
        return None
    if type(age) is not int or age < 0:
        raise QualityStatusError(f"{label}.age_seconds inválido.")
    if state == "CURRENT" and age > max_age:
        raise QualityStatusError(f"{label} CURRENT excede max_age_seconds.")
    if state == "STALE" and age <= max_age:
        raise QualityStatusError(f"{label} STALE no excede max_age_seconds.")
    return age


def _external_dimensions(quality, performance_status, recovery_health, states, reasons, classes, refs):
    result = {}
    required = quality["dimensions"]
    if required["performance"]["required"]:
        if performance_status is None:
            states.append("UNKNOWN"); reasons.append("performance_missing")
            classes.append("quality_performance_unknown")
            result["performance"] = {
                "status": "UNKNOWN", "source": "performance-v1",
                "reasons": ["performance_missing"], "evidence_refs": [],
                "work_item_classes": [], "recalculated": False,
            }
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
            result["recovery"] = {
                "status": "UNKNOWN", "source": "recovery_health_v1",
                "reasons": ["recovery_missing"], "evidence_refs": [],
                "work_item_classes": [], "recalculated": False,
            }
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
