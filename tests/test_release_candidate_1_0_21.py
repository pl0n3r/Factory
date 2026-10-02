#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.21."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1021Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_21(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.21"})

    def test_candidate_keeps_1_0_20_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_20.py::ReleaseCandidate1020Tests::"
                "test_candidate_version_is_1_0_20",
                "tests/test_release_candidate_1_0_20.py::ReleaseCandidate1020Tests::"
                "test_candidate_keeps_1_0_19_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_20.py::ReleaseCandidate1020Tests::"
                "test_candidate_requires_consumer_permission_preflight_and_rollback_runbook",
                "tests/test_release_candidate_1_0_20.py::ReleaseCandidate1020Tests::"
                "test_candidate_requires_post_release_startup_failure_watchdog",
                "tests/test_release_candidate_1_0_20.py::ReleaseCandidate1020Tests::"
                "test_candidate_keeps_human_release_boundary_and_rejects_reused_1_0_19_gate",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_20.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 20))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.20"})',
            historical,
        )

    def test_candidate_keeps_empty_permissions_preflight_fail_closed(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_empty_inline_job_permissions_are_supported_as_no_permissions",
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_non_empty_inline_permissions_remain_fail_closed",
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_current_factory_ci_empty_permissions_parse_to_contents_read_envelope",
            ),
        )

    def test_candidate_keeps_safe_release_order_before_v1_promotion(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_maintenance_preflight_allows_previous_stable_v1",
                "tests/test_release_bootstrap_runtime.py::ReleaseBootstrapRuntimeTests::"
                "test_first_release_still_requires_v1_on_expected_sha",
                "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
                "test_release_keeps_published_v1_trust_root_before_channel_move",
                "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
                "test_channel_gate_blocks_selftest_until_v1_matches_approved_sha",
                "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
                "test_guide_orders_semantic_release_before_manual_v1_move_and_selftest",
            ),
        )

    def test_candidate_requires_new_exact_sha_human_gate(self) -> None:
        self._run_canonical_targets(
            "AC-05",
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
        self.assertNotIn("#851", workflow)
        self.assertNotIn("#879", workflow)


if __name__ == "__main__":
    unittest.main()
