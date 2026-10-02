#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.20."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1020Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_20(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        parts = payload["version"].split(".")
        self.assertEqual(len(parts), 3)
        self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 20))

    def test_candidate_keeps_1_0_19_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        target = (
            "tests/test_release_candidate_1_0_19.py::ReleaseCandidate1019Tests::"
            "test_candidate_version_and_previous_release_compatibility"
        )
        self._run_canonical_targets("AC-02", (target,))

        historical = (
            self.root / "tests/test_release_candidate_1_0_19.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 19))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.19"})',
            historical,
        )

    def test_candidate_requires_consumer_permission_preflight_and_rollback_runbook(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_coordinacion_reusable_contract.py::T::"
                "test_v1_0_18_caller_permission_envelope_starts_comment_label_pr_issue_and_validate",
                "tests/test_coordinacion_reusable_contract.py::T::"
                "test_sweep_does_not_raise_reusable_permission_envelope_for_non_sweep_operations",
                "tests/test_reusable_permission_compat.py::ReusablePermissionCompatTests::"
                "test_incident_860_permission_regressions_are_detected",
                "tests/test_reusable_permission_compat.py::ReusablePermissionCompatTests::"
                "test_all_callers_must_be_compatible_without_majority_shortcut",
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_all_six_consumer_callers_must_be_compatible_before_release",
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_release_job_requires_consumer_compat_preflight_and_human_gate",
                "tests/test_reusable_release_rollback.py::ReusableReleaseRollbackTests::"
                "test_runbook_has_evidence_target_action_and_verification",
                "tests/test_reusable_release_rollback.py::ReusableReleaseRollbackTests::"
                "test_runbook_preserves_human_admin_tag_boundary",
            ),
        )

    def test_candidate_requires_post_release_startup_failure_watchdog(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_reusable_release_watchdog.py::ReusableReleaseWatchdogTests::"
                "test_startup_failures_are_bound_to_repo_workflow_run_and_factory_sha",
                "tests/test_reusable_release_watchdog.py::ReusableReleaseWatchdogTests::"
                "test_two_distinct_affected_repositories_recommend_rollback_without_authority",
                "tests/test_reusable_release_watchdog.py::ReusableReleaseWatchdogTests::"
                "test_workflow_never_moves_tags_and_keeps_rollback_advisory_only",
            ),
        )

    def test_candidate_keeps_human_release_boundary_and_rejects_reused_1_0_19_gate(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-05",
            (
                "tests/test_release_candidate_1_0_19.py::ReleaseCandidate1019Tests::"
                "test_candidate_keeps_human_release_boundary",
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


if __name__ == "__main__":
    unittest.main()
