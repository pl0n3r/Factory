"""Factory #2031: regresiones y estado real de las 70 filas del lote 15.

La evidencia usa pruebas reales ya existentes; lo histórico, el cron retirado
y la adopción de consumidores están etiquetados explícitamente como limitaciones.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

from intelligence.risk_compiler import (
    BASE_CONTROLS, HIGH_CONTROLS, MEDIUM_CONTROLS, _controls_for,
)

ROOT = Path(__file__).resolve().parents[1]
ROWS = (
    ("docs/risk-compiler.md:L13-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_risk_uses_task_and_project_dna",), "REGRESION"),
    ("docs/risk-compiler.md:L16-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_risk_uses_task_and_project_dna", "tests/test_risk_compiler.py::RiskCompilerTests::test_high_risk_never_compiles_weaker_controls",), "REGRESION"),
    ("docs/risk-compiler.md:L23-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_blast_radius_and_controls_are_traceable", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L24-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_blast_radius_and_controls_are_traceable", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L25-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_blast_radius_and_controls_are_traceable", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L26-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_blast_radius_and_controls_are_traceable", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L36-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_high_risk_never_compiles_weaker_controls", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L37-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_high_risk_never_compiles_weaker_controls", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L38-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_high_risk_never_compiles_weaker_controls", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L41-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_high_risk_never_compiles_weaker_controls", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_riesgo_trazable_y_controles_acumulativos",), "REGRESION"),
    ("docs/risk-compiler.md:L52-U1", "intelligence/risk_compiler.py", ("tests/test_risk_compiler.py::RiskCompilerTests::test_unknown_critical_signal_fails_safe",), "REGRESION"),
    ("docs/roles-profesionales.md:L3-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_catalog_has_all_required_complete_roles",), "REGRESION"),
    ("docs/roles-profesionales.md:L9-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_validate_pr_accepts_complete_multi_role_evidence",), "REGRESION"),
    ("docs/roles-profesionales.md:L10-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_validate_pr_accepts_complete_multi_role_evidence",), "REGRESION"),
    ("docs/roles-profesionales.md:L11-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_missing_checklist_fails_closed",), "REGRESION"),
    ("docs/roles-profesionales.md:L12-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_risk_without_cross_review_fails", "tests/test_roles_kit.py::RolesKitTests::test_schema_change_requires_dba_and_cross_review", "tests/test_roles_kit.py::RolesKitTests::test_workflow_change_requires_infra_sre_security",), "REGRESION"),
    ("docs/roles-profesionales.md:L14-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_issue_type_can_assign_role_without_files", "tests/test_roles_kit.py::RolesKitTests::test_workflow_change_requires_infra_sre_security",), "REGRESION"),
    ("docs/roles-profesionales.md:L14-U2", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_validate_pr_accepts_complete_multi_role_evidence", "tests/test_roles_kit.py::RolesKitTests::test_declaration_parser_does_not_accept_trailing_content_as_slug",), "REGRESION"),
    ("docs/roles-profesionales.md:L18-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_english_labels_are_enforced",), "REGRESION"),
    ("docs/roles-profesionales.md:L19-U1", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_english_labels_are_enforced",), "REGRESION"),
    ("docs/roles-profesionales.md:L21-U1", "scripts/roles_kit.py", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_validate_is_read_only_and_mutations_are_isolated", "tests/test_roles_kit.py::RolesKitTests::test_catalog_has_all_required_complete_roles",), "REGRESION"),
    ("docs/roles-profesionales.md:L25-U1", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_modes_language_and_ref_are_closed",), "REGRESION"),
    ("docs/roles-profesionales.md:L25-U2", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_modes_language_and_ref_are_closed",), "REGRESION"),
    ("docs/roles-profesionales.md:L26-U1", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_validate_is_read_only_and_mutations_are_isolated",), "REGRESION"),
    ("docs/roles-profesionales.md:L27-U1", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_validate_is_read_only_and_mutations_are_isolated",), "REGRESION"),
    ("docs/roles-profesionales.md:L28-U1", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_validate_is_read_only_and_mutations_are_isolated",), "REGRESION"),
    ("docs/roles-profesionales.md:L29-U1", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_context_enters_python_via_stdin_not_path_input", "tests/test_roles_kit.py::RolesKitTests::test_context_is_bounded_and_closed",), "REGRESION"),
    ("docs/roles-profesionales.md:L29-U2", ".github/workflows/roles.yml", ("tests/test_roles_workflow_contract.py::RolesWorkflowContractTests::test_context_enters_python_via_stdin_not_path_input", "tests/test_roles_kit.py::RolesKitTests::test_validation_and_cli_boundaries_are_covered",), "REGRESION"),
    ("docs/roles-profesionales.md:L30-U1", ".github/workflows/roles.yml", ("tests/test_roles_kit.py::RolesKitTests::test_issue_type_can_assign_role_without_files", "tests/test_roles_kit.py::RolesKitTests::test_validation_and_cli_boundaries_are_covered",), "REGRESION"),
    ("docs/roles-profesionales.md:L30-U2", "scripts/roles_kit.py", ("tests/test_roles_kit.py::RolesKitTests::test_context_is_bounded_and_closed", "tests/test_roles_kit.py::RolesKitTests::test_validation_and_cli_boundaries_are_covered",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L3-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_superseded_ce_task_is_pass_with_auditable_reason", "tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_non_superseded_ce_failure_remains_fail_closed",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L7-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_superseded_ce_task_is_pass_with_auditable_reason", "tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_similar_but_ambiguous_message_does_not_bypass_failure",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L10-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_superseded_ce_task_is_pass_with_auditable_reason",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L11-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_superseded_ce_task_is_pass_with_auditable_reason",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L12-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_superseded_ce_task_is_pass_with_auditable_reason",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L13-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_similar_but_ambiguous_message_does_not_bypass_failure",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L15-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_superseded_ce_task_closes_existing_watch_issue",), "REGRESION"),
    ("docs/sonar-superseded-ce.md:L21-U1", "quality/sonar.py", ("tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_non_superseded_ce_failure_remains_fail_closed", "tests/test_sonar_superseded_ce.py::SonarSupersededCeTests::test_similar_but_ambiguous_message_does_not_bypass_failure",), "REGRESION"),
    ("docs/tanda1-handoff.md:L9-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L9-U2", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L13-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L25-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L26-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L27-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L28-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L29-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_tanda1_and_first_release_are_closed", "tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_handoff_is_archived_as_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L33-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_handoff_is_archived_as_closed",), "HISTORICO"),
    ("docs/tanda1-handoff.md:L35-U1", "docs/tanda1-handoff.md", ("tests/test_readme_tanda1.py::ReadmeTanda1Tests::test_release_maintenance_boundary_is_documented",), "REGRESION"),
    ("docs/unattended-daily-summary.md:B04", ".github/workflows/unattended-watchdog.yml", ("tests/test_unattended_daily_summary.py::UnattendedDailySummaryTests::test_offline_publish_once_survives_without_daily_trigger", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_resumen_diario_no_declara_cron_activo",), "NO_ACTIVO"),
    ("docs/unattended-handoff-consumer-pack.md:L5-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_consumers_can_distinguish_allow_pause_blocked_unknown_without_recalculation", "tests/test_unattended_handoff_conformance_cli.py::UnattendedHandoffConformanceCliTests::test_cli_validates_local_fixture_deterministically",), "CONSUMIDOR_PENDIENTE"),
    ("docs/unattended-handoff-consumer-pack.md:L9-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_schema.py::UnattendedHandoffSchemaTests::test_schema_accepts_canonical_allow_pause_blocked_unknown_fixtures",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L33-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_consumers_can_distinguish_allow_pause_blocked_unknown_without_recalculation", "tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L43-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_schema.py::UnattendedHandoffSchemaTests::test_extra_sensitive_unknown_or_contradictory_fields_fail_closed", "tests/test_unattended_handoff_conformance_cli.py::UnattendedHandoffConformanceCliTests::test_cli_validates_local_fixture_deterministically",), "CONSUMIDOR_PENDIENTE"),
    ("docs/unattended-handoff-consumer-pack.md:L49-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L51-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L52-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L53-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L54-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L55-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L56-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L58-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L63-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_conformance_cli.py::UnattendedHandoffConformanceCliTests::test_cli_validates_local_fixture_deterministically", "tests/test_unattended_handoff_conformance_cli.py::UnattendedHandoffConformanceCliTests::test_cli_is_secret_free_and_external_io_free",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L64-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_schema.py::UnattendedHandoffSchemaTests::test_schema_accepts_canonical_allow_pause_blocked_unknown_fixtures", "tests/test_unattended_handoff_conformance_cli.py::UnattendedHandoffConformanceCliTests::test_cli_validates_local_fixture_deterministically",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L65-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_consumers_can_distinguish_allow_pause_blocked_unknown_without_recalculation", "tests/test_unattended_handoff_schema.py::UnattendedHandoffSchemaTests::test_schema_accepts_canonical_allow_pause_blocked_unknown_fixtures",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L67-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_consumers_can_distinguish_allow_pause_blocked_unknown_without_recalculation", "tests/test_unattended_handoff_conformance_cli.py::UnattendedHandoffConformanceCliTests::test_cli_validates_local_fixture_deterministically",), "REGRESION"),
    ("docs/unattended-handoff-consumer-pack.md:L68-U1", "config/unattended-handoff-v1.schema.json", ("tests/test_unattended_handoff_consumer_pack.py::UnattendedHandoffConsumerPackTests::test_pack_never_grants_reservation_merge_deploy_spend_or_live_authority", "tests/test_verificacion_factory_15.py::VerificacionFactory15Tests::test_handoff_esta_acotado_a_fixtures_offline",), "REGRESION"),
    ("docs/unattended-kill-switch.md:L11-U1", "scripts/unattended_kill_switch.py", ("tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_source_is_canonical_public_and_owner_controlled", "tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_missing_or_invalid_switch_fails_closed",), "REGRESION"),
    ("docs/unattended-kill-switch.md:L15-U1", "scripts/unattended_kill_switch.py", ("tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_reopened_canonical_source_fails_closed", "tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_single_closed_running_and_paused_remain_valid",), "REGRESION"),
    ("docs/unattended-kill-switch.md:L19-U1", "scripts/unattended_kill_switch.py", ("tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_source_is_canonical_public_and_owner_controlled", "tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_running_paused_missing_and_resume_feed_global_pause",), "REGRESION"),
    ("docs/unattended-kill-switch.md:L19-U2", "scripts/unattended_kill_switch.py", ("tests/test_unattended_kill_switch.py::UnattendedKillSwitchTests::test_running_paused_missing_and_resume_feed_global_pause",), "REGRESION"),
)


class VerificacionFactory15Tests(unittest.TestCase):
    """Mapa exacto, pruebas negativas y fronteras del lote 15/18."""

    def test_inventario_y_fuentes_70(self):
        """Cada fila del Issue aparece exactamente una vez en la hoja de evidencia."""
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({key for key, *_ in ROWS}), 70)
        self.assertEqual({key.split(":")[0] for key, *_ in ROWS}, {
            "docs/risk-compiler.md", "docs/roles-profesionales.md",
            "docs/sonar-superseded-ce.md", "docs/tanda1-handoff.md",
            "docs/unattended-daily-summary.md",
            "docs/unattended-handoff-consumer-pack.md",
            "docs/unattended-kill-switch.md",
        })
        doc = (ROOT / "docs/verificacion/verificacion-15.md").read_text(encoding="utf-8")
        table = []
        for line in doc.splitlines():
            if not line.startswith("| `docs/"):
                continue
            cells = [part.strip() for part in line.strip("|").split("|")]
            self.assertEqual(len(cells), 4)
            self.assertTrue(all(cell.startswith("`") and cell.endswith("`")
                                for cell in cells[:3]))
            table.append((cells[0][1:-1], cells[1][1:-1],
                          tuple(cells[2][1:-1].split(";")), cells[3]))
        self.assertEqual(table, list(ROWS))
        for key, source, refs, status in ROWS:
            with self.subTest(row=key):
                self.assertTrue((ROOT / key.split(":")[0]).is_file())
                self.assertTrue((ROOT / source).is_file())
                self.assertTrue(refs)
                self.assertIn(status, {
                    "REGRESION", "HISTORICO", "NO_ACTIVO", "CONSUMIDOR_PENDIENTE"
                })
        self.assertIn("NO_ACTIVO", doc)
        self.assertIn("HISTORICO", doc)
        self.assertIn("CONSUMIDOR_PENDIENTE", doc)
        self.assertIn("docs/matriz-cobertura.md", doc)

    def test_metodos_de_regresion_reales_sin_mock_de_salida(self):
        """Ejecuta cada aserción real referida una vez; un método ausente falla."""
        refs = sorted({ref for _, _, targets, _ in ROWS for ref in targets})
        self.assertGreaterEqual(len(refs), 30)
        for ref in refs:
            path, cls, method = ref.split("::")
            self.assertTrue(path.startswith("tests/test_") and path.endswith(".py"))
            self.assertTrue(method.startswith("test_"))
            self.assertTrue((ROOT / path).is_file())
            if path == "tests/test_verificacion_factory_15.py":
                self.assertIn(method, {
                    "test_riesgo_trazable_y_controles_acumulativos",
                    "test_resumen_diario_no_declara_cron_activo",
                    "test_handoff_esta_acotado_a_fixtures_offline",
                })
                continue  # unittest discover corre también estos métodos.
            module_name = "_factory15_" + Path(path).stem
            if module_name not in sys.modules:
                spec = importlib.util.spec_from_file_location(module_name, ROOT / path)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            suite = unittest.TestLoader().loadTestsFromName(
                cls + "." + method, sys.modules[module_name]
            )
            output = io.StringIO()
            result = unittest.TextTestRunner(stream=output).run(suite)
            with self.subTest(reference=ref):
                self.assertEqual(result.testsRun, 1, output.getvalue())
                self.assertTrue(result.wasSuccessful(), output.getvalue())

    def test_riesgo_trazable_y_controles_acumulativos(self):
        """Regresión directa: high contiene medium y low, sin dilución."""
        low = set(_controls_for("low"))
        medium = set(_controls_for("medium"))
        high = set(_controls_for("high"))
        self.assertEqual(low, set(BASE_CONTROLS))
        self.assertEqual(medium - low, set(MEDIUM_CONTROLS))
        self.assertEqual(high - medium, set(HIGH_CONTROLS))
        self.assertLess(len(low), len(medium))
        self.assertLess(len(medium), len(high))

    def test_resumen_diario_no_declara_cron_activo(self):
        """El cron histórico de las 08:00 no está habilitado en el workflow."""
        workflow = (ROOT / ".github/workflows/unattended-watchdog.yml").read_text(encoding="utf-8")
        self.assertNotIn("cron: '0 13 * * *'", workflow)
        self.assertNotIn("  daily-summary:", workflow)
        self.assertIn("cron: '*/15 * * * *'", workflow)

    def test_handoff_esta_acotado_a_fixtures_offline(self):
        """ALLOW comunica estado; jamás otorga reserva, fusión o gasto."""
        base = ROOT / "tests/fixtures/unattended_handoff_v1"
        for name in ("allow", "pause", "blocked", "unknown"):
            with self.subTest(fixture=name):
                item = json.loads((base / (name + ".json")).read_text(encoding="utf-8"))
                self.assertEqual(item["authority"], "unchanged")
                self.assertEqual(
                    item["permissions"],
                    {key: False for key in ("reserve", "merge", "deploy", "spend", "live")},
                )
        self.assertTrue((ROOT / "config/unattended-handoff-v1.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
