"""Factory #2022 / lote 06: 70 claims ligados a regresiones ejecutables exactas.

El mapa no afirma cobertura de consumidores; los tests delegan en unittest reales.
"""
from __future__ import annotations
import ast
import importlib.util
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROWS = (
    ("docs/knowledge-lifecycle.md:L40-U1", ("tests/test_knowledge_lifecycle.py::KnowledgeLifecycleTests::test_pruning_proposes_without_deleting_history",)),
    ("docs/knowledge-lifecycle.md:L40-U2", ("tests/test_knowledge_lifecycle.py::KnowledgeLifecycleTests::test_pruning_proposes_without_deleting_history", "tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_pruning_and_supersession_preserve_history_without_delete",)),
    ("docs/knowledge-lifecycle.md:L42-U1", ("tests/test_knowledge_lifecycle.py::KnowledgeLifecycleTests::test_expired_rule_cannot_increase_autonomy", "tests/test_knowledge_lifecycle.py::KnowledgeLifecycleTests::test_revalidation_restores_active_state_with_new_evidence",)),
    ("docs/knowledge-operations-e2e.md:L7-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_verified_postmortems_can_feed_guardrail_candidate_without_promotion",)),
    ("docs/knowledge-operations-e2e.md:L9-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_stale_knowledge_is_excluded_and_pruning_is_non_destructive",)),
    ("docs/knowledge-operations-e2e.md:L13-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_verified_postmortems_can_feed_guardrail_candidate_without_promotion",)),
    ("docs/knowledge-operations-e2e.md:L14-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_pruning_and_supersession_preserve_history_without_delete",)),
    ("docs/knowledge-operations-e2e.md:L15-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_e2e_preserves_provenance_authority_and_has_no_external_runtime", "tests/test_verificacion_factory_06.py::VerificacionFactory06Tests::test_static_boundaries_without_external_io",)),
    ("docs/knowledge-operations-e2e.md:L16-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_output_is_non_executing_and_sanitized", "tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_e2e_preserves_provenance_authority_and_has_no_external_runtime",)),
    ("docs/knowledge-operations-e2e.md:L17-U1", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_adapts_current_scoped_items_for_context_compiler",)),
    ("docs/knowledge-operations-e2e.md:L18-U1", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_context_adapter_preserves_provenance_and_authority",)),
    ("docs/knowledge-operations-e2e.md:L20-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_readme_boundary_keeps_deep_knowledge_outside_operational_portada",)),
    ("docs/knowledge-operations.md:L9-U1", ("tests/test_knowledge_lifecycle.py::KnowledgeLifecycleTests::test_promotable_knowledge_requires_provenance_scope_and_review_policy",)),
    ("docs/knowledge-operations.md:L11-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_current_scoped_knowledge_reaches_context_compiler_without_authority_expansion",)),
    ("docs/knowledge-operations.md:L13-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_verified_postmortems_can_feed_guardrail_candidate_without_promotion", "tests/test_knowledge_lifecycle.py::KnowledgeLifecycleTests::test_pruning_proposes_without_deleting_history",)),
    ("docs/knowledge-operations.md:L20-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata",)),
    ("docs/knowledge-operations.md:L21-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata", "tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_fails_closed_for_sensitive_unknown_or_inconsistent_metadata",)),
    ("docs/knowledge-operations.md:L22-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata",)),
    ("docs/knowledge-operations.md:L23-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata",)),
    ("docs/knowledge-operations.md:L24-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata",)),
    ("docs/knowledge-operations.md:L25-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata",)),
    ("docs/knowledge-operations.md:L26-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_reuses_lifecycle_freshness_and_supersession",)),
    ("docs/knowledge-operations.md:L27-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_reuses_lifecycle_freshness_and_supersession",)),
    ("docs/knowledge-operations.md:L35-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_fails_closed_for_sensitive_unknown_or_inconsistent_metadata",)),
    ("docs/knowledge-operations.md:L42-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_reuses_lifecycle_freshness_and_supersession",)),
    ("docs/knowledge-operations.md:L45-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_reuses_lifecycle_freshness_and_supersession", "tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_fails_closed_for_stale_sensitive_or_unknown_input",)),
    ("docs/knowledge-operations.md:L56-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_fails_closed_for_sensitive_unknown_or_inconsistent_metadata",)),
    ("docs/knowledge-operations.md:L58-U1", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_fails_closed_for_stale_sensitive_or_unknown_input",)),
    ("docs/knowledge-operations.md:L63-U1", ("tests/test_verificacion_factory_06.py::VerificacionFactory06Tests::test_static_boundaries_without_external_io",)),
    ("docs/knowledge-operations.md:L64-U1", ("tests/test_verificacion_factory_06.py::VerificacionFactory06Tests::test_static_boundaries_without_external_io",)),
    ("docs/knowledge-operations.md:L65-U1", ("tests/test_verificacion_factory_06.py::VerificacionFactory06Tests::test_static_boundaries_without_external_io",)),
    ("docs/knowledge-operations.md:L67-U1", ("tests/test_knowledge_contract.py::KnowledgeContractTests::test_contract_reuses_lifecycle_freshness_and_supersession", "tests/test_verificacion_factory_06.py::VerificacionFactory06Tests::test_static_boundaries_without_external_io",)),
    ("docs/knowledge-operations.md:L68-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_e2e_preserves_provenance_authority_and_has_no_external_runtime",)),
    ("docs/knowledge-operations.md:L69-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_readme_boundary_keeps_deep_knowledge_outside_operational_portada",)),
    ("docs/knowledge-postmortem.md:L9-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_distinguishes_known_and_unknown_root_cause_with_evidence",)),
    ("docs/knowledge-postmortem.md:L10-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_distinguishes_known_and_unknown_root_cause_with_evidence",)),
    ("docs/knowledge-postmortem.md:L10-U2", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_distinguishes_known_and_unknown_root_cause_with_evidence",)),
    ("docs/knowledge-postmortem.md:L10-U3", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_only_emits_guardrail_input_from_verified_known_cause",)),
    ("docs/knowledge-postmortem.md:L11-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_fields_are_closed_bounded_deterministic_and_sensitive_safe",)),
    ("docs/knowledge-postmortem.md:L12-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_output_is_non_executing_and_sanitized",)),
    ("docs/knowledge-postmortem.md:L16-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_only_emits_guardrail_input_from_verified_known_cause",)),
    ("docs/knowledge-postmortem.md:L20-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_reuses_knowledge_contract_and_preserves_authority",)),
    ("docs/knowledge-postmortem.md:L21-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_only_emits_guardrail_input_from_verified_known_cause",)),
    ("docs/knowledge-postmortem.md:L22-U1", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_adapts_current_scoped_items_for_context_compiler",)),
    ("docs/knowledge-postmortem.md:L23-U1", ("tests/test_knowledge_operations_e2e.py::KnowledgeOperationsE2ETests::test_capture_lifecycle_context_and_guardrail_flow_is_traceable",)),
    ("docs/knowledge-postmortem.md:L25-U1", ("tests/test_knowledge_postmortem.py::KnowledgePostmortemTests::test_postmortem_output_is_non_executing_and_sanitized", "tests/test_verificacion_factory_06.py::VerificacionFactory06Tests::test_static_boundaries_without_external_io",)),
    ("docs/knowledge-selection.md:L5-U1", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_adapts_current_scoped_items_for_context_compiler",)),
    ("docs/knowledge-selection.md:L7-U1", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_adapts_current_scoped_items_for_context_compiler", "tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_fails_closed_for_stale_sensitive_or_unknown_input",)),
    ("docs/knowledge-selection.md:L7-U2", ("tests/test_knowledge_selection.py::KnowledgeSelectionTests::test_selection_fails_closed_for_stale_sensitive_or_unknown_input",)),
    ("docs/label-color-sync.md:L7-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_apply_plan_only_edits_existing_colors_in_allowlisted_repositories",)),
    ("docs/label-color-sync.md:L7-U2", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_brvtal_uses_english_catalog_without_renaming_labels",)),
    ("docs/label-color-sync.md:L8-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_es_and_en_catalogs_keep_color_parity_by_key",)),
    ("docs/label-color-sync.md:L9-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_dry_run_is_deterministic_and_reports_only_color_drift",)),
    ("docs/label-color-sync.md:L10-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_apply_plan_only_edits_existing_colors_in_allowlisted_repositories", "tests/test_sync_label_colors.py::SyncLabelColorsTests::test_client_paginates_reads_and_apply_only_patches_color",)),
    ("docs/label-color-sync.md:L11-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_brvtal_uses_english_catalog_without_renaming_labels",)),
    ("docs/label-color-sync.md:L17-U1", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_planned_state_exists_in_both_catalogs_with_same_semantic_key_and_color",)),
    ("docs/label-color-sync.md:L18-U1", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_planned_state_exists_in_both_catalogs_with_same_semantic_key_and_color",)),
    ("docs/label-color-sync.md:L18-U2", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_planned_state_exists_in_both_catalogs_with_same_semantic_key_and_color", "tests/test_labels_catalogs.py::LabelCatalogTests::test_raw_planning_issue_without_execution_evidence_fails_closed",)),
    ("docs/label-color-sync.md:L20-U1", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_required_dimensions_exist", "tests/test_labels_catalogs.py::LabelCatalogTests::test_raw_planning_issue_without_execution_evidence_fails_closed",)),
    ("docs/label-color-sync.md:L22-U1", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_raw_planning_issue_without_execution_evidence_fails_closed",)),
    ("docs/label-color-sync.md:L22-U2", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_raw_planning_issue_without_execution_evidence_fails_closed",)),
    ("docs/label-color-sync.md:L22-U3", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_identical_colors_produce_empty_idempotent_plan", "tests/test_labels_catalogs.py::LabelCatalogTests::test_raw_planning_issue_without_execution_evidence_fails_closed",)),
    ("docs/label-color-sync.md:L24-U1", ("tests/test_labels_catalogs.py::LabelCatalogTests::test_planned_state_exists_in_both_catalogs_with_same_semantic_key_and_color",)),
    ("docs/label-color-sync.md:L24-U2", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_workflow_is_owner_only_secret_safe_and_apply_is_explicit",)),
    ("docs/label-color-sync.md:L28-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_workflow_is_owner_only_secret_safe_and_apply_is_explicit",)),
    ("docs/label-color-sync.md:L30-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_workflow_is_owner_only_secret_safe_and_apply_is_explicit", "tests/test_sync_label_colors.py::SyncLabelColorsTests::test_cli_reports_success_and_safe_errors_without_network",)),
    ("docs/label-color-sync.md:L30-U2", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_es_and_en_catalogs_keep_color_parity_by_key", "tests/test_sync_label_colors.py::SyncLabelColorsTests::test_apply_plan_only_edits_existing_colors_in_allowlisted_repositories",)),
    ("docs/label-color-sync.md:L32-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_execute_dry_run_never_passes_token_to_client", "tests/test_sync_label_colors.py::SyncLabelColorsTests::test_workflow_is_owner_only_secret_safe_and_apply_is_explicit",)),
    ("docs/label-color-sync.md:L36-U1", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_apply_plan_only_edits_existing_colors_in_allowlisted_repositories", "tests/test_sync_label_colors.py::SyncLabelColorsTests::test_collect_snapshots_and_execute_apply_are_idempotent",)),
    ("docs/label-color-sync.md:L36-U2", ("tests/test_sync_label_colors.py::SyncLabelColorsTests::test_apply_plan_only_edits_existing_colors_in_allowlisted_repositories",)),
)

class VerificacionFactory06Tests(unittest.TestCase):
    def test_inventario_de_70_afirmaciones_y_documentacion(self):
        self.assertEqual(len(ROWS), 70)
        keys = [key for key, _ in ROWS]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual({key.split(":")[0] for key in keys}, {
            "docs/knowledge-lifecycle.md", "docs/knowledge-operations-e2e.md",
            "docs/knowledge-operations.md", "docs/knowledge-postmortem.md",
            "docs/knowledge-selection.md", "docs/label-color-sync.md",
        })
        document = (ROOT / "docs/verificacion/verificacion-06.md").read_text(encoding="utf-8")
        lines = []
        for line in document.splitlines():
            if not line.startswith("| `docs/"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            self.assertEqual(len(cells), 4)
            key, source, refs, state = cells
            self.assertTrue(all(item.startswith("`") and item.endswith("`") for item in (key, source, refs)))
            lines.append((key[1:-1], source[1:-1], refs[1:-1], state))
        self.assertEqual(len(lines), 70)
        self.assertEqual(
            {key: tuple(refs.split(";")) for key, _src, refs, _state in lines},
            dict(ROWS),
        )
        for key, source, refs, state in lines:
            with self.subTest(claim=key):
                self.assertTrue((ROOT / key.split(":")[0]).is_file())
                self.assertTrue((ROOT / source).is_file())
                self.assertTrue(refs.startswith("tests/"))
                if state == "DEPENDENCIA_CONSUMIDOR":
                    self.assertTrue(key.startswith("docs/label-color-sync.md:L24-"))
        self.assertIn("ControlBot#752", document)
        self.assertIn("sin escribir en docs/matriz-cobertura.md", document.lower())

    def test_regresiones_ejecutables_por_fila(self):
        refs = sorted({ref for _key, refs in ROWS for ref in refs})
        self.assertGreaterEqual(len(refs), 20)
        for ref in refs:
            path, class_name, method = ref.split("::")
            self.assertTrue(path.startswith("tests/test_") and path.endswith(".py"))
            self.assertRegex(method, r"^test_[a-z0-9_]+$")
            if path == "tests/test_verificacion_factory_06.py":
                self.assertEqual(method, "test_static_boundaries_without_external_io")
                continue  # unittest discover ejecuta esta regresión en el mismo job.
            module_name = "_factory_verificacion06_" + Path(path).stem
            if module_name not in sys.modules:
                spec = importlib.util.spec_from_file_location(module_name, ROOT / path)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            suite = unittest.TestLoader().loadTestsFromName(
                class_name + "." + method, sys.modules[module_name]
            )
            output = io.StringIO()
            result = unittest.TextTestRunner(stream=output).run(suite)
            with self.subTest(reference=ref):
                self.assertEqual(result.testsRun, 1, output.getvalue())
                self.assertTrue(result.wasSuccessful(), output.getvalue())

    def test_static_boundaries_without_external_io(self):
        """Cierra store/red/scheduler/procesos en los adapters de conocimiento."""
        banned_imports = {
            "os", "pathlib", "subprocess", "socket", "urllib", "requests",
            "httpx", "sqlite3", "mysql", "asyncio", "threading", "schedule",
        }
        banned_calls = {"open", "exec", "eval", "__import__"}
        for path in (
            "knowledge/contract.py", "knowledge/postmortem.py",
            "knowledge/selection.py", "evolution/knowledge_lifecycle.py",
        ):
            with self.subTest(path=path):
                tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
                imported, called = set(), set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(a.name.split(".")[0] for a in node.names)
                    if isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module.split(".")[0])
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        called.add(node.func.id)
                self.assertFalse(imported & banned_imports, path)
                self.assertFalse(called & banned_calls, path)
        self.assertFalse((ROOT / ".github/workflows/sync-label-colors.yml").exists())

if __name__ == "__main__":
    unittest.main()
