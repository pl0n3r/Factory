"""Estado canónico de Performance Engineering para Readiness y consumidores."""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from performance.detector import CLASSIFICATIONS

HEALTH_STATES = {"HEALTHY", "DEGRADED", "UNKNOWN", "BLOCKED"}
_REMEDIATION = {"NO_ACTION", "BLOCKED", "ESCALATE", "AUTO_REPAIR"}
_COMPARISON = {"ADOPT", "REVERT_OR_REPLAN"}
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_REASON = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_SENSITIVE = re.compile(
    r"(?:\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{10,}\b|"
    r"\bsk-[A-Za-z0-9]{20,}\b|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b)",
    re.IGNORECASE,
)


class PerformanceStatusError(ValueError):
    """Estado de performance fuera del contrato v1."""


def derive_performance_status(
    detection: Mapping[str, Any],
    *,
    remediation: Mapping[str, Any] | None = None,
    comparison: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Proyecta evidencia canónica sin introducir score o algoritmo paralelo."""
    finding = _detection(detection)
    plan = _remediation(remediation) if remediation is not None else None
    outcome = _comparison(comparison) if comparison is not None else None

    reasons = set(finding["reasons"])
    if finding["evidence_state"] != "CURRENT":
        status = "UNKNOWN"
        reasons.add("evidence_not_current")
    elif plan and plan["decision"] in {"ESCALATE", "BLOCKED"}:
        status = "BLOCKED"
        reasons.add(f"remediation_{plan['decision'].lower()}")
    elif finding["classification"] == "PERF_INCIDENT":
        status = "BLOCKED"
        reasons.add("performance_incident")
    elif finding["classification"] == "PERF_DEGRADATION":
        status = "DEGRADED"
        reasons.add("performance_degradation")
    elif finding["classification"] == "PERF_INFO":
        if outcome and outcome["decision"] != "ADOPT":
            status = "DEGRADED"
            reasons.add("improvement_not_adopted")
        else:
            status = "HEALTHY"
    else:
        status = "UNKNOWN"
        reasons.add("classification_review")

    refs = {finding["evidence_ref"]}
    if outcome:
        refs.update((outcome["before_evidence_ref"], outcome["after_evidence_ref"]))

    return {
        "version": 1,
        "status": status,
        "reasons": sorted(reasons),
        "project": finding["project"],
        "surface": finding["surface"],
        "metric": finding["metric"],
        "classification": finding["classification"],
        "evidence_state": finding["evidence_state"],
        "freshness": dict(finding["freshness"]),
        "identity": dict(finding["identity"]),
        "evidence_refs": sorted(refs),
        "remediation_decision": None if plan is None else plan["decision"],
        "comparison_decision": None if outcome is None else outcome["decision"],
        "authority": "unchanged",
        "execute_actions": False,
        "parallel_queue": False,
    }


def readiness_projection(status: Mapping[str, Any]) -> dict[str, Any]:
    """Expone la dimensión performance sin recalcular su clasificación."""
    required = {
        "status", "reasons", "evidence_refs", "evidence_state",
        "project", "surface", "metric", "authority", "execute_actions",
    }
    if not isinstance(status, Mapping) or not required.issubset(status):
        raise PerformanceStatusError("status incompleto.")
    if status["status"] not in HEALTH_STATES or status["authority"] != "unchanged":
        raise PerformanceStatusError("status incompatible con Readiness.")
    if status["execute_actions"] is not False:
        raise PerformanceStatusError("status no puede ejecutar acciones.")
    return {
        "version": 1,
        "dimension": "performance",
        "status": status["status"],
        "reasons": list(status["reasons"]),
        "evidence_state": status["evidence_state"],
        "evidence_refs": list(status["evidence_refs"]),
        "project": status["project"],
        "surface": status["surface"],
        "metric": status["metric"],
        "source": "performance-v1",
    }


def _detection(raw: Any) -> dict[str, Any]:
    required = {
        "project", "surface", "metric", "classification", "evidence_state",
        "reasons", "freshness", "identity", "evidence_ref",
    }
    if not isinstance(raw, Mapping) or not required.issubset(raw):
        raise PerformanceStatusError("detection incompleta.")
    if raw["classification"] not in CLASSIFICATIONS:
        raise PerformanceStatusError("classification fuera de catálogo.")
    if raw["evidence_state"] not in {"CURRENT", "STALE", "INSUFFICIENT", "UNKNOWN"}:
        raise PerformanceStatusError("evidence_state fuera de catálogo.")
    reasons = raw["reasons"]
    if not isinstance(reasons, list) or any(
        not isinstance(item, str) or _REASON.fullmatch(item) is None for item in reasons
    ):
        raise PerformanceStatusError("reasons inválidas.")
    freshness = raw["freshness"]
    if not isinstance(freshness, Mapping) or set(freshness) != {"age_seconds", "max_age_seconds"}:
        raise PerformanceStatusError("freshness inválida.")
    identity = raw["identity"]
    if not isinstance(identity, Mapping) or set(identity) != {"sha", "release"}:
        raise PerformanceStatusError("identity inválida.")
    _optional(identity["sha"], _SHA, "identity.sha")
    _optional(identity["release"], _RELEASE, "identity.release")
    evidence_ref = _safe_ref(raw["evidence_ref"], "evidence_ref")
    return {**raw, "reasons": sorted(set(reasons)), "evidence_ref": evidence_ref}


def _remediation(raw: Any) -> dict[str, Any]:
    if (
        not isinstance(raw, Mapping)
        or raw.get("decision") not in _REMEDIATION
        or raw.get("authority") != "unchanged"
        or raw.get("execute_actions") is not False
    ):
        raise PerformanceStatusError("remediation incompatible.")
    return dict(raw)


def _comparison(raw: Any) -> dict[str, Any]:
    if (
        not isinstance(raw, Mapping)
        or raw.get("decision") not in _COMPARISON
        or raw.get("authority") != "unchanged"
        or raw.get("execute_actions") is not False
    ):
        raise PerformanceStatusError("comparison incompatible.")
    result = dict(raw)
    result["before_evidence_ref"] = _safe_ref(raw.get("before_evidence_ref"), "before_evidence_ref")
    result["after_evidence_ref"] = _safe_ref(raw.get("after_evidence_ref"), "after_evidence_ref")
    return result


def _safe_ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None or _SENSITIVE.search(value):
        raise PerformanceStatusError(f"{label} inválida o sensible.")
    return value


def _optional(value: Any, pattern: re.Pattern[str], label: str) -> None:
    if value is not None and (not isinstance(value, str) or pattern.fullmatch(value) is None):
        raise PerformanceStatusError(f"{label} inválida.")
