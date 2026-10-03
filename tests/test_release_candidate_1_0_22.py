#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.22."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1022Tests(unittest.TestCase):
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

    def test_candidate_version_is_1_0_22(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        parts = payload["version"].split(".")
        self.assertEqual(len(parts), 3)
        self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 22))

    def test_candidate_keeps_1_0_21_guarantees_as_historical_compatibility(
        self,
    ) -> None:
        self._run_canonical_targets(
            "AC-02",
            (
                "tests/test_release_candidate_1_0_21.py::ReleaseCandidate1021Tests::"
                "test_candidate_version_is_1_0_21",
                "tests/test_release_candidate_1_0_21.py::ReleaseCandidate1021Tests::"
                "test_candidate_keeps_1_0_20_guarantees_as_historical_compatibility",
                "tests/test_release_candidate_1_0_21.py::ReleaseCandidate1021Tests::"
                "test_candidate_keeps_empty_permissions_preflight_fail_closed",
                "tests/test_release_candidate_1_0_21.py::ReleaseCandidate1021Tests::"
                "test_candidate_keeps_safe_release_order_before_v1_promotion",
                "tests/test_release_candidate_1_0_21.py::ReleaseCandidate1021Tests::"
                "test_candidate_requires_new_exact_sha_human_gate",
            ),
        )

        historical = (
            self.root / "tests/test_release_candidate_1_0_21.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 21))",
            historical,
        )
        self.assertNotIn(
            'self.assertEqual(payload, {"version": "1.0.21"})',
            historical,
        )

    def test_candidate_keeps_top_level_empty_permissions_repair(self) -> None:
        self._run_canonical_targets(
            "AC-03",
            (
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_empty_inline_top_level_permissions_are_supported_as_no_permissions",
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_non_empty_inline_top_level_permissions_remain_fail_closed",
            ),
        )

    def test_candidate_keeps_reusable_permission_envelope_sweep(self) -> None:
        self._run_canonical_targets(
            "AC-04",
            (
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_all_factory_reusable_workflows_have_parseable_permission_envelopes",
                "tests/test_reusable_release_preflight.py::ReusableReleasePreflightTests::"
                "test_current_factory_acceptance_empty_permissions_parse_to_declared_envelope",
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
        self.assertNotIn("#895", workflow)


if __name__ == "__main__":
    unittest.main()
