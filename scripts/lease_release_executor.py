"""Ejecutor V3 fail-closed, sólo mediante un adaptador autenticado inyectado.

No importa credenciales, HTTP ni el coordinador. Un Port real debe usar el
MISMO lock distribuido de Coordinación y firmar markers con identidad bot.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol
from uuid import UUID

LOCK_GROUP = "factory-coordination"
AVAILABLE = "estado: disponible"
RECOVERY = "estado: requiere recuperación"
ACTIVE = frozenset({"estado: reservado", "estado: en revisión", RECOVERY})
SHA = re.compile(r"[a-f0-9]{40}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class Snapshot:
    issue: int
    repository_id: int
    reservation_id: str
    owner: str
    branch: str
    branch_sha: str
    status: str
    phase: str
    now: datetime
    last_activity_at: datetime
    recovery_since: datetime | None
    marker: dict[str, Any]
    fingerprint: str
    complete: bool
    authenticated: bool
    issue_open: bool
    kill_switch_running: bool
    ci_running: bool
    changes_requested: bool
    owner_recovered: bool
    rate_remaining: int
    rate_limit: int


@dataclass(frozen=True)
class Result:
    action: str
    reason: str
    wrote: bool = False


class Port(Protocol):
    def read(self, issue: int) -> Snapshot: ...
    def lock(self, group: str) -> Any: ...
    def append(self, issue: int, body: str, expected: Snapshot) -> None: ...
    def status(self, issue: int, state: str, expected: Snapshot) -> None: ...


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _identity(s: Snapshot) -> tuple[Any, ...]:
    return (s.issue, s.repository_id, s.owner, s.reservation_id,
            s.branch, s.branch_sha)


def _trusted(s: Any, *, allow_partial: bool = False) -> bool:
    if type(s) is not Snapshot:
        return False
    flags = (s.complete, s.authenticated, s.issue_open, s.kill_switch_running,
             s.ci_running, s.changes_requested, s.owner_recovered)
    if any(type(f) is not bool for f in flags):
        return False
    if not (s.complete and s.authenticated and s.issue_open
            and s.kill_switch_running and not s.ci_running
            and not s.changes_requested and not s.owner_recovered):
        return False
    if (type(s.issue) is not int or s.issue <= 0 or type(s.repository_id) is not int
            or s.repository_id <= 0 or type(s.owner) is not str
            or type(s.branch) is not str or type(s.reservation_id) is not str
            or type(s.branch_sha) is not str or SHA.fullmatch(s.branch_sha) is None
            or type(s.fingerprint) is not str or HEX.fullmatch(s.fingerprint) is None
            or type(s.status) is not str or s.status not in ACTIVE
            or type(s.phase) is not str or s.phase != "construccion"):
        return False
    try:
        UUID(s.reservation_id)
    except (ValueError, TypeError, AttributeError):
        return False
    if s.branch != f"trabajo/issue-{s.issue}" or not s.owner.strip():
        return False
    if (type(s.rate_limit) is not int or type(s.rate_remaining) is not int
            or s.rate_limit <= 0 or s.rate_remaining < 0
            or s.rate_remaining > s.rate_limit
            or s.rate_remaining * 5 < s.rate_limit):
        return False
    now, last, recovery = _utc(s.now), _utc(s.last_activity_at), _utc(s.recovery_since)
    if now is None or last is None or last > now:
        return False
    if s.status == RECOVERY:
        if recovery is None or recovery > now or recovery < last:
            return False
    elif s.recovery_since is not None:
        return False
    m = s.marker
    if type(m) is not dict or type(m.get("version")) is not int or m["version"] != 3:
        return False
    if (m.get("owner") != s.owner or m.get("reservation_id") != s.reservation_id
            or m.get("branch") != s.branch):
        return False
    if type(m.get("active")) is not bool or (not allow_partial and not m["active"]):
        return False
    if (any(type(m.get(k)) is not str or HEX.fullmatch(m[k]) is None
            for k in ("acceptance_sha256", "task_marker_sha256"))
            or type(m.get("task_paths")) is not list or not m["task_paths"]
            or any(type(p) is not str for p in m["task_paths"])
            or type(m.get("task_depends_on")) is not list
            or any(type(x) is not int or x <= 0 for x in m["task_depends_on"])):
        return False
    return True


def _eligible(s: Snapshot, action: str) -> bool:
    """Veto redundante: nunca reemplaza al decisor puro."""
    now, last = _utc(s.now), _utc(s.last_activity_at)
    if now is None or last is None:
        return False
    try:
        if action == "mark_recovery":
            return s.status != RECOVERY and now >= last + timedelta(minutes=30)
        if action == "release":
            r = _utc(s.recovery_since)
            return (s.status == RECOVERY and r is not None
                    and r >= last + timedelta(minutes=30)
                    and now >= r + timedelta(minutes=10)
                    and now >= last + timedelta(minutes=40))
    except OverflowError:
        return False
    return False


def _same(a: Snapshot, b: Snapshot) -> bool:
    return (_identity(a) == _identity(b) and a.fingerprint == b.fingerprint
            and a.status == b.status and a.marker == b.marker
            and a.last_activity_at == b.last_activity_at
            and a.recovery_since == b.recovery_since and a.phase == b.phase
            and _utc(a.now) <= _utc(b.now))


def _release_marker(s: Snapshot) -> str:
    marker = dict(s.marker)
    marker.update(active=False, reason="auto-inactivity-release")
    payload = json.dumps(marker, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":"))
    return (f"<!-- condor-reserva {payload} -->\n"
            f"Reserva {s.reservation_id} liberada; rama {s.branch} preservada, "
            f"SHA {s.branch_sha}, última actividad "
            f"{_utc(s.last_activity_at).isoformat()}; "
            "adopción sólo mediante /adoptar-contrato-huerfana.")

def _postappend(current: Snapshot, after: Snapshot, action: str) -> bool:
    """No cambiar etiqueta con evidencia temporal/lease obsoleta tras append.

    El fingerprint puede cambiar porque el comentario recién publicado
    forma parte del snapshot, pero el marker debe ser exactamente el previsto.
    """
    expected = dict(current.marker)
    if action == "release":
        expected.update(active=False, reason="auto-inactivity-release")
    return (_trusted(after, allow_partial=action == "release")
            and _identity(after) == _identity(current)
            and after.status == current.status and after.phase == current.phase
            and after.last_activity_at == current.last_activity_at
            and after.recovery_since == current.recovery_since
            and _utc(current.now) <= _utc(after.now)
            and after.marker == expected and _eligible(after, action))


def execute(issue: int, port: Port, decide: Callable[[Snapshot], Any], *,
            feature_enabled: bool = False, dry_run: bool = True) -> Result:
    """Revalida dos veces bajo lock. Todas las escrituras pasan por Port CAS."""
    if type(feature_enabled) is not bool or type(dry_run) is not bool:
        return Result("unknown", "invalid_execution_flags")
    if type(issue) is not int or issue <= 0:
        return Result("unknown", "invalid_issue")
    if not feature_enabled:
        return Result("wait", "feature_disabled")
    try:
        first = port.read(issue)
        if not _trusted(first, allow_partial=True) or first.issue != issue:
            return Result("unknown", "untrusted_snapshot")
        if first.marker["active"] is False:
            # Reconciliar un marker de bot escrito antes de cambiar la etiqueta;
            # nunca publicar un segundo marker ni reactivar un claim.
            if (first.marker.get("reason") != "auto-inactivity-release"
                    or not _eligible(first, "release")):
                return Result("wait", "partial_not_reconcilable")
            if dry_run:
                return Result("release", "dry_run_reconcile")
            with port.lock(f"{LOCK_GROUP}-{first.repository_id}"):
                locked, current = port.read(issue), port.read(issue)
                if not (all(_trusted(x, allow_partial=True) for x in (locked, current))
                        and _same(first, locked) and _same(locked, current)
                        and current.marker["active"] is False
                        and current.marker.get("reason") == "auto-inactivity-release"
                        and _eligible(locked, "release")
                        and _eligible(current, "release")):
                    return Result("unknown", "partial_reconciliation_drift")
                port.status(issue, AVAILABLE, current)
                return Result("release", "partial_reconciled", True)
        action = getattr(decide(first), "action", None)
        if not _eligible(first, action):
            return Result("wait", "decision_not_eligible")
        if dry_run:
            return Result(action, "dry_run")
        with port.lock(f"{LOCK_GROUP}-{first.repository_id}"):
            locked = port.read(issue)
            if (not _trusted(locked) or not _same(first, locked)
                    or not _eligible(locked, action)):
                return Result("unknown", "stale_inside_lock")
            if getattr(decide(locked), "action", None) != action:
                return Result("unknown", "decision_drift")
            current = port.read(issue)
            if (not _trusted(current) or not _same(locked, current)
                    or not _eligible(current, action)):
                return Result("unknown", "prewrite_drift")
            if getattr(decide(current), "action", None) != action:
                return Result("unknown", "decision_drift")
            if action == "mark_recovery":
                body = (f"Auto-release: 30 min sin actividad autenticada; "
                        f"UUID {current.reservation_id}, rama {current.branch}, "
                        f"SHA {current.branch_sha}. Gracia 10 min; "
                        "reserva todavía activa.")
                port.append(issue, body, current)
                after = port.read(issue)
                if not _postappend(current, after, action):
                    return Result(action, "partial_comment_only")
                port.status(issue, RECOVERY, after)
                return Result(action, "recovery_marked", True)
            port.append(issue, _release_marker(current), current)
            after = port.read(issue)
            if not _postappend(current, after, action):
                return Result(action, "partial_marker_only")
            port.status(issue, AVAILABLE, after)
            return Result(action, "released", True)
    except Exception:
        # Si hubo escritura parcial no borrar rama ni forzar rollback. Un
        # reintento bajo el lock sólo puede reconciliar marker bot exacto.
        return Result("unknown", "port_failure_or_partial_write")
