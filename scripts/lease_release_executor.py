"""Ejecutor V3 fail-closed, sólo mediante un adaptador autenticado inyectado.

No importa credenciales, HTTP ni el coordinador. Un Port real debe usar el
MISMO lock distribuido de Coordinación y firmar markers con identidad bot.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

LOCK_GROUP = "factory-coordination"
AVAILABLE = "estado: disponible"
RECOVERY = "estado: requiere recuperación"
ACTIVE = frozenset({"estado: reservado", "estado: en revisión", RECOVERY})
SHA = re.compile(r"[a-f0-9]{40}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
# Contract parity with scripts/coordinar_trabajo.py::SESSION_RE.
# Input comments may be normalized by Coordinación, but trusted snapshots
# and bot markers are expected to carry the canonical lowercase form.
SESSION_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


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
    """Resultado auditable de una transición; wrote NO significa 'sin efectos'.

    wrote=True exclusivamente si se confirmó la transición terminal.
    write_state=none: no intento; partial: hubo intento sin estado final;
    complete: transición terminal verificada; unknown: efecto ambiguo.
    Todo partial/unknown necesita reconciliación bajo lock antes de reintentar.
    """
    action: str
    reason: str
    wrote: bool = False
    write_state: str = "none"

    def __post_init__(self) -> None:
        if (type(self.wrote) is not bool
                or self.write_state not in ("none", "partial", "complete", "unknown")
                or self.wrote != (self.write_state == "complete")):
            raise ValueError("inconsistent_write_state")


@dataclass(frozen=True)
class RecoveryNoteProof:
    """Búsqueda completa de notas ligadas al UUID/branch/actividad exactos.

    El adaptador debe paginar con GitHub autenticado, verificar el payload
    del comentario y comprobar el autor canónico github-actions[bot].
    Un error/403/página truncada produce complete=False, nunca count=0.
    """
    complete: bool
    authenticated: bool
    count: int
    owner: str
    reservation_id: str
    branch: str
    branch_sha: str
    last_activity_at: datetime
    acceptance_sha256: str
    task_marker_sha256: str
    created_at: datetime | None
    author: str | None


@dataclass(frozen=True)
class RecoveryLabelProof:
    """Evento labeled de API paginada, atribuible al mismo UUID V3.

    El timeline no lleva UUID por sí solo: el Port autenticado debe
    correlacionarlo con la nota y reserva vigentes, y rechazar carreras,
    reetiquetados o event histories incompletos.
    """
    complete: bool
    authenticated: bool
    count: int
    owner: str
    reservation_id: str
    branch: str
    branch_sha: str
    label: str
    created_at: datetime | None
    author: str | None


class Port(Protocol):
    def read(self, issue: int) -> Snapshot: ...
    def lock(self, group: str) -> Any: ...
    def append(self, issue: int, body: str, expected: Snapshot) -> None: ...
    def recovery_note(self, issue: int, expected: Snapshot) -> RecoveryNoteProof: ...
    def recovery_label(self, issue: int, expected: Snapshot) -> RecoveryLabelProof: ...
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
    if SESSION_RE.fullmatch(s.reservation_id) is None:
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
    required = {
        "version", "owner", "reservation_id", "branch", "active",
        "reason", "acceptance_sha256", "task_marker_sha256",
        "task_paths", "task_depends_on",
    }
    if (type(m) is not dict or set(m) != required
            or type(m.get("version")) is not int or m["version"] != 3
            or type(m.get("reason")) is not str or not m["reason"]):
        return False
    if (m.get("owner") != s.owner or m.get("reservation_id") != s.reservation_id
            or m.get("branch") != s.branch):
        return False
    if type(m.get("active")) is not bool or (not allow_partial and not m["active"]):
        return False
    if (any(type(m.get(k)) is not str or HEX.fullmatch(m[k]) is None
            for k in ("acceptance_sha256", "task_marker_sha256"))
            or type(m.get("task_paths")) is not list or not m["task_paths"]
            or any(type(p) is not str or not p for p in m["task_paths"])
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


def _note_ok(proof: Any, s: Snapshot) -> bool:
    """Sólo cero o una nota acreditada por API/actor, nunca evidencia parcial."""
    if type(proof) is not RecoveryNoteProof:
        return False
    if (type(proof.complete) is not bool or type(proof.authenticated) is not bool
            or not proof.complete or not proof.authenticated
            or type(proof.count) is not int or proof.count not in (0, 1)
            or proof.owner != s.owner or proof.reservation_id != s.reservation_id
            or proof.branch != s.branch or proof.branch_sha != s.branch_sha
            or _utc(proof.last_activity_at) != _utc(s.last_activity_at)
            or proof.acceptance_sha256 != s.marker["acceptance_sha256"]
            or proof.task_marker_sha256 != s.marker["task_marker_sha256"]):
        return False
    if proof.count == 0:
        return proof.created_at is None and proof.author is None
    at, now, activity = (_utc(proof.created_at), _utc(s.now),
                         _utc(s.last_activity_at))
    if at is None or now is None or activity is None:
        return False
    try:
        return (proof.author == "github-actions[bot]"
                and at >= activity + timedelta(minutes=30) and at <= now)
    except OverflowError:
        return False


def _recovery_label_ok(note: Any, label: Any, s: Snapshot) -> bool:
    """Gracia desde evento RECOVERY efectivo, nunca desde nota previa."""
    if (s.status != RECOVERY or not _note_ok(note, s)
            or note.count != 1 or type(label) is not RecoveryLabelProof):
        return False
    if (type(label.complete) is not bool
            or type(label.authenticated) is not bool
            or not label.complete or not label.authenticated
            or type(label.count) is not int or label.count != 1
            or label.owner != s.owner or label.reservation_id != s.reservation_id
            or label.branch != s.branch or label.branch_sha != s.branch_sha
            or label.label != RECOVERY or label.author != "github-actions[bot]"):
        return False
    at, comment_at, now = (_utc(label.created_at),
                           _utc(note.created_at), _utc(s.now))
    if at is None or comment_at is None or now is None:
        return False
    return (comment_at <= at <= now
            and _utc(s.recovery_since) == at)


def _recovery_proven(port: Port, issue: int, s: Snapshot) -> bool:
    return _recovery_label_ok(port.recovery_note(issue, s),
                              port.recovery_label(issue, s), s)


def _same(a: Snapshot, b: Snapshot) -> bool:
    return (_identity(a) == _identity(b) and a.fingerprint == b.fingerprint
            and a.status == b.status and a.marker == b.marker
            and a.last_activity_at == b.last_activity_at
            and a.recovery_since == b.recovery_since and a.phase == b.phase
            and _utc(a.now) <= _utc(b.now))


def _released_ok(before: Snapshot, confirmed: Any) -> bool:
    """Verifica el estado terminal disponible después del CAS de etiqueta.

    AVAILABLE no pertenece al conjunto ACTIVE; se autentica un equivalente
    RECOVERY solo para validar esquema/identidad sin admitir como activa la
    reserva efectivamente liberada.
    """
    if (type(confirmed) is not Snapshot or confirmed.status != AVAILABLE
            or confirmed.recovery_since is not None):
        return False
    expected_marker = dict(before.marker)
    expected_marker.update(active=False, reason="auto-inactivity-release")
    if confirmed.marker != expected_marker:
        return False
    probe = replace(confirmed, status=RECOVERY,
                    recovery_since=before.recovery_since)
    return (_trusted(probe, allow_partial=True)
            and _identity(confirmed) == _identity(before)
            and confirmed.phase == before.phase
            and confirmed.last_activity_at == before.last_activity_at
            and _utc(confirmed.now) >= _utc(before.now))


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
                if not _recovery_proven(port, issue, current):
                    return Result("unknown", "recovery_label_untrusted")
                port.status(issue, AVAILABLE, current)
                final = port.read(issue)
                if not _released_ok(current, final):
                    return Result("release", "unverified_release", write_state="partial")
                return Result("release", "partial_reconciled", True, "complete")
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
                proof = port.recovery_note(issue, current)
                if not _note_ok(proof, current):
                    return Result("unknown", "recovery_note_untrusted")
                if proof.count == 0:
                    evidence = {
                        "version": 1, "reservation_id": current.reservation_id,
                        "owner": current.owner, "branch": current.branch,
                        "branch_sha": current.branch_sha,
                        "last_activity_at": _utc(current.last_activity_at).isoformat(),
                        "acceptance_sha256": current.marker["acceptance_sha256"],
                        "task_marker_sha256": current.marker["task_marker_sha256"],
                    }
                    body = ("<!-- factory-lease-recovery " +
                            json.dumps(evidence, sort_keys=True,
                                       separators=(",", ":")) + " -->\n"
                            "Auto-release: 30 min sin actividad autenticada; "
                            "reserva todavía activa, gracia de 10 min.")
                    port.append(issue, body, current)
                    after = port.read(issue)
                    proof = port.recovery_note(issue, after)
                else:
                    # Reintento tras append confirmado y fallo del cambio
                    # de etiqueta; no publicar otra nota para este UUID.
                    after = current
                if (not _postappend(current, after, action)
                        or not _note_ok(proof, after) or proof.count != 1):
                    return Result(action, "partial_comment_only", write_state="partial")
                port.status(issue, RECOVERY, after)
                confirmed = port.read(issue)
                if (not _trusted(confirmed)
                        or _identity(confirmed) != _identity(after)
                        or confirmed.status != RECOVERY
                        or confirmed.marker != after.marker
                        or confirmed.last_activity_at != after.last_activity_at
                        or _utc(confirmed.now) < _utc(after.now)
                        or not _recovery_label_ok(
                            proof, port.recovery_label(issue, confirmed),
                            confirmed)):
                    return Result(action, "unverified_recovery_since", write_state="partial")
                return Result(action, "recovery_marked", True, "complete")
            if not _recovery_proven(port, issue, current):
                return Result("unknown", "recovery_label_untrusted")
            port.append(issue, _release_marker(current), current)
            after = port.read(issue)
            if (not _postappend(current, after, action)
                    or not _recovery_proven(port, issue, after)):
                return Result(action, "partial_marker_only", write_state="partial")
            port.status(issue, AVAILABLE, after)
            final = port.read(issue)
            if not _released_ok(after, final):
                return Result(action, "unverified_release", write_state="partial")
            return Result(action, "released", True, "complete")
    except Exception:
        # Si hubo escritura parcial no borrar rama ni forzar rollback. Un
        # reintento bajo el lock sólo puede reconciliar marker bot exacto.
        return Result("unknown", "port_failure_or_partial_write", write_state="unknown")
