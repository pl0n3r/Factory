#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.26."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1026Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_26(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.26"})

    def test_candidate_keeps_1_0_25_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_25.py::ReleaseCandidate1025Tests::"
                "test_candidate_version_is_1_0_25",
                "tests/test_release_candidate_1_0_25.py::ReleaseCandidate1025Tests::"
                "test_candidate_keeps_1_0_24_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_25.py::ReleaseCandidate1025Tests::"
                "test_candidate_keeps_bounded_public_check_pagination_contract",
                "tests/test_release_candidate_1_0_25.py::ReleaseCandidate1025Tests::"
                "test_candidate_keeps_release_gate_and_window_guarantees",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_25.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 25))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.25"})',
            historical,
        )

    def test_candidate_keeps_authenticated_bounded_public_check_transport(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_rate_limit_fallback_reads_authenticated_checks_with_github_token",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_authenticated_check_transport_paginates_bounded_exact_head_evidence",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_authenticated_check_transport_fails_closed_above_bound_or_inconsistent_pages",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_authenticated_check_transport_cannot_regress_to_anonymous_curl",
            ),
        )

    def test_candidate_keeps_pr_label_write_split_contract(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_etiquetas_workflow_contract.py::"
                "EtiquetasWorkflowContractTests::"
                "test_pr_validate_job_has_minimum_write_authority",
                "tests/test_etiquetas_workflow_contract.py::"
                "EtiquetasWorkflowContractTests::"
                "test_non_pr_job_remains_read_only",
                "tests/test_etiquetas_workflow_contract.py::"
                "EtiquetasWorkflowContractTests::"
                "test_pr_and_non_pr_jobs_are_mutually_exclusive_and_keep_labels_check_name",
                "tests/test_etiquetas_workflow_contract.py::"
                "EtiquetasWorkflowContractTests::"
                "test_pr_validate_keeps_safe_label_inheritance_without_changing_sweep",
            ),
        )

    def test_candidate_keeps_false_available_parent_fail_closed_contract(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_labels_kit.py::LabelsKitTests::"
                "test_unknown_dimension_like_state_does_not_default_issue_to_available",
                "tests/test_labels_kit.py::LabelsKitTests::"
                "test_unknown_dimension_like_type_or_priority_fails_closed_without_fabricating_dimension",
                "tests/test_dispatcher_v2.py::DispatcherV2Tests::"
                "test_available_parent_without_executable_contract_is_repaired_and_skipped",
                "tests/test_dispatcher_v2.py::DispatcherV2Tests::"
                "test_legacy_executable_leaf_normalization_from_943_still_retries_once",
            ),
        )


if __name__ == "__main__":
    unittest.main()
