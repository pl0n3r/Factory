#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.19."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType


class ReleaseCandidate1019Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def _load_test_module(self, relative_path: str) -> ModuleType:
        path = self.root / relative_path
        module_name = "_factory_release_1019_" + path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run_canonical_test(self, relative_path: str, method_name: str) -> None:
        module = self._load_test_module(relative_path)
        cases = [
            candidate
            for candidate in vars(module).values()
            if isinstance(candidate, type)
            and issubclass(candidate, unittest.TestCase)
            and method_name in candidate.__dict__
        ]
        self.assertEqual(
            len(cases),
            1,
            f"{relative_path} debe definir exactamente un TestCase con {method_name}",
        )
        result = unittest.TestResult()
        unittest.TestSuite([cases[0](method_name)]).run(result)
        problems = result.failures + result.errors
        if problems:
            rendered = "\n".join(detail for _case, detail in problems)
            self.fail(
                f"Regresión canónica falló: {relative_path}::{method_name}\n{rendered}"
            )
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.skipped)

    def test_candidate_version_and_previous_release_compatibility(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.19"})
        self._run_canonical_test(
            "tests/test_release_candidate_1_0_18.py",
            "test_candidate_is_at_least_1_0_18_and_keeps_1_0_18_guarantees",
        )

    def test_candidate_executes_verified_unblock_regressions(self) -> None:
        for method_name in (
            "test_block_sweep_unblocks_verified_workflow_once",
            "test_block_sweep_fails_closed_on_unverified_or_invalid_condition",
            "test_block_sweep_retry_does_not_duplicate_evidence_comment",
            "test_block_sweep_supports_closed_issue_condition",
        ):
            with self.subTest(method_name=method_name):
                self._run_canonical_test(
                    "tests/test_coordinar_trabajo.py",
                    method_name,
                )

    def test_candidate_executes_dispatch_inventory_regressions(self) -> None:
        for method_name in (
            "test_dispatch_distinguishes_blocked_unmaterialized_and_no_work",
            "test_human_or_live_inventory_states_never_materialize",
            "test_dispatch_exposes_canonical_work_inventory_projection",
        ):
            with self.subTest(method_name=method_name):
                self._run_canonical_test(
                    "tests/test_dispatch_inventory.py",
                    method_name,
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
