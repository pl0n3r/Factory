"""Factory #2025 (lote 09): regresiones reales para 70 claims documentales.

Testigos locales sintéticos; NO certifica CI histórico, proveedor ni producción.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-09.md"
TICK = chr(96)
ROWS = (
    ("docs/performance-detection.md:L11-U1", "tests/test_performance_detector.py::PerformanceDetectorTests::test_stale_insufficient_or_unknown_evidence_fails_closed", "REGRESION_LOCAL"),
    ("docs/performance-detection.md:L12-U1", "tests/test_performance_detector.py::PerformanceDetectorTests::test_budget_comparison_uses_exact_contract_metric", "REGRESION_LOCAL"),
    ("docs/performance-detection.md:L13-U1", "tests/test_performance_detector.py::PerformanceDetectorTests::test_budget_comparison_uses_exact_contract_metric", "REGRESION_LOCAL"),
    ("docs/performance-detection.md:L16-U1", "tests/test_performance_detector.py::PerformanceDetectorTests::test_incident_requires_critical_operational_impact_beyond_breach", "REGRESION_LOCAL"),
    ("docs/performance-engineering.md:L11-U1", "tests/test_performance_loop_e2e.py::PerformanceLoopE2ETests::test_noncurrent_evidence_is_unknown_never_healthy", "REGRESION_LOCAL"),
    ("docs/performance-engineering.md:L12-U1", "tests/test_performance_loop_e2e.py::PerformanceLoopE2ETests::test_status_maps_current_classifications_without_hidden_score", "REGRESION_LOCAL"),
    ("docs/performance-engineering.md:L13-U1", "tests/test_performance_loop_e2e.py::PerformanceLoopE2ETests::test_status_maps_current_classifications_without_hidden_score", "REGRESION_LOCAL"),
    ("docs/performance-engineering.md:L14-U1", "tests/test_performance_loop_e2e.py::PerformanceLoopE2ETests::test_status_maps_current_classifications_without_hidden_score", "REGRESION_LOCAL"),
    ("docs/performance-engineering.md:L16-U1", "tests/test_performance_loop_e2e.py::PerformanceLoopE2ETests::test_status_maps_current_classifications_without_hidden_score", "REGRESION_LOCAL"),
    ("docs/performance-engineering.md:L20-U1", "tests/test_performance_loop_e2e.py::PerformanceLoopE2ETests::test_readiness_projection_copies_canonical_status_without_recalculation", "REGRESION_LOCAL"),
    ("docs/performance-github-actions-ci.md:L9-U1", "tests/test_performance_github_actions_ci.py::FactoryRunnerCiObservationTests::test_noncanonical_runs_and_mismatched_identity_fail_closed", "PRODUCTOR_EXTERNO"),
    ("docs/performance-github-actions-ci.md:L9-U3", "tests/test_performance_github_actions_ci.py::FactoryRunnerCiObservationTests::test_adapter_does_not_perform_side_effects_or_claim_prod_success", "REGRESION_LOCAL"),
    ("docs/performance-github-actions-ci.md:L11-U1", "tests/test_performance_github_actions_ci.py::FactoryRunnerCiObservationTests::test_real_main_ci_breach_uses_exact_contract_without_rebaseline", "REGRESION_LOCAL"),
    ("docs/performance-github-actions-ci.md:L11-U2", "tests/test_performance_github_actions_ci.py::FactoryRunnerCiObservationTests::test_real_main_ci_breach_uses_exact_contract_without_rebaseline", "REGRESION_LOCAL"),
    ("docs/performance-github-actions-ci.md:L13-U1", "tests/test_performance_github_actions_ci.py::FactoryRunnerCiObservationTests::test_noncanonical_runs_and_mismatched_identity_fail_closed", "REGRESION_LOCAL"),
    ("docs/performance-github-actions-ci.md:L15-U1", "tests/test_performance_github_actions_ci.py::FactoryRunnerCiObservationTests::test_stale_run_is_not_healthy_and_authority_never_expands", "REGRESION_LOCAL"),
    ("docs/performance-grindflow.md:L7-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_contract_schema_accepts_exact_measured_ci_metric", "REGRESION_LOCAL"),
    ("docs/performance-grindflow.md:L7-U2", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "HISTORICO"),
    ("docs/performance-grindflow.md:L8-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "HISTORICO"),
    ("docs/performance-grindflow.md:L9-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "HISTORICO"),
    ("docs/performance-grindflow.md:L9-U2", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "HISTORICO"),
    ("docs/performance-grindflow.md:L9-U3", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_budget_guard_rejects_fake_or_unsupported_measurements", "HISTORICO"),
    ("docs/performance-grindflow.md:L10-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "HISTORICO"),
    ("docs/performance-grindflow.md:L10-U2", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "HISTORICO"),
    ("docs/performance-grindflow.md:L11-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_contract_schema_accepts_exact_measured_ci_metric", "HISTORICO"),
    ("docs/performance-grindflow.md:L11-U2", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_budget_guard_rejects_fake_or_unsupported_measurements", "HISTORICO"),
    ("docs/performance-grindflow.md:L11-U3", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_budget_guard_rejects_fake_or_unsupported_measurements", "HISTORICO"),
    ("docs/performance-grindflow.md:L22-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_contract_schema_accepts_exact_measured_ci_metric", "REGRESION_LOCAL"),
    ("docs/performance-grindflow.md:L22-U2", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_budget_guard_rejects_fake_or_unsupported_measurements", "REGRESION_LOCAL"),
    ("docs/performance-grindflow.md:L22-U3", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_budget_guard_rejects_fake_or_unsupported_measurements", "REGRESION_LOCAL"),
    ("docs/performance-grindflow.md:L26-U1", "tests/test_performance_grindflow_contract.py::GrindflowPerformanceContractTests::test_baselines_are_real_or_explicitly_unknown", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L3-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_plan_requires_material_finding_and_allowed_action", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L9-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_plan_requires_material_finding_and_allowed_action", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L11-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_plan_requires_material_finding_and_allowed_action", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L12-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_plan_requires_material_finding_and_allowed_action", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L13-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_escalation_conditions_force_human_gate", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L14-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_auto_repair_requires_reversible_tested_authorized_safe_change", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L17-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_output_is_sanitized_non_executing_and_queue_only", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L21-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_before_after_requires_same_current_identity_and_budget_direction", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L23-U2", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_before_after_rejects_same_timestamp_and_repeated_ref", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L25-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_before_after_rejects_impossible_sample_count_and_window", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L25-U2", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_before_after_rejects_invalid_measurement_values", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L25-U4", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_before_after_valid_sampled_measurement_still_adopts", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L25-U5", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_before_after_adopts_only_newer_distinct_current_evidence", "REGRESION_LOCAL"),
    ("docs/performance-remediation.md:L29-U1", "tests/test_performance_remediation.py::PerformanceRemediationTests::test_output_is_sanitized_non_executing_and_queue_only", "REGRESION_LOCAL"),
    ("docs/performance-team-compiler-bridge.md:L3-U1", "tests/test_performance_team_compiler_bridge.py::PerformanceTeamCompilerBridgeTests::test_database_current_composes_real_team_with_dba", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L7-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L8-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L9-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L10-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_owner_priority_remains_authoritative", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L18-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L22-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L23-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L27-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L28-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L29-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L30-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_signals_have_provenance_and_confidence", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L31-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_owner_priority_remains_authoritative", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L37-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_tradeoffs_are_explainable_within_same_priority", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L39-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_owner_priority_remains_authoritative", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L46-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_owner_priority_remains_authoritative", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L47-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_no_magic_score_or_winner_is_required", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L48-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_owner_priority_remains_authoritative", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L49-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_missing_evidence_yields_uncertainty", "REGRESION_LOCAL"),
    ("docs/portfolio-signals.md:L55-U1", "tests/test_portfolio_signals.py::PortfolioSignalsTests::test_docs_preserve_human_decision_boundary", "REGRESION_LOCAL"),
    ("docs/pr-label-governance.md:L3-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_owner_commands_and_audit_document_fail_closed", "REGRESION_LOCAL"),
    ("docs/pr-label-governance.md:L7-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_audit_classifies_required_etiquetas_or_unknown", "REGRESION_LOCAL"),
    ("docs/pr-label-governance.md:L19-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_merged_pr_with_failed_etiquetas_emits_single_alert", "HISTORICO"),
    ("docs/pr-label-governance.md:L23-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGRESION_LOCAL"),
    ("docs/pr-label-governance.md:L32-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGRESION_LOCAL"),
)


class VerificacionFactory09Tests(unittest.TestCase):
    """Comprueba filas, fuentes, suites reales y límites de autoridad."""

    def test_inventario_y_trazabilidad_exacta_de_70_filas(self):
        """El informe conserva cada fila con testigo y limitación exactos."""
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({row[0] for row in ROWS}), 70)
        report = REPORT.read_text(encoding="utf-8")
        entries = []
        for line in report.splitlines():
            if not line.startswith("| " + TICK + "docs/"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            self.assertEqual(len(cells), 4, line)
            self.assertTrue(cells[0].startswith(TICK) and cells[0].endswith(TICK))
            self.assertTrue(cells[1].startswith(TICK) and cells[1].endswith(TICK))
            entries.append((cells[0][1:-1], cells[1][1:-1], cells[2]))
        self.assertEqual(entries, list(ROWS))
        self.assertEqual(sum(m == "HISTORICO" for _, _, m in ROWS), 11)
        self.assertEqual(sum(m == "PRODUCTOR_EXTERNO" for _, _, m in ROWS), 1)
        self.assertIn("0 promociones", report)
        self.assertIn("NO_VERIFICABLE", report)
        self.assertIn("no equivale a", report.lower())
        self.assertIn("docs/matriz-cobertura.md", report)

    def test_fuentes_y_referencias_concretas(self):
        """Un ancla o testigo desaparecido genera una regresión reproducible."""
        for key, ref, mode in ROWS:
            with self.subTest(row=key):
                match = re.fullmatch(r"(docs/[\w.-]+\.md):L(\d+)-U(\d+)", key)
                self.assertIsNotNone(match)
                path, line, unit = match.groups()
                src = ROOT / path
                self.assertTrue(src.is_file(), key)
                lines = src.read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(int(line), len(lines), key)
                self.assertTrue(lines[int(line) - 1].strip(), key)
                filename, cls, method = ref.split("::")
                self.assertTrue(filename.startswith("tests/test_"))
                self.assertTrue(filename.endswith(".py"))
                self.assertRegex(method, r"^test_[a-z0-9_]+$")
                source = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("class " + cls, source)
                self.assertIn("def " + method + "(", source)
                self.assertIn(mode, {"REGRESION_LOCAL", "HISTORICO",
                                     "PRODUCTOR_EXTERNO"})

    def test_ejecucion_de_metodos_testigo_reales(self):
        """Ejecuta métodos existentes; no acepta solo nombres o simulación."""
        refs = sorted({ref for _, ref, _ in ROWS})
        self.assertGreaterEqual(len(refs), 30)
        for ref in refs:
            filename, cls, method = ref.split("::")
            module_name = "_factory09_" + Path(filename).stem
            if module_name not in sys.modules:
                spec = importlib.util.spec_from_file_location(
                    module_name, ROOT / filename,
                )
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            suite = unittest.TestLoader().loadTestsFromName(
                cls + "." + method, sys.modules[module_name],
            )
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream).run(suite)
            with self.subTest(reference=ref):
                self.assertEqual(result.testsRun, 1, stream.getvalue())
                self.assertTrue(result.wasSuccessful(), stream.getvalue())

    def test_limite_externo_permanece_unknown(self):
        """No trata muestras históricas como evidencia operativa vigente."""
        report = REPORT.read_text(encoding="utf-8")
        self.assertIn("no se verifica", report.lower())
        self.assertIn("sin datos reales", report.lower())
        self.assertIn("HISTORICO", report)
        self.assertIn("PRODUCTOR_EXTERNO", report)
        self.assertTrue((ROOT / "docs/matriz-cobertura.md").is_file())


if __name__ == "__main__":
    unittest.main()
