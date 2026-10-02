#!/usr/bin/env python3
"""Guardas puras del modo desatendido seguro, sin I/O ni efectos."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re

from scripts.adaptive_fencing import FencingDecision

RISKS = {"low", "medium", "high", "UNKNOWN"}
BREAKER_SCOPES = {"agent", "repo"}
SENSITIVE = ("go_live", "spend", "irreversible", "real_data")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class GuardValidationError(ValueError):
    pass


@dataclass(frozen=True)
class GuardDecision:
    action: str
    authority: str
    pause_allowed: bool
    reasons: tuple[str, ...]
    evidence_fingerprint: str


def _fp(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _exact(value: object, keys: set[str], name: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GuardValidationError(f"invalid_{name}_shape")
    return value


def _number(value: object, name: str, *, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuardValidationError(f"invalid_{name}")
    if not math.isfinite(float(value)) or value < 0 or (integer and not isinstance(value, int)):
        raise GuardValidationError(f"invalid_{name}")
    return value


def _tri(value: object, name: str) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise GuardValidationError(f"invalid_{name}")


def _positive_int(value: object, name: str) -> int:
    parsed = _number(value, name, integer=True)
    if parsed <= 0:
        raise GuardValidationError(f"invalid_{name}")
    return int(parsed)


def _normalize(config: object, evidence: object, metrics: object):
    cfg = _exact(config, {"global_pause", "breakers", "ceilings"}, "config")
    if not isinstance(cfg["global_pause"], bool):
        raise GuardValidationError("invalid_global_pause")
    ceilings = _exact(cfg["ceilings"], {"usage", "cost", "parallelism"}, "ceilings")
    ceilings = {
        "usage": _number(ceilings["usage"], "usage_limit"),
        "cost": _number(ceilings["cost"], "cost_limit"),
        "parallelism": _number(ceilings["parallelism"], "parallelism_limit", integer=True),
    }

    ev = _exact(
        evidence,
        {"breakers", "risk", "second_pass", "sensitive", "production_change", "backup_required", "backup_verified"},
        "evidence",
    )
    if ev["risk"] not in RISKS:
        raise GuardValidationError("invalid_risk")
    sensitive = _exact(ev["sensitive"], set(SENSITIVE), "sensitive")
    if any(not isinstance(sensitive[key], bool) for key in SENSITIVE):
        raise GuardValidationError("invalid_sensitive_flag")
    if not isinstance(ev["production_change"], bool) or not isinstance(ev["backup_required"], bool):
        raise GuardValidationError("invalid_production_backup_flags")

    breaker_cfg, breaker_ev = cfg["breakers"], ev["breakers"]
    if not isinstance(breaker_cfg, dict) or not breaker_cfg or not isinstance(breaker_ev, dict):
        raise GuardValidationError("invalid_breakers")
    if set(breaker_cfg) != set(breaker_ev):
        raise GuardValidationError("breaker_evidence_mismatch")
    clean_cfg, clean_ev = {}, {}
    for name in sorted(breaker_cfg):
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
            raise GuardValidationError("invalid_breaker_identifier")
        configured = _exact(
            breaker_cfg[name],
            {"scope", "threshold"},
            "breaker_config",
        )
        scope = configured["scope"]
        if scope not in BREAKER_SCOPES:
            raise GuardValidationError("invalid_breaker_scope")
        threshold = _positive_int(
            configured["threshold"],
            "breaker_threshold",
        )
        observed = _exact(
            breaker_ev[name],
            {"consecutive_failures", "fresh", "consistent"},
            "breaker_evidence",
        )
        clean_cfg[name] = {"scope": scope, "threshold": threshold}
        clean_ev[name] = {
            "consecutive_failures": _number(
                observed["consecutive_failures"],
                "breaker_consecutive_failures",
                integer=True,
            ),
            "fresh": _tri(observed["fresh"], "breaker_fresh"),
            "consistent": _tri(observed["consistent"], "breaker_consistent"),
        }

    measured = _exact(metrics, {"usage", "cost", "parallelism"}, "measurements")
    measured = {
        "usage": _number(measured["usage"], "usage"),
        "cost": _number(measured["cost"], "cost"),
        "parallelism": _number(measured["parallelism"], "parallelism", integer=True),
    }
    return (
        {"global_pause": cfg["global_pause"], "breakers": clean_cfg, "ceilings": ceilings},
        {
            "breakers": clean_ev,
            "risk": ev["risk"],
            "second_pass": _tri(ev["second_pass"], "second_pass"),
            "sensitive": dict(sensitive),
            "production_change": ev["production_change"],
            "backup_required": ev["backup_required"],
            "backup_verified": _tri(ev["backup_verified"], "backup_verified"),
        },
        measured,
    )


def _decision(action: str, pause: bool, reasons: list[str], payload: object) -> GuardDecision:
    return GuardDecision(action, "unchanged", pause, tuple(sorted(set(reasons))), _fp(payload))


def _blocked(reason: str) -> GuardDecision:
    return _decision("BLOCKED", False, [reason], {"invalid": reason})


def _pause(fencing: FencingDecision, reason: str, payload: object) -> GuardDecision:
    if fencing.pause_allowed:
        return _decision("PAUSE", True, [reason], payload)
    return _decision("BLOCKED", False, [reason, "adaptive_pause_not_allowed"], payload)


def evaluate_unattended_guards(
    fencing: FencingDecision, config: object, evidence: object, measurements: object
) -> GuardDecision:
    """Compone fencing + guardas explícitas sin ampliar autoridad."""
    if not isinstance(fencing, FencingDecision):
        return _blocked("invalid_fencing_decision")
    if fencing.action not in {"keep", "replan", "fail_closed"}:
        return _blocked("invalid_fencing_action")
    if fencing.action == "fail_closed":
        return _blocked("adaptive_fencing_fail_closed")
    if fencing.action == "replan" and not fencing.pause_allowed:
        return _blocked("adaptive_pause_not_allowed")
    try:
        cfg, ev, metrics = _normalize(config, evidence, measurements)
    except GuardValidationError as exc:
        return _blocked(str(exc))

    payload = {
        "fencing": {
            "action": fencing.action,
            "pause_allowed": fencing.pause_allowed,
            "generation": fencing.generation,
            "attempt": fencing.attempt,
            "snapshot": fencing.snapshot_fingerprint,
            "event": fencing.event_fingerprint,
        },
        "config": cfg,
        "evidence": ev,
        "measurements": metrics,
    }
    if cfg["global_pause"]:
        return _pause(fencing, "global_pause_active", payload)

    for name in sorted(cfg["breakers"]):
        configured, observed = cfg["breakers"][name], ev["breakers"][name]
        if observed["fresh"] is not True:
            return _blocked("breaker_evidence_not_fresh")
        if observed["consistent"] is not True:
            return _blocked("breaker_evidence_not_consistent")
        state = (
            "open"
            if observed["consecutive_failures"] >= configured["threshold"]
            else "closed"
        )
        if state == "open":
            return _pause(fencing, "circuit_breaker_open", payload)

    for field in ("usage", "cost", "parallelism"):
        if metrics[field] > cfg["ceilings"][field]:
            return _pause(fencing, f"{field}_ceiling_exceeded", payload)

    if ev["risk"] == "UNKNOWN":
        return _blocked("risk_unknown")
    if ev["risk"] == "high" and ev["second_pass"] is not True:
        return _blocked("high_risk_second_pass_required")
    if any(ev["sensitive"][key] for key in SENSITIVE):
        return _blocked("sensitive_authority_not_granted")
    if ev["production_change"] and ev["backup_required"] and ev["backup_verified"] is not True:
        return _blocked("required_backup_not_verified")

    return _decision("ALLOW", False, ["guards_satisfied"], payload)
