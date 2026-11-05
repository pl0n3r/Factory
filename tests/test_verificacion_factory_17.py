"""Factory #2033: 70 testigos causales del lote 17/18; solo fixtures offline.

No promueve estados de la matriz ni acredita permisos, gastos o producción.
Cada testigo existente se ejecuta y su límite queda registrado en la bitácora.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-17.md"
ROWS = (
    ("ISSUE-304:AC-05", "tests/test_performance_remediation.py", "PerformanceRemediationTests", "test_plan_requires_material_finding_and_allowed_action", "PARCIAL", "No prueba despliegue de cache/CDN ni autoriza cambio sin hipótesis y presupuesto."),
    ("ISSUE-304:AC-06", "tests/test_performance_loop_e2e.py", "PerformanceLoopE2ETests", "test_noncurrent_evidence_is_unknown_never_healthy", "LOCAL", "Contrato determinista offline; requiere evidencia operativa para afirmar producción."),
    ("ISSUE-304:AC-07", "tests/test_performance_remediation.py", "PerformanceRemediationTests", "test_output_is_sanitized_non_executing_and_queue_only", "PARCIAL", "Plan local no acredita WorkItem remoto registrado en Factory #269."),
    ("ISSUE-304:AC-08", "tests/test_performance_remediation.py", "PerformanceRemediationTests", "test_auto_repair_requires_reversible_tested_authorized_safe_change", "LOCAL", "Contrato determinista offline; requiere evidencia operativa para afirmar producción."),
    ("ISSUE-304:AC-09", "tests/test_performance_remediation.py", "PerformanceRemediationTests", "test_escalation_conditions_force_human_gate", "LOCAL", "Contrato determinista offline; requiere evidencia operativa para afirmar producción."),
    ("ISSUE-304:AC-10", "tests/test_performance_loop_e2e.py", "PerformanceLoopE2ETests", "test_readiness_projection_copies_canonical_status_without_recalculation", "LOCAL", "Contrato determinista offline; requiere evidencia operativa para afirmar producción."),
    ("ISSUE-304:AC-11", "tests/test_performance_loop_e2e.py", "PerformanceLoopE2ETests", "test_e2e_regression_to_adopted_improvement_becomes_healthy", "PARCIAL", "E2E de fixtures; no acredita observación o before/after productivo."),
    ("ISSUE-304:AC-12", "tests/test_performance_loop_e2e.py", "PerformanceLoopE2ETests", "test_e2e_fail_closed_paths_never_become_healthy_or_parallel_queue", "LOCAL", "Contrato determinista offline; requiere evidencia operativa para afirmar producción."),
    ("ISSUE-305:AC-01", "tests/test_recovery_contract.py", "RecoveryContractTests", "test_manifest_v1_schema_and_validator_are_closed_and_deterministic", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-02", "tests/test_recovery_contract.py", "RecoveryContractTests", "test_manifest_models_32110_rpo_rto_retention_and_explicit_not_applicable", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-03", "tests/test_recovery_contract.py", "RecoveryContractTests", "test_invalid_sensitive_or_incoherent_manifest_fails_closed_without_echo", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-04", "tests/test_recovery_adapters.py", "RecoveryAdaptersTests", "test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware", "PARCIAL", "Adapters son declarativos y sin I/O; no prueba servicios externos."),
    ("ISSUE-305:AC-05", "tests/test_recovery_pipeline.py", "RecoveryPipelineTests", "test_backup_pipeline_is_deterministic_declarative_and_external_io_free", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-06", "tests/test_recovery_pipeline.py", "RecoveryPipelineTests", "test_required_backup_cannot_be_verified_without_contract_evidence", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-07", "tests/test_recovery_drill.py", "RecoveryDrillTests", "test_disposable_restore_drill_validates_integrity_health_smoke_and_rto", "PARCIAL", "Restore aislado sintético; falta recibo de restauración real."),
    ("ISSUE-305:AC-08", "tests/test_recovery_drill.py", "RecoveryDrillTests", "test_restore_authority_never_implies_productive_or_destructive_cutover", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-09", "tests/test_recovery_status.py", "RecoveryStatusTests", "test_recovery_health_is_explainable_freshness_aware_and_fail_closed", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-10", "tests/test_recovery_status.py", "RecoveryStatusTests", "test_recovery_drift_maps_to_canonical_work_item_classes_without_scheduler", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-11", "tests/test_recovery_status.py", "RecoveryStatusTests", "test_readiness_projection_reuses_recovery_health_without_recalculation", "LOCAL", "Contrato offline; no acredita backup/restore real ni proveedor autorizado."),
    ("ISSUE-305:AC-12", "tests/test_recovery_e2e.py", "RecoveryE2ETests", "test_backup_offsite_restore_health_smoke_and_rpo_rto_flow_without_source_or_secrets", "PARCIAL", "E2E fake no acredita object storage remoto ni RPO/RTO real."),
    ("ISSUE-1080:AC-01", "tests/test_release_auto_eligibility.py", "ReleaseAutoEligibilityTests", "test_construction_all_exact_main_gates_yields_dry_run_only", "CONTRADICE", "La regresión valida dry-run únicamente; no prueba publicación automática."),
    ("ISSUE-1080:AC-02", "tests/test_release_auto_eligibility.py", "ReleaseAutoEligibilityTests", "test_live_or_release_machinery_requires_human_gate", "LOCAL", "Criterio de release simulado, sin permiso de publicar ni mover v1."),
    ("ISSUE-1080:AC-03", "tests/test_release_auto_policy.py", "ReleaseAutoPolicyTests", "test_freeze_kill_switch_and_security_veto", "LOCAL", "Criterio de release simulado, sin permiso de publicar ni mover v1."),
    ("ISSUE-1080:AC-04", "tests/test_release_auto_rollback_plan.py", "ReleaseAutoRollbackPlanTests", "test_authenticated_startup_failure_proposes_only_human_rollback", "PARCIAL", "Plan humano condicionado, no prueba rollback real del tag."),
    ("ISSUE-1082:AC-01", "tests/test_principios_construccion.py", "PrincipiosConstruccionTests", "test_regla_cero_y_ocho_invariantes_con_fuentes", "LOCAL", "Contrato del kit; no acredita ejecución autenticada en seis consumidores."),
    ("ISSUE-1082:AC-02", "tests/test_plan_sync_agentes_consumidores.py", "PlanSyncAgentesConsumidoresTests", "test_plans_six_consumers_without_overwriting_local_rules", "PARCIAL", "Plan de sync offline no prueba propagación efectiva a seis consumidores."),
    ("ISSUE-1082:AC-03", "tests/test_salud_cola_alertar.py", "SaludColaAlertarTests", "test_deduplicate_and_update_one_factory_issue_only", "PARCIAL", "Modelo de deduplicación no demuestra alerta real entregada."),
    ("ISSUE-1082:AC-04", "tests/test_parallel_coordination.py", "ParallelCoordinationTests", "test_candidate_file_lease_v3_rejects_directory_candidate", "LOCAL", "Contrato del kit; no acredita ejecución autenticada en seis consumidores."),
    ("ISSUE-1382:AC-01", "tests/test_lease_activity_collector.py", "LeaseActivityCollectorTests", "test_complete_authenticated_snapshots_track_owner_activity", "LOCAL", "Prueba local; faltan los ciclos y la autorización externa para activación."),
    ("ISSUE-1382:AC-02", "tests/test_lease_auto_release_run.py", "LeaseAutoReleaseRunTests", "test_switch_recheck_rejects_pause_and_untrusted_state_during_inventory", "LOCAL", "Prueba local; faltan los ciclos y la autorización externa para activación."),
    ("ISSUE-1382:AC-03", "tests/test_lease_auto_release_integration.py", "LeaseAutoReleaseIntegrationTests", "test_authenticated_complete_activity_evidence_fail_closed", "LOCAL", "Prueba local; faltan los ciclos y la autorización externa para activación."),
    ("ISSUE-1382:AC-04", "tests/test_lease_auto_release_run.py", "LeaseAutoReleaseRunTests", "test_observation_reports_current_repository_without_writes", "LOCAL", "Prueba local; faltan los ciclos y la autorización externa para activación."),
    ("ISSUE-1382:AC-05", "tests/test_lease_auto_release_run.py", "LeaseAutoReleaseRunTests", "test_phase_a_candidate_requires_authenticated_receipts_and_24h_100_cycles", "PARCIAL", "No hay acta real de 24 h ni 100 ciclos por repositorio."),
    ("ISSUE-1382:AC-06", "tests/test_lease_auto_release_run.py", "LeaseAutoReleaseRunTests", "test_authorized_activation_caps_three_releases_and_preserves_pr_branch", "PARCIAL", "No se habilita Fase B ni se simulan liberaciones en GitHub."),
    ("ISSUE-1382:AC-07", "tests/test_lease_phase_a_artifact_qa.py", "LeasePhaseAArtifactQATests", "test_documented_manual_attestation_and_no_network_or_release", "LOCAL", "Prueba local; faltan los ciclos y la autorización externa para activación."),
    ("docs/lista-salida-produccion.md:L7-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "LOCAL", "La lista separa implementación técnica de operación."),
    ("docs/lista-salida-produccion.md:L7-U2", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_cubre_todo_el_alcance", "PARCIAL", "Un épico/roadmap no acredita LISTO de producción."),
    ("docs/lista-salida-produccion.md:L8-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_sin_cobertura_tiene_issue", "LOCAL", "La hoja canónica exige trazabilidad; inventario histórico no implica entrega actual."),
    ("docs/lista-salida-produccion.md:L9-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_cubre_todo_el_alcance", "DOCUMENTAL", "Fuentes citadas no sustituyen verificación auténtica."),
    ("docs/lista-salida-produccion.md:L9-U2", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_resumen_final", "EXTERNO", "Observer y smoke deben verificarse en cada consumidor real."),
    ("docs/lista-salida-produccion.md:L79-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_sin_cobertura_tiene_issue", "DOCUMENTAL", "No se crean hojas ficticias: solo evidencia de los issues originales."),
    ("docs/lista-salida-produccion.md:L83-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "Falta offsite y restore real bajo D-066."),
    ("docs/lista-salida-produccion.md:L83-U2", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "Contrato offline no prueba backup real."),
    ("docs/lista-salida-produccion.md:L84-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "La puerta OWNER de publicación SHA sigue vigente."),
    ("docs/lista-salida-produccion.md:L84-U2", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "PR verde no publica Factory@v1."),
    ("docs/lista-salida-produccion.md:L85-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "No hay recibo de guardia/alertas/carga real."),
    ("docs/lista-salida-produccion.md:L86-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "HTTPS, accesibilidad y privacidad dependen del consumidor."),
    ("docs/lista-salida-produccion.md:L87-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_sin_cobertura_tiene_issue", "PARCIAL", "#1553 necesita verificación de su implementación exact-main."),
    ("docs/lista-salida-produccion.md:L87-U2", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_sin_cobertura_tiene_issue", "HISTORICO", "La ausencia histórica no acredita estado vigente."),
    ("docs/lista-salida-produccion.md:L88-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_formato_y_estados", "EXTERNO", "Gasto/proveedores y credenciales requieren permiso OWNER."),
    ("docs/lista-salida-produccion.md:L90-U1", "tests/test_lista_salida_produccion.py", "ListaSalidaTests", "test_resumen_final", "LOCAL", "Nunca infiere VALIDATED_IN_PRODUCTION del checklist."),
    ("docs/auditoria-pre-v1.md:B01", "tests/test_contraste_matriz_prev1_release.py", "ContrasteTests", "test_cada_documento_tiene_veredicto", "HISTORICO", "Auditoría ligada a SHA previo; tests actuales no certifican estado externo ni dependencias ejecutadas."),
    ("docs/auditoria-pre-v1.md:B02", "tests/test_contraste_matriz_prev1_release.py", "ContrasteTests", "test_cubierto_enlaza_prueba_existente", "HISTORICO", "Auditoría ligada a SHA previo; tests actuales no certifican estado externo ni dependencias ejecutadas."),
    ("docs/auditoria-pre-v1.md:B03", "tests/test_contraste_matriz_prev1_release.py", "ContrasteTests", "test_faltante_tiene_issue", "HISTORICO", "Auditoría ligada a SHA previo; tests actuales no certifican estado externo ni dependencias ejecutadas."),
    ("docs/auditoria-pre-v1.md:B04", "tests/test_contraste_matriz_prev1_release.py", "ContrasteTests", "test_matriz_actualizada", "HISTORICO", "Auditoría ligada a SHA previo; tests actuales no certifican estado externo ni dependencias ejecutadas."),
    ("docs/release-bootstrap.md:B01", "tests/test_release_bootstrap_workflow.py", "ReleaseBootstrapWorkflowTests", "test_published_v1_is_used_for_release_and_post_selftest", "LOCAL", "Kit publicado queda fijado a v1; no ref privilegiada dinámica."),
    ("docs/release-bootstrap.md:B02", "tests/test_release_bootstrap_workflow.py", "ReleaseBootstrapWorkflowTests", "test_release_keeps_published_v1_trust_root_before_channel_move", "EXTERNO", "Gate/decisión OWNER exact-SHA no sustituible por test."),
    ("docs/release-bootstrap.md:B03", "tests/test_release_bootstrap_workflow.py", "ReleaseBootstrapWorkflowTests", "test_guide_orders_semantic_release_before_manual_v1_move_and_selftest", "PARCIAL", "La guía ordena pasos, no acredita ejecución de publicación."),
    ("docs/release-bootstrap.md:B04", "tests/test_release_bootstrap_workflow.py", "ReleaseBootstrapWorkflowTests", "test_latest_rejects_distinct_shas_in_gate_body", "LOCAL", "Deriva invalida evidencia, no se hereda decisión stale."),
    ("docs/release-bootstrap.md:B05", "tests/test_release_bootstrap_workflow.py", "ReleaseBootstrapWorkflowTests", "test_latest_requires_newest_success_per_required_workflow_exact_sha", "PARCIAL", "Freeze/TTL y provenance reales necesitan inspección autenticada."),
    ("docs/readme-progress-readiness.md:B04", "tests/test_readme_progress.py", "ReadmeProgressTests", "test_unknown_stale_and_not_applicable_are_fail_closed", "LOCAL", "Estados de siete proyectos requieren observador real; UNKNOWN no es GREEN."),
    ("docs/readme-contract.md:B03", "tests/test_readme_contract_v2.py", "ReadmeContractV2Tests", "test_live_badges_use_only_platform_sources_and_no_generated_commits", "LOCAL", "La insignia requiere URL/health auténticos, no proxy."),
    ("docs/readme-contract.md:B04", "tests/test_readme_contract_v2.py", "ReadmeContractV2Tests", "test_live_badges_use_only_platform_sources_and_no_generated_commits", "LOCAL", "READMEs no crean commits para refrescar métricas."),
    ("docs/factory-living-software.md:B05", "tests/test_living_software_operational_e2e.py", "LivingSoftwareOperationalE2ETests", "test_manifest_uses_real_coordination_and_execution_evidence", "PARCIAL", "E2E reproducible no prueba ciclo live en producción."),
    ("docs/factory-living-software.md:B06", "tests/test_living_integration.py", "LivingIntegrationTests", "test_protocol_preserves_human_authority_boundaries", "LOCAL", "Promoción real continúa bloqueada por gates humanos."),
    ("docs/factoryrunner-execution-plane.md:B01", "tests/test_factoryrunner_architecture.py", "FactoryRunnerArchitectureTests", "test_authority_boundaries_are_explicit", "LOCAL", "Factory gobierna y ControlBot decide; no se amplía autoridad."),
    ("docs/factoryrunner-execution-plane.md:B02", "tests/test_factoryrunner_architecture.py", "FactoryRunnerArchitectureTests", "test_shared_hosting_is_primary_without_os_assumptions", "PARCIAL", "Contrato de hosting no prueba despliegue sin root real."),
    ("docs/factoryrunner-execution-plane.md:B03", "tests/test_factoryrunner_architecture.py", "FactoryRunnerArchitectureTests", "test_orders_are_secret_free_and_controlbot_owns_durable_state", "LOCAL", "Aliases/secretos resueltos solo en frontera autorizada."),
    ("docs/factoryrunner-execution-plane.md:B04", "tests/test_factoryrunner_architecture.py", "FactoryRunnerArchitectureTests", "test_runner_loss_is_reconstructible_and_idempotent", "LOCAL", "Entrega y eventos rechazan duplicados y stale en fixture."),
    ("docs/factoryrunner-execution-plane.md:B05", "tests/test_factoryrunner_architecture.py", "FactoryRunnerArchitectureTests", "test_orders_are_secret_free_and_controlbot_owns_durable_state", "PARCIAL", "Estado durable en ControlBot debe verificarse en runtime del consumidor."),
)


class VerificacionFactory17Tests(unittest.TestCase):
    def test_inventario_exactamente_setenta_filas(self):
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({r[0] for r in ROWS}), 70)
        doc = REPORT.read_text(encoding="utf-8")
        self.assertIn("NO_VERIFICABLE", doc)
        self.assertNotIn("CUBIERTO |", doc)
        for ident, filename, cls, method, status, limit in ROWS:
            with self.subTest(fila=ident):
                self.assertTrue((ROOT / filename).is_file(), filename)
                self.assertTrue(method.startswith("test_"))
                self.assertIn(f"`{ident}`", doc)
                self.assertIn(f"`{filename}::{cls}::{method}`", doc)
                self.assertIn(limit, doc)
                self.assertIn(status, {"LOCAL", "PARCIAL", "CONTRADICE", "DOCUMENTAL", "EXTERNO", "HISTORICO"})

    def test_testigos_ejecutan_contratos_y_fallan_si_se_revierten(self):
        modules = {}
        seen = set()
        for ident, filename, cls, method, _status, _limit in ROWS:
            key = (filename, cls, method)
            if key in seen:
                continue
            seen.add(key)
            with self.subTest(fila=ident, testigo=key):
                if filename not in modules:
                    name = "factory_verify17_" + Path(filename).stem
                    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[name] = mod
                    spec.loader.exec_module(mod)
                    modules[filename] = mod
                case = getattr(modules[filename], cls)(method)
                result = unittest.TestResult()
                unittest.TestSuite([case]).run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, str(result.errors))
                self.assertFalse(result.failures, str(result.failures))
                self.assertFalse(result.skipped, str(result.skipped))

    def test_no_confundir_fixtures_con_produccion(self):
        statuses = {r[0]: r[4] for r in ROWS}
        self.assertEqual(statuses["ISSUE-1080:AC-01"], "CONTRADICE")
        self.assertEqual(statuses["ISSUE-305:AC-12"], "PARCIAL")
        self.assertEqual(statuses["ISSUE-1382:AC-05"], "PARCIAL")
        self.assertEqual(statuses["docs/lista-salida-produccion.md:L83-U1"], "EXTERNO")
        self.assertTrue(all(r[5] for r in ROWS))


if __name__ == "__main__":
    unittest.main()
