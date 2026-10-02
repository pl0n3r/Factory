#!/usr/bin/env python3
"""Watchdog puro del modo desatendido seguro: evidencia, STATE y resumen diario."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re

from scripts.presence_contract import PresenceValidationError, classify_presence
from scripts.unattended_guards import GuardDecision

CONFIG_FIELDS = frozenset({
    "ready_without_dispatch_minutes",
    "reservation_stale_minutes",
    "state_stale_minutes",
})
EVIDENCE_FIELDS = frozenset({
    "now",
    "presence",
    "work_ready",
    "ready_since",
    "next_dispatch_planned",
    "reservation",
    "state",
    "incidents",
    "already_alerted_fingerprints",
    "active_fronts",
    "human_gates",
    "integrated",
    "reverted",
    "next_actions",
})
STATE_FIELDS = frozenset({
    "work_identity",
    "repository",
    "branch",
    "head_sha",
    "reservation_id",
    "risk",
    "severity",
    "evidence",
    "last_state",
    "next_action",
    "blockers",
    "updated_at",
})
RESERVATION_FIELDS = frozenset({"active", "work_identity", "updated_at", "freshness"})
INCIDENT_FIELDS = frozenset({"incident_id", "severity", "source", "updated_at", "freshness"})
RISKS = frozenset({"low", "medium", "high", "UNKNOWN"})
SEVERITIES = frozenset({"S1", "S2", "S3", "UNKNOWN"})
FRESHNESS = frozenset({"fresh", "stale", "unknown"})
SENSITIVE_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "credential",
    "private_key",
    "authorization",
    "transcript",
    "conversation",
)
SENSITIVE_VALUE_FRAGMENTS = (
    "password=",
    "passwd=",
    "secret=",
    "token=",
    "cookie=",
    "authorization:",
    "private_key",
)
EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


class WatchdogValidationError(ValueError):
    """Entrada inválida o insegura para 4C."""


@dataclass(frozen=True)
class WatchdogIncident:
    code: str
    severity: str
    fingerprint: str
    repeated: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DailySummary:
    active_fronts: tuple[str, ...]
    state_freshness: str
    incidents: tuple[str, ...]
    blockers: tuple[str, ...]
    human_gates: tuple[str, ...]
    integrated: tuple[str, ...]
    reverted: tuple[str, ...]
    next_actions: tuple[str, ...]


@dataclass(frozen=True)
class WatchdogDecision:
    action: str
    authority: str
    incidents: tuple[WatchdogIncident, ...]
    new_alert_fingerprints: tuple[str, ...]
    interrupt_owner: bool
    daily_summary: DailySummary
    evidence_fingerprint: str


def _fingerprint(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _reject_keys(mapping: dict[str, object], allowed: frozenset[str]) -> None:
    for key in mapping:
        if not isinstance(key, str):
            raise WatchdogValidationError("invalid_field_name")
        lowered = key.lower()
        if any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS):
            raise WatchdogValidationError(f"sensitive_field:{key}")
        if key not in allowed:
            raise WatchdogValidationError(f"unknown_field:{key}")


def _safe_text(value: object, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise WatchdogValidationError(f"invalid_{field}")
    text = value.strip()
    lowered = text.lower()
    if len(text) > 512:
        raise WatchdogValidationError(f"invalid_{field}")
    if any(fragment in lowered for fragment in SENSITIVE_VALUE_FRAGMENTS):
        raise WatchdogValidationError(f"sensitive_{field}")
    if EMAIL_RE.search(text):
        raise WatchdogValidationError(f"pii_{field}")
    return text


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise WatchdogValidationError(f"invalid_{field}")
    items = tuple(_safe_text(item, field) for item in value)
    if len(items) != len(set(items)):
        raise WatchdogValidationError(f"duplicate_{field}")
    return tuple(sorted(items))


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise WatchdogValidationError(f"invalid_{field}")
    return value


def _timestamp(value: object, field: str) -> tuple[str, datetime]:
    text = _safe_text(value, field)
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise WatchdogValidationError(f"invalid_{field}") from exc
    if parsed.tzinfo is None:
        raise WatchdogValidationError(f"invalid_{field}")
    return text, parsed


def _age_minutes(now: datetime, then: datetime, field: str) -> float:
    seconds = (now - then).total_seconds()
    if seconds < 0:
        raise WatchdogValidationError(f"future_{field}")
    return seconds / 60.0


def _normalize_config(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise WatchdogValidationError("invalid_config")
    _reject_keys(value, CONFIG_FIELDS)
    if set(value) != CONFIG_FIELDS:
        raise WatchdogValidationError("invalid_config_shape")
    return {field: _positive_int(value[field], field) for field in CONFIG_FIELDS}


def validate_state(
    payload: object,
    *,
    now: datetime,
    stale_after_minutes: int,
) -> dict[str, object]:
    """Valida STATE v4A, rechaza evidencia sensible y deriva freshness por edad."""
    if not isinstance(payload, dict):
        raise WatchdogValidationError("invalid_state")
    _reject_keys(payload, STATE_FIELDS)
    if set(payload) != STATE_FIELDS:
        raise WatchdogValidationError("invalid_state_shape")

    repository = _safe_text(payload["repository"], "repository")
    if not REPO_RE.fullmatch(repository):
        raise WatchdogValidationError("invalid_repository")
    head_sha = _safe_text(payload["head_sha"], "head_sha", nullable=True)
    if head_sha is not None and not SHA_RE.fullmatch(head_sha):
        raise WatchdogValidationError("invalid_head_sha")
    risk = _safe_text(payload["risk"], "risk")
    severity = _safe_text(payload["severity"], "severity")
    if risk not in RISKS:
        raise WatchdogValidationError("invalid_risk")
    if severity not in SEVERITIES:
        raise WatchdogValidationError("invalid_severity")
    updated_at, updated_dt = _timestamp(payload["updated_at"], "state_updated_at")
    age = _age_minutes(now, updated_dt, "state_updated_at")

    return {
        "work_identity": _safe_text(payload["work_identity"], "work_identity"),
        "repository": repository,
        "branch": _safe_text(payload["branch"], "branch", nullable=True),
        "head_sha": head_sha,
        "reservation_id": _safe_text(payload["reservation_id"], "reservation_id", nullable=True),
        "risk": risk,
        "severity": severity,
        "evidence": _string_list(payload["evidence"], "state_evidence"),
        "last_state": _safe_text(payload["last_state"], "last_state"),
        "next_action": _safe_text(payload["next_action"], "next_action"),
        "blockers": _string_list(payload["blockers"], "state_blockers"),
        "updated_at": updated_at,
        "freshness": "stale" if age >= stale_after_minutes else "fresh",
    }


def _normalize_reservation(
    payload: object,
    *,
    now: datetime,
    stale_after_minutes: int,
    state_work_identity: str,
) -> dict[str, object] | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise WatchdogValidationError("invalid_reservation")
    _reject_keys(payload, RESERVATION_FIELDS)
    if set(payload) != RESERVATION_FIELDS:
        raise WatchdogValidationError("invalid_reservation_shape")
    if not isinstance(payload["active"], bool):
        raise WatchdogValidationError("invalid_reservation_active")
    freshness = _safe_text(payload["freshness"], "reservation_freshness")
    if freshness not in FRESHNESS:
        raise WatchdogValidationError("invalid_reservation_freshness")
    work_identity = _safe_text(payload["work_identity"], "reservation_work_identity")
    if payload["active"] and work_identity != state_work_identity:
        raise WatchdogValidationError("reservation_state_identity_mismatch")
    updated_at, updated_dt = _timestamp(payload["updated_at"], "reservation_updated_at")
    age = _age_minutes(now, updated_dt, "reservation_updated_at")
    return {
        "active": payload["active"],
        "work_identity": work_identity,
        "updated_at": updated_at,
        "freshness": freshness,
        "age_minutes": age,
        "stale_after_minutes": stale_after_minutes,
    }


def _normalize_reported_incidents(value: object, *, now: datetime) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise WatchdogValidationError("invalid_incidents")
    normalized: list[dict[str, object]] = []
    ids: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise WatchdogValidationError("invalid_incident")
        _reject_keys(raw, INCIDENT_FIELDS)
        if set(raw) != INCIDENT_FIELDS:
            raise WatchdogValidationError("invalid_incident_shape")
        incident_id = _safe_text(raw["incident_id"], "incident_id")
        if incident_id in ids:
            raise WatchdogValidationError("duplicate_incident_id")
        ids.add(incident_id)
        severity = _safe_text(raw["severity"], "incident_severity")
        freshness = _safe_text(raw["freshness"], "incident_freshness")
        if severity not in SEVERITIES:
            raise WatchdogValidationError("invalid_incident_severity")
        if freshness not in FRESHNESS:
            raise WatchdogValidationError("invalid_incident_freshness")
        updated_at, updated_dt = _timestamp(raw["updated_at"], "incident_updated_at")
        _age_minutes(now, updated_dt, "incident_updated_at")
        normalized.append({
            "incident_id": incident_id,
            "severity": severity,
            "source": _safe_text(raw["source"], "incident_source"),
            "updated_at": updated_at,
            "freshness": freshness,
        })
    return tuple(sorted(normalized, key=lambda item: str(item["incident_id"])))


def _incident(
    code: str,
    severity: str,
    reasons: tuple[str, ...],
    material: object,
    already_alerted: frozenset[str],
) -> WatchdogIncident:
    fingerprint = _fingerprint({"code": code, "severity": severity, "material": material})
    return WatchdogIncident(
        code=code,
        severity=severity,
        fingerprint=fingerprint,
        repeated=fingerprint in already_alerted,
        reasons=tuple(sorted(reasons)),
    )


def _empty_summary(reason: str) -> DailySummary:
    return DailySummary((), "unknown", (f"UNKNOWN:{reason}",), (reason,), (), (), (), ())


def _blocked(reason: str, guard: GuardDecision | None = None) -> WatchdogDecision:
    incident = _incident(reason, "UNKNOWN", (reason,), {"reason": reason}, frozenset())
    return WatchdogDecision(
        action="BLOCKED",
        authority="unchanged",
        incidents=(incident,),
        new_alert_fingerprints=(incident.fingerprint,),
        interrupt_owner=False,
        daily_summary=_empty_summary(reason),
        evidence_fingerprint=_fingerprint({"invalid": reason, "guard": None if guard is None else guard.action}),
    )


def evaluate_unattended_watchdog(
    guard: GuardDecision,
    config: object,
    evidence: object,
) -> WatchdogDecision:
    """Evalúa actividad/STATE y produce evidencia determinista sin I/O."""
    if not isinstance(guard, GuardDecision):
        return _blocked("invalid_guard_decision")
    if guard.authority != "unchanged" or guard.action not in {"ALLOW", "PAUSE", "BLOCKED"}:
        return _blocked("invalid_guard_contract", guard)
    if not isinstance(evidence, dict):
        return _blocked("invalid_evidence", guard)

    try:
        cfg = _normalize_config(config)
        _reject_keys(evidence, EVIDENCE_FIELDS)
        if set(evidence) != EVIDENCE_FIELDS:
            raise WatchdogValidationError("invalid_evidence_shape")
        now_text, now_dt = _timestamp(evidence["now"], "now")
        presence_payload = evidence["presence"]
        if not isinstance(presence_payload, dict):
            raise WatchdogValidationError("invalid_presence")
        presence = classify_presence(presence_payload)

        if not isinstance(evidence["work_ready"], bool):
            raise WatchdogValidationError("invalid_work_ready")
        if not isinstance(evidence["next_dispatch_planned"], bool):
            raise WatchdogValidationError("invalid_next_dispatch_planned")

        state = validate_state(
            evidence["state"],
            now=now_dt,
            stale_after_minutes=cfg["state_stale_minutes"],
        )
        reservation = _normalize_reservation(
            evidence["reservation"],
            now=now_dt,
            stale_after_minutes=cfg["reservation_stale_minutes"],
            state_work_identity=str(state["work_identity"]),
        )
        reported_incidents = _normalize_reported_incidents(evidence["incidents"], now=now_dt)
        active_fronts = _string_list(evidence["active_fronts"], "active_fronts")
        human_gates = _string_list(evidence["human_gates"], "human_gates")
        integrated = _string_list(evidence["integrated"], "integrated")
        reverted = _string_list(evidence["reverted"], "reverted")
        next_actions = _string_list(evidence["next_actions"], "next_actions")

        alerted_raw = evidence["already_alerted_fingerprints"]
        if not isinstance(alerted_raw, list):
            raise WatchdogValidationError("invalid_already_alerted_fingerprints")
        if any(not isinstance(item, str) or not FINGERPRINT_RE.fullmatch(item) for item in alerted_raw):
            raise WatchdogValidationError("invalid_alert_fingerprint")
        already_alerted = frozenset(alerted_raw)

        ready_since = evidence["ready_since"]
        ready_since_text: str | None = None
        ready_age: float | None = None
        if ready_since is not None:
            ready_since_text, ready_since_dt = _timestamp(ready_since, "ready_since")
            ready_age = _age_minutes(now_dt, ready_since_dt, "ready_since")
        if evidence["work_ready"] and not evidence["next_dispatch_planned"] and ready_age is None:
            raise WatchdogValidationError("missing_ready_since")
    except (WatchdogValidationError, PresenceValidationError) as exc:
        return _blocked(str(exc), guard)

    incidents: list[WatchdogIncident] = []
    presence_material = {
        "classifications": presence.classifications,
        "reasons": presence.reasons,
    }
    presence_summary = {
        "observed_at": presence_payload.get("observed_at"),
        **presence_material,
    }
    if "unknown" in presence.classifications:
        incidents.append(_incident(
            "presence_insufficient",
            "UNKNOWN",
            tuple(presence.reasons) or ("presence_unknown",),
            presence_material,
            already_alerted,
        ))
    elif "degraded" in presence.classifications:
        incidents.append(_incident(
            "presence_degraded",
            "S3",
            tuple(presence.reasons) or ("presence_degraded",),
            presence_material,
            already_alerted,
        ))

    if (
        evidence["work_ready"]
        and not evidence["next_dispatch_planned"]
        and ready_age is not None
        and ready_age >= cfg["ready_without_dispatch_minutes"]
    ):
        incidents.append(_incident(
            "ready_without_dispatch",
            "S3",
            ("work_ready_without_next_dispatch",),
            {
                "ready_since": ready_since_text,
                "threshold": cfg["ready_without_dispatch_minutes"],
            },
            already_alerted,
        ))

    if reservation is not None and reservation["active"]:
        if reservation["freshness"] == "unknown":
            incidents.append(_incident(
                "reservation_evidence_unknown",
                "UNKNOWN",
                ("reservation_freshness_unknown",),
                {
                    "work_identity": reservation["work_identity"],
                    "updated_at": reservation["updated_at"],
                },
                already_alerted,
            ))
        elif (
            reservation["freshness"] == "stale"
            or reservation["age_minutes"] >= cfg["reservation_stale_minutes"]
        ):
            incidents.append(_incident(
                "reservation_without_progress",
                "S3",
                ("reservation_stale_or_over_threshold",),
                {
                    "work_identity": reservation["work_identity"],
                    "updated_at": reservation["updated_at"],
                    "freshness": reservation["freshness"],
                    "threshold": cfg["reservation_stale_minutes"],
                },
                already_alerted,
            ))

    if state["freshness"] == "stale":
        incidents.append(_incident(
            "state_stale",
            "S3",
            ("state_over_freshness_threshold",),
            {
                "work_identity": state["work_identity"],
                "updated_at": state["updated_at"],
                "threshold": cfg["state_stale_minutes"],
            },
            already_alerted,
        ))

    if state["risk"] == "UNKNOWN":
        incidents.append(_incident(
            "state_risk_unknown",
            "UNKNOWN",
            ("state_risk_unknown",),
            {
                "work_identity": state["work_identity"],
                "updated_at": state["updated_at"],
            },
            already_alerted,
        ))

    if state["severity"] in {"S1", "S2", "UNKNOWN"}:
        incidents.append(_incident(
            "state_severity",
            str(state["severity"]),
            (f"state_severity:{state['severity']}",),
            {
                "work_identity": state["work_identity"],
                "updated_at": state["updated_at"],
                "severity": state["severity"],
            },
            already_alerted,
        ))

    for item in reported_incidents:
        severity = str(item["severity"]) if item["freshness"] == "fresh" else "UNKNOWN"
        incidents.append(_incident(
            f"reported:{item['incident_id']}",
            severity,
            (f"source:{item['source']}", f"freshness:{item['freshness']}"),
            item,
            already_alerted,
        ))

    incidents.sort(key=lambda item: (item.severity, item.code, item.fingerprint))
    new_alerts = tuple(sorted(item.fingerprint for item in incidents if not item.repeated))
    interrupt_owner = any(
        item.severity in {"S1", "S2"} and not item.repeated for item in incidents
    )

    if guard.action == "BLOCKED":
        action = "BLOCKED"
    elif guard.action == "PAUSE":
        action = "PAUSE"
    elif any(item.severity == "UNKNOWN" for item in incidents):
        action = "BLOCKED"
    elif incidents:
        action = "PAUSE" if guard.pause_allowed is True else "BLOCKED"
    else:
        action = "ALLOW"

    blockers = set(state["blockers"])
    blockers.update(item.code for item in incidents)
    if guard.action != "ALLOW":
        blockers.update(guard.reasons)

    summary = DailySummary(
        active_fronts=active_fronts,
        state_freshness=str(state["freshness"]),
        incidents=tuple(sorted(f"{item.severity}:{item.code}" for item in incidents)),
        blockers=tuple(sorted(blockers)),
        human_gates=human_gates,
        integrated=integrated,
        reverted=reverted,
        next_actions=next_actions,
    )
    normalized = {
        "now": now_text,
        "presence": presence_summary,
        "work_ready": evidence["work_ready"],
        "ready_since": ready_since_text,
        "next_dispatch_planned": evidence["next_dispatch_planned"],
        "reservation": reservation,
        "state": state,
        "reported_incidents": reported_incidents,
        "guard": {
            "action": guard.action,
            "authority": guard.authority,
            "pause_allowed": guard.pause_allowed,
            "reasons": guard.reasons,
            "evidence_fingerprint": guard.evidence_fingerprint,
        },
        "summary": {
            "active_fronts": summary.active_fronts,
            "state_freshness": summary.state_freshness,
            "incidents": summary.incidents,
            "blockers": summary.blockers,
            "human_gates": summary.human_gates,
            "integrated": summary.integrated,
            "reverted": summary.reverted,
            "next_actions": summary.next_actions,
        },
    }
    return WatchdogDecision(
        action=action,
        authority="unchanged",
        incidents=tuple(incidents),
        new_alert_fingerprints=new_alerts,
        interrupt_owner=interrupt_owner,
        daily_summary=summary,
        evidence_fingerprint=_fingerprint(normalized),
    )
