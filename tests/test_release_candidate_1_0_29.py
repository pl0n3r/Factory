#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.29 (#1172).

No publica tags, no consulta GitHub ni infiere el gate humano. La selección
de evidencia de CI/main, startup watcher, freeze y v1 es externa y exact-SHA.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1029Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_version_is_1_0_29(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload, {"version": "1.0.29"})

    @staticmethod
    def _acceptance_tools():
        try:
            from scripts.aceptacion_kit import Criterion, run_named_test
        except ModuleNotFoundError as exc:
            if exc.name != "scripts":
                raise
            from aceptacion_kit import Criterion, run_named_test
        return Criterion, run_named_test

    def test_required_repairs_previous_contracts_and_release_drift(self) -> None:
        Criterion, run_named_test = self._acceptance_tools()
        # Contratos que materializan las garantías históricas de 1.0.27.
        previous = (
            "test_candidate_version_is_1_0_27",
            "test_candidate_keeps_1_0_26_guarantees_as_historical_compatibility",
            "test_candidate_keeps_authenticated_policy_transport_contract",
            "test_candidate_keeps_release_gate_and_window_separation",
        )
        targets = [
            "tests/test_release_candidate_1_0_27.py::ReleaseCandidate1027Tests::"
            + method for method in previous
        ]
        # Representantes ejecutables de los repairs fusionados en main. Se
        # ejecutan los módulos reales, no inspecciones superficiales de nombres.
        targets.extend((
            "tests/test_bootstrap_coordination.py::BootstrapCoordinationTests::"
            "test_bootstrap_is_idempotent_and_rejects_conflicting_intent",
            "tests/test_release_comment_pages.py::ReleaseCommentPagesTests::"
            "test_malformed_or_incomplete_comment_pages_fail_closed",
            "tests/test_release_api_budget.py::ReleaseApiBudgetTests::"
            "test_rate_limit_retries_bounded_and_always_fail_closed",
            "tests/test_lease_authority_snapshot.py::LeaseAuthoritySnapshotTests::"
            "test_blocked_issue_with_active_v3_remains_exclusive",
            "tests/test_automerge_construccion.py::AutoMergeConstruccionTests::"
            "test_valid_construction_candidate_is_diagnostic_only",
            "tests/test_automerge_construccion.py::AutoMergeConstruccionTests::"
            "test_live_sensitive_paths_and_freeze_require_human_gate",
            "tests/test_captura_leccion_workflow.py::CaptureLessonWorkflowTests::"
            "test_event_gate_executed_against_fixtures",
            "tests/test_recovery_manifests.py::RecoveryManifestsTests::"
            "test_five_manifests_validate_against_closed_schema",
            "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
            "test_latest_rejects_distinct_shas_in_gate_body",
            "tests/test_release_bootstrap_workflow.py::ReleaseBootstrapWorkflowTests::"
            "test_preflight_revalidates_v1_ruleset_read_only",
            "tests/test_politica_workflow_contract.py::PoliticaWorkflowContractTests::"
            "test_authenticated_check_transport_cannot_regress_to_anonymous_curl",
        ))
        for target in targets:
            with self.subTest(target=target):
                run_named_test(Criterion("AC-02", "test", target), self.root)

        # El compare verificado v1...main incluye deriva en estos componentes.
        # Su existencia NO autoriza reusar una puerta de release vieja: la
        # revalidación actual exact-SHA se hará fuera de este test.
        release_machinery_drift = (
            ".github/workflows/factory-ci.yml",
            ".github/workflows/release-bootstrap.yml",
            "scripts/release_api_budget.py",
        )
        for name in release_machinery_drift:
            with self.subTest(drift=name):
                path = self.root / name
                self.assertTrue(path.is_file(), "missing_release_machine")
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
