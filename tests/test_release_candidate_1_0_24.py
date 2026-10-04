#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.24."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1024Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_24(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.24"})

    def test_candidate_keeps_1_0_23_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_23.py::ReleaseCandidate1023Tests::"
                "test_candidate_version_is_1_0_23",
                "tests/test_release_candidate_1_0_23.py::ReleaseCandidate1023Tests::"
                "test_candidate_keeps_1_0_22_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_23.py::ReleaseCandidate1023Tests::"
                "test_candidate_keeps_bounded_observer_convergence_contract",
                "tests/test_release_candidate_1_0_23.py::ReleaseCandidate1023Tests::"
                "test_candidate_requires_new_exact_sha_human_gate",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_23.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 23))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.23"})',
            historical,
        )

    def test_candidate_keeps_release_gate_and_window_guarantees(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_version_gate_authorizes_current_head_when_version_matches_and_checks_green",
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_head_drift_touching_release_machinery_requires_new_gate",
                "tests/test_release_window_expired_decision.py::ReleaseWindowExpiredDecisionTests::"
                "test_newer_b_gate_supersedes_older_active_a_window",
                "tests/test_release_window_expired_decision.py::ReleaseWindowExpiredDecisionTests::"
                "test_latest_gate_is_selected_per_version_not_globally",
                "tests/test_release_window_payload_bound.py::ReleaseWindowPayloadBoundTests::"
                "test_release_window_parser_keeps_two_megabyte_fail_closed_bound",
            ),
        )

    def test_candidate_keeps_reviewer_rate_limit_fallback_fail_closed(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_politica_kit.py::T::"
                "test_single_rate_limit_is_not_enough_to_pass",
                "tests/test_politica_kit.py::T::"
                "test_rate_limit_plus_failed_retry_passes_in_construction_when_other_gates_green",
                "tests/test_politica_kit.py::T::"
                "test_rate_limit_fallback_never_applies_with_open_blocking_finding_or_other_phase_or_other_head",
                "tests/test_politica_kit.py::T::"
                "test_rate_limit_before_head_commit_is_not_exact_head_evidence",
            ),
        )

    def test_candidate_keeps_reviewer_rate_limit_transport_backward_compatible(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-05",
            (
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_rate_limit_fallback_keeps_legacy_caller_permissions",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_rate_limit_fallback_reads_public_checks_without_token",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_rate_limit_fallback_audit_is_read_only",
                "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
                "test_template_policy_caller_stays_legacy_compatible",
                "tests/test_politica_kit.py::T::"
                "test_single_rate_limit_is_not_enough_to_pass",
                "tests/test_politica_kit.py::T::"
                "test_rate_limit_fallback_never_applies_with_open_blocking_finding_or_other_phase_or_other_head",
            ),
        )


if __name__ == "__main__":
    unittest.main()
