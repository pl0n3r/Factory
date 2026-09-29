#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.9."""

from __future__ import annotations

import json
import re
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
        """El candidato conserva autenticidad histórica y cadena legacy lineal."""
        bootstrap = (
            self.root / "scripts" / "bootstrap_coordination.py"
        ).read_text(encoding="utf-8")
        regressions = (
            self.root / "tests" / "test_bootstrap_coordination.py"
        ).read_text(encoding="utf-8")

        for marker in (
            "def main_descends_from",
            "def legacy_marker",
            "def commit_matches_marker",
            "def materialize_replacement",
            "historical=parse_marker",
            "previous=expected",
            "len(parents)!=1",
            "parents[0].get(\"sha\")!=previous",
        ):
            self.assertIn(marker, bootstrap)

        for marker in (
            "test_legacy_from_previous_main_can_be_reconciled_against_current_exact_main",
            "test_grindflow_188_real_sha_transition",
            "test_cross_main_legacy_rejects_non_linear_history",
            "f5b74ddff10569023dd1b2a73de5dd8937bc3192",
            "e9d3daafd407abd4d375f5b7b344e4316b8935eb",
            "3282f81e8bdec055bd91e2347f43a4c2bd9e6125",
            "7f5929a70990574453855e02d8c5021bf97a646b",
        ):
            self.assertIn(marker, regressions)

    def test_candidate_keeps_human_release_boundary(self) -> None:
        """Preparar 1.0.9 no elimina la puerta humana de publicación."""
        workflow = (
            self.root / ".github" / "workflows" / "release-bootstrap.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("expected_sha:", workflow)
        self.assertIn("gate_issue:", workflow)
        self.assertIn("needs: preflight", workflow)
        self.assertIsNone(re.search(r"(?m)^\s{2}push\s*:", workflow))


if __name__ == "__main__":
    unittest.main()
