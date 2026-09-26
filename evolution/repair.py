"""Repair plans: reversible, verifiable and never destructively autonomous."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from seguridad.puertas_humanas import GateValidationError, validate_gate


REPAIR_VERSION = 1
DECISION_EVIDENCE_VERSION = 1
MAX_STEPS = 16
_TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
_ISSUE_REF = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9]\d*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _scope_payload(
    *,
    diagnosis: Any,
    actions: Any,
    verification: Any,
    rollback: Any,
    destructive: bool,
) -> dict[str, Any]:
    if type(destructive) is not bool:
        raise RepairError("destructive debe ser boolean")
    return {
        "diagnosis": _text(diagnosis, "diagnosis"),
        "actions": _steps(actions, "actions"),
        "verification": _steps(verification, "verification"),
        "rollback": _rollback(rollback),
        "destructive": destructive,
    }


def _decision_fingerprint(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("fingerprint", None)
    return _stable_hash(unsigned)


def _validate_decision_evidence(
    value: Any,
    *,
    scope_fingerprint: str,
) -> tuple[dict[str, Any], str]:
    required = {
        "version",
        "issue_ref",
        "author_association",
        "gate",
        "selected_option",
        "status",
        "fingerprint",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RepairError("decision_evidence inválida")
    if type(value["version"]) is not int or value["version"] != DECISION_EVIDENCE_VERSION:
        raise RepairError("decision_evidence.version inválida")
    issue_ref = _text(value["issue_ref"], "decision_evidence.issue_ref", 160)
    if _ISSUE_REF.fullmatch(issue_ref) is None:
        raise RepairError("decision_evidence.issue_ref inválida")
    association = _text(
        value["author_association"],
        "decision_evidence.author_association",
        32,
    )
    if association not in _TRUSTED_ASSOCIATIONS:
        raise RepairError("decision_evidence no proviene de actor confiable")
    if value["status"] != "resolved":
        raise RepairError("decision_evidence no está resuelta")
    selected = _text(value["selected_option"], "decision_evidence.selected_option", 1)
    try:
        gate = validate_gate(value["gate"])
    except GateValidationError as exc:
        raise RepairError("decision_evidence contiene puerta inválida") from exc
    options = {item["id"]: item for item in gate["options"]}
    if selected not in options:
        raise RepairError("decision_evidence selecciona opción inexistente")
    expected_effect = f"authorize-destructive-repair:{scope_fingerprint}"
    if options[selected].get("effect") != expected_effect:
        raise RepairError("decision_evidence no autoriza este scope destructivo")

    fingerprint = value["fingerprint"]
    normalized = {
        "version": DECISION_EVIDENCE_VERSION,
        "issue_ref": issue_ref,
        "author_association": association,
        "gate": gate,
        "selected_option": selected,
        "status": "resolved",
    }
    expected_fingerprint = _stable_hash(normalized)
    if (
        not isinstance(fingerprint, str)
        or _SHA256.fullmatch(fingerprint) is None
        or fingerprint != expected_fingerprint
    ):
        raise RepairError("decision_evidence fingerprint no coincide")
    normalized["fingerprint"] = fingerprint
    decision_ref = f"owner-decision:{issue_ref}:{selected}"
    return normalized, decision_ref


def _authority(
    value: Any,
    decision_evidence: Any,
    destructive: bool,
    *,
    scope_fingerprint: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not destructive:
        if value is not None or decision_evidence is not None:
            raise RepairError(
                "human_authority/decision_evidence solo aplican a reparación destructiva"
            )
        return (
            {
                "required": "none",
                "approved": True,
                "decision_ref": None,
                "evidence_fingerprint": None,
            },
            None,
        )

    blocked = {
        "required": "human",
        "approved": False,
        "decision_ref": None,
        "evidence_fingerprint": None,
    }
    if value is None:
        return blocked, None
    if not isinstance(value, dict) or set(value) != {"approved", "decision_ref"}:
        raise RepairError("human_authority inválida")
    if value["approved"] is not True:
        return blocked, None
    requested_ref = _text(
        value["decision_ref"],
        "human_authority.decision_ref",
        200,
    )
    if decision_evidence is None:
        return blocked, None
    try:
        evidence, decision_ref = _validate_decision_evidence(
            decision_evidence,
            scope_fingerprint=scope_fingerprint,
        )
    except RepairError:
        return blocked, None
    if requested_ref != decision_ref:
        return blocked, evidence
    return (
        {
            "required": "human",
            "approved": True,
            "decision_ref": decision_ref,
            "evidence_fingerprint": evidence["fingerprint"],
        },
        evidence,
    )


def compile_repair_plan(
    *,
    diagnosis: Any,
    actions: Any,
    verification: Any,
    rollback: Any,
    destructive: bool = False,
    human_authority: Any = None,
    decision_evidence: Any = None,
) -> dict[str, Any]:
    """Compile a non-executing repair plan with source-bound human authority."""
    scope = _scope_payload(
        diagnosis=diagnosis,
        actions=actions,
        verification=verification,
        rollback=rollback,
        destructive=destructive,
    )
    scope_fingerprint = _stable_hash(scope)
    authority, normalized_evidence = _authority(
        human_authority,
        decision_evidence,
        destructive,
        scope_fingerprint=scope_fingerprint,
    )
    plan = {
        "version": REPAIR_VERSION,
        **scope,
        "scope_fingerprint": scope_fingerprint,
        "authority": authority,
        "authority_evidence": normalized_evidence,
        "automatic_execution_allowed": False,
        "authorized_execution_ready": (
            not destructive or authority["approved"] is True
        ),
        "execution": "not-performed",
    }
    plan["fingerprint"] = _stable_hash(plan)
    return plan


def validate_repair_plan(plan: Any) -> dict[str, Any]:
    """Revalidate scope and durable human evidence without weakening authority."""
    expected = {
        "version",
        "diagnosis",
        "actions",
        "verification",
        "rollback",
        "destructive",
        "scope_fingerprint",
        "authority",
        "authority_evidence",
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

    scope = _scope_payload(
        diagnosis=plan["diagnosis"],
        actions=plan["actions"],
        verification=plan["verification"],
        rollback=plan["rollback"],
        destructive=plan["destructive"],
    )
    scope_fingerprint = _stable_hash(scope)
    if plan["scope_fingerprint"] != scope_fingerprint:
        raise RepairError("repair scope fingerprint no coincide")

    authority = plan["authority"]
    authority_input = None
    if plan["destructive"] and isinstance(authority, dict):
        if authority.get("approved") is True:
            authority_input = {
                "approved": True,
                "decision_ref": authority.get("decision_ref"),
            }
    expected_authority, expected_evidence = _authority(
        authority_input,
        plan["authority_evidence"],
        plan["destructive"],
        scope_fingerprint=scope_fingerprint,
    )
    if authority != expected_authority:
        raise RepairError("estado de autoridad inconsistente")
    if plan["authority_evidence"] != expected_evidence:
        raise RepairError("evidencia de autoridad inconsistente")

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
