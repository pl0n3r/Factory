"""Regresiones sintéticas ejecutables de las 36 filas de Factory #2034.

Cada testigo ejecuta un caso real de la suite existente; nunca certifica
producción, credenciales, decisiones humanas ni ascenso de la matriz.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Las suites de seguridad se ejecutan originalmente desde su propio directorio.
SECURITY_DIR = str(ROOT / "seguridad")
if SECURITY_DIR not in sys.path:
    sys.path.insert(0, SECURITY_DIR)
REPORT = ROOT / "docs/verificacion/verificacion-18.md"

# (ID exacto, ruta del test, clase TestCase, método, límite explícito).
ROWS = (
    ('docs/factoryrunner-execution-plane.md:B06', 'tests/test_factoryrunner_architecture.py', 'FactoryRunnerArchitectureTests', 'test_remote_capabilities_and_mac_fallback_share_protocol', 'LOCAL; la inviabilidad real de cada host requiere evidencia externa'),
    ('docs/dieta-factory.md:B01', 'tests/test_dieta_fase2a.py', 'DietaFase2ATests', 'test_historical_inventory_and_live_phase_routes_consistent', 'HISTORICO; los estados en vivo no se infieren desde baselines'),
    ('docs/dieta-factory.md:B04', 'tests/test_dieta_fase1a.py', 'DietaFase1ATests', 'test_optional_triggers_removed_only_after_dependency_and_consumer_preflight', 'LOCAL; preflight vigente de cada consumidor requiere nueva ejecución'),
    ('docs/dieta-factory.md:B05', 'tests/test_dieta_fase1b.py', 'DietaFase1BTests', 'test_hard_gates_and_rollback_are_preserved', 'PARCIAL; ninguna prueba local garantiza reversión acumulada completa sin verificar cada fase'),
    ('docs/factory-lab.md:B06', 'tests/test_factory_lab_contract.py', 'FactoryLabContractTests', 'test_promotion_requires_constitution_and_fitness', 'CONTRADICE; mejorar Fitness NO autoriza despliegue productivo'),
    ('docs/liberacion-automatica-de-reservas.md:B01', 'tests/test_lease_auto_release_run.py', 'LeaseAutoReleaseRunTests', 'test_scheduled_dry_run_defaults_off_and_never_writes', 'LOCAL; prueba de modo observación, no historial externo'),
    ('docs/liberacion-automatica-de-reservas.md:B02', 'tests/test_lease_auto_release_integration.py', 'LeaseAutoReleaseIntegrationTests', 'test_authenticated_review_veto_complete', 'LOCAL; wait no acredita ausencia de pushes fuera del inventario'),
    ('docs/liberacion-automatica-de-reservas.md:B04', 'tests/test_lease_auto_release_run.py', 'LeaseAutoReleaseRunTests', 'test_phase_a_candidate_requires_authenticated_receipts_and_24h_100_cycles', 'PARCIAL; QA individual y 100 ciclos externos necesitan actas auténticas'),
    ('docs/orquestador.md:B01', 'tests/test_orquestador_kit.py', 'OrchestratorKitTests', 'test_dag_has_deterministic_order', 'LOCAL; el test del DAG no acredita permisos de creación remota'),
    ('docs/orquestador.md:B02', 'tests/test_orquestador_kit.py', 'OrchestratorKitTests', 'test_reservation_blocks_wrong_owner_dependency_and_active_collision', 'LOCAL; reserva remota requiere lease V3 autenticada'),
    ('docs/orquestador.md:B04', 'tests/test_parallel_coordination.py', 'ParallelCoordinationTests', 'test_case_and_unicode_aliases_are_file_collisions', 'PARCIAL; renames y HEAD exigen inventario autenticado'),
    ('docs/automerge-construccion.md:B01', 'tests/test_automerge_workflow.py', 'AutoMergeWorkflowTests', 'test_dry_run_workflow_is_read_only_and_never_merges', 'LOCAL; dry-run no autoriza merge real'),
    ('docs/automerge-construccion.md:B02', 'tests/test_automerge_construccion.py', 'AutoMergeConstruccionTests', 'test_draft_checks_reviews_threads_and_sha_drift_fail_closed', 'LOCAL; requiere checks auténticos exact-SHA para merge real'),
    ('docs/automerge-construccion.md:B03', 'tests/test_automerge_construccion.py', 'AutoMergeConstruccionTests', 'test_live_sensitive_paths_and_freeze_require_human_gate', 'LOCAL; freeze y decisión humana externa siguen siendo vetos'),
    ('docs/no-work-dedup.md:B01', 'tests/test_no_work_dedup.py', 'NoWorkDedupTests', 'test_fingerprint_tracks_queue_leases_prs_and_kill_switch', 'LOCAL; inventario remoto de los siete repos no se simula como observado'),
    ('docs/no-work-dedup.md:B02', 'tests/test_no_work_dedup.py', 'NoWorkDedupTests', 'test_inventory_change_updates_same_canonical_comment', 'LOCAL; la publicación requiere permiso y revalidación'),
    ('docs/no-work-dedup.md:B03', 'tests/test_no_work_dedup.py', 'NoWorkDedupTests', 'test_prewrite_revalidation_requires_same_comment_and_expected_fingerprint', 'LOCAL; carrera real requiere CAS y lectura auténtica'),
    ('docs/puertas-humanas.md:B01', 'seguridad/test_puertas_humanas.py', 'GateTests', 'test_options_and_recommendation_are_validated', 'LOCAL; procedencia del creador no certifica editor del cuerpo'),
    ('docs/puertas-humanas.md:B02', 'seguridad/test_decision_respuesta.py', 'DecisionRespuestaTests', 'test_evidence_v2_binds_gate_fingerprint_and_semantic_drift_fails_closed', 'LOCAL; journal no ejecuta acción de la opción'),
    ('docs/puertas-humanas.md:B03', 'seguridad/test_puertas_humanas.py', 'GateDedupTests', 'test_reconciliation_keeps_lowest_issue_number', 'LOCAL; serialización real depende del workflow remoto'),
    ('docs/puertas-humanas.md:B05', 'seguridad/test_puertas_humanas.py', 'GateTests', 'test_options_and_recommendation_are_validated', 'PARCIAL; safe_default no concede autoridad irreversible'),
    ('docs/puertas-humanas.md:B06', 'seguridad/test_puertas_humanas.py', 'GateDedupTests', 'test_bot_privacy_gate_preserves_release_and_human_authority', 'LOCAL; nothing_live exige observación fiable, no declaración arbitraria'),
    ('docs/politica-revisor-externo.md:B01', 'tests/test_politica_workflow_contract.py', 'T', 'test_required_reviewer_policy_is_loaded_from_base_sha_before_candidate_checkout', 'LOCAL; BASE exacta y gates requieren CI autenticado'),
    ('docs/politica-revisor-externo.md:B02', 'tests/test_politica_kit.py', 'T', 'test_sha_less_rerun_requires_exact_head_failed_policy_or_denies_fallback', 'LOCAL; no presume cuota real sin evidencia HEAD'),
    ('docs/politica-revisor-externo.md:B03', 'tests/test_politica_kit.py', 'T', 'test_sha_less_rate_limit_accepts_only_authenticated_timeline_exact_head_owner_retry', 'LOCAL; no convierte mensajes aislados en revisión real'),
    ('docs/politica-revisor-externo.md:B04', 'tests/test_release_bootstrap.py', 'ReleaseBootstrapTests', 'test_rearm_chain_stops_at_human_decided_gate', 'LOCAL; puente de evidencia no autoriza mover v1'),
    ('docs/immune-repair.md:B03', 'tests/test_immune_repair.py', 'ImmuneRepairTests', 'test_trusted_decision_source_can_authorize_exact_scope', 'LOCAL; provenance remota necesita origen autenticado'),
    ('docs/immune-repair.md:B04', 'tests/test_immune_repair.py', 'ImmuneRepairTests', 'test_trusted_incident_registry_proves_repeated_failure', 'LOCAL; fallos reales no se inventan desde fixtures'),
    ('docs/quality-health.md:B01', 'tests/test_quality_contract.py', 'QualityContractTests', 'test_invalid_unknown_or_duplicate_contract_fails_closed', 'LOCAL; freshness externa no se presume'),
    ('docs/quality-health.md:B02', 'tests/test_quality_status.py', 'QualityStatusTests', 'test_sonar_fail_unknown_and_stale_never_promote_to_pass', 'LOCAL; no recalcula Quality Gate externo'),
    ('docs/quality-health.md:B03', 'tests/test_quality_status.py', 'QualityStatusTests', 'test_performance_and_recovery_are_external_dimensions_without_recalculation', 'LOCAL; no acredita restore o presupuestos reales'),
    ('docs/quality-health.md:B04', 'tests/test_quality_status.py', 'QualityStatusTests', 'test_readiness_projection_reuses_quality_health_and_unknown_or_blocked_never_ready', 'LOCAL; no convierte UNKNOWN/BLOCKED en ready'),
    ('AGENTES.md:B01', 'tests/test_orquestador_kit.py', 'OrchestratorKitTests', 'test_reservation_blocks_wrong_owner_dependency_and_active_collision', 'PARCIAL; PR branch y Validar se verifican por CI y reserva V3 en GitHub'),
    ('AGENTES.md:B02', 'tests/test_workflow_event_guard.py', 'WorkflowEventGuardTests', 'test_code_executing_reusables_guard_privileged_events_before_checkout', 'LOCAL; caller real necesita permiso de lectura y gate'),
    ('AGENTES.md:B03', 'tests/test_version_release.py', 'VersionReleaseTests', 'test_version_es_semantica', 'PARCIAL; publicación/movimiento v1 sigue bajo autoridad humana separada'),
    ('AGENTES.md:B04', 'tests/test_roles_kit.py', 'RolesKitTests', 'test_validate_pr_accepts_complete_multi_role_evidence', 'PARCIAL; remoto mínimo requiere validación del entorno, no eleva autoridad'),
)


class VerificacionFactory18Tests(unittest.TestCase):
    def test_inventario_exacto_y_reporte_completo(self) -> None:
        self.assertEqual(36, len(ROWS))
        self.assertEqual(36, len({r[0] for r in ROWS}))
        body = REPORT.read_text(encoding="utf-8")
        self.assertNotIn("CUBIERTO |", body)
        self.assertIn("NO_VERIFICABLE", body)
        for row_id, filename, cls, method, limit in ROWS:
            with self.subTest(fila=row_id):
                self.assertTrue((ROOT / filename).is_file())
                self.assertTrue(cls and method.startswith("test_"))
                self.assertIn(f"`{row_id}`", body)
                self.assertIn(f"`{filename}::{cls}::{method}`", body)
                self.assertIn(limit, body)

    def test_testigos_existentes_ejecutan_aserciones_con_fixtures_sinteticos(self) -> None:
        modules = {}
        completed = set()
        for row_id, filename, cls, method, _ in ROWS:
            key = (filename, cls, method)
            if key in completed:
                continue
            completed.add(key)
            with self.subTest(fila=row_id, prueba=key):
                if filename not in modules:
                    name = "verificacion_18_" + Path(filename).stem
                    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    spec.loader.exec_module(module)
                    modules[filename] = module
                test_case = getattr(modules[filename], cls)(method)
                result = unittest.TestResult()
                unittest.TestSuite([test_case]).run(result)
                self.assertEqual(1, result.testsRun)
                self.assertEqual([], result.errors, "Error en el testigo: " + str(result.errors))
                self.assertEqual([], result.failures, "Comportamiento revertido: " + str(result.failures))

    def test_limites_no_son_autorizaciones(self) -> None:
        labels = {r[0]: r[4] for r in ROWS}
        self.assertTrue(labels["docs/factory-lab.md:B06"].startswith("CONTRADICE"))
        self.assertIn("NO autoriza despliegue", labels["docs/factory-lab.md:B06"])
        self.assertTrue(labels["docs/dieta-factory.md:B05"].startswith("PARCIAL"))
        self.assertTrue(labels["AGENTES.md:B03"].startswith("PARCIAL"))
        self.assertTrue(all(r[4] for r in ROWS))


if __name__ == "__main__":
    unittest.main()
