"""Factory #2024: 70 filas documentales con testigos ejecutables, sin falsa cobertura.

Los tests reusan métodos reales de regresión con datos sintéticos. No consultan
red ni autentican artefactos externos, producción o decisiones del OWNER.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-08.md"
ROWS = (
    ("docs/organizational-complexity.md:L16-U1", "- minutos de espera;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L17-U1", "- minutos de revisión;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L18-U1", "- minutos de ejecución útil;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L19-U1", "- las cinco dimensiones protegidas de Factory Constitution;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_budget_is_contextual_and_preserves_constitution", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L20-U1", "- evidencia y scope comparable.", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_workitem_complexity_is_reproducible", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L28-U1", "1. `task_size=small|medium|large` del modelo de #7;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_budget_is_contextual_and_preserves_constitution", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L29-U1", "2. multiplicador de `task_type` ya definido en `metricas/presupuestos.json`;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_budget_is_contextual_and_preserves_constitution", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L30-U1", "3. `risk=low|medium|high|critical`.", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_budget_is_contextual_and_preserves_constitution", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L40-U1", "- valor observado;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_excess_overhead_generates_simplification_candidate", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L41-U1", "- budget contextual;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_excess_overhead_generates_simplification_candidate", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L42-U1", "- estado `within|over`.", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_excess_overhead_generates_simplification_candidate", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L48-U1", "`compare_simplification()` reutiliza Fitness Engine. Solo compara observaciones de la mi", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_simplification_requires_no_protected_regression", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L52-U1", "- Constitution: security/privacy/traceability/reversibility/authority, dirección `higher", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_simplification_requires_no_protected_regression", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L53-U1", "- organizational_overhead_minutes, context_tokens y governance_items, dirección `lower`.", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_simplification_requires_no_protected_regression", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L61-U1", "- `useful_execution_minutes`;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L62-U1", "- `organizational_overhead_minutes`;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L63-U1", "- `total_minutes`;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L64-U1", "- `overhead_ratio`;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L65-U1", "- candidatos de simplificación;", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L66-U1", "- conteo de dimensiones excedidas.", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/organizational-complexity.md:L68-U1", "Esto permite observar el costo operativo de la organización sin confundir trabajo produc", "tests/test_organizational_complexity.py::OrganizationalComplexityTests::test_report_separates_execution_and_overhead", "REGRESION_LOCAL"),
    ("docs/performance-brvtal.md:L3-U1", "Este documento materializa la policy específica de BRVTAL que desbloquea la frontera bas", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_policy_documents_evidence_and_lab_limitations", "HISTORICO"),
    ("docs/performance-brvtal.md:L17-U1", "- mobile: FCP 380 ms, LCP 1624 ms, CLS 0;", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_reproducible_medians_and_explicit_budgets", "HISTORICO"),
    ("docs/performance-brvtal.md:L18-U1", "- desktop: FCP 456 ms, LCP 1772 ms, CLS 0.005.", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_reproducible_medians_and_explicit_budgets", "HISTORICO"),
    ("docs/performance-brvtal.md:L20-U1", "El artifact real `production-performance-36853443439` (id `11160130127`) registra el att", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_artifact_backed_provenance_timestamp", "HISTORICO"),
    ("docs/performance-brvtal.md:L20-U2", "El artifact real `production-performance-36853443439` (id `11160130127`) registra el att", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_artifact_backed_provenance_timestamp", "HISTORICO"),
    ("docs/performance-brvtal.md:L20-U3", "El artifact real `production-performance-36853443439` (id `11160130127`) registra el att", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_artifact_backed_provenance_timestamp", "HISTORICO"),
    ("docs/performance-brvtal.md:L26-U1", "- FCP `<= 1800 ms`, alineado con la referencia pública de web.dev para una puntuación FC", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_reproducible_medians_and_explicit_budgets", "REFERENCIA_PUBLICA"),
    ("docs/performance-brvtal.md:L27-U1", "- LCP `<= 2500 ms`, alineado con la referencia pública de web.dev para LCP “good”: https", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_reproducible_medians_and_explicit_budgets", "REFERENCIA_PUBLICA"),
    ("docs/performance-brvtal.md:L28-U1", "- CLS `<= 0.1`, alineado con la referencia pública de web.dev para CLS “good”: https://w", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_contract_uses_reproducible_medians_and_explicit_budgets", "REFERENCIA_PUBLICA"),
    ("docs/performance-brvtal.md:L30-U1", "Las páginas públicas de web.dev explican esos umbrales en contexto de experiencia de usu", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_policy_documents_evidence_and_lab_limitations", "REGRESION_LOCAL"),
    ("docs/performance-brvtal.md:L34-U1", "El productor actual emite una observación puntual con `window_seconds=1` y `sample_count", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_three_historical_samples_are_info_without_breach", "HISTORICO"),
    ("docs/performance-brvtal.md:L36-U1", "`dom_content_loaded` y `load_event_end` siguen siendo telemetría útil, pero no tienen bu", "tests/test_performance_brvtal_contract.py::BrvtalPerformanceContractTests::test_unbudgeted_timing_metrics_remain_unknown", "REGRESION_LOCAL"),
    ("docs/performance-ci-professional-report.md:L6-U1", "algoritmos Readiness. El caller debe autenticar por su cuenta el GET de GitHub", "tests/test_performance_ci_professional_report.py::CiProfessionalReportTests::test_noncanonical_or_missing_provenance_fails_closed", "AUTENTICACION_EXTERNA"),
    ("docs/performance-ci-professional-report.md:L14-U1", "El contrato `performance/contracts/factoryrunner.json` permite únicamente", "tests/test_performance_ci_professional_report.py::CiProfessionalReportTests::test_output_minimal_and_nonexecuting", "REGRESION_LOCAL"),
    ("docs/performance-ci-professional-report.md:L15-U1", "`observe, diagnose, benchmark`; no autoriza `create_work_item` ni", "tests/test_performance_ci_professional_report.py::CiProfessionalReportTests::test_output_minimal_and_nonexecuting", "REGRESION_LOCAL"),
    ("docs/performance-ci-professional-report.md:L20-U1", "el cuello, no asignación ni diagnóstico causal verificado. Un run sano", "tests/test_performance_ci_professional_report.py::CiProfessionalReportTests::test_real_ci_regression_recommends_professionals_with_exact_readiness", "AUTENTICACION_EXTERNA"),
    ("docs/performance-ci-professional-report.md:L23-U1", "solamente campos canónicos saneados, nunca payload arbitrario, credenciales", "tests/test_performance_ci_professional_report.py::CiProfessionalReportTests::test_output_minimal_and_nonexecuting", "REGRESION_LOCAL"),
    ("docs/performance-ci-professional-report.md:L28-U1", "`candidate_terminal=false` siguen siendo invariantes. Esta hoja solo avanza", "tests/test_performance_ci_professional_report.py::CiProfessionalReportTests::test_output_minimal_and_nonexecuting", "REGRESION_LOCAL"),
    ("docs/performance-ci-suite-benchmark.md:L5-U1", "El contrato `performance/contracts/factoryrunner.json` sigue fijando el presupuesto real", "tests/test_performance_ci_suite_benchmark.py::CiSuiteBenchmarkTests::test_real_runs_differ_in_test_count_and_are_not_comparable", "REGRESION_LOCAL"),
    ("docs/performance-ci-suite-benchmark.md:L7-U1", "El caller autorizado lee GitHub Actions por GET autenticado para un run y job **exactos*", "tests/test_performance_ci_suite_benchmark.py::CiSuiteBenchmarkTests::test_invalid_or_ambiguous_logs_fail_closed", "AUTENTICACION_EXTERNA"),
    ("docs/performance-ci-suite-benchmark.md:L7-U2", "El caller autorizado lee GitHub Actions por GET autenticado para un run y job **exactos*", "tests/test_performance_ci_suite_benchmark.py::CiSuiteBenchmarkTests::test_invalid_or_ambiguous_logs_fail_closed", "REGRESION_LOCAL"),
    ("docs/performance-ci-suite-benchmark.md:L22-U1", "Las cuatro pruebas verifican extracción limitada, escenarios negativos, no comparabilida", "tests/test_performance_ci_suite_benchmark.py::CiSuiteBenchmarkTests::test_real_runs_differ_in_test_count_and_are_not_comparable", "REGRESION_LOCAL"),
    ("docs/performance-ci-suite-benchmark.md:L22-U2", "Las cuatro pruebas verifican extracción limitada, escenarios negativos, no comparabilida", "tests/test_performance_ci_suite_benchmark.py::CiSuiteBenchmarkTests::test_comparable_synthetic_runs_only_produce_advisory_delta", "E2E_PENDIENTE"),
    ("docs/performance-classification.md:L3-U1", "Factory clasifica evidencia Performance v1 producida por proyectos mediante una sola fro", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_valid_brvtal_envelope_uses_canonical_detector", "REGRESION_LOCAL"),
    ("docs/performance-classification.md:L5-U1", "El productor debe enviar `version=1`, `classification_authority=factory-performance-v1`,", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_identity_provenance_and_shape_fail_closed", "REGRESION_LOCAL"),
    ("docs/performance-classification.md:L5-U2", "El productor debe enviar `version=1`, `classification_authority=factory-performance-v1`,", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_identity_provenance_and_shape_fail_closed", "REGRESION_LOCAL"),
    ("docs/performance-classification.md:L7-U1", "El CLI `scripts/performance-classify.py` es offline y determinista. Lee contrato y envel", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_cli_is_deterministic_and_offline", "REGRESION_LOCAL"),
    ("docs/performance-classification.md:L11-U1", "Este slice termina en clasificación. Factory #304 todavía requiere una regresión materia", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_unbudgeted_metrics_remain_unknown_through_classifier", "E2E_PENDIENTE"),
    ("docs/performance-classifier.md:L5-U1", "Factory Performance v1 conserva sus ocho campos de envelope obligatorios. El", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_release_contract_legacy_and_unknown_fields", "REGRESION_LOCAL"),
    ("docs/performance-classifier.md:L14-U1", "El campo **opcional** se verifica con lista cerrada de dos nombres, diseño", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_release_contract_invalid_metadata_fails_closed", "REGRESION_LOCAL"),
    ("docs/performance-classifier.md:L16-U1", "\\`identity.release\\` no preceda el mínimo declarado. Se rechazan campos", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_release_contract_invalid_metadata_fails_closed", "REGRESION_LOCAL"),
    ("docs/performance-classifier.md:L21-U1", "y **nunca** cambia baselines, budgets, severidad, freshness, autoridad de", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_release_contract_production_witness_classification", "HISTORICO"),
    ("docs/performance-classifier.md:L31-U1", "del productor, no autorización de remediación ni cierre del épico #304.", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_release_contract_production_witness_classification", "HISTORICO"),
    ("docs/performance-classifier.md:L33-U1", "Validación offline: \\`python3 -m unittest tests.test_performance_classifier\\`", "tests/test_performance_classifier.py::PerformanceClassifierTests::test_release_contract_cli_offline_deterministic", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L7-U1", "Un documento v1 contiene `project` y una o más `surfaces`. Cada métrica exige:", "tests/test_performance_contract.py::PerformanceContractTests::test_baseline_budget_window_freshness_and_evidence_are_required", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L9-U1", "- `baseline`: valor, unidad y `observed_at`;", "tests/test_performance_contract.py::PerformanceContractTests::test_baseline_budget_window_freshness_and_evidence_are_required", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L10-U1", "- `budget`: operador `lte|gte`, valor y la misma unidad del baseline;", "tests/test_performance_contract.py::PerformanceContractTests::test_baseline_budget_window_freshness_and_evidence_are_required", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L11-U1", "- `window`: `duration_seconds` y `min_samples`;", "tests/test_performance_contract.py::PerformanceContractTests::test_baseline_budget_window_freshness_and_evidence_are_required", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L12-U1", "- `freshness.max_age_seconds`;", "tests/test_performance_contract.py::PerformanceContractTests::test_baseline_budget_window_freshness_and_evidence_are_required", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L13-U1", "- `evidence`: `source`, referencia opaca y timestamp;", "tests/test_performance_contract.py::PerformanceContractTests::test_baseline_budget_window_freshness_and_evidence_are_required", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L15-U1", "- `escalation_conditions`: catálogo cerrado de costo, arquitectura, consistencia, semánt", "tests/test_performance_contract.py::PerformanceContractTests::test_actions_and_escalations_are_closed_deterministic_and_non_authorizing", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L17-U2", "El validador falla cerrado ante campos desconocidos, números no finitos, unidades incomp", "tests/test_performance_contract.py::PerformanceContractTests::test_invalid_unknown_or_sensitive_input_fails_closed_without_echo", "REGRESION_LOCAL"),
    ("docs/performance-contract.md:L23-U1", "Este slice solo valida que exista un límite de freshness y evidencia fechada. No decide", "tests/test_performance_contract.py::PerformanceContractTests::test_schema_validator_and_docs_share_contract_v1", "E2E_PENDIENTE"),
    ("docs/performance-contract.md:L23-U2", "Este slice solo valida que exista un límite de freshness y evidencia fechada. No decide", "tests/test_performance_contract.py::PerformanceContractTests::test_schema_validator_and_docs_share_contract_v1", "E2E_PENDIENTE"),
    ("docs/performance-contract.md:L27-U1", "- #310: contrato, schema y validación.", "tests/test_performance_contract.py::PerformanceContractTests::test_schema_validator_and_docs_share_contract_v1", "E2E_PENDIENTE"),
    ("docs/performance-contract.md:L28-U1", "- #311: detección de regresiones y triage.", "tests/test_performance_contract.py::PerformanceContractTests::test_schema_validator_and_docs_share_contract_v1", "E2E_PENDIENTE"),
    ("docs/performance-contract.md:L29-U1", "- #312: remediación gobernada + before/after.", "tests/test_performance_contract.py::PerformanceContractTests::test_schema_validator_and_docs_share_contract_v1", "E2E_PENDIENTE"),
    ("docs/performance-contract.md:L30-U1", "- #313: estado consumible por Readiness y escenario E2E.", "tests/test_performance_contract.py::PerformanceContractTests::test_schema_validator_and_docs_share_contract_v1", "E2E_PENDIENTE"),
    ("docs/performance-detection.md:L9-U1", "La evidencia queda fail-closed:", "tests/test_performance_detector.py::PerformanceDetectorTests::test_stale_insufficient_or_unknown_evidence_fails_closed", "REGRESION_LOCAL"),
)
LIMITS = {
    "REGRESION_LOCAL": "Test sintético local; no acredita despliegue ni resultado productivo.",
    "HISTORICO": "Test del fixture; run, timestamp y origen histórico no reautenticados.",
    "REFERENCIA_PUBLICA": "Budget local probado; referencia web.dev y p75 de campo no autenticados.",
    "AUTENTICACION_EXTERNA": "Verifica rechazo local; falta atestar GET auténtico e identidad externa.",
    "E2E_PENDIENTE": "Frontera local probada; falta ejecución real autorizada y before/after.",
}


def parse_report(content: str) -> list[tuple[str, str, str, str]]:
    """Falla cerrado por columnas, estados o limitaciones incompletas."""
    entries = []
    for line in content.splitlines():
        if not line.startswith("| `docs/"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) != 6:
            raise AssertionError("Columnas de verificación alteradas")
        key, anchor, reference, mode, state, limit = cols
        if not (key.startswith("`") and key.endswith("`") and
                reference.startswith("`") and reference.endswith("`")):
            raise AssertionError("Referencia no canónica")
        if state != "NO_VERIFICABLE" or mode not in LIMITS:
            raise AssertionError("Promoción no autorizada")
        if limit != LIMITS[mode] or not limit.strip():
            raise AssertionError("Brecha faltante o truncada")
        entries.append((key[1:-1], anchor.replace("&#124;", "|").replace("&#96;", "`"),
                        reference[1:-1], mode))
    return entries


class VerificacionFactory08Tests(unittest.TestCase):
    """Protege inventario, anclas, testigos y no promoción."""

    def test_inventario_exactamente_70_con_brechas(self):
        """Los 70 IDs se mantienen, sin cubrir filas por afirmación."""
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({x[0] for x in ROWS}), 70)
        report = REPORT.read_text(encoding="utf-8")
        self.assertEqual(parse_report(report), list(ROWS))
        self.assertIn("0 promociones", report)
        self.assertIn("NO_VERIFICABLE", report)
        self.assertIn("docs/matriz-cobertura.md", report)
        self.assertNotIn("| CUBIERTO |", report)

    def test_anclas_documentales_y_metodos_existentes(self):
        """No admite líneas, archivos o métodos inexistentes."""
        for key, anchor, reference, mode in ROWS:
            with self.subTest(row=key):
                m = re.fullmatch(r"(docs/[a-z0-9.-]+\.md):L([0-9]+)-U([0-9]+)", key)
                self.assertIsNotNone(m)
                path, line, _unit = m.groups()
                src = ROOT / path
                self.assertTrue(src.is_file())
                contents = src.read_text(encoding="utf-8").splitlines()
                self.assertGreaterEqual(len(contents), int(line))
                self.assertEqual(contents[int(line) - 1].strip()[:88].rstrip(), anchor)
                filename, cls, method = reference.split("::")
                self.assertTrue(filename.startswith("tests/test_"))
                source = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("class " + cls + "(", source)
                self.assertIn("def " + method + "(", source)
                self.assertIn(mode, LIMITS)

    def test_ejecuta_regresiones_reales_con_fixtures_locales(self):
        """Ejecuta cada testigo distinto y verifica éxito real, no nombres."""
        refs = sorted({reference for _key, _anchor, reference, _mode in ROWS})
        self.assertGreaterEqual(len(refs), 22)
        for reference in refs:
            filename, cls, method = reference.split("::")
            name = "_factory08_" + Path(filename).stem
            if name not in sys.modules:
                spec = importlib.util.spec_from_file_location(name, ROOT / filename)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                sys.modules[name] = module
                spec.loader.exec_module(module)
            suite = unittest.TestLoader().loadTestsFromName(
                cls + "." + method, sys.modules[name],
            )
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream).run(suite)
            with self.subTest(testigo=reference):
                self.assertEqual(result.testsRun, 1, stream.getvalue())
                self.assertTrue(result.wasSuccessful(), stream.getvalue())

    def test_mutaciones_no_promueven_ni_ocultan_brechas(self):
        """Borrar, duplicar, cambiar testigo o truncar brecha falla."""
        report = REPORT.read_text(encoding="utf-8")
        original = parse_report(report)
        self.assertEqual(original, list(ROWS))
        target = next(line for line in report.splitlines() if line.startswith("| `docs/"))
        bad = [
            report.replace(target + "\n", "", 1),
            report.replace(target + "\n", target + "\n" + target + "\n", 1),
            report.replace(" | NO_VERIFICABLE | ", " | CUBIERTO | ", 1),
            report.replace(" | REGRESION_LOCAL | ", " | DESCONOCIDO | ", 1),
            report.replace("Test sintético local; no acredita despliegue ni resultado productivo.",
                           "Test sintético local;", 1),
            report.replace("::test_", "::test_inexistente_", 1),
        ]
        for index, mutated in enumerate(bad):
            with self.subTest(caso=index):
                self.assertNotEqual(mutated, report)
                try:
                    observed = parse_report(mutated)
                except AssertionError:
                    continue  # Estado o brecha inválida se rechaza explícitamente.
                self.assertNotEqual(observed, list(ROWS))

    def test_evidencia_externa_no_se_declara_verificada(self):
        """Los límites históricos y de autorización siguen pendientes."""
        modes = {x[3] for x in ROWS}
        self.assertEqual(modes, set(LIMITS))
        report = REPORT.read_text(encoding="utf-8")
        for value in ("no acredita", "no se toca", "no_verificable", "0 promociones"):
            self.assertIn(value, report.lower())


if __name__ == "__main__":
    unittest.main()
