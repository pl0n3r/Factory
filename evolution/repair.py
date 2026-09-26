"""Repair plans: reversible, verifiable and never destructively autonomous."""
from __future__ import annotations

import hashlib
import json
from typing import Any


REPAIR_VERSION = 1
MAX_STEPS = 16


class RepairError(ValueError):
    """Invalid or unsafe repair plan."""


def _stable_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _text(value: Any, field: str, max_len: int = 500) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > max_len
        or "\n" in value
        or "\r" in value
    ):
        raise RepairError(f"{field} debe ser texto de una línea")
    return value.strip()


def _steps(value: Any, field: str) -> list[str]:
    if (
        not isinstance(value, (list, tuple))
        or not 1 <= len(value) <= MAX_STEPS
    ):
        raise RepairError(f"{field} debe contener 1..{MAX_STEPS} pasos")
    return [_text(item, field, 300) for item in value]


def _rollback(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"strategy", "steps"}:
        raise RepairError("rollback debe declarar strategy y steps")
    strategy = value["strategy"]
    if strategy not in {"revert", "restore_baseline"}:
        raise RepairError("rollback.strategy inválida")
    return {
        "strategy": strategy,
        "steps": _steps(value["steps"], "rollback.steps"),
    }


def _authority(value: Any, destructive: bool) -> dict[str, Any]:
    if not destructive:
        if value is not None:
            raise RepairError("human_authority solo aplica a reparación destructiva")
        return {
            "required": "none",
            "approved": True,
            "decision_ref": None,
        }

    if value is None:
        return {
            "required": "human",
            "approved": False,
            "decision_ref": None,
        }
    if not isinstance(value, dict) or set(value) != {"approved", "decision_ref"}:
        raise RepairError("human_authority inválida")
    if value["approved"] is not True:
        raise RepairError("human_authority debe contener aprobación explícita")
    decision_ref = _text(value["decision_ref"], "human_authority.decision_ref", 160)
    return {
        "required": "human",
        "approved": True,
        "decision_ref": decision_ref,
    }


def compile_repair_plan(
    *,
    diagnosis: Any,
    actions: Any,
    verification: Any,
    rollback: Any,
    destructive: bool = False,
    human_authority: Any = None,
) -> dict[str, Any]:
    """Compile a non-executing repair plan with verification and rollback."""
    if type(destructive) is not bool:
        raise RepairError("destructive debe ser boolean")
    plan = {
        "version": REPAIR_VERSION,
        "diagnosis": _text(diagnosis, "diagnosis"),
        "actions": _steps(actions, "actions"),
        "verification": _steps(verification, "verification"),
        "rollback": _rollback(rollback),
        "destructive": destructive,
        "authority": _authority(human_authority, destructive),
        "automatic_execution_allowed": False,
        "authorized_execution_ready": (
            not destructive
            or (
                isinstance(human_authority, dict)
                and human_authority.get("approved") is True
            )
        ),
        "execution": "not-performed",
    }
    plan["fingerprint"] = _stable_hash(plan)
    return plan


def validate_repair_plan(plan: Any) -> dict[str, Any]:
    """Validate a previously compiled plan without weakening its authority."""
    expected = {
        "version",
        "diagnosis",
        "actions",
        "verification",
        "rollback",
        "destructive",
        "authority",
        "automatic_execution_allowed",
        "authorized_execution_ready",
        "execution",
        "fingerprint",
    }
    if not isinstance(plan, dict) or set(plan) != expected:
        raise RepairError("repair plan incompleto o con campos extra")
    fingerprint = plan["fingerprint"]
    unsigned = dict(plan)
    unsigned.pop("fingerprint")
    if not isinstance(fingerprint, str) or fingerprint != _stable_hash(unsigned):
        raise RepairError("repair plan fingerprint no coincide")
    if type(plan["version"]) is not int or plan["version"] != REPAIR_VERSION:
        raise RepairError("repair plan version inválida")
    _text(plan["diagnosis"], "diagnosis")
    _steps(plan["actions"], "actions")
    _steps(plan["verification"], "verification")
    _rollback(plan["rollback"])
    if type(plan["destructive"]) is not bool:
        raise RepairError("destructive debe ser boolean")

    authority = plan["authority"]
    authority_input = None
    if plan["destructive"]:
        if not isinstance(authority, dict):
            raise RepairError("reparación destructiva exige autoridad humana")
        if authority.get("approved") is True:
            authority_input = {
                "approved": True,
                "decision_ref": authority.get("decision_ref"),
            }
    expected_authority = _authority(authority_input, plan["destructive"])
    if authority != expected_authority:
        raise RepairError("estado de autoridad inconsistente")

    if plan["automatic_execution_allowed"] is not False:
        raise RepairError("ejecución automática prohibida")
    if plan["execution"] != "not-performed":
        raise RepairError("Repair Engine no ejecuta acciones")
    expected_ready = (
        not plan["destructive"]
        or expected_authority["approved"] is True
    )
    if plan["authorized_execution_ready"] is not expected_ready:
        raise RepairError("estado de autoridad destructiva inconsistente")
    return plan
