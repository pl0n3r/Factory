#!/usr/bin/env python3
"""Presence Contract v1 para Adaptive Orchestration de Factory."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

ACTIVE_STATES = frozenset({
    "assigned",
    "working",
    "waiting_tool",
    "waiting_human",
    "reviewing",
    "blocked",
})
DEGRADED_STATES = frozenset({
    "stale",
    "offline",
    "rate_limited",
    "requires_login",
    "failed",
})
SESSION_FIELDS = frozenset({
    "session_id",
    "agent_id",
    "project",
    "repo",
    "work_item",
    "issue_ref",
    "pr_ref",
    "state",
    "assignment",
    "claims",
    "capabilities",
    "heartbeat_at",
    "freshness",
    "generation",
    "attempt",
    "safe_point",
    "preemptibility",
})
SNAPSHOT_FIELDS = frozenset({"version", "source", "observed_at", "sessions", "capacity"})
CAPACITY_FIELDS = frozenset({
    "known_slots",
    "eligible_free_slots",
    "degraded_slots",
    "freshness",
})
SENSITIVE_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "credential",
    "transcript",
    "conversation",
    "private_key",
    "authorization",
)


class PresenceValidationError(ValueError):
    """Snapshot inválido o inseguro."""


@dataclass(frozen=True)
class PresenceAssessment:
    """Resultado determinista derivado de un snapshot autoritativo."""

    classifications: tuple[str, ...]
    active_sessions: int
    eligible_free_slots: int
    degraded_sessions: int
    degraded_slots: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SessionPresence:
    """Efecto de una Session sobre la evaluación agregada."""

    active: int = 0
    degraded: int = 0
    uncertain: bool = False
    reason: str | None = None


def _reject_sensitive_or_unknown(mapping: dict[str, object], allowed: frozenset[str]) -> None:
    for key in mapping:
        lowered = key.lower()
        if any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS):
            raise PresenceValidationError(f"sensitive_field:{key}")
        if key not in allowed:
            raise PresenceValidationError(f"unknown_field:{key}")


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PresenceValidationError(f"invalid_{field}")
    return value.strip()


def _require_non_negative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PresenceValidationError(f"invalid_{field}")
    return value


def _require_string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PresenceValidationError(f"invalid_{field}")
    normalized = tuple(_require_text(item, field) for item in value)
    if len(normalized) != len(set(normalized)):
        raise PresenceValidationError(f"duplicate_{field}")
    return normalized


def _parse_timestamp(value: object, field: str) -> tuple[str, datetime]:
    text = _require_text(value, field)
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise PresenceValidationError(f"invalid_{field}") from exc
    if parsed.tzinfo is None:
        raise PresenceValidationError(f"invalid_{field}")
    return text, parsed


def _validate_session(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise PresenceValidationError("invalid_session")
    _reject_sensitive_or_unknown(payload, SESSION_FIELDS)

    normalized: dict[str, object] = {
        "session_id": _require_text(payload.get("session_id"), "session_id"),
        "agent_id": _require_text(payload.get("agent_id"), "agent_id"),
        "state": _require_text(payload.get("state"), "state"),
        "freshness": _require_text(payload.get("freshness"), "freshness"),
        "generation": _require_non_negative_int(payload.get("generation"), "generation"),
        "attempt": _require_non_negative_int(payload.get("attempt"), "attempt"),
        "claims": _require_string_list(payload.get("claims", []), "claims"),
        "capabilities": _require_string_list(payload.get("capabilities", []), "capabilities"),
        "safe_point": payload.get("safe_point"),
        "preemptibility": payload.get("preemptibility"),
    }
    if normalized["state"] not in ACTIVE_STATES | DEGRADED_STATES | {"idle", "paused"}:
        raise PresenceValidationError("invalid_state")
    if normalized["freshness"] not in {"fresh", "stale", "unknown"}:
        raise PresenceValidationError("invalid_freshness")
    if normalized["safe_point"] is not None and not isinstance(normalized["safe_point"], bool):
        raise PresenceValidationError("invalid_safe_point")
    if normalized["preemptibility"] is not None and normalized["preemptibility"] not in {
        "preemptible",
        "non_preemptible",
    }:
        raise PresenceValidationError("invalid_preemptibility")

    heartbeat = payload.get("heartbeat_at")
    if heartbeat is not None:
        normalized["heartbeat_at"], normalized["_heartbeat_dt"] = _parse_timestamp(
            heartbeat, "heartbeat_at"
        )
    else:
        normalized["heartbeat_at"] = None
        normalized["_heartbeat_dt"] = None

    for optional in ("project", "repo", "work_item", "issue_ref", "pr_ref", "assignment"):
        value = payload.get(optional)
        normalized[optional] = None if value is None else _require_text(value, optional)
    return normalized


def validate_presence_snapshot(payload: dict[str, object]) -> dict[str, object]:
    """Valida y normaliza PresenceSnapshot v1 sin persistirlo."""
    if not isinstance(payload, dict):
        raise PresenceValidationError("snapshot_must_be_object")
    _reject_sensitive_or_unknown(payload, SNAPSHOT_FIELDS)

    if type(payload.get("version")) is not int or payload["version"] != 1:
        raise PresenceValidationError("unsupported_version")
    source = _require_text(payload.get("source"), "source")
    observed_at, observed_dt = _parse_timestamp(payload.get("observed_at"), "observed_at")

    sessions_raw = payload.get("sessions")
    if not isinstance(sessions_raw, list):
        raise PresenceValidationError("invalid_sessions")
    sessions = tuple(_validate_session(item) for item in sessions_raw)
    session_ids = [str(item["session_id"]) for item in sessions]
    if len(session_ids) != len(set(session_ids)):
        raise PresenceValidationError("duplicate_session_id")
    for session in sessions:
        heartbeat_dt = session.pop("_heartbeat_dt")
        if heartbeat_dt is not None and heartbeat_dt > observed_dt:
            raise PresenceValidationError("heartbeat_after_observed_at")

    capacity_raw = payload.get("capacity")
    if not isinstance(capacity_raw, dict):
        raise PresenceValidationError("invalid_capacity")
    _reject_sensitive_or_unknown(capacity_raw, CAPACITY_FIELDS)
    capacity = {
        "known_slots": _require_non_negative_int(capacity_raw.get("known_slots"), "known_slots"),
        "eligible_free_slots": _require_non_negative_int(
            capacity_raw.get("eligible_free_slots"), "eligible_free_slots"
        ),
        "degraded_slots": _require_non_negative_int(
            capacity_raw.get("degraded_slots"), "degraded_slots"
        ),
        "freshness": _require_text(capacity_raw.get("freshness"), "capacity_freshness"),
    }
    if capacity["freshness"] not in {"fresh", "stale", "unknown"}:
        raise PresenceValidationError("invalid_capacity_freshness")
    if capacity["eligible_free_slots"] + capacity["degraded_slots"] > capacity["known_slots"]:
        raise PresenceValidationError("capacity_counts_exceed_known_slots")

    return {
        "version": 1,
        "source": source,
        "observed_at": observed_at,
        "sessions": sessions,
        "capacity": capacity,
    }


def _session_presence(session: dict[str, object]) -> SessionPresence:
    session_id = session["session_id"]
    freshness = session["freshness"]
    state = session["state"]

    if freshness == "unknown":
        return SessionPresence(uncertain=True, reason=f"session:{session_id}:freshness_unknown")
    if freshness == "stale":
        return SessionPresence(
            degraded=1,
            uncertain=True,
            reason=f"session:{session_id}:stale",
        )
    if state in DEGRADED_STATES:
        return SessionPresence(degraded=1, reason=f"session:{session_id}:degraded")
    if freshness == "fresh" and session["heartbeat_at"] is None:
        return SessionPresence(uncertain=True, reason=f"session:{session_id}:heartbeat_missing")
    if state in ACTIVE_STATES:
        return SessionPresence(active=1)
    return SessionPresence()


def _compose_classifications(
    active: int,
    eligible_free: int,
    known_slots: int,
    degraded_sessions: int,
    degraded_slots: int,
    reasons: list[str],
) -> tuple[str, ...]:
    signals: list[str] = []
    if active == 1:
        signals.append("solo")
    elif active >= 2:
        signals.append("multi")

    if eligible_free > 0:
        signals.append("idle_capacity")
    elif known_slots > 0:
        signals.append("saturated")
    if degraded_sessions > 0 or degraded_slots > 0:
        signals.append("degraded")
    if not signals:
        signals.append("unknown")
        reasons.append("insufficient_presence_and_capacity_evidence")
    return tuple(signals)


def classify_presence(payload: dict[str, object]) -> PresenceAssessment:
    """Clasifica presencia/capacidad con semántica fail-closed y orden estable."""
    snapshot = validate_presence_snapshot(payload)
    reasons: list[str] = []
    active = 0
    degraded_sessions = 0
    uncertain = False

    for session in snapshot["sessions"]:
        effect = _session_presence(session)
        active += effect.active
        degraded_sessions += effect.degraded
        uncertain = uncertain or effect.uncertain
        if effect.reason is not None:
            reasons.append(effect.reason)

    capacity = snapshot["capacity"]
    if capacity["freshness"] != "fresh":
        uncertain = True
        reasons.append(f"capacity:{capacity['freshness']}")

    degraded_slots = int(capacity["degraded_slots"])
    if uncertain:
        classifications = ("unknown",)
        eligible_free = 0
    else:
        eligible_free = int(capacity["eligible_free_slots"])
        classifications = _compose_classifications(
            active=active,
            eligible_free=eligible_free,
            known_slots=int(capacity["known_slots"]),
            degraded_sessions=degraded_sessions,
            degraded_slots=degraded_slots,
            reasons=reasons,
        )

    return PresenceAssessment(
        classifications=classifications,
        active_sessions=active,
        eligible_free_slots=eligible_free,
        degraded_sessions=degraded_sessions,
        degraded_slots=degraded_slots,
        reasons=tuple(sorted(reasons)),
    )
