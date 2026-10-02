#!/usr/bin/env python3
"""Regresiones históricas del candidato Factory 1.0.19."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1019Tests(unittest.TestCase):
    UNBLOCK_REGRESSION_TARGETS = (
        "tests/test_coordinar_trabajo.py::CoordinacionTests::"
        "test_block_sweep_unblocks_verified_workflow_once",
        "tests/test_coordinar_trabajo.py::CoordinacionTests::"
        "test_block_sweep_fails_closed_on_unverified_or_invalid_condition",
        "tests/test_coordinar_trabajo_unblock_validation.py::"
        "UnblockValidationTests::test_missing_targets_fail_closed_without_stopping_sweep",
        "tests/test_coordinar_trabajo.py::CoordinacionTests::"
        "test_block_sweep_retry_does_not_duplicate_evidence_comment",
        "tests/test_coordinar_trabajo.py::CoordinacionTests::"
        "test_block_sweep_supports_closed_issue_condition",
    )

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

    def _run_canonical_targets(self, criterion_id: str, targets: tuple[str, ...]) -> None:
        Criterion, run_named_test = self._acceptance_tools()
        for target in targets:
            with self.subTest(target=target):
                run_named_test(Criterion(criterion_id, "test", target), self.root)

    def test_candidate_version_and_previous_release_compatibility(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        parts = payload["version"].split(".")
        self.assertEqual(len(parts), 3)
        self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 19))
        self._run_canonical_targets(
            "AC-01",
            (
                "tests/test_release_candidate_1_0_18.py::ReleaseCandidate1018Tests::"
                "test_candidate_is_at_least_1_0_18_and_keeps_1_0_18_guarantees",
            ),
        )

    def test_candidate_executes_verified_unblock_regressions(self) -> None:
        self._run_canonical_targets(
            "AC-01",
            self.UNBLOCK_REGRESSION_TARGETS,
        )

    def test_candidate_requires_missing_evidence_fail_closed_regression(self) -> None:
        required = (
            "tests/test_coordinar_trabajo_unblock_validation.py::"
            "UnblockValidationTests::test_missing_targets_fail_closed_without_stopping_sweep"
        )
        self.assertIn(required, self.UNBLOCK_REGRESSION_TARGETS)

    def test_candidate_executes_dispatch_inventory_regressions(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_dispatch_inventory.py::DispatcherV2Tests::"
                "test_dispatch_distinguishes_blocked_unmaterialized_and_no_work",
                "tests/test_dispatch_inventory.py::DispatcherV2Tests::"
                "test_human_or_live_inventory_states_never_materialize",
                "tests/test_dispatch_inventory.py::DispatcherV2Tests::"
                "test_dispatch_exposes_canonical_work_inventory_projection",
            ),
        )

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
