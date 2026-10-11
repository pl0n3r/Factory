"""Pruebas offline; ningún acceso a GitHub ni credenciales de producción."""
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo
from types import SimpleNamespace

from scripts.lease_release_executor import (
    AVAILABLE, RECOVERY, RecoveryLabelProof, RecoveryNoteProof, Result, Snapshot,
    execute,
)

START = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)
ID = "3945eeb7-1df8-4439-b196-98897eb3a71a"


def snapshot(*, recovery=True):
    return Snapshot(
        issue=1191, repository_id=123, reservation_id=ID, owner="pl0n3r",
        branch="trabajo/issue-1191", branch_sha="a" * 40,
        status=RECOVERY if recovery else "estado: en revisión",
        phase="construccion", now=START + timedelta(minutes=41),
        last_activity_at=START,
        recovery_since=START + timedelta(minutes=30) if recovery else None,
        marker={"version": 3, "owner": "pl0n3r", "branch": "trabajo/issue-1191",
                "reservation_id": ID, "active": True, "reason": "tomar",
                "acceptance_sha256": "b" * 64, "task_marker_sha256": "c" * 64,
                "task_paths": ["scripts/x.py"], "task_depends_on": []},
        fingerprint="d" * 64, complete=True, authenticated=True,
        issue_open=True, kill_switch_running=True, ci_running=False,
        changes_requested=False, owner_recovered=False,
        rate_remaining=60, rate_limit=100,
    )


class UndefinedOffset(tzinfo):
    """Fecha con tzinfo nominal pero sin offset verificable."""
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


class FakePort:
    def __init__(self, item):
        self.item = item
        self.writes = []
        self.locked = False
        self.drift = None
        self.fail_status = False
        self.noop_available = False
        self.locked_clock_drift = None  # (locked_read_ordinal, absolute_minute)
        self.locked_reads = 0
        self.note_at = item.recovery_since if item.status == RECOVERY else None
        self.label_at = item.recovery_since if item.status == RECOVERY else None
        self.label_complete = True
        self.label_authenticated = True
        self.label_author = "github-actions[bot]"
        self.label_count = None
        self.note_complete = True
        self.note_authenticated = True
        self.note_author = "github-actions[bot]"
        self.note_count = None  # opcional para simular duplicidad

    def read(self, issue):
        assert issue == 1191
        if self.locked:
            self.locked_reads += 1
            if (self.locked_clock_drift is not None
                    and self.locked_reads == self.locked_clock_drift[0]):
                self.item = replace(self.item, now=START + timedelta(
                    minutes=self.locked_clock_drift[1]))
                return self.item
        if self.drift is not None:
            value, self.drift = self.drift, None
            return value
        return self.item

    @contextmanager
    def lock(self, group):
        assert group == "factory-coordination-123"
        self.locked = True
        try:
            yield
        finally:
            self.locked = False

    def recovery_note(self, issue, expected):
        assert self.locked and issue == 1191
        found = int(self.note_at is not None) if self.note_count is None else self.note_count
        return RecoveryNoteProof(
            complete=self.note_complete, authenticated=self.note_authenticated,
            count=found, owner=expected.owner,
            reservation_id=expected.reservation_id, branch=expected.branch,
            branch_sha=expected.branch_sha,
            last_activity_at=expected.last_activity_at,
            acceptance_sha256=expected.marker["acceptance_sha256"],
            task_marker_sha256=expected.marker["task_marker_sha256"],
            created_at=self.note_at if found else None,
            author=self.note_author if found else None)

    def recovery_label(self, issue, expected):
        assert self.locked and issue == 1191
        count = int(self.label_at is not None) if self.label_count is None else self.label_count
        return RecoveryLabelProof(
            complete=self.label_complete, authenticated=self.label_authenticated,
            count=count, owner=expected.owner,
            reservation_id=expected.reservation_id, branch=expected.branch,
            branch_sha=expected.branch_sha, label=RECOVERY,
            created_at=self.label_at if count else None,
            author=self.label_author if count else None)

    def append(self, issue, body, expected):
        assert self.locked and expected is self.item
        self.writes.append(("comment", body))
        if body.startswith("<!-- factory-lease-recovery "):
            self.note_at = self.item.now
        if body.startswith("<!-- condor-reserva "):
            self.item = replace(self.item, marker={**self.item.marker,
                "active": False, "reason": "auto-inactivity-release"})

    def status(self, issue, status, expected):
        assert self.locked and expected is self.item
        if self.fail_status:
            raise RuntimeError("partial")
        if status == AVAILABLE and self.noop_available:
            return  # ACK without persistence: release must not report success.
        self.writes.append(("status", status))
        if status == RECOVERY:
            self.label_at = self.item.now
        self.item = replace(
            self.item, status=status,
            recovery_since=(self.label_at if status == RECOVERY else
                            None if status == AVAILABLE else
                            self.item.recovery_since))


def decision(s):
    return SimpleNamespace(action="release" if s.status == RECOVERY else "mark_recovery")


class LeaseReleaseExecutorTests(unittest.TestCase):
    def test_dry_run_feature_flag_and_killswitch_block_all_writes(self):
        port = FakePort(snapshot())
        self.assertEqual(execute(1191, port, decision).reason, "feature_disabled")
        self.assertEqual(execute(1191, port, decision, feature_enabled=True).reason,
                         "dry_run")
        self.assertEqual(port.writes, [])
        for item in (replace(snapshot(), kill_switch_running=False),
                     replace(snapshot(), phase="live"),
                     replace(snapshot(), complete=False),
                     replace(snapshot(), rate_remaining=19),
                     replace(snapshot(), ci_running=True),
                     replace(snapshot(), changes_requested=True)):
            port = FakePort(item)
            answer = execute(1191, port, decision, feature_enabled=True,
                             dry_run=False)
            self.assertFalse(answer.wrote)
            self.assertEqual(port.writes, [])
        for marker_delta in (
            {"reason": ""},
            {"reason": None},
            {"reason": "tomar", "unexpected_field": "x"},
            {"task_paths": [""]},
            {"task_paths": []},
            {"task_depends_on": [True]},
        ):
            with self.subTest(invalid_marker=marker_delta):
                initial = snapshot()
                malformed = replace(initial, marker={
                    **initial.marker, **marker_delta})
                port = FakePort(malformed)
                result = execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual(result.reason, "untrusted_snapshot")
                self.assertEqual(port.writes, [])
        # Identidad canónica de Coordinación: minúsculas, UUID v1..v5
        # y variante RFC 4122. Actualizar también el marker para que
        # el negativo no dependa de una discrepancia entre ambos campos.
        for malformed in (
            "00000000-0000-0000-0000-000000000000",
            "3945eeb7-1df8-7439-b196-98897eb3a71a",
            "3945eeb7-1df8-4439-7196-98897eb3a71a",
            ID.upper(),
            ID.replace("-", ""),
        ):
            with self.subTest(reservation_id=malformed):
                original = snapshot()
                tampered = replace(
                    original, reservation_id=malformed,
                    marker={**original.marker, "reservation_id": malformed})
                isolated = FakePort(tampered)
                result = execute(1191, isolated, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual(result.reason, "untrusted_snapshot")
                self.assertEqual(isolated.writes, [])

    def test_claim_integrity_and_utc_offset_fail_closed(self):
        """No liberar con timezone indeterminado ni claims V3 ambiguos."""
        for field in ("now", "last_activity_at", "recovery_since"):
            with self.subTest(untrusted_clock=field):
                broken = replace(snapshot(), **{
                    field: START.replace(tzinfo=UndefinedOffset())})
                fake = FakePort(broken)
                result = execute(1191, fake, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual(result.reason, "untrusted_snapshot")
                self.assertEqual(fake.writes, [])

        bad_markers = (
            {"reason": "liberar"},
            {"reason": "auto-inactivity-release"},
            {"task_paths": ["scripts/x.py", "scripts/x.py"]},
            {"task_paths": ["DOCS/file.md", "docs/file.md"]},
            {"task_paths": ["docs/", "docs/file.md"]},
            {"task_paths": ["scripts/café.py", "scripts/cafe\u0301.py"]},
            {"task_paths": ["../outside.py"]},
            {"task_depends_on": [1190, 1190]},
        )
        for delta in bad_markers:
            with self.subTest(ambiguous_v3=delta):
                base = snapshot()
                fake = FakePort(replace(base, marker={**base.marker, **delta}))
                result = execute(1191, fake, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual(result.reason, "untrusted_snapshot")
                self.assertEqual(fake.writes, [])

        for reason in ("liberar", "tomar"):
            with self.subTest(inactive_reason=reason):
                base = snapshot()
                fake = FakePort(replace(base, marker={
                    **base.marker, "active": False, "reason": reason}))
                result = execute(1191, fake, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual(result.reason, "untrusted_snapshot")
                self.assertEqual(fake.writes, [])

        good = snapshot()
        fake = FakePort(replace(good, marker={
            **good.marker,
            "task_paths": ["scripts/a.py", "docs/b.md"],
            "task_depends_on": [1175, 1190],
        }))
        self.assertEqual(
            execute(1191, fake, decision, feature_enabled=True).reason,
            "dry_run")
        self.assertEqual(fake.writes, [])

    def test_mark_recovery_and_release_revalidate_under_shared_lock(self):
        port = FakePort(snapshot(recovery=False))
        answer = execute(1191, port, decision, feature_enabled=True,
                         dry_run=False)
        self.assertEqual(answer.reason, "recovery_marked")
        self.assertEqual(port.item.status, RECOVERY)
        self.assertEqual(len(port.writes), 2)
        self.assertEqual(port.item.recovery_since, START + timedelta(minutes=41))
        # La gracia se cuenta desde la etiqueta RECOVERY auténtica, no
        # desde el primer preflight ni desde un comentario anticipado.
        port.item = replace(port.item, now=START + timedelta(minutes=50))
        before = len(port.writes)
        self.assertFalse(execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False).wrote)
        self.assertEqual(len(port.writes), before)
        port.item = replace(port.item, now=START + timedelta(minutes=51))
        self.assertEqual(execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "released")
        self.assertEqual(port.item.status, AVAILABLE)
        port = FakePort(snapshot())
        port.drift = replace(port.item, branch_sha="e" * 40)
        self.assertEqual(execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "stale_inside_lock")
        self.assertEqual(port.writes, [])
        port = FakePort(replace(snapshot(), recovery_since=START + timedelta(minutes=29)))
        self.assertFalse(execute(1191, port, decision, feature_enabled=True,
                                 dry_run=False).wrote)
        self.assertEqual(port.writes, [])
        # Neither a stale lock read nor the final pre-write read may
        # authorize a transition when the trusted clock goes backward.
        # The fake decision intentionally only consults status, so the
        # executor's *independent* 30+10 minute guard must reject both.
        for recovery, clock_minute in ((False, 20), (True, 35)):
            for locked_read in (1, 2):
                with self.subTest(recovery=recovery, locked_read=locked_read):
                    port = FakePort(snapshot(recovery=recovery))
                    port.locked_clock_drift = (locked_read, clock_minute)
                    result = execute(1191, port, decision,
                                     feature_enabled=True, dry_run=False)
                    self.assertFalse(result.wrote)
                    self.assertEqual(port.writes, [])
        # A third read occurs AFTER the append, before changing the label.
        # It may see an earlier clock: never write the final status then.
        for recovery, minute in ((False, 20), (True, 35)):
            with self.subTest(postappend_regression=recovery):
                port = FakePort(snapshot(recovery=recovery))
                port.locked_clock_drift = (3, minute)
                result = execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertFalse(result.wrote)
                self.assertEqual(len(port.writes), 1)
                self.assertEqual(port.writes[0][0], "comment")
                self.assertEqual(port.item.status,
                                 RECOVERY if recovery else "estado: en revisión")
        # Monotonic advancement of trusted UTC under the lock remains valid.
        for recovery in (False, True):
            with self.subTest(advancing_clock_recovery=recovery):
                port = FakePort(snapshot(recovery=recovery))
                port.locked_clock_drift = (2, 42)
                self.assertTrue(execute(1191, port, decision,
                                        feature_enabled=True, dry_run=False).wrote)
        port = FakePort(snapshot())
        port.item = replace(port.item, reservation_id="bad")
        self.assertFalse(execute(1191, port, decision, feature_enabled=True,
                                 dry_run=False).wrote)

    def test_release_preserves_branch_and_handles_partial_writes(self):
        port = FakePort(snapshot())
        answer = execute(1191, port, decision, feature_enabled=True, dry_run=False)
        self.assertEqual((answer.action, answer.reason), ("release", "released"))
        self.assertEqual(port.item.status, AVAILABLE)
        self.assertEqual(port.item.branch, "trabajo/issue-1191")
        self.assertEqual(port.item.branch_sha, "a" * 40)
        self.assertFalse(port.item.marker["active"])
        self.assertIn('"active":false', port.writes[0][1])
        self.assertEqual(port.writes[1], ("status", AVAILABLE))
        failed = FakePort(snapshot())
        failed.fail_status = True
        result = execute(1191, failed, decision,
                         feature_enabled=True, dry_run=False)
        self.assertEqual(result.reason, "port_failure_or_partial_write")
        self.assertFalse(failed.item.marker["active"])
        self.assertEqual(failed.item.status, RECOVERY)
        # Tras una escritura parcial, revalidar bajo lock y completar sólo
        # el estado pendiente, sin otro marker ni modificación de la rama.
        self.assertEqual(execute(1191, failed, decision,
                                 feature_enabled=True).reason,
                         "dry_run_reconcile")
        failed.fail_status = False
        again = execute(1191, failed, decision,
                        feature_enabled=True, dry_run=False)
        self.assertEqual(again.reason, "partial_reconciled")
        self.assertEqual(len(failed.writes), 2)
        self.assertEqual(failed.item.status, AVAILABLE)
        self.assertEqual(failed.item.branch_sha, "a" * 40)
        # Port.status puede devolver None/ACK sin persistir la etiqueta.
        # Ni release normal ni reconciliación parcial pueden informar éxito.
        for partial in (False, True):
            with self.subTest(noop_available=partial):
                port = FakePort(snapshot())
                if partial:
                    port.item = replace(port.item, marker={
                        **port.item.marker, "active": False,
                        "reason": "auto-inactivity-release"})
                port.noop_available = True
                result = execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual(result.reason, "unverified_release")
                self.assertFalse(result.wrote)
                self.assertEqual(port.item.status, RECOVERY)
        # Reintento de nota de recuperación ya publicada tras fallo de
        # etiqueta: debe reconciliar sin duplicar el comentario.
        recover = FakePort(snapshot(recovery=False))
        recover.fail_status = True
        self.assertEqual(execute(1191, recover, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "port_failure_or_partial_write")
        self.assertEqual(len(recover.writes), 1)
        self.assertEqual(recover.item.status, "estado: en revisión")
        recover.fail_status = False
        self.assertEqual(execute(1191, recover, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "recovery_marked")
        self.assertEqual(len(recover.writes), 2)
        self.assertEqual(recover.writes[0][0], "comment")
        self.assertEqual(recover.writes[1], ("status", RECOVERY))
        self.assertEqual(recover.item.recovery_since, recover.label_at)
        # Falla etiqueta a +41 y reintenta a +61: no liberar hasta +71.
        late = FakePort(snapshot(recovery=False))
        late.fail_status = True
        self.assertEqual(execute(1191, late, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "port_failure_or_partial_write")
        original_note = late.note_at
        late.fail_status = False
        late.item = replace(late.item, now=START + timedelta(minutes=61))
        self.assertEqual(execute(1191, late, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "recovery_marked")
        self.assertEqual(late.note_at, original_note)
        self.assertEqual(late.label_at, START + timedelta(minutes=61))
        self.assertEqual(late.item.recovery_since, late.label_at)
        count = len(late.writes)
        self.assertFalse(execute(1191, late, decision,
                                 feature_enabled=True, dry_run=False).wrote)
        self.assertEqual(len(late.writes), count)
        late.item = replace(late.item, now=START + timedelta(minutes=70))
        self.assertFalse(execute(1191, late, decision,
                                 feature_enabled=True, dry_run=False).wrote)
        late.item = replace(late.item, now=START + timedelta(minutes=71))
        self.assertEqual(execute(1191, late, decision,
                                 feature_enabled=True, dry_run=False).reason,
                         "released")
        # No permitir release con nota/etiqueta inconsistente o API parcial.
        for kind in ("no_note", "no_label", "wrong_actor", "partial_timeline",
                     "untrusted_timeline", "duplicate_label", "old_since"):
            with self.subTest(untrusted_label=kind):
                port = FakePort(snapshot())
                if kind == "no_note":
                    port.note_at = None
                elif kind == "no_label":
                    port.label_at = None
                elif kind == "wrong_actor":
                    port.label_author = "malicious-user"
                elif kind == "partial_timeline":
                    port.label_complete = False
                elif kind == "untrusted_timeline":
                    port.label_authenticated = False
                elif kind == "duplicate_label":
                    port.label_count = 2
                else:
                    port.item = replace(port.item,
                        recovery_since=START + timedelta(minutes=31))
                result = execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertFalse(result.wrote)
                self.assertEqual(port.writes, [])
        # Actor dudoso, consulta incompleta, más de una nota => fail closed.
        for attr, value in (("note_author", "attacker"),
                            ("note_complete", False),
                            ("note_authenticated", False),
                            ("note_count", 2)):
            with self.subTest(untrusted_note=attr):
                fake = FakePort(snapshot(recovery=False))
                fake.note_at = fake.item.now
                setattr(fake, attr, value)
                result = execute(1191, fake, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertFalse(result.wrote)
                self.assertEqual(fake.writes, [])
        # The idempotent partial-marker path also vetoes clock regressions.
        partial = FakePort(replace(snapshot(), marker={**snapshot().marker,
            "active": False, "reason": "auto-inactivity-release"}))
        partial.locked_clock_drift = (2, 35)
        self.assertFalse(execute(1191, partial, decision,
                                 feature_enabled=True, dry_run=False).wrote)
        self.assertEqual(partial.writes, [])


    def test_result_tracks_none_partial_complete_and_unknown(self):
        """wrote=False no permite descartar efectos parcialmente persistidos."""
        port = FakePort(snapshot(recovery=False))
        disabled = execute(1191, port, decision)
        self.assertEqual((disabled.wrote, disabled.write_state),
                         (False, "none"))
        simulated = execute(1191, port, decision, feature_enabled=True)
        self.assertEqual((simulated.wrote, simulated.write_state),
                         (False, "none"))
        self.assertEqual(port.writes, [])

        success = execute(1191, port, decision,
                          feature_enabled=True, dry_run=False)
        self.assertEqual((success.reason, success.wrote, success.write_state),
                         ("recovery_marked", True, "complete"))
        self.assertEqual(len(port.writes), 2)

        for recovery, minute in ((False, 20), (True, 35)):
            with self.subTest(partial_after_append=recovery):
                partial = FakePort(snapshot(recovery=recovery))
                partial.locked_clock_drift = (3, minute)
                outcome = execute(1191, partial, decision,
                                  feature_enabled=True, dry_run=False)
                self.assertFalse(outcome.wrote)
                self.assertEqual(outcome.write_state, "partial")
                self.assertEqual(len(partial.writes), 1)

        failed = FakePort(snapshot())
        failed.fail_status = True
        error = execute(1191, failed, decision,
                        feature_enabled=True, dry_run=False)
        self.assertEqual((error.wrote, error.write_state),
                         (False, "unknown"))
        self.assertEqual(len(failed.writes), 1)
        self.assertFalse(failed.item.marker["active"])

        for partial_marker in (False, True):
            with self.subTest(ack_without_persistence=partial_marker):
                port = FakePort(snapshot())
                if partial_marker:
                    port.item = replace(port.item, marker={
                        **port.item.marker, "active": False,
                        "reason": "auto-inactivity-release"})
                port.noop_available = True
                result = execute(1191, port, decision,
                                 feature_enabled=True, dry_run=False)
                self.assertEqual((result.reason, result.wrote, result.write_state),
                                 ("unverified_release", False, "partial"))

        unverified = FakePort(snapshot(recovery=False))
        unverified.label_author = "untrusted-actor"
        result = execute(1191, unverified, decision,
                         feature_enabled=True, dry_run=False)
        self.assertEqual((result.reason, result.wrote, result.write_state),
                         ("unverified_recovery_since", False, "partial"))
        self.assertEqual(len(unverified.writes), 2)

        failed.fail_status = False
        reconciled = execute(1191, failed, decision,
                             feature_enabled=True, dry_run=False)
        self.assertEqual((reconciled.reason, reconciled.wrote,
                          reconciled.write_state),
                         ("partial_reconciled", True, "complete"))

        with self.assertRaises(ValueError):
            Result("release", "contradiction", True)
        with self.assertRaises(ValueError):
            Result("unknown", "contradiction", write_state="complete")



if __name__ == "__main__":
    unittest.main()
