#!/usr/bin/env python3
"""Guardas puras del modo desatendido seguro.

Este módulo no ejecuta efectos. Solo compone una ``FencingDecision`` ya calculada
por ``adaptive_fencing`` con configuración y evidencia explícitas para producir
una decisión determinista ALLOW, PAUSE o BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Mapping

from scripts.adaptive_fencing import FencingDecision

ACTIONS = frozenset({"ALLOW", "PAUSE", "BLOCKED"})
RISK_LEVELS = frozenset({"low", "medium", "high", "UNKNOWN"})
BREAKER_STATES = frozenset({"open", "closed", "UNKNOWN"})
SENSITIVE_KEYS = frozenset({"go_live", "spend", "irreversible", "real_data"})
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class GuardValidationError(ValueError):
    """Entrada inválida para el contrato fail-closed de guardas."""


@dataclass(frozen=True)
class GuardDecision:
    """Resultado puro y sanitizado de las guardas desatendidas."""

    action: str
    authority: str
    pause_allowed: bool
    reasons: tuple[str, ...]
    evidence_fingerprint: str


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _number(value: object, field: str, *, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuardValidationError(f"invalid_{field}")
    if not math.isfinite(float(value)) or value < 0:
        raise GuardValidationError(f"invalid_{field}")
    if integer and not isinstance(value, int):
        raise GuardValidationError(f"invalid_{field}")
    return value


def _tristate(value: object, field: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise GuardValidationError(f"invalid_{field}")


def _closed_mapping(payload: object, *, fields: set[str], name: str) -> Mapping[str, object]:
    if not isinstance(payload, dict):
        raise GuardValidationError(f"invalid_{name}")
    unknown = set(payload) - fields
    missing = fields - set(payload)
    if unknown or missing:
        raise GuardValidationError(f"invalid_{name}_shape")
    return payload


def _normalize_breakers(config: object, evidence: object) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(config, dict) or not config:
        raise GuardValidationError("invalid_breakers")
    if not isinstance(evidence, dict):
        raise GuardValidationError("invalid_breaker_evidence")
    if set(config) != set(evidence):
        raise GuardValidationError("breaker_evidence_mismatch")

    normalized_config: dict[str, object] = {}
    normalized_evidence: dict[str, object] = {}
    for name in sorted(config):
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise GuardValidationError("invalid_breaker_identifier")
        configured = _closed_mapping(
            config[name],
            fields={"state"},
            name="breaker_config",
        )
        state = configured["state"]
        if state not in BREAKER_STATES:
            raise GuardValidationError("invalid_breaker_state")
        observed = _closed_mapping(
            evidence[name],
            fields={"condition", "fresh", "consistent"},
            name="breaker_evidence",
        )
        normalized_config[name] = {"state": state}
        normalized_evidence[name] = {
            "condition": _tristate(observed["condition"], "breaker_condition"),
            "fresh": _tristate(observed["fresh"], "breaker_fresh"),
            "consistent": _tristate(observed["consistent"], "breaker_consistent"),
        }
    return normalized_config, normalized_evidence


def _normalize_inputs(
    config: object,
    evidence: object,
    measurements: object,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    config_map = _closed_mapping(
        config,
        fields={"global_pause", "breakers", "ceilings"},
        name="config",
    )
    if not isinstance(config_map["global_pause"], bool):
        raise GuardValidationError("invalid_global_pause")

    ceilings = _closed_mapping(
        config_map["ceilings"],
        fields={"usage", "cost", "parallelism"},
        name="ceilings",
    )
    normalized_ceilings = {
        "usage": _number(ceilings["usage"], "usage_limit"),
        "cost": _number(ceilings["cost"], "cost_limit"),
        "parallelism": _number(
            ceilings["parallelism"], "parallelism_limit", integer=True
        ),
    }

    evidence_map = _closed_mapping(
        evidence,
        fields={
            "breakers",
            "risk",
            "second_pass",
            "sensitive",
            "production_change",
            "backup_required",
            "backup_verified",
        },
        name="evidence",
    )
    risk = evidence_map["risk"]
    if risk not in RISK_LEVELS:
        raise GuardValidationError("invalid_risk")
    sensitive = _closed_mapping(
        evidence_map["sensitive"],
        fields=set(SENSITIVE_KEYS),
        name="sensitive",
    )
    normalized_sensitive: dict[str, bool] = {}
    for key in sorted(SENSITIVE_KEYS):
        value = sensitive[key]
        if not isinstance(value, bool):
            raise GuardValidationError("invalid_sensitive_flag")
        normalized_sensitive[key] = value

    for field in ("production_change", "backup_required"):
        if not isinstance(evidence_map[field], bool):
            raise GuardValidationError(f"invalid_{field}")

    breaker_config, breaker_evidence = _normalize_breakers(
        config_map["breakers"], evidence_map["breakers"]
    )
    normalized_evidence = {
        "breakers": breaker_evidence,
        "risk": risk,
        "second_pass": _tristate(evidence_map["second_pass"], "second_pass"),
        "sensitive": normalized_sensitive,
        "production_change": evidence_map["production_change"],
        "backup_required": evidence_map["backup_required"],
        "backup_verified": _tristate(evidence_map["backup_verified"], "backup_verified"),
    }

    measurements_map = _closed_mapping(
        measurements,
        fields={"usage", "cost", "parallelism"},
        name="measurements",
    )
    normalized_measurements = {
        "usage": _number(measurements_map["usage"], "usage"),
        "cost": _number(measurements_map["cost"], "cost"),
        "parallelism": _number(
            measurements_map["parallelism"], "parallelism", integer=True
        ),
    }
    normalized_config = {
        "global_pause": config_map["global_pause"],
        "breakers": breaker_config,
        "ceilings": normalized_ceilings,
    }
    return normalized_config, normalized_evidence, normalized_measurements


def _decision(
    action: str,
    *,
    pause_allowed: bool,
    reasons: list[str] | tuple[str, ...],
    fingerprint_payload: object,
) -> GuardDecision:
    if action not in ACTIONS:
        raise GuardValidationError("invalid_guard_action")
    return GuardDecision(
        action=action,
        authority="unchanged",
        pause_allowed=pause_allowed,
        reasons=tuple(sorted(set(reasons))),
        evidence_fingerprint=_fingerprint(fingerprint_payload),
    )


def _blocked(reason: str) -> GuardDecision:
    """Falla cerrado sin reflejar payloads inválidos en la salida."""
    return _decision(
        "BLOCKED",
        pause_allowed=False,
        reasons=[reason],
        fingerprint_payload={"invalid": reason},
    )


def _pause_or_block(fencing: FencingDecision, reason: str, payload: object) -> GuardDecision:
    if fencing.pause_allowed:
        return _decision(
            "PAUSE",
            pause_allowed=True,
            reasons=[reason],
            fingerprint_payload=payload,
        )
    return _decision(
        "BLOCKED",
        pause_allowed=False,
        reasons=[reason, "adaptive_pause_not_allowed"],
        fingerprint_payload=payload,
    )


def evaluate_unattended_guards(
    fencing: FencingDecision,
    config: object,
    evidence: object,
    measurements: object,
) -> GuardDecision:
    """Evalúa guardas sin I/O ni efectos y conserva la autoridad del fencing."""
    if not isinstance(fencing, FencingDecision):
        return _blocked("invalid_fencing_decision")
    if fencing.action == "fail_closed":
        return _blocked("adaptive_fencing_fail_closed")

    try:
        checked_config, checked_evidence, checked_measurements = _normalize_inputs(
            config, evidence, measurements
        )
    except GuardValidationError as exc:
        return _blocked(str(exc))

    payload = {
        "fencing": {
            "action": fencing.action,
            "pause_allowed": fencing.pause_allowed,
            "generation": fencing.generation,
            "attempt": fencing.attempt,
            "snapshot_fingerprint": fencing.snapshot_fingerprint,
            "event_fingerprint": fencing.event_fingerprint,
        },
        "config": checked_config,
        "evidence": checked_evidence,
        "measurements": checked_measurements,
    }

    if checked_config["global_pause"]:
        return _pause_or_block(fencing, "global_pause_active", payload)

    breaker_config = checked_config["breakers"]
    breaker_evidence = checked_evidence["breakers"]
    assert isinstance(breaker_config, dict)
    assert isinstance(breaker_evidence, dict)
    for name in sorted(breaker_config):
        state = breaker_config[name]["state"]
        observed = breaker_evidence[name]
        if state == "UNKNOWN":
            return _blocked("breaker_state_unknown")
        if observed["fresh"] is not True:
            return _blocked("breaker_evidence_not_fresh")
        if observed["consistent"] is not True:
            return _blocked("breaker_evidence_not_consistent")
        condition = observed["condition"]
        if condition is None:
            return _blocked("breaker_condition_unknown")
        if state == "closed" and condition is True:
            return _blocked("breaker_state_contradictory")
        if state == "open" and condition is not True:
            return _blocked("breaker_state_contradictory")
        if state == "open":
            return _pause_or_block(fencing, "circuit_breaker_open", payload)

    ceilings = checked_config["ceilings"]
    for field in ("usage", "cost", "parallelism"):
        if checked_measurements[field] > ceilings[field]:
            return _pause_or_block(fencing, f"{field}_ceiling_exceeded", payload)

    if checked_evidence["risk"] == "UNKNOWN":
        return _blocked("risk_unknown")
    if checked_evidence["risk"] == "high" and checked_evidence["second_pass"] is not True:
        return _blocked("high_risk_second_pass_required")

    sensitive = checked_evidence["sensitive"]
    if any(sensitive[key] for key in SENSITIVE_KEYS):
        return _blocked("sensitive_authority_not_granted")

    if checked_evidence["production_change"] and checked_evidence["backup_required"]:
        if checked_evidence["backup_verified"] is not True:
            return _blocked("required_backup_not_verified")

    return _decision(
        "ALLOW",
        pause_allowed=False,
        reasons=["guards_satisfied"],
        fingerprint_payload=payload,
    )
