#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.16."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1016Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_16(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.16"})

    def test_candidate_preserves_recovery_required_reacquisition(self) -> None:
        implementation = (
            self.root / "scripts/coordinar_trabajo.py"
        ).read_text(encoding="utf-8")
        regressions = (
            self.root / "tests/test_coordinar_trabajo.py"
        ).read_text(encoding="utf-8")

        for token in (
            "recovery_required = STATUS_RECOVERY in label_names(issue)",
            "lock_branch = recovery_lock_branch(issue_number)",
            "latest = active_reservation(api, issue_number)",
            "return recover_stale_work(",
        ):
            self.assertIn(token, implementation)

        for test_name in (
            "test_recovery_required_can_be_reclaimed_after_recent_branch_activity",
            "test_recovery_required_reuses_existing_branch_and_pr",
        ):
            self.assertIn(f"def {test_name}(", regressions)

        self.assertIn(
            "reservation_from_pr_body(api.pulls[15][\"body\"])", regressions
        )

    def test_candidate_preserves_fresh_lease_fail_closed(self) -> None:
        regressions = (
            self.root / "tests/test_coordinar_trabajo.py"
        ).read_text(encoding="utf-8")
        start = regressions.index(
            "def test_fresh_reservation_cannot_be_recovered"
        )
        end = regressions.index(
            "def test_recovery_required_can_be_reclaimed_after_recent_branch_activity",
            start,
        )
        block = regressions[start:end]
        self.assertIn('reserve_work(api, 12, "otra-sesion", "MEMBER")', block)
        self.assertIn("self.assertIsNone(result)", block)
        self.assertIn('reservation["reservation_id"], SESSION_A', block)

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: preflight",
        ):
            self.assertIn(token, workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
