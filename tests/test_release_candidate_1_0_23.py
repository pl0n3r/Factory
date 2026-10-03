#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.23."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1023Tests(unittest.TestCase):
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

    def _run_canonical_targets(
        self,
        criterion_id: str,
        targets: tuple[str, ...],
    ) -> None:
        Criterion, run_named_test = self._acceptance_tools()
        for target in targets:
            with self.subTest(target=target):
                run_named_test(
                    Criterion(criterion_id, "test", target),
                    self.root,
                )

    def test_candidate_version_is_1_0_23(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.23"})

    def test_candidate_keeps_1_0_22_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_22.py::ReleaseCandidate1022Tests::"
                "test_candidate_version_is_1_0_22",
                "tests/test_release_candidate_1_0_22.py::ReleaseCandidate1022Tests::"
                "test_candidate_keeps_1_0_21_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_22.py::ReleaseCandidate1022Tests::"
                "test_candidate_keeps_top_level_empty_permissions_repair",
                "tests/test_release_candidate_1_0_22.py::ReleaseCandidate1022Tests::"
                "test_candidate_keeps_reusable_permission_envelope_sweep",
                "tests/test_release_candidate_1_0_22.py::ReleaseCandidate1022Tests::"
                "test_candidate_requires_new_exact_sha_human_gate",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_22.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 22))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.22"})',
            historical,
        )

    def test_candidate_keeps_bounded_observer_convergence_contract(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_observar_workflow_contract.py::ObserverWorkflowContractTests::"
                "test_convergence_inputs_default_to_one_shot_and_are_bounded",
                "tests/test_observar_workflow_contract.py::ObserverWorkflowContractTests::"
                "test_bounded_convergence_reuses_exact_observation_and_reports_only_final_result",
                "tests/test_observar_workflow_contract.py::ObserverWorkflowContractTests::"
                "test_invalid_convergence_inputs_fail_closed_before_checkout",
                "tests/test_observar_workflow_contract.py::ObserverWorkflowContractTests::"
                "test_trust_boundary_and_permissions_remain_fail_closed",
            ),
        )

    def test_candidate_requires_new_exact_sha_human_gate(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_v2_release_target_must_match_expected_sha",
            ),
        )

        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("GATE_ISSUE: $" + "{{ inputs.gate_issue }}", workflow)
        self.assertIn("EXPECTED_SHA: $" + "{{ inputs.expected_sha }}", workflow)
        for old_gate in ("#851", "#879", "#895", "#901"):
            self.assertNotIn(old_gate, workflow)


if __name__ == "__main__":
    unittest.main()
