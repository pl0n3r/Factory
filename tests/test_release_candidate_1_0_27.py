#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.27."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1027Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_27(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.27"})

    def test_candidate_keeps_1_0_26_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_26.py::ReleaseCandidate1026Tests::"
                "test_candidate_version_is_1_0_26",
                "tests/test_release_candidate_1_0_26.py::ReleaseCandidate1026Tests::"
                "test_candidate_keeps_1_0_25_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_26.py::ReleaseCandidate1026Tests::"
                "test_candidate_keeps_authenticated_bounded_public_check_transport",
                "tests/test_release_candidate_1_0_26.py::ReleaseCandidate1026Tests::"
                "test_candidate_keeps_pr_label_write_split_contract",
                "tests/test_release_candidate_1_0_26.py::ReleaseCandidate1026Tests::"
                "test_candidate_keeps_false_available_parent_fail_closed_contract",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_26.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 26))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.26"})',
            historical,
        )

    def test_candidate_keeps_authenticated_policy_transport_contract(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_release_candidate_1_0_26.py::ReleaseCandidate1026Tests::"
                "test_candidate_keeps_authenticated_bounded_public_check_transport",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_rate_limit_fallback_reads_authenticated_checks_with_github_token",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_authenticated_check_transport_cannot_regress_to_anonymous_curl",
            ),
        )

    def test_candidate_keeps_release_gate_and_window_separation(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_release_candidate_1_0_25.py::ReleaseCandidate1025Tests::"
                "test_candidate_keeps_release_gate_and_window_guarantees",
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_head_drift_touching_release_machinery_requires_new_gate",
                "tests/test_release_window_payload_bound.py::ReleaseWindowPayloadBoundTests::"
                "test_release_window_parser_keeps_two_megabyte_fail_closed_bound",
            ),
        )


if __name__ == "__main__":
    unittest.main()
