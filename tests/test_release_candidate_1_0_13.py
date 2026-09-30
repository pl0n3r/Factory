#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.13."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1013Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_is_at_least_1_0_13_and_keeps_acceptance_fix(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        self.assertRegex(payload["version"], r"^\d+\.\d+\.\d+$")
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 13))

        workflow = (
            self.root / ".github/workflows/aceptacion.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'gh api --paginate "repos/$REPOSITORY/commits/$SHA/check-runs?per_page=100" --slurp',
            workflow,
        )
        self.assertIn(
            "jq '{check_runs: [.[].check_runs[]]}' /tmp/check-pages.json > /tmp/checks.json",
            workflow,
        )

    def test_candidate_contains_acceptance_check_pagination_fix(self) -> None:
        workflow = (
            self.root / ".github/workflows/aceptacion.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'gh api --paginate "repos/$REPOSITORY/commits/$SHA/check-runs?per_page=100" --slurp',
            workflow,
        )
        self.assertIn(
            "jq '{check_runs: [.[].check_runs[]]}' /tmp/check-pages.json > /tmp/checks.json",
            workflow,
        )

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
