#!/usr/bin/env python3
"""Regresiones mínimas del candidato Factory 1.0.11."""

import json
import unittest
from pathlib import Path

from scripts import coordinar_trabajo as coordinator


class ReleaseCandidate1011Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def tearDown(self) -> None:
        coordinator.configure_profile("es")

    def test_candidate_version_is_1_0_11(self) -> None:
        source = self.root / "config" / "version.json"
        self.assertEqual(json.loads(source.read_text()), {"version": "1.0.11"})

    def test_candidate_contains_labels_startup_fix(self) -> None:
        workflow = (self.root / ".github/workflows/etiquetas.yml").read_text()
        minimum = (
            "    permissions:\n"
            "      contents: read\n"
            "      issues: write\n"
            "      pull-requests: read\n"
        )
        self.assertIn(minimum, workflow)
        self.assertNotIn("pull-requests: write", workflow)

    def test_candidate_contains_profile_invariant_contract_renewal(self) -> None:
        reservation = "0b9040ef-85eb-5c31-b5b9-9722a07675bf"
        expected = ("renovar-contrato", reservation)
        for profile in ("es", "en"):
            coordinator.configure_profile(profile)
            self.assertEqual(
                coordinator.parse_comment_command(f"/renovar-contrato {reservation}"),
                expected,
            )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command("/renovar-contrato invalid")

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (self.root / ".github/workflows/release-bootstrap.yml").read_text()
        required = ("workflow_dispatch:", "expected_sha:", "gate_issue:", "needs: preflight")
        self.assertTrue(all(token in workflow for token in required))
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
