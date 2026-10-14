#!/usr/bin/env python3
"""Decisor puro de inactividad de reservas V3; fail-closed y sin IO.

Separar esta decisión de GitHub Actions es deliberado: el recolector DEBE
demostrar paginación completa, pertenencia del titular, SHAs/estado vigentes,
CI/reviews y kill switch antes y DESPUÉS de adquirir el lock compartido.
Una Decision nunca constituye por sí misma autoridad para mutar GitHub.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

Action = Literal["unknown", "wait", "mark_recovery", "release"]
SHA = re.compile(r"[0-9a-f]{40}")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
RESERVED = "estado: reservado"
REVIEW = "estado: en revisión"
RECOVERY = "estado: requiere recuperación"

@dataclass(frozen=True)
class Evidence:
    now: datetime
    last_activity_at: datetime | None
    recovery_since: datetime | None
    status: str
    phase: str
    issue_open: bool
    v3_active: bool
    lease_id: str
    owner: str
    branch_sha: str
    branch_present: bool
    evidence_complete: bool
    trusted_phase: bool
    kill_switch_running: bool
    ci_running: bool
    changes_requested: bool
    owner_recovered: bool
    rate_remaining: int
    rate_limit: int

@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str
    libera_en_min: int | None = None


def _utc(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        # A tzinfo with no UTC offset must not become the runner's local time.
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError, TypeError, RuntimeError):
        return None


def decide(e: Evidence) -> Decision:
    """30 min para marcar, y 10 min adicionales DESDE marca para liberar.

    Cron cada 10 min: la liberación nominal es >=40 min, no a los 30
    minutos exactos. Cualquier campo no probado prohíbe la mutación.
    """
    if type(e) is not Evidence:
        return Decision("unknown", "invalid_envelope")
    booleans = (
        e.issue_open, e.v3_active, e.branch_present, e.evidence_complete,
        e.trusted_phase, e.kill_switch_running, e.ci_running,
        e.changes_requested, e.owner_recovered,
    )
    if not all(type(value) is bool for value in booleans):
        return Decision("unknown", "invalid_evidence_types")
    # Dataclass annotations are not enforced at runtime: reject custom
    # comparison objects before evaluating phase/status or any release gate.
    if type(e.phase) is not str or type(e.status) is not str:
        return Decision("unknown", "invalid_evidence_types")
    if (type(e.rate_limit) is not int or type(e.rate_remaining) is not int
            or e.rate_limit <= 0 or e.rate_remaining < 0
            or e.rate_remaining > e.rate_limit):
        return Decision("unknown", "invalid_api_budget")
    if e.rate_remaining * 5 < e.rate_limit:
        return Decision("unknown", "api_budget_below_20_percent")
    if not e.evidence_complete or not e.trusted_phase:
        return Decision("unknown", "incomplete_authenticated_evidence")
    if not e.kill_switch_running:
        return Decision("wait", "unattended_paused")
    if not e.issue_open or not e.v3_active or not e.branch_present:
        return Decision("wait", "no_active_reserved_issue")
    if (type(e.owner) is not str or not e.owner.strip()
            or type(e.lease_id) is not str or UUID.fullmatch(e.lease_id) is None
            or type(e.branch_sha) is not str or SHA.fullmatch(e.branch_sha) is None):
        return Decision("unknown", "unverified_reservation_identity")
    if e.phase != "construccion":
        if e.phase == "live":
            return Decision("wait", "live_protected")
        return Decision("unknown", "unknown_phase")
    if e.changes_requested or e.ci_running or e.owner_recovered:
        return Decision("wait", "protected_or_active_work")
    if e.status not in (RESERVED, REVIEW, RECOVERY):
        return Decision("wait", "issue_not_releasable")
    now = _utc(e.now)
    last = _utc(e.last_activity_at)
    if now is None or last is None or last > now:
        return Decision("unknown", "unverifiable_activity_clock")
    if e.status in (RESERVED, REVIEW):
        if e.recovery_since is not None:
            return Decision("unknown", "unexpected_recovery_timestamp")
        try:
            deadline = last + timedelta(minutes=30)
        except OverflowError:
            return Decision("unknown", "invalid_clock_range")
        if now >= deadline:
            return Decision("mark_recovery", "inactive_30_minutes", 10)
        return Decision("wait", "activity_window", max(
            1, math.ceil((deadline - now).total_seconds() / 60) + 10
        ))
    recovery = _utc(e.recovery_since)
    if recovery is None or recovery < last or recovery > now:
        return Decision("unknown", "unverifiable_recovery_clock")
    try:
        # Recovery itself must not predate the 30-minute inactivity threshold.
        if recovery < last + timedelta(minutes=30):
            return Decision("unknown", "premature_recovery_marker")
        deadline = max(
            last + timedelta(minutes=40), recovery + timedelta(minutes=10)
        )
    except OverflowError:
        return Decision("unknown", "invalid_clock_range")
    if now >= deadline:
        return Decision("release", "inactive_after_recovery_grace", 0)
    return Decision("wait", "recovery_grace", max(
        1, math.ceil((deadline - now).total_seconds() / 60)
    ))
