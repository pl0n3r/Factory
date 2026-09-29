#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.9."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate109Tests(unittest.TestCase):
    """Fija versión, contrato cross-main y frontera humana de publicación."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_9(self) -> None:
        """La fuente canónica declara exactamente 1.0.9."""
        payload = json.loads(
            (self.root / "config" / "version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.9"})

    def test_candidate_contains_cross_main_bootstrap_contract(self) -> None:
        """El candidato conserva la reconciliación cross-main de GrindFlow #188."""
        coordinator = (
            self.root / "scripts" / "bootstrap_coordination.py"
        ).read_text(encoding="utf-8")
        regressions = (
            self.root / "tests" / "test_bootstrap_coordination.py"
        ).read_text(encoding="utf-8")

        production_contract = (
            'historical=parse_marker(pr.get("body"))',
            'self.main_descends_from(name,historical["expected_main_sha"],req["expected_main_sha"])',
            "def commit_matches_marker(",
            "or len(parents)!=1",
            'or parents[0].get("sha")!=previous',
            "def materialize_replacement(",
            '"parents":[expected]',
            "Supersedes bootstrap PR #{legacy_pr}.",
        )
        for marker in production_contract:
            self.assertIn(marker, coordinator)

        regression_contract = (
            "test_historical_legacy_identity_is_verified_independently_from_new_request",
            "test_legacy_from_previous_main_can_be_reconciled_against_current_exact_main",
            "test_grindflow_188_real_sha_transition",
            "test_cross_main_legacy_rejects_non_linear_history",
            "f5b74ddff10569023dd1b2a73de5dd8937bc3192",
            "4e28fbb277c3642e48535a005540d159c2c5c21e",
            "7f5929a70990574453855e02d8c5021bf97a646b",
        )
        for marker in regression_contract:
            self.assertIn(marker, regressions)

    def test_candidate_keeps_human_release_boundary(self) -> None:
        """Preparar 1.0.9 no publica: exige dispatch, SHA exacto y gate humano."""
        workflow = (
            self.root / ".github" / "workflows" / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("expected_sha:", workflow)
        self.assertIn("gate_issue:", workflow)
        self.assertNotIn("\npush:", workflow)


if __name__ == "__main__":
    unittest.main()
