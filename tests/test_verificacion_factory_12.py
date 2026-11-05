"""Factory #2028: comprobar 70 cláusulas sin confundir testigos locales con producción."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-12.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
ROWS = tuple(tuple(row) for row in json.loads(r'''[["docs/quality-regression.md:L27-U1","tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler","REGRESION_LOCAL","solo en ese caso se genera una lesson compatible con lecciones"],["docs/quality-regression.md:L27-U2","tests/test_quality_regression.py::QualityRegressionTests::test_unverified_fix_or_missing_regression_test_never_emits_guardrail_material","REGRESION_LOCAL","una observación no verificada conserva evidencia diagnóstica p"],["docs/quality-regression.md:L31-U1","tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler","REGRESION_LOCAL","dos o más lessons verificadas con fuentes github distintas y e"],["docs/quality-regression.md:L31-U2","tests/test_quality_regression.py::QualityRegressionTests::test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler","REGRESION_LOCAL","este módulo solo expone el candidato retornado por ese contrat"],["docs/quality-regression.md:L33-U1","tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue","REGRESION_LOCAL","no se crea un immune guardrail engine paralelo no hay schedule"],["docs/quality-regression.md:L37-U1","tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue","REGRESION_LOCAL","quality health y proyección a readiness 293 pertenecen a 347"],["docs/quality-regression.md:L38-U1","tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue","REGRESION_LOCAL","clasificación corrección operativa mediante queue 269 pertenec"],["docs/quality-regression.md:L39-U1","tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue","REGRESION_LOCAL","el e2e transversal pertenece a 348"],["docs/quality-regression.md:L40-U1","tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue","REGRESION_LOCAL","este módulo no modifica performance ni recovery"],["docs/quality-regression.md:L41-U1","tests/test_quality_regression.py::QualityRegressionTests::test_docs_define_regression_boundary_without_parallel_engine_or_queue","REGRESION_LOCAL","no existe autoridad para ejecutar fixes promover políticas o d"],["docs/quality-sonar-watch.md:L3-U1","tests/test_sonar_watch.py::SonarWatchTests::test_sonar_watch_no_longer_has_scheduled_or_manual_triggers","SONAR_WATCH_OFFLINE","estado post f1c 1308 pr 1309 sonar watch no se ejecuta automát"],["docs/quality-sonar-watch.md:L3-U2","tests/test_sonar_watch.py::SonarWatchTests::test_retired_workflow_and_offline_engine_are_preserved","SONAR_WATCH_OFFLINE","los issues auto sonar 1052 1053 no se refrescan automáticament"],["docs/quality-sonar-watch.md:L3-U3","tests/test_sonar_watch.py::SonarWatchTests::test_offline_runtime_loads_versioned_config_without_workflow","SONAR_WATCH_OFFLINE","el motor offline scripts sonar watch py y la proyección qualit"],["docs/quality-sonar-watch.md:L22-U1","tests/test_sonar_watch.py::SonarWatchTests::test_versioned_runtime_config_covers_exact_factory_catalog","SONAR_WATCH_OFFLINE","no requieren reinterpretar observación runtime como política"],["docs/quality-sonar-watch.md:L24-U1","tests/test_sonar_watch.py::SonarWatchTests::test_versioned_runtime_config_covers_exact_factory_catalog","SONAR_WATCH_OFFLINE","migrar analysis method de un proyecto requiere nueva decisión"],["docs/quality-sonar-watch.md:L30-U1","tests/test_sonar_watch.py::SonarWatchTests::test_public_projects_need_no_token_and_private_projects_fail_closed_without_one","SONAR_WATCH_OFFLINE","si alguno exige private y no existe sonar token aborta sin toc"],["docs/quality-sonar-watch.md:L32-U1","tests/test_sonar_watch.py::SonarWatchTests::test_public_projects_need_no_token_and_private_projects_fail_closed_without_one","SONAR_WATCH_OFFLINE","payload ausente o ambiguo falla cerrado"],["docs/quality-sonar-watch.md:L32-U2","tests/test_sonar_watch.py::SonarWatchTests::test_analysis_method_uses_read_only_settings_get_only","SONAR_WATCH_OFFLINE","no se convierte en política implícita"],["docs/quality-sonar-watch.md:L42-U1","tests/test_sonar_watch.py::SonarWatchTests::test_autoscan_setting_maps_strictly_to_analysis_method","SONAR_WATCH_OFFLINE","el parser exige exactamente un setting sonar autoscan enabled"],["docs/quality-sonar-watch.md:L42-U2","tests/test_sonar_watch.py::SonarWatchTests::test_autoscan_setting_maps_strictly_to_analysis_method","SONAR_WATCH_OFFLINE","ausencia duplicidad key inesperada o cualquier otro valor fall"],["docs/quality-sonar-watch.md:L46-U1","tests/test_sonar_watch.py::SonarWatchTests::test_offline_runtime_loads_versioned_config_without_workflow","SONAR_WATCH_OFFLINE","esto no autoriza ejecutarlo ni sincronizar issues reales"],["docs/quality-sonar-watch.md:L48-U1","tests/test_sonar_watch.py::SonarWatchTests::test_sonar_watch_no_longer_has_scheduled_or_manual_triggers","SONAR_WATCH_OFFLINE","los checks sonar ci based sonar yml y codeql siguen como valid"],["docs/quality-sonar-watch.md:L52-U1","tests/test_sonar_watch.py::SonarWatchTests::test_current_pass_closes_only_matching_auto_issue","SONAR_WATCH_OFFLINE","un pass solo lo cierra con freshness current"],["docs/quality-sonar-watch.md:L52-U2","tests/test_sonar_watch.py::SonarWatchTests::test_not_applicable_closes_auto_issue_once_and_preserves_required_failures","SONAR_WATCH_OFFLINE","una señal not applicable no abre issue si existe uno abierto d"],["docs/quality-sonar-watch.md:L54-U1","tests/test_sonar_watch.py::SonarWatchTests::test_auto_alert_creation_has_canonical_labels_and_block_reason","SONAR_WATCH_OFFLINE","todo issue abierto que administra el watcher se crea o reconci"],["docs/quality-sonar-watch.md:L54-U2","tests/test_sonar_watch.py::SonarWatchTests::test_terminal_signals_do_not_fake_readiness_or_pass","SONAR_WATCH_OFFLINE","las alertas son observaciones no hojas ejecutables el cuerpo e"],["docs/quality-sonar-watch.md:L54-U3","tests/test_sonar_watch.py::SonarWatchTests::test_current_pass_closes_only_matching_auto_issue","SONAR_WATCH_OFFLINE","en cierre verificado el estado de github pasa a closed y la et"],["docs/quality-sonar-watch.md:L54-U4","tests/test_sonar_watch.py::SonarWatchTests::test_not_applicable_closes_auto_issue_once_and_preserves_required_failures","SONAR_WATCH_OFFLINE","el contenido histórico no se reescribe como pass"],["docs/quality-sonar-watch.md:L54-U5","tests/test_sonar_watch.py::SonarWatchTests::test_reconcile_unlabeled_auto_alert_without_duplicates","SONAR_WATCH_OFFLINE","se preservan etiquetas fuera de las familias tipo prioridad es"],["docs/quality-sonar-watch.md:L56-U1","tests/test_sonar_watch.py::SonarWatchTests::test_issue_body_contains_concrete_quality_gate_and_ce_failure_evidence","SONAR_WATCH_OFFLINE","el cuerpo conserva estado razón freshness referencias opacas y"],["docs/quality-sonar-watch.md:L60-U1","tests/test_sonar_watch.py::SonarWatchTests::test_ci_missing_coverage_remains_actionable","SONAR_WATCH_OFFLINE","controlbot y factory usan ci cobertura ausente sigue siendo un"],["docs/quality-sonar-watch.md:L60-U2","tests/test_sonar_watch.py::SonarWatchTests::test_versioned_runtime_config_covers_exact_factory_catalog","SONAR_WATCH_OFFLINE","cambiar método o visibilidad exige actualizar el contrato"],["docs/quality-sonar-watch.md:L64-U1","tests/test_sonar_watch.py::SonarWatchTests::test_runtime_auth_and_settings_scenarios_are_fail_closed_without_sonar_writes","SONAR_WATCH_OFFLINE","si falta configuración el contrato es ambiguo una respuesta no"],["docs/quality-sonar.md:L5-U1","tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed","SONAR_NORMALIZACION","debe declarar"],["docs/quality-sonar.md:L7-U1","tests/test_quality_sonar.py::QualitySonarTests::test_factory_project_catalog_is_explicit_and_bounded","SONAR_NORMALIZACION","project dentro del catálogo explícito brvtal condor controlbot"],["docs/quality-sonar.md:L8-U1","tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed","SONAR_NORMALIZACION","snapshot at con zona horaria y evidence refs no sensibles"],["docs/quality-sonar.md:L9-U1","tests/test_quality_sonar.py::QualitySonarTests::test_quality_gate_and_failed_condition_are_normalized","SONAR_NORMALIZACION","quality gate con estado ok error y condiciones fallidas cuando"],["docs/quality-sonar.md:L10-U1","tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed","SONAR_NORMALIZACION","analysis con analyzed at método automatic ci y si existe cober"],["docs/quality-sonar.md:L11-U1","tests/test_quality_sonar.py::QualitySonarTests::test_failed_ce_task_preserves_sanitized_server_error","SONAR_NORMALIZACION","ce task y su error message cuando el servidor marca failed"],["docs/quality-sonar.md:L12-U1","tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds","SONAR_NORMALIZACION","uso de líneas de organización visibilidad y deuda histórica"],["docs/quality-sonar.md:L13-U1","tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed","SONAR_NORMALIZACION","ausencia conocida de una señal como null no omitiendo la clave"],["docs/quality-sonar.md:L15-U1","tests/test_quality_sonar.py::QualitySonarTests::test_invalid_sensitive_or_incomplete_payload_fails_closed","SONAR_NORMALIZACION","un valor explícitamente ausente null se normaliza como unknown"],["docs/quality-sonar.md:L21-U1","tests/test_quality_sonar.py::QualitySonarTests::test_quality_gate_and_failed_condition_are_normalized","SONAR_NORMALIZACION","quality gate"],["docs/quality-sonar.md:L22-U1","tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed","SONAR_NORMALIZACION","analysis freshness"],["docs/quality-sonar.md:L24-U1","tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed","SONAR_NORMALIZACION","organization line usage"],["docs/quality-sonar.md:L25-U1","tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed","SONAR_NORMALIZACION","visibility"],["docs/quality-sonar.md:L26-U1","tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed","SONAR_NORMALIZACION","analysis method"],["docs/quality-sonar.md:L28-U1","tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds","SONAR_NORMALIZACION","historical debt"],["docs/quality-sonar.md:L30-U1","tests/test_quality_sonar.py::QualitySonarTests::test_quality_gate_and_failed_condition_are_normalized","SONAR_NORMALIZACION","cada señal contiene status pass fail unknown stale not applica"],["docs/quality-sonar.md:L32-U1","tests/test_quality_sonar.py::QualitySonarTests::test_freshness_visibility_analysis_method_and_coverage_fail_closed","SONAR_NORMALIZACION","analysis method ci exige evidencia de cobertura coverage avail"],["docs/quality-sonar.md:L32-U2","tests/test_quality_sonar.py::SonarEvidenceTests::test_automatic_missing_coverage_is_not_applicable","SONAR_NORMALIZACION","la señal se conserva como not applicable nunca como pass"],["docs/quality-sonar.md:L32-U3","tests/test_quality_sonar.py::SonarEvidenceTests::test_organization_line_usage_applicability_follows_visibility_policy","SONAR_NORMALIZACION","de forma equivalente organization line usage es not applicable"],["docs/quality-sonar.md:L34-U1","tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds","SONAR_NORMALIZACION","los evidence ref item level se validan pero no se propagan al"],["docs/quality-sonar.md:L34-U2","tests/test_quality_sonar.py::QualitySonarTests::test_historical_debt_is_grouped_against_explicit_thresholds","SONAR_NORMALIZACION","la autoridad del lote queda en snapshot evidence refs evitando"],["docs/reconciliacion-issues-20261024.md:L5-U1","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","el contrato de un issue no se declara cumplido por un pr parci"],["docs/reconciliacion-issues-20261024.md:L20-U1","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","8 issues abiertos"],["docs/reconciliacion-issues-20261024.md:L20-U2","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","0 cierres automáticos justificables por aceptación integral"],["docs/reconciliacion-issues-20261024.md:L20-U3","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","la existencia de commits parciales no permite cerrar épicas ni"],["docs/reconciliacion-issues-20261024.md:L21-U1","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","no se fusiona factory v1 no se activa ninguna liberación de le"],["docs/reconciliacion-issues-20261024.md:L21-U2","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","esta hoja solo reclama su documento y su test"],["docs/reconciliacion-issues-20261024.md:L22-U1","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","antes de un corte posterior hay que releer issues head de main"],["docs/reconciliacion-issues-20261024.md:L22-U2","tests/test_reconciliacion_issues_20261024.py::ReconciliacionIssuesTests::test_acceptance","RECONCILIACION_HISTORICA","este documento no prueba el estado futuro"],["docs/recovery-adapters.md:L7-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware","RECOVERY_SIN_IO","object storage destino técnico primario offsite"],["docs/recovery-adapters.md:L7-U2","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_remains_primary_and_icloud_is_not_supported","RECOVERY_SIN_IO","siempre permanece primario"],["docs/recovery-adapters.md:L8-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware","RECOVERY_SIN_IO","google drive cold copy opcional y solo si el recovery manifest"],["docs/recovery-adapters.md:L9-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_object_storage_remains_primary_and_icloud_is_not_supported","RECOVERY_SIN_IO","icloud no soportado y no es dependencia del contrato"],["docs/recovery-adapters.md:L13-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_adapter_contract_is_declarative_external_io_free_and_non_authorizing","RECOVERY_SIN_IO","cada intención recibe un recovery manifest v1 ya validable por"],["docs/recovery-adapters.md:L15-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_invalid_sensitive_or_unsafe_adapter_input_fails_closed_without_echo","RECOVERY_SIN_IO","provider object storage google drive"],["docs/recovery-adapters.md:L16-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_adapter_contract_is_declarative_external_io_free_and_non_authorizing","RECOVERY_SIN_IO","operation upload materialize verify"],["docs/recovery-adapters.md:L17-U1","tests/test_recovery_adapters.py::RecoveryAdaptersTests::test_invalid_sensitive_or_unsafe_adapter_input_fails_closed_without_echo","RECOVERY_SIN_IO","object ref referencia opaca no path ni url"]]'''))
MODES = {
    "REGRESION_LOCAL", "SONAR_WATCH_OFFLINE", "SONAR_NORMALIZACION",
    "RECONCILIACION_HISTORICA", "RECOVERY_SIN_IO",
}


def normalized(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


def report_rows(report: str) -> list[tuple[str, str, str, str, str]]:
    parts = report.split("## Trazabilidad de las 70 unidades")
    if len(parts) != 2:
        raise ValueError("Missing or duplicate evidence heading")
    blocks = parts[1].split("## Validación y reversión")
    if len(blocks) != 2:
        raise ValueError("Missing or duplicate evidence terminator")
    result = []
    for line in blocks[0].splitlines():
        if not line.startswith("| "):
            continue
        fields = [field.strip() for field in line.strip("|").strip().split(" | ")]
        if fields[0] in {"Fila exacta", "---"}:
            continue
        if len(fields) != 5:
            raise ValueError("Malformed evidence row")
        key, witness, mode, anchor, status = fields
        if not all(part.startswith(chr(96)) and part.endswith(chr(96))
                   for part in (key, witness, anchor)):
            raise ValueError("Unquoted evidence ID, witness or anchor")
        result.append((key[1:-1], witness[1:-1], mode, anchor[1:-1], status))
    if len(result) != 70 or len({row[0] for row in result}) != 70:
        raise ValueError("Missing, duplicate or extra evidence row")
    if tuple(result) != tuple((*row, "NO_VERIFICABLE") for row in ROWS):
        raise ValueError("Evidence mapping or status was altered")
    return result


def validate_sources(*, source_overrides: dict[str, str] | None = None,
                     matrix_override: str | None = None) -> None:
    matrix = MATRIX.read_text(encoding="utf-8") if matrix_override is None else matrix_override
    inventory = {}
    pattern = re.compile(r"^\| ([^|]+) \| (.*?) \| (NO_VERIFICABLE|SIN_COBERTURA|CUBIERTO|NO_APLICA) \|")
    for line in matrix.splitlines():
        matched = pattern.match(line)
        if matched is None:
            continue
        key = matched[1].strip(chr(96))
        if key in inventory:
            raise ValueError("Duplicate matrix key " + key)
        inventory[key] = matched[2], matched[3]
    cache = {}
    for key, witness, mode, anchor in ROWS:
        if key not in inventory or inventory[key][1] != "NO_VERIFICABLE":
            raise ValueError("Absent or reclassified matrix key " + key)
        if mode not in MODES or not anchor or len(anchor) > 160:
            raise ValueError("Invalid evidence scope or anchor")
        match = re.fullmatch(r"(docs/[\w.-]+\.md):L(\d+)-U\d+", key)
        if not match:
            raise ValueError("Malformed source ID " + key)
        path, linenum = match.groups()
        if path not in cache:
            override = (source_overrides or {}).get(path)
            cache[path] = (ROOT / path).read_text(encoding="utf-8").splitlines() if override is None else override.splitlines()
        lines = cache[path]
        if int(linenum) > len(lines):
            raise ValueError("Source line missing " + key)
        if normalized(anchor) not in normalized(lines[int(linenum)-1]):
            raise ValueError("Source anchor drift " + key)
        if normalized(anchor) not in normalized(inventory[key][0]):
            raise ValueError("Matrix clause drift " + key)
        pieces = witness.split("::")
        if len(pieces) != 3 or not pieces[0].endswith(".py") or not pieces[2].startswith("test_"):
            raise ValueError("Invalid executable witness " + key)


class VerificacionFactory12Tests(unittest.TestCase):
    def test_70_filas_exactas_sin_promocion(self):
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({row[0] for row in ROWS}), 70)
        content = REPORT.read_text(encoding="utf-8")
        self.assertEqual(len(report_rows(content)), 70)
        self.assertIn("0 promociones", content)
        self.assertIn("consolidación #2035", content)
        self.assertIn("NO_VERIFICABLE", content)

    def test_anclas_de_matriz_y_documentos_reales(self):
        validate_sources()

    def test_testigos_conductuales_ejecutados(self):
        references = sorted({row[1] for row in ROWS})
        self.assertGreaterEqual(len(references), 18)
        for name in references:
            with self.subTest(testigo=name):
                filename, cls, method = name.split("::")
                path = ROOT / filename
                self.assertTrue(path.is_file(), filename)
                for parent in (str(ROOT), str(path.parent)):
                    if parent not in sys.path:
                        sys.path.insert(0, parent)
                modname = "_factory12_" + path.stem
                if modname not in sys.modules:
                    spec = importlib.util.spec_from_file_location(modname, path)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[modname] = module
                    spec.loader.exec_module(module)
                suite = unittest.TestLoader().loadTestsFromName(
                    cls + "." + method, sys.modules[modname]
                )
                output = io.StringIO()
                result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
                self.assertEqual(result.testsRun, 1, name + ": " + output.getvalue())
                self.assertTrue(result.wasSuccessful(), name + ": " + output.getvalue())

    def test_mutaciones_fail_closed(self):
        report = REPORT.read_text(encoding="utf-8")
        row = next(line for line in report.splitlines()
                   if line.startswith("| " + chr(96) + "docs/"))
        bad_reports = (
            report.replace(row + "\n", "", 1),
            report.replace(row, row + "\n" + row, 1),
            report.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            report.replace(row, row.replace(ROWS[0][3], "testigo_inventado"), 1),
            report.replace(row, row.replace(ROWS[0][0], "docs/falso.md:L1-U1"), 1),
            report.replace(row, row + "\n| ruta:falsa | ref | local | falsedad | NO_VERIFICABLE |", 1),
        )
        for i, bad in enumerate(bad_reports):
            with self.subTest(caso=i), self.assertRaises(ValueError):
                report_rows(bad)
        path = "docs/quality-regression.md"
        original = (ROOT / path).read_text(encoding="utf-8").splitlines()
        original[26] = "fuente deliberadamente alterada"
        with self.assertRaises(ValueError):
            validate_sources(source_overrides={path: "\n".join(original)})
        source_matrix = MATRIX.read_text(encoding="utf-8")
        first_id = "| " + chr(96) + ROWS[0][0] + chr(96) + " |"
        matrix_line = next(line for line in source_matrix.splitlines() if line.startswith(first_id))
        with self.assertRaises(ValueError):
            validate_sources(matrix_override=source_matrix.replace(matrix_line, matrix_line.replace("Solo en ese caso", "texto falso"), 1))


if __name__ == "__main__":
    unittest.main()
