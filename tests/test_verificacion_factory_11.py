"""Factory #2027: 70 testigos reales y trazabilidad fail-closed del lote 11/18.

Se ejecutan testigos de código existentes con datos sintéticos. Ningún testigo
local convierte evidencia de GitHub, reglas administrativas o deploy en GREEN.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-11.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
ROWS = (
    ("docs/provisioning.md:L5-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_create_adopt_retry_conflict_are_offline", "PROVISIONAMIENTO_LOCAL", "tanto un repo nuevo como uno adoptado deben"),
    ("docs/provisioning.md:L6-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_contract_validates_inputs_and_uses_external_authority", "PROVISIONAMIENTO_LOCAL", "la autoridad externa es exclusivamente fact"),
    ("docs/provisioning.md:L6-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_workflow_documents_minimum_credential", "PROVISIONAMIENTO_LOCAL", "el github_token del workflow conserva conte"),
    ("docs/provisioning.md:L7-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_workflow_documents_minimum_credential", "PROVISIONAMIENTO_LOCAL", "la credencial debe pertenecer a pl0n3r y li"),
    ("docs/provisioning.md:L7-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_contract_validates_inputs_and_uses_external_authority", "PROVISIONAMIENTO_LOCAL", "factory valida la identidad autenticada ant"),
    ("docs/provisioning.md:L8-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_failure_boundaries_and_gateway_paths_are_covered", "PROVISIONAMIENTO_LOCAL", "si la credencial falta el workflow falla an"),
    ("docs/provisioning.md:L8-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_contract_validates_inputs_and_uses_external_authority", "PROVISIONAMIENTO_LOCAL", "su valor nunca se pega en issues chats urls"),
    ("docs/provisioning.md:L9-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_workflow_documents_minimum_credential", "PROVISIONAMIENTO_LOCAL", "el runtime se descarga desde el sha exacto"),
    ("docs/provisioning.md:L9-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_workflow_documents_minimum_credential", "PROVISIONAMIENTO_LOCAL", "la gobernanza se descarga por separado desd"),
    ("docs/provisioning.md:L9-U3", "tests/test_provision_project.py::ProvisionProjectTests::test_gateway_helpers_cover_http_marker_and_fail_closed_branches", "PROVISIONAMIENTO_LOCAL", "el sha exacto resuelto de esa gobernanza qu"),
    ("docs/provisioning.md:L10-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_bootstrap_uses_canonical_template", "PROVISIONAMIENTO_LOCAL", "el bootstrap construye localmente template"),
    ("docs/provisioning.md:L10-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_bootstrap_uses_canonical_template", "PROVISIONAMIENTO_LOCAL", "no usa git database rest para inicializar u"),
    ("docs/provisioning.md:L11-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_retry_is_idempotent", "PROVISIONAMIENTO_LOCAL", "la descripción de recuperación liga un dige"),
    ("docs/provisioning.md:L12-U1", "tests/test_provision_project.py::ProvisionProjectTests::test_retry_is_idempotent", "PROVISIONAMIENTO_LOCAL", "un retry con el mismo marker converge sin n"),
    ("docs/provisioning.md:L12-U2", "tests/test_provision_project.py::ProvisionProjectTests::test_conflict_invalid_owner_and_missing_token_fail_closed", "PROVISIONAMIENTO_LOCAL", "un repo preexistente público no vacío con i"),
    ("docs/puertas-humanas-lenguaje-simple.md:L3-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "las decisiones nuevas deben entenderse sin"),
    ("docs/puertas-humanas-lenguaje-simple.md:L4-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "el mensaje breve debe explicar qué se decid"),
    ("docs/puertas-humanas-lenguaje-simple.md:L8-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "pregunta una frase corta en title_simple pr"),
    ("docs/puertas-humanas-lenguaje-simple.md:L9-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "resumen dos o tres frases cortas en summary"),
    ("docs/puertas-humanas-lenguaje-simple.md:L9-U2", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "no más de 25 palabras por oración"),
    ("docs/puertas-humanas-lenguaje-simple.md:L10-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "opciones label es un título corto"),
    ("docs/puertas-humanas-lenguaje-simple.md:L10-U2", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "effect y explain_simple"),
    ("docs/puertas-humanas-lenguaje-simple.md:L12-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "impacto indicar claramente si afecta datos"),
    ("docs/puertas-humanas-lenguaje-simple.md:L14-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "recomendación usar why_recommended para exp"),
    ("docs/puertas-humanas-lenguaje-simple.md:L15-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "detalles técnicos separados referencias a i"),
    ("docs/puertas-humanas-lenguaje-simple.md:L19-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "evitar palabras como exact main fail closed"),
    ("docs/puertas-humanas-lenguaje-simple.md:L28-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "todavía no se conectarán cuentas ni persona"),
    ("docs/puertas-humanas-lenguaje-simple.md:L30-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "a preparar prueba solo se crea una prueba c"),
    ("docs/puertas-humanas-lenguaje-simple.md:L35-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "recomendación preparar la prueba permite re"),
    ("docs/puertas-humanas-lenguaje-simple.md:L47-U1", "tests/test_puertas_lenguaje_simple.py::PuertasLenguajeSimpleTests::test_gate_text_is_plain_language", "NORMA_Y_GUARDA_LOCAL", "validación histórica no se alteran sus opci"),
    ("docs/quality-contract.md:L7-U1", "tests/test_quality_contract.py::QualityContractTests::test_performance_and_recovery_are_external_dimensions_not_parallel_pipelines", "NORMA_Y_GUARDA_LOCAL", "performance 304 y recovery 305 son dimensio"),
    ("docs/quality-contract.md:L15-U1", "tests/test_quality_contract.py::QualityContractTests::test_sonar_schema_extension_is_optional_and_closed", "NORMA_Y_GUARDA_LOCAL", "expected_visibility public private"),
    ("docs/quality-contract.md:L16-U1", "tests/test_quality_contract.py::QualityContractTests::test_sonar_schema_extension_is_optional_and_closed", "NORMA_Y_GUARDA_LOCAL", "analysis_method automatic ci"),
    ("docs/quality-contract.md:L17-U1", "tests/test_quality_contract.py::QualityContractTests::test_sonar_monitoring_thresholds_are_explicit_and_deterministic", "NORMA_Y_GUARDA_LOCAL", "max_analysis_age_seconds freshness máxima d"),
    ("docs/quality-contract.md:L18-U1", "tests/test_quality_contract.py::QualityContractTests::test_sonar_monitoring_thresholds_are_explicit_and_deterministic", "NORMA_Y_GUARDA_LOCAL", "max_organization_line_usage_percent porcent"),
    ("docs/quality-contract.md:L19-U1", "tests/test_quality_contract.py::QualityContractTests::test_sonar_monitoring_thresholds_are_explicit_and_deterministic", "NORMA_Y_GUARDA_LOCAL", "max_open_vulnerabilities max_open_bugs y ma"),
    ("docs/quality-contract.md:L20-U1", "tests/test_quality_contract.py::QualityContractTests::test_sonar_monitoring_thresholds_are_explicit_and_deterministic", "NORMA_Y_GUARDA_LOCAL", "max_debt_age_days antigüedad máxima permiti"),
    ("docs/quality-contract.md:L22-U1", "tests/test_quality_contract.py::QualityContractTests::test_legacy_contract_without_sonar_preserves_canonical_form_and_fingerprint", "NORMA_Y_GUARDA_LOCAL", "si sonar está ausente el significado es son"),
    ("docs/quality-engineering.md:L19-U1", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_current_verified_healthy_flow_reaches_quality_pass_and_ready", "NORMA_Y_GUARDA_LOCAL", "los gates exigidos por dod se presentan com"),
    ("docs/quality-engineering.md:L31-U1", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority", "NORMA_Y_GUARDA_LOCAL", "evidencia stale o unknown quality health un"),
    ("docs/quality-engineering.md:L32-U1", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority", "NORMA_Y_GUARDA_LOCAL", "regresión flaky nunca pass"),
    ("docs/quality-engineering.md:L32-U2", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority", "NORMA_Y_GUARDA_LOCAL", "permanece degradación explícita"),
    ("docs/quality-engineering.md:L33-U1", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_critical_quality_failure_materializes_corrective_work_through_existing_dispatcher", "NORMA_Y_GUARDA_LOCAL", "un blocker crítico nunca se diluye con gate"),
    ("docs/quality-engineering.md:L41-U1", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_performance_and_recovery_remain_external_without_recalculation", "NORMA_Y_GUARDA_LOCAL", "quality solo consume sus proyecciones"),
    ("docs/quality-engineering.md:L43-U1", "tests/test_quality_engineering_e2e.py::QualityEngineeringE2ETests::test_docs_define_single_quality_pipeline_and_external_dimension_boundaries", "NORMA_Y_GUARDA_LOCAL", "el rollout a condor grindflow brvtal contro"),
    ("docs/quality-gates.md:L7-U1", "tests/test_quality_gates.py::QualityGateCompilerTests::test_missing_mismatched_or_undeclared_quality_context_fails_closed", "NORMA_Y_GUARDA_LOCAL", "risk y dod consumen quality contract solo s"),
    ("docs/quality-gates.md:L7-U2", "tests/test_quality_gates.py::QualityGateCompilerTests::test_missing_mismatched_or_undeclared_quality_context_fails_closed", "NORMA_Y_GUARDA_LOCAL", "falta mismatch o superficie desconocida fal"),
    ("docs/quality-gates.md:L11-U1", "tests/test_quality_gates.py::QualityGateCompilerTests::test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk", "NORMA_Y_GUARDA_LOCAL", "la criticidad quality solo puede elevar rie"),
    ("docs/quality-gates.md:L11-U2", "tests/test_quality_gates.py::QualityGateCompilerTests::test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk", "NORMA_Y_GUARDA_LOCAL", "nunca reduce señales blast radius ni contro"),
    ("docs/quality-project-dna.md:L9-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_valid_quality_contract_is_attached_by_reference_and_fingerprint", "DESCUBRIMIENTO_LOCAL", "la extensión contiene únicamente"),
    ("docs/quality-project-dna.md:L12-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_valid_quality_contract_is_attached_by_reference_and_fingerprint", "DESCUBRIMIENTO_LOCAL", "source_ref"),
    ("docs/quality-project-dna.md:L13-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_valid_quality_contract_is_attached_by_reference_and_fingerprint", "DESCUBRIMIENTO_LOCAL", "fingerprint sha 256 del quality contract ca"),
    ("docs/quality-project-dna.md:L17-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_docs_define_reference_only_boundary", "DESCUBRIMIENTO_LOCAL", "el quality contract completo no se copia de"),
    ("docs/quality-project-dna.md:L18-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_invalid_contract_reference_or_tampered_dna_fails_closed_without_inference", "DESCUBRIMIENTO_LOCAL", "project dna no infiere quality gates desde"),
    ("docs/quality-project-dna.md:L19-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_existing_project_dna_discovery_remains_backward_compatible", "DESCUBRIMIENTO_LOCAL", "si no se aporta explícitamente un quality c"),
    ("docs/quality-project-dna.md:L20-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_valid_quality_contract_is_attached_by_reference_and_fingerprint", "DESCUBRIMIENTO_LOCAL", "attach_quality_contract valida primero proj"),
    ("docs/quality-project-dna.md:L21-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_invalid_contract_reference_or_tampered_dna_fails_closed_without_inference", "DESCUBRIMIENTO_LOCAL", "validate_project_dna valida el shape cerrad"),
    ("docs/quality-project-dna.md:L22-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_schema_documents_quality_extension_without_closing_extensions_namespace", "DESCUBRIMIENTO_LOCAL", "el namespace general extensions permanece a"),
    ("docs/quality-project-dna.md:L24-U1", "tests/test_quality_project_dna.py::QualityProjectDnaTests::test_docs_define_reference_only_boundary", "DESCUBRIMIENTO_LOCAL", "project dna solo declara qué contrato gobie"),
    ("docs/quality-regression.md:L9-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green", "NORMA_Y_GUARDA_LOCAL", "before cantidad de corridas fallos referenc"),
    ("docs/quality-regression.md:L10-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green", "NORMA_Y_GUARDA_LOCAL", "after la misma forma para demostrar el esta"),
    ("docs/quality-regression.md:L11-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_unverified_fix_or_missing_regression_test_never_emits_guardrail_material", "NORMA_Y_GUARDA_LOCAL", "regression_test_ref referencia del test de"),
    ("docs/quality-regression.md:L12-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_invalid_future_sensitive_or_incoherent_evidence_fails_closed_without_echo", "NORMA_Y_GUARDA_LOCAL", "causa raíz y prevención necesarias para der"),
    ("docs/quality-regression.md:L18-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green", "NORMA_Y_GUARDA_LOCAL", "un fallo se considera reproducido únicament"),
    ("docs/quality-regression.md:L18-U2", "tests/test_quality_regression.py::QualityRegressionTests::test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green", "NORMA_Y_GUARDA_LOCAL", "cualquier muestra con 0 failures runs sea b"),
    ("docs/quality-regression.md:L20-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler", "NORMA_Y_GUARDA_LOCAL", "un fix solo queda verificado cuando"),
    ("docs/quality-regression.md:L22-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler", "NORMA_Y_GUARDA_LOCAL", "el fallo before es reproducible"),
    ("docs/quality-regression.md:L23-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler", "NORMA_Y_GUARDA_LOCAL", "after termina con cero fallos"),
    ("docs/quality-regression.md:L24-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler", "NORMA_Y_GUARDA_LOCAL", "existe regression_test_ref"),
    ("docs/quality-regression.md:L25-U1", "tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler", "NORMA_Y_GUARDA_LOCAL", "la evidencia temporal y las referencias son"),
)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[^\w]+', " ", text.casefold())).strip()


def report_rows(text: str) -> list[tuple[str, str, str, str, str]]:
    result = []
    for line in text.splitlines():
        if not line.startswith("| `docs/"):
            continue
        columns = [part.strip() for part in line.strip("|").split("|")]
        if len(columns) != 5:
            raise ValueError("An ambiguous evidence table is not permitted")
        key, witness, mode, anchor, status = columns
        if not (key.startswith("`") and key.endswith("`")
                and witness.startswith("`") and witness.endswith("`")
                and anchor.startswith("`") and anchor.endswith("`")):
            raise ValueError("Missing provenance delimiter")
        result.append((key[1:-1], witness[1:-1], mode, anchor[1:-1], status))
    if len(result) != 70 or len({x[0] for x in result}) != 70:
        raise ValueError("Missing, duplicate, or extra rows")
    if [x[:4] for x in result] != list(ROWS):
        raise ValueError("Evidence mapping changed without contract revision")
    if any(row[4] != "NO_VERIFICABLE" for row in result):
        raise ValueError("Local evidence cannot certify external readiness")
    return result


class VerificacionFactory11Tests(unittest.TestCase):
    def test_70_filas_exactas_y_sin_promociones(self):
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({row[0] for row in ROWS}), 70)
        report = REPORT.read_text(encoding="utf-8")
        self.assertEqual(len(report_rows(report)), 70)
        self.assertIn("0 promociones", report)
        self.assertIn("docs/matriz-cobertura.md", report)
        self.assertIn("evidencia externa", report.lower())

    def test_cada_unidad_existe_en_fuente_y_matriz(self):
        matrix = MATRIX.read_text(encoding="utf-8").splitlines()
        inventory = {}
        for line in matrix:
            match = re.match(r"^\| `(docs/[^\u0060]+:L\d+-U\d+)` \| (.*?) \| (NO_VERIFICABLE|SIN_COBERTURA) \|", line)
            if match:
                inventory[match.group(1)] = (match.group(2), match.group(3))
        sources = {}
        for key, ref, mode, anchor in ROWS:
            with self.subTest(unit=key):
                match = re.fullmatch(r"(docs/[\w.-]+\.md):L(\d+)-U(\d+)", key)
                self.assertIsNotNone(match)
                path, line_number, _unit_number = match.groups()
                if path not in sources:
                    sources[path] = (ROOT / path).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(int(line_number), len(sources[path]))
                line = sources[path][int(line_number) - 1]
                self.assertIn(normalized(anchor), normalized(line))
                self.assertIn(key, inventory)
                unit, status = inventory[key]
                self.assertEqual(status, "NO_VERIFICABLE")
                self.assertIn(normalized(anchor), normalized(unit))
                self.assertIn(mode, {
                    "REGLA_Y_EVIDENCIA_EXTERNA", "PREVIEW_LOCAL_NO_DEPLOY",
                    "NORMA_Y_GUARDA_LOCAL", "DESCUBRIMIENTO_LOCAL",
                    "PROVISIONAMIENTO_LOCAL",
                })
                filename, cls, method = ref.split("::")
                self.assertTrue(filename.startswith("tests/test_"))
                self.assertTrue(filename.endswith(".py"))
                self.assertRegex(method, r"^test_[a-z0-9_]+$")

    def test_testigos_ejecutables_sobre_codigo_existente(self):
        """Un nombre de método falso no basta: ejecutar todos los testigos únicos."""
        refs = sorted({ref for _, ref, _, _ in ROWS})
        self.assertGreaterEqual(len(refs), 10)
        for ref in refs:
            with self.subTest(witness=ref):
                filename, cls, method = ref.split("::")
                modname = "_factory_verify11_" + Path(filename).stem
                if modname not in sys.modules:
                    spec = importlib.util.spec_from_file_location(modname, ROOT / filename)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[modname] = module
                    spec.loader.exec_module(module)
                suite = unittest.TestLoader().loadTestsFromName(
                    cls + "." + method, sys.modules[modname],
                )
                stream = io.StringIO()
                result = unittest.TextTestRunner(
                    stream=stream, verbosity=0,
                ).run(suite)
                self.assertEqual(result.testsRun, 1, ref + ": " + stream.getvalue())
                self.assertTrue(result.wasSuccessful(), ref + ": " + stream.getvalue())

    def test_rechaza_retiro_duplicacion_y_falsos_verdes(self):
        baseline = REPORT.read_text(encoding="utf-8")
        lines = baseline.splitlines()
        row_line = next(x for x in lines if x.startswith("| `docs/"))
        self.assertEqual(len(report_rows(baseline)), 70)
        variants = [
            baseline.replace(row_line + "\n", "", 1),
            baseline.replace(row_line, row_line + "\n" + row_line, 1),
            baseline.replace(row_line, row_line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            baseline.replace(row_line, row_line.replace(ROWS[0][3], "evidencia-inventada"), 1),
            baseline.replace(row_line, row_line.replace(ROWS[0][0], "docs/falso.md:L1-U1"), 1),
        ]
        for text in variants:
            with self.subTest(mutation=text.count("\n")):
                with self.assertRaises(ValueError):
                    report_rows(text)


if __name__ == "__main__":
    unittest.main()
