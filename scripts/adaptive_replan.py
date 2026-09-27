#!/usr/bin/env python3
"""Motor determinista de replanning para Adaptive Orchestration."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from scripts.presence_contract import PresenceAssessment, classify_presence

EVENT_TYPES = frozenset({
    "session_join",
    "session_leave",
    "presence_changed",
    "workitem_changed",
    "dependency_changed",
    "claim_changed",
    "reservation_changed",
    "health_changed",
    "incident_changed",
    "ci_changed",
    "review_changed",
    "deploy_changed",
    "owner_decision_resolved",
    "capacity_changed",
})
READINESS_TYPES = frozenset({
    "workitem_changed",
    "dependency_changed",
    "claim_changed",
    "reservation_changed",
})
IMMEDIATE_TYPES = frozenset({"health_changed", "incident_changed"})


class ReplanValidationError(ValueError):
    """Entrada inválida para el motor de replanning."""


@dataclass(frozen=True)
class ReplanEvent:
    """Evento normalizado que puede cambiar el plan."""

    event_type: str
    subject: str
    state: str
    evidence_ref: str


@dataclass(frozen=True)
class ReplanDecision:
    """Decisión pura y atribuible del motor."""

    action: str
    reasons: tuple[str, ...]
    snapshot_fingerprint: str
    event_fingerprint: str
    coalesced_events: int


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplanValidationError(f"invalid_{field}")
    return value.strip()


def normalize_event(payload: dict[str, object]) -> ReplanEvent:
    """Valida un evento sin interpretar prioridad ni ranking."""
    if not isinstance(payload, dict):
        raise ReplanValidationError("event_must_be_object")
    allowed = {"event_type", "subject", "state", "evidence_ref"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ReplanValidationError(f"unknown_field:{unknown[0]}")
    event_type = _text(payload.get("event_type"), "event_type")
    if event_type not in EVENT_TYPES:
        raise ReplanValidationError("invalid_event_type")
    return ReplanEvent(
        event_type=event_type,
        subject=_text(payload.get("subject"), "subject"),
        state=_text(payload.get("state"), "state"),
        evidence_ref=_text(payload.get("evidence_ref"), "evidence_ref"),
    )


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_fingerprint(snapshot: dict[str, object]) -> str:
    """Fingerprint estable del snapshot lógico de presencia."""
    return _canonical_hash(snapshot)


def event_fingerprint(event: ReplanEvent) -> str:
    """Fingerprint estable de un evento normalizado."""
    return _canonical_hash({
        "event_type": event.event_type,
        "subject": event.subject,
        "state": event.state,
        "evidence_ref": event.evidence_ref,
    })


def coalesce_events(events: list[dict[str, object]]) -> tuple[ReplanEvent, ...]:
    """Deduplica eventos equivalentes con orden reproducible."""
    unique: dict[str, ReplanEvent] = {}
    for payload in events:
        event = normalize_event(payload)
        unique.setdefault(event_fingerprint(event), event)
    return tuple(unique[key] for key in sorted(unique))


def _presence_fail_closed(assessment: PresenceAssessment) -> bool:
    return "unknown" in assessment.classifications or any(
        reason.endswith("stale")
        or reason.endswith("freshness_unknown")
        or reason.startswith("capacity:stale")
        or reason.startswith("capacity:unknown")
        for reason in assessment.reasons
    )


def _presence_reasons(assessment: PresenceAssessment) -> list[str]:
    return [f"presence:{value}" for value in assessment.classifications]


def decide_replan(
    snapshot: dict[str, object],
    events: list[dict[str, object]],
    *,
    active_work_safe: bool,
    active_work_ready: bool,
    readiness_changed: bool = False,
    owner_decision_target_ready: bool | None = None,
) -> ReplanDecision:
    """Decide keep/replan/fail_closed sin ejecutar trabajo ni duplicar ranking."""
    assessment = classify_presence(snapshot)
    normalized_events = coalesce_events(events)
    reasons: list[str] = []
    untrusted_events = [
        f"event_{event.state}:{event.event_type}:{event.subject}"
        for event in normalized_events
        if event.state in {"unknown", "stale"}
    ]

    if _presence_fail_closed(assessment) or untrusted_events:
        reasons.extend(_presence_reasons(assessment))
        reasons.extend(assessment.reasons)
        reasons.extend(untrusted_events)
        return ReplanDecision(
            action="fail_closed",
            reasons=tuple(sorted(set(reasons))),
            snapshot_fingerprint=snapshot_fingerprint(snapshot),
            event_fingerprint=_canonical_hash(
                [event_fingerprint(event) for event in normalized_events]
            ),
            coalesced_events=len(normalized_events),
        )

    event_types = {event.event_type for event in normalized_events}
    immediate = bool(event_types & IMMEDIATE_TYPES)
    presence_changed = bool(
        event_types
        & {
            "session_join",
            "session_leave",
            "presence_changed",
            "capacity_changed",
        }
    )
    readiness_event = bool(event_types & READINESS_TYPES) or readiness_changed
    owner_event = "owner_decision_resolved" in event_types

    if immediate:
        reasons.append("immediate_operational_replan")
    if presence_changed:
        reasons.append("presence_or_capacity_changed")
    if readiness_event:
        reasons.append("readiness_changed")
    if owner_event:
        reasons.append("owner_decision_resolved")
        if owner_decision_target_ready is False:
            reasons.append("owner_decision_target_not_ready")

    should_replan = immediate or presence_changed or readiness_event
    if owner_event and owner_decision_target_ready is True:
        should_replan = True

    if (
        should_replan
        and not immediate
        and active_work_safe
        and active_work_ready
        and not readiness_event
    ):
        reasons.append("continuity_preserved")
        action = "keep"
    elif should_replan:
        action = "replan"
    else:
        reasons.append("no_material_change")
        action = "keep"

    return ReplanDecision(
        action=action,
        reasons=tuple(sorted(set(reasons))),
        snapshot_fingerprint=snapshot_fingerprint(snapshot),
        event_fingerprint=_canonical_hash(
            [event_fingerprint(event) for event in normalized_events]
        ),
        coalesced_events=len(normalized_events),
    )
