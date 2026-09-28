"""Remediación gobernada y before/after para hallazgos de performance."""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from performance.contract import ESCALATION_CONDITIONS
from performance.detector import CLASSIFICATIONS
from scripts.work_origin import validate_work_item

DECISIONS = {"NO_ACTION", "BLOCKED", "ESCALATE", "AUTO_REPAIR"}
OUTCOMES = {"ADOPT", "REVERT_OR_REPLAN"}
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#@-]{0,239}$")
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{0,79}$")
_RANK = {"PERF_INFO": 0, "PERF_DEGRADATION": 1, "PERF_INCIDENT": 2, "PERF_REVIEW": 3}


class PerformanceRemediationError(ValueError):
    """Plan o evidencia de remediación fuera del contrato v1."""


def plan_remediation(
    detection: Mapping[str, Any],
    triage: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Deriva una decisión y WorkItem puro; nunca ejecuta la intervención."""
    finding = _detection(detection)
    staffing = _triage(triage, finding)
    change = _proposal(proposal, finding)
    work_item = validate_work_item(change["work_item"])

    missing_roles = sorted(set(staffing["role_hints"]) - set(work_item["required_roles"]))
    if missing_roles:
        raise PerformanceRemediationError("WorkItem no incluye todos los role_hints del triage.")

    if finding["classification"] == "PERF_INFO":
        decision, reasons = "NO_ACTION", ["finding_not_material"]
    elif finding["evidence_state"] != "CURRENT":
        decision, reasons = "BLOCKED", ["evidence_not_current"]
    elif change["workflow_action"] not in finding["allowed_actions"]:
        raise PerformanceRemediationError("workflow_action no está permitida por Performance Contract.")
    else:
        escalations = set(change["triggered_conditions"])
        if change["changes_product_semantics"]:
            escalations.add("business_semantics")
        if not change["within_authority"]:
            escalations.add("authority_missing")
        if escalations:
            decision, reasons = "ESCALATE", sorted(escalations)
        elif not change["reversible"] or not change["tests_covered"]:
            decision, reasons = "BLOCKED", ["safety_requirements_incomplete"]
        else:
            decision, reasons = "AUTO_REPAIR", []

    return {
        "version": 1,
        "decision": decision,
        "reasons": reasons,
        "project": finding["project"],
        "surface": finding["surface"],
        "metric": finding["metric"],
        "classification": finding["classification"],
        "workflow_action": change["workflow_action"],
        "change_id": change["change_id"],
        "hypothesis_ref": change["hypothesis_ref"],
        "rollback_ref": change["rollback_ref"],
        "work_item": work_item,
        "queue_required": decision in {"AUTO_REPAIR", "ESCALATE", "BLOCKED"},
        "human_gate_required": decision == "ESCALATE",
        "authority": "unchanged",
        "execute_actions": False,
    }


def evaluate_before_after(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    """Decide adopción solo con evidencia comparable y mejora demostrada."""
    old, new = _detection(before), _detection(after)
    identity = ("project", "surface", "metric")
    if any(old[field] != new[field] for field in identity):
        raise PerformanceRemediationError("before/after pertenece a identidades distintas.")
    if old["budget"] is None or new["budget"] is None or old["budget"] != new["budget"]:
        raise PerformanceRemediationError("before/after requiere el mismo budget.")
    if old["observed"]["unit"] != new["observed"]["unit"]:
        raise PerformanceRemediationError("before/after usa unidades incompatibles.")

    if old["evidence_state"] != "CURRENT" or new["evidence_state"] != "CURRENT":
        return _comparison(old, new, False, "REVERT_OR_REPLAN", ["evidence_not_current"])

    operator = old["budget"]["operator"]
    old_value, new_value = old["observed"]["value"], new["observed"]["value"]
    improved = new_value < old_value if operator == "lte" else new_value > old_value
    worse_classification = _RANK[new["classification"]] > _RANK[old["classification"]]
    decision = "ADOPT" if improved and not worse_classification else "REVERT_OR_REPLAN"
    reasons = [] if decision == "ADOPT" else [
        "classification_worsened" if worse_classification else "no_measured_improvement"
    ]
    return _comparison(old, new, improved, decision, reasons)


def _comparison(
    before: dict[str, Any],
    after: dict[str, Any],
    improved: bool,
    decision: str,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "version": 1,
        "decision": decision,
        "reasons": reasons,
        "project": before["project"],
        "surface": before["surface"],
        "metric": before["metric"],
        "operator": None if before["budget"] is None else before["budget"]["operator"],
        "before_value": before["observed"]["value"],
        "after_value": after["observed"]["value"],
        "delta": after["observed"]["value"] - before["observed"]["value"],
        "improved": improved,
        "before_evidence_ref": before["evidence_ref"],
        "after_evidence_ref": after["evidence_ref"],
        "authority": "unchanged",
        "execute_actions": False,
    }


def _detection(raw: Any) -> dict[str, Any]:
    required = {
        "project", "surface", "metric", "classification", "evidence_state",
        "observed", "budget", "evidence_ref", "allowed_actions",
        "escalation_conditions",
    }
    if not isinstance(raw, Mapping) or not required.issubset(raw):
        raise PerformanceRemediationError("resultado de detección incompleto.")
    if raw["classification"] not in CLASSIFICATIONS:
        raise PerformanceRemediationError("classification fuera de catálogo.")
    if raw["evidence_state"] not in {"CURRENT", "STALE", "INSUFFICIENT", "UNKNOWN"}:
        raise PerformanceRemediationError("evidence_state fuera de catálogo.")
    if not isinstance(raw["observed"], Mapping) or set(raw["observed"]) != {
        "value", "unit", "observed_at", "sample_count", "window_seconds"
    }:
        raise PerformanceRemediationError("observed fuera de contrato.")
    return dict(raw)


def _triage(raw: Any, finding: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(raw, Mapping)
        or raw.get("classification") != finding["classification"]
        or raw.get("authority") != "unchanged"
        or raw.get("execute_actions") is not False
        or raw.get("create_work_item") is not False
        or not isinstance(raw.get("role_hints"), list)
        or not raw["role_hints"]
    ):
        raise PerformanceRemediationError("triage incompatible con detección.")
    return dict(raw)


def _proposal(raw: Any, finding: Mapping[str, Any]) -> dict[str, Any]:
    fields = {
        "version", "workflow_action", "change_id", "hypothesis_ref", "reversible",
        "tests_covered", "within_authority", "changes_product_semantics",
        "triggered_conditions", "rollback_ref", "work_item",
    }
    if not isinstance(raw, Mapping) or set(raw) != fields or raw["version"] != 1:
        raise PerformanceRemediationError("proposal no coincide con contrato v1.")
    for name in ("reversible", "tests_covered", "within_authority", "changes_product_semantics"):
        if type(raw[name]) is not bool:
            raise PerformanceRemediationError(f"{name} debe ser booleano.")
    conditions = raw["triggered_conditions"]
    if (
        not isinstance(conditions, list)
        or len(conditions) != len(set(conditions))
        or any(item not in ESCALATION_CONDITIONS for item in conditions)
    ):
        raise PerformanceRemediationError("triggered_conditions fuera de catálogo.")
    return {
        "version": 1,
        "workflow_action": _id(raw["workflow_action"], "workflow_action"),
        "change_id": _id(raw["change_id"], "change_id"),
        "hypothesis_ref": _ref(raw["hypothesis_ref"], "hypothesis_ref"),
        "reversible": raw["reversible"],
        "tests_covered": raw["tests_covered"],
        "within_authority": raw["within_authority"],
        "changes_product_semantics": raw["changes_product_semantics"],
        "triggered_conditions": sorted(conditions),
        "rollback_ref": _ref(raw["rollback_ref"], "rollback_ref"),
        "work_item": raw["work_item"],
    }


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise PerformanceRemediationError(f"{label} inválido.")
    return value


def _ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise PerformanceRemediationError(f"{label} inválida.")
    return value
