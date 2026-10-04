#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.25."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1025Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_25(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        parts = payload["version"].split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))
        self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 25))

    def test_candidate_keeps_1_0_24_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_24.py::ReleaseCandidate1024Tests::"
                "test_candidate_version_is_1_0_24",
                "tests/test_release_candidate_1_0_24.py::ReleaseCandidate1024Tests::"
                "test_candidate_keeps_1_0_23_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_24.py::ReleaseCandidate1024Tests::"
                "test_candidate_keeps_reviewer_rate_limit_fallback_fail_closed",
                "tests/test_release_candidate_1_0_24.py::ReleaseCandidate1024Tests::"
                "test_candidate_keeps_reviewer_rate_limit_transport_backward_compatible",
                "tests/test_release_candidate_1_0_24.py::ReleaseCandidate1024Tests::"
                "test_candidate_keeps_bounded_public_check_pagination_contract",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_24.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 24))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.24"})',
            historical,
        )

    def test_candidate_keeps_bounded_public_check_pagination_contract(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_public_check_transport_paginates_bounded_exact_head_evidence",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_public_check_transport_fails_closed_above_bound_or_inconsistent_pages",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_public_check_transport_remains_anonymous_and_bounded",
                "tests/test_politica_kit.py::T::"
                "test_rate_limit_fallback_never_applies_with_open_blocking_finding_or_other_phase_or_other_head",
            ),
        )

    def test_candidate_keeps_release_gate_and_window_guarantees(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_release_candidate_1_0_24.py::ReleaseCandidate1024Tests::"
                "test_candidate_keeps_release_gate_and_window_guarantees",
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_head_drift_touching_release_machinery_requires_new_gate",
                "tests/test_release_window_payload_bound.py::ReleaseWindowPayloadBoundTests::"
                "test_release_window_parser_keeps_two_megabyte_fail_closed_bound",
            ),
        )


if __name__ == "__main__":
    unittest.main()
