#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.18."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1018Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_18(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.18"})

    def test_candidate_preserves_release_open_pull_feedback(self) -> None:
        implementation = (
            self.root / "scripts/coordinar_trabajo.py"
        ).read_text(encoding="utf-8")
        regressions = (
            self.root / "tests/test_coordinar_trabajo.py"
        ).read_text(encoding="utf-8")

        for token in (
            'raise CoordinationError(',
            '"No se puede liberar la reserva mientras existan PR abiertos "',
            '"si eres el OWNER y corresponde cerrar esa línea de trabajo."',
        ):
            self.assertIn(token, implementation)
        for test_name in (
            "test_normal_release_with_open_pull_fails_closed_and_explains_blocker",
            "test_force_release_with_open_pull_preserves_existing_semantics",
            "test_normal_release_without_open_pull_still_releases",
        ):
            self.assertIn(f"def {test_name}(", regressions)

    def test_candidate_preserves_factory_release_authority_canonicalization(self) -> None:
        implementation = (
            self.root / "seguridad/puertas_humanas.py"
        ).read_text(encoding="utf-8")
        regressions = (
            self.root / "seguridad/test_puertas_humanas.py"
        ).read_text(encoding="utf-8")

        for token in (
            'gate["category"] == "factory-release"',
            'set(target) == {"version", "sha"}',
            '"channel": "v1"',
            '"safe_default": gate["safe_default"]',
        ):
            self.assertIn(token, implementation)
        for test_name in (
            "test_factory_release_authority_ignores_explanatory_copy",
            "test_release_1017_race_converges_without_body_edit",
            "test_factory_release_target_remains_part_of_identity",
            "test_factory_release_incompatible_machine_contract_fails_closed",
            "test_non_release_authority_still_uses_effect",
        ):
            self.assertIn(f"def {test_name}(", regressions)

    def test_previous_candidate_is_historical_and_keeps_1_0_17_guarantees(self) -> None:
        historical = (
            self.root / "tests/test_release_candidate_1_0_17.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "def test_candidate_is_at_least_1_0_17_and_keeps_1_0_17_guarantees(",
            historical,
        )
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 17))",
            historical,
        )
        for call in (
            "self.test_candidate_packages_performance_classifier_boundary()",
            "self.test_candidate_preserves_sonar_hardening()",
            "self.test_candidate_keeps_human_release_boundary()",
        ):
            self.assertIn(call, historical)

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        expected_sha_token = "EXPECTED_SHA: $" + "{{ inputs.expected_sha }}"
        gate_issue_token = "GATE_ISSUE: $" + "{{ inputs.gate_issue }}"
        for token in (
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: preflight",
            expected_sha_token,
            gate_issue_token,
        ):
            self.assertIn(token, workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
