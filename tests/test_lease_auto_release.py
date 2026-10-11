"""Regresiones del decisor puro para liberar reservas; no usa red ni GitHub real."""
from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from scripts.lease_auto_release import (
    RECOVERY, RESERVED, REVIEW, Evidence, decide,
)

START = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
ID = "945515c7-78b2-4dc6-9803-06808fd0abb8"


def fixture(minute: int = 29, *, status: str = RESERVED,
            recovery_minute: int | None = None) -> Evidence:
    return Evidence(
        now=START + timedelta(minutes=minute),
        last_activity_at=START,
        recovery_since=(
            START + timedelta(minutes=recovery_minute)
            if recovery_minute is not None else None
        ),
        status=status, phase="construccion",
        issue_open=True, v3_active=True, lease_id=ID,
        owner="pl0n3r", branch_sha="a" * 40,
        branch_present=True, evidence_complete=True, trusted_phase=True,
        kill_switch_running=True, ci_running=False,
        changes_requested=False, owner_recovered=False,
        rate_remaining=20, rate_limit=100,
    )


class LeaseAutoReleaseTests(unittest.TestCase):
    def test_stale_grace_and_fail_closed_guards(self) -> None:
        # Exactitud del contrato: detección a los 30 min; liberación SOLO
        # tras 10 min desde la transición verificable a recuperación.
        expected = (
            (29, RESERVED, None, "wait", 11),
            (30, RESERVED, None, "mark_recovery", 10),
            (39, RECOVERY, 30, "wait", 1),
            (40, RECOVERY, 30, "release", 0),
            (49, RECOVERY, 40, "wait", 1),
            (50, RECOVERY, 40, "release", 0),
            (44, RECOVERY, 35, "wait", 1),
            (45, RECOVERY, 35, "release", 0),
        )
        for minute, state, recovered, action, remaining in expected:
            with self.subTest(minute=minute, state=state):
                result = decide(fixture(minute, status=state,
                                        recovery_minute=recovered))
                self.assertEqual(result.action, action)
                self.assertEqual(result.libera_en_min, remaining)

        for changed in (
            {"kill_switch_running": False},
            {"ci_running": True},
            {"changes_requested": True},
            {"phase": "live"},
            {"owner_recovered": True},
            {"issue_open": False},
            {"v3_active": False},
            {"branch_present": False},
            {"status": "estado: bloqueado"},
        ):
            with self.subTest(block=changed):
                self.assertNotEqual(
                    decide(replace(fixture(60, status=RECOVERY,
                                           recovery_minute=30), **changed)).action,
                    "release",
                )
        for changed in (
            {"evidence_complete": False},
            {"trusted_phase": False},
            {"rate_remaining": 19},
            {"rate_remaining": None},
            {"rate_remaining": True},
            {"lease_id": "invalid"},
            {"branch_sha": "not-a-sha"},
            {"last_activity_at": None},
            {"last_activity_at": START.replace(tzinfo=None)},
            {"last_activity_at": START + timedelta(hours=2)},
            {"recovery_since": None},
            {"recovery_since": START.replace(tzinfo=None)},
            {"recovery_since": START - timedelta(minutes=1)},
            {"recovery_since": START + timedelta(minutes=61)},
            {"ci_running": None},
            {"status": None},
        ):
            with self.subTest(unknown=changed):
                self.assertNotEqual(
                    decide(replace(fixture(60, status=RECOVERY,
                                           recovery_minute=30), **changed)).action,
                    "release",
                )

    def test_original_owner_return_or_competing_evidence_preserves_lease(self):
        case = fixture(50, status=RECOVERY, recovery_minute=30)
        self.assertEqual(
            decide(replace(case, last_activity_at=START + timedelta(minutes=39))).action,
            "unknown",
        )
        self.assertEqual(decide(replace(case, owner_recovered=True)).action, "wait")
        self.assertEqual(decide(replace(case, ci_running=True)).reason,
                         "protected_or_active_work")
        self.assertEqual(decide(replace(case, changes_requested=True)).action, "wait")

    def test_budget_exact_20_percent_and_unknown_are_distinct(self):
        e = fixture(50, status=RECOVERY, recovery_minute=30)
        self.assertEqual(decide(e).action, "release")
        self.assertEqual(decide(replace(e, rate_remaining=19)).action, "unknown")
        self.assertEqual(decide(replace(e, rate_limit=0)).action, "unknown")
        self.assertEqual(decide(replace(e, rate_remaining=101)).action, "unknown")

    def test_no_io_or_external_authority_is_derived(self):
        e = fixture(45, status=REVIEW)
        self.assertEqual(decide(e).action, "mark_recovery")
        self.assertEqual(e.status, REVIEW)
        self.assertEqual(e.branch_sha, "a" * 40)
        self.assertNotEqual(decide(replace(e, phase="UNKNOWN")).action, "release")
        self.assertNotEqual(decide(replace(e, trusted_phase=False)).action, "release")


if __name__ == "__main__":
    unittest.main()
