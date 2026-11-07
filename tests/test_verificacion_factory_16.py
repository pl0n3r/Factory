#!/usr/bin/env python3
"""Testigos ejecutables y límites honestos del lote 16 de cobertura Factory.

No promueve filas en docs/matriz-cobertura.md y no usa servicios externos.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import unittest

from scripts.unattended_kill_switch import (
    CANONICAL_OWNER,
    CANONICAL_REPOSITORY_URL,
    CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-16.md"
SUITES = {
    "K": ("tests/test_unattended_kill_switch.py", "UnattendedKillSwitchTests"),
    "D": ("tests/test_unattended_safe_mode_e2e.py", "UnattendedSafeModeE2ETests"),
    "S": ("tests/test_unattended_state_source.py", "UnattendedStateSourceTests"),
    "W": ("tests/test_unattended_watchdog_runtime.py", "UnattendedWatchdogRuntimeTests"),
    "P": ("tests/test_performance_remediation.py", "PerformanceRemediationTests"),
}
# ID de la matriz, testigo de código en repo, método exacto, límite de inferencia.
ROWS = (
    ("docs/unattended-kill-switch.md:L20-U1", "K", "test_running_paused_missing_and_resume_feed_global_pause", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L20-U2", "K", "test_running_paused_missing_and_resume_feed_global_pause", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L21-U1", "K", "test_missing_or_invalid_switch_fails_closed", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L21-U2", "K", "test_missing_or_invalid_switch_fails_closed", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L25-U1", "K", "test_owner_runbook_is_short_and_explicit", "LIMITE_GOBERNANZA"),
    ("docs/unattended-kill-switch.md:L27-U1", "K", "test_plan_and_startup_card_check_switch_before_dispatch_or_write", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L31-U1", "K", "test_owner_runbook_is_short_and_explicit", "LIMITE_GOBERNANZA"),
    ("docs/unattended-kill-switch.md:L33-U1", "K", "test_running_paused_missing_and_resume_feed_global_pause", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L37-U1", "K", "test_missing_or_invalid_switch_fails_closed", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L39-U1", "K", "test_missing_or_invalid_switch_fails_closed", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L40-U1", "K", "test_missing_or_invalid_switch_fails_closed", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L41-U1", "K", "test_plan_and_startup_card_check_switch_before_dispatch_or_write", "LIMITE_GOBERNANZA"),
    ("docs/unattended-kill-switch.md:L42-U1", "K", "test_case_variant_duplicate_header_fails_closed", "LIMITE_GOBERNANZA"),
    ("docs/unattended-kill-switch.md:L46-U1", "K", "test_case_variant_duplicate_header_fails_closed", "SINTETICO"),
    ("docs/unattended-kill-switch.md:L48-U1", "K", "test_owner_runbook_is_short_and_explicit", "LIMITE_GOBERNANZA"),
    ("docs/unattended-kill-switch.md:L52-U1", "K", "test_plan_and_startup_card_check_switch_before_dispatch_or_write", "LIMITE_GOBERNANZA"),
    ("docs/unattended-safe-mode-drill.md:L5-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L16-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L23-U1", "D", "test_healthy_baseline_stays_allowed_without_false_alerts", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L24-U1", "D", "test_healthy_baseline_stays_allowed_without_false_alerts", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L25-U1", "D", "test_healthy_baseline_stays_allowed_without_false_alerts", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L30-U1", "D", "test_pause_breaker_and_ceilings_stop_new_work_without_expanding_authority", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L31-U1", "D", "test_pause_breaker_and_ceilings_stop_new_work_without_expanding_authority", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L34-U1", "D", "test_pause_breaker_and_ceilings_stop_new_work_without_expanding_authority", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L40-U1", "D", "test_stale_state_idle_dispatch_and_stalled_reservation_are_idempotently_reported", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L41-U1", "D", "test_stale_state_idle_dispatch_and_stalled_reservation_are_idempotently_reported", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L42-U1", "D", "test_stale_state_idle_dispatch_and_stalled_reservation_are_idempotently_reported", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L43-U1", "D", "test_stale_state_idle_dispatch_and_stalled_reservation_are_idempotently_reported", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L46-U1", "D", "test_stale_state_idle_dispatch_and_stalled_reservation_are_idempotently_reported", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L52-U1", "D", "test_sustained_red_smoke_prefers_reversible_rollback_or_fail_closed_stop", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L62-U1", "D", "test_sustained_red_smoke_prefers_reversible_rollback_or_fail_closed_stop", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L63-U1", "D", "test_sustained_red_smoke_prefers_reversible_rollback_or_fail_closed_stop", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L64-U1", "D", "test_sustained_red_smoke_prefers_reversible_rollback_or_fail_closed_stop", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L65-U1", "D", "test_sustained_red_smoke_prefers_reversible_rollback_or_fail_closed_stop", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L74-U1", "D", "test_only_s1_s2_interrupt_owner_and_unknown_stays_fail_closed", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L80-U1", "D", "test_only_s1_s2_interrupt_owner_and_unknown_stays_fail_closed", "SINTETICO"),
    ("docs/unattended-safe-mode-drill.md:L80-U2", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L85-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L92-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L93-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L94-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L95-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L97-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode-drill.md:L98-U1", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode.md:B03", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-safe-mode.md:B04", "D", "test_sensitive_authority_boundaries_remain_closed_and_external_io_free", "LIMITE_OPERATIVO"),
    ("docs/unattended-state-source.md:L11-U1", "S", "test_state_marker_is_closed_bound_and_secret_free", "SINTETICO"),
    ("docs/unattended-state-source.md:L13-U1", "S", "test_state_marker_is_closed_bound_and_secret_free", "SINTETICO"),
    ("docs/unattended-state-source.md:L13-U2", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L13-U3", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L17-U1", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L18-U1", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L18-U2", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L19-U1", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L20-U1", "S", "test_invalid_or_incoherent_sources_fail_closed", "SINTETICO"),
    ("docs/unattended-state-source.md:L21-U1", "S", "test_plan_requires_machine_readable_state_at_handoff", "LIMITE_INTEGRACION"),
    ("docs/unattended-state-source.md:L29-U1", "S", "test_presence_never_invents_heartbeat_or_capacity", "SINTETICO"),
    ("docs/unattended-state-source.md:L30-U1", "S", "test_presence_never_invents_heartbeat_or_capacity", "SINTETICO"),
    ("docs/unattended-state-source.md:L31-U1", "S", "test_presence_never_invents_heartbeat_or_capacity", "SINTETICO"),
    ("docs/unattended-state-source.md:L33-U1", "S", "test_presence_never_invents_heartbeat_or_capacity", "LIMITE_INTEGRACION"),
    ("docs/unattended-state-source.md:L41-U1", "S", "test_state_marker_is_closed_bound_and_secret_free", "SINTETICO"),
    ("docs/unattended-state-source.md:L45-U1", "W", "test_runtime_projects_live_github_state_source_fail_closed", "LIMITE_INTEGRACION"),
    ("docs/unattended-state-source.md:L46-U1", "S", "test_plan_requires_machine_readable_state_at_handoff", "LIMITE_INTEGRACION"),
    ("docs/unattended-state-source.md:L47-U1", "S", "test_invalid_or_incoherent_sources_fail_closed", "LIMITE_INTEGRACION"),
    ("docs/unattended-watchdog-runtime.md:B03", "W", "test_watchdog_schedule_keeps_explicit_quarter_hour_cadence", "LIMITE_OPERATIVO"),
    ("docs/unattended-watchdog-runtime.md:B04", "W", "test_main_push_never_runs_daily_summary", "LIMITE_OPERATIVO"),
    ("ISSUE-304:AC-01", "P", "test_plan_requires_material_finding_and_allowed_action", "BRECHA_EPIC_304"),
    ("ISSUE-304:AC-02", "P", "test_before_after_requires_same_current_identity_and_budget_direction", "BRECHA_EPIC_304"),
    ("ISSUE-304:AC-03", "P", "test_output_is_sanitized_non_executing_and_queue_only", "BRECHA_EPIC_304"),
    ("ISSUE-304:AC-04", "P", "test_before_after_adopts_only_newer_distinct_current_evidence", "BRECHA_EPIC_304"),
)
LIMITS = frozenset({"LIMITE_GOBERNANZA", "LIMITE_OPERATIVO",
                    "LIMITE_INTEGRACION", "BRECHA_EPIC_304"})


def _canonical_issue(state: str = "RUNNING") -> dict[str, object]:
    """Fixture sintético sin red; la identidad no implica autor de edición."""
    return {
        "number": 767,
        "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL,
        "state": "closed",
        "user": {"login": CANONICAL_OWNER},
        "body": (
            '<!-- factory-unattended-kill-switch '
            f'{{"version":1,"state":"{state}","owner":"pl0n3r"}} -->'
        ),
    }


class VerificacionFactory16Tests(unittest.TestCase):
    """La evidencia debe permanecer causal y distinguir límites externos."""

    def test_exactamente_las_70_filas_del_lote_sin_promocion(self):
        self.assertEqual(len(ROWS), 70)
        identifiers = [item[0] for item in ROWS]
        self.assertEqual(len(set(identifiers)), 70)
        report = REPORT.read_text(encoding="utf-8")
        rendered = re.findall(r"^\| \x60([^\x60]+)\x60 \|", report, re.MULTILINE)
        self.assertEqual(rendered, identifiers)
        self.assertIn("No se promueve ninguna fila", report)
        self.assertNotIn("| CUBIERTO |", report)
        self.assertEqual(sum(id_.startswith("ISSUE-304:") for id_ in identifiers), 4)

    def test_todos_los_testigos_estan_identificados_en_codigo_real(self):
        """Un nombre inventado o un archivo ausente rompe este gate."""
        for identifier, suite_key, method, scope in ROWS:
            with self.subTest(row=identifier):
                self.assertIn(suite_key, SUITES)
                self.assertIn(scope, {"SINTETICO"} | LIMITS)
                path, klass = SUITES[suite_key]
                source = (ROOT / path).read_text(encoding="utf-8")
                self.assertRegex(source, r"(?m)^class " + re.escape(klass) + r"\(")
                self.assertRegex(
                    source,
                    r"(?m)^\s+def " + re.escape(method) + r"\(self\)",
                )

    def test_regresiones_reales_corren_con_fixtures_sinteticos(self):
        """Ejecuta cada testigo distinto: se detecta al revertir su contrato."""
        cache = {}
        for suite_key, method in sorted({(row[1], row[2]) for row in ROWS}):
            path, klass = SUITES[suite_key]
            if suite_key not in cache:
                spec = importlib.util.spec_from_file_location(
                    f"_factory_16_witness_{suite_key}", ROOT / path
                )
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                cache[suite_key] = module
            case = getattr(cache[suite_key], klass)(methodName=method)
            result = unittest.TestResult()
            case.run(result)
            self.assertTrue(
                result.wasSuccessful(),
                f"{path}::{method}: errores={result.errors}, fallos={result.failures}",
            )

    def test_kill_switch_fail_closed_incluso_con_running_ambiguo(self):
        running = evaluate_unattended_kill_switch(_canonical_issue())
        self.assertEqual((running.state, running.global_pause), ("RUNNING", False))
        paused = evaluate_unattended_kill_switch(_canonical_issue("PAUSED"))
        self.assertEqual((paused.state, paused.global_pause), ("PAUSED", True))
        reopened = _canonical_issue()
        reopened["state"] = "open"
        self.assertEqual(
            (evaluate_unattended_kill_switch(reopened).state,
             evaluate_unattended_kill_switch(reopened).global_pause),
            ("UNKNOWN", True),
        )
        ambiguous = _canonical_issue()
        ambiguous["body"] += "\n" + _canonical_issue("PAUSED")["body"]
        denial = evaluate_unattended_kill_switch(ambiguous)
        self.assertEqual((denial.state, denial.global_pause),
                         ("UNKNOWN", True))

    def test_limites_operativos_y_epic_304_no_se_presentan_como_produccion(self):
        report = REPORT.read_text(encoding="utf-8")
        self.assertIn("sin demostrar operación real", report)
        for row_id, _, _, scope in ROWS:
            with self.subTest(row=row_id):
                line = next(
                    (line for line in report.splitlines()
                     if line.startswith("| \x60" + row_id + "\x60 |")), ""
                )
                self.assertTrue(line)
                self.assertIn("NO_VERIFICABLE", line)
                self.assertIn(scope, line)
        for row_id in ("ISSUE-304:AC-01", "ISSUE-304:AC-02",
                       "ISSUE-304:AC-03", "ISSUE-304:AC-04"):
            self.assertIn(row_id, report)
            self.assertIn("BRECHA_EPIC_304", next(
                line for line in report.splitlines()
                if line.startswith("| \x60" + row_id + "\x60 |")
            ))


if __name__ == "__main__":
    unittest.main()
