"""Pruebas offline; ningún acceso a GitHub ni credenciales de producción."""
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from scripts.lease_release_executor import (
    AVAILABLE, RECOVERY, Snapshot, execute,
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


class FakePort:
    def __init__(self, item):
        self.item = item
        self.writes = []
        self.locked = False
        self.drift = None
        self.fail_status = False
        self.locked_clock_drift = None  # (locked_read_ordinal, absolute_minute)
        self.locked_reads = 0

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

    def append(self, issue, body, expected):
        assert self.locked and expected is self.item
        self.writes.append(("comment", body))
        if body.startswith("<!-- condor-reserva "):
            self.item = replace(self.item, marker={**self.item.marker,
                "active": False, "reason": "auto-inactivity-release"})

    def status(self, issue, status, expected):
        assert self.locked and expected is self.item
        if self.fail_status:
            raise RuntimeError("partial")
        self.writes.append(("status", status))
        self.item = replace(self.item, status=status)


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

    def test_mark_recovery_and_release_revalidate_under_shared_lock(self):
        port = FakePort(snapshot(recovery=False))
        answer = execute(1191, port, decision, feature_enabled=True,
                         dry_run=False)
        self.assertEqual(answer.reason, "recovery_marked")
        self.assertEqual(port.item.status, RECOVERY)
        self.assertEqual(len(port.writes), 2)
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
        # The idempotent partial-marker path also vetoes clock regressions.
        partial = FakePort(replace(snapshot(), marker={**snapshot().marker,
            "active": False, "reason": "auto-inactivity-release"}))
        partial.locked_clock_drift = (2, 35)
        self.assertFalse(execute(1191, partial, decision,
                                 feature_enabled=True, dry_run=False).wrote)
        self.assertEqual(partial.writes, [])


if __name__ == "__main__":
    unittest.main()
