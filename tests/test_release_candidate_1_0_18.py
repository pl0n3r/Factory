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

    @staticmethod
    def _acceptance_tools():
        try:
            from scripts.aceptacion_kit import Criterion, run_named_test
        except ModuleNotFoundError as exc:
            if exc.name != "scripts":
                raise
            from aceptacion_kit import Criterion, run_named_test
        return Criterion, run_named_test

    def test_candidate_version_is_1_0_18(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.18"})

    def test_candidate_preserves_release_open_pull_feedback(self) -> None:
        Criterion, run_named_test = self._acceptance_tools()

        for target in (
            "tests/test_coordinar_trabajo.py::ReleaseOpenPullFeedbackTests::"
            "test_normal_release_with_open_pull_fails_closed_and_explains_blocker",
            "tests/test_coordinar_trabajo.py::ReleaseOpenPullFeedbackTests::"
            "test_force_release_with_open_pull_preserves_existing_semantics",
            "tests/test_coordinar_trabajo.py::ReleaseOpenPullFeedbackTests::"
            "test_normal_release_without_open_pull_still_releases",
        ):
            run_named_test(Criterion("AC-01", "test", target), self.root)

    def test_candidate_preserves_factory_release_authority_canonicalization(
        self,
    ) -> None:
        Criterion, run_named_test = self._acceptance_tools()

        for target in (
            "seguridad/test_puertas_humanas.py::GateDedupTests::"
            "test_factory_release_authority_ignores_explanatory_copy",
            "seguridad/test_puertas_humanas.py::GateDedupTests::"
            "test_release_1017_race_converges_without_body_edit",
            "seguridad/test_puertas_humanas.py::GateDedupTests::"
            "test_factory_release_target_remains_part_of_identity",
            "seguridad/test_puertas_humanas.py::GateDedupTests::"
            "test_factory_release_incompatible_machine_contract_fails_closed",
            "seguridad/test_puertas_humanas.py::GateDedupTests::"
            "test_non_release_authority_still_uses_effect",
        ):
            run_named_test(Criterion("AC-02", "test", target), self.root)

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
