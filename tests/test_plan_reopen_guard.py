#!/usr/bin/env python3
"""Regresiones del guard de reapertura sobre evidencia exact-main."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")


class PlanReopenGuardTests(unittest.TestCase):
    def test_plan_requires_exact_main_preflight_before_reopen(self):
        for value in (
            "Preflight exact-main antes de reapertura o repair",
            "antes de reabrir un Issue cerrado como `completed`/`duplicate`",
            "resuelve el SHA exacto actual de `main`",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_plan_requires_contract_and_merged_pr_verification(self):
        required = (
            "relee el Issue y su contrato vigente",
            "verifica los AC y paths reclamados",
            "árbol actual de `main`",
            "PRs fusionados relevantes",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_plan_forbids_reopen_reservation_branch_and_pr_when_main_already_satisfies_contract(self):
        rule = (
            "Si `main` ya satisface el contrato, **no reabras el Issue, "
            "no ejecutes `/tomar`, no crees `trabajo/issue-N` ni abras PR**."
        )
        self.assertIn(rule, PLAN)
        self.assertIn(
            "Publica únicamente una reconciliación con evidencia exact-main",
            PLAN,
        )

    def test_plan_forbids_stale_close_when_main_does_not_satisfy_contract(self):
        required = (
            "Preflight exact-main antes de cierre/reconciliación terminal",
            "marcar `completed`/`duplicate`/`not_planned`",
            "Si `main` **no** satisface el contrato",
            "no cierres ni canceles el Issue/PR",
            "no liberes la lease por “ya satisfecho”",
            "Conserva la línea activa",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_plan_requires_reread_after_concurrent_change(self):
        required = (
            "otra línea cambia el Issue, la rama, `main` o un PR relevante",
            "descarta el snapshot previo",
            "relee el estado actual antes de cualquier mutación",
            "cierre/cancelación terminal ni liberación por reconciliación",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_regression_mentions_observed_stale_snapshot_pattern(self):
        self.assertIn("#699 → #703/#704/#705", PLAN)
        self.assertIn("#741/#763", PLAN)
        self.assertIn("atribuyó a `#762` un contrato que exact-main todavía no contenía", PLAN)
        preflight = PLAN.index("Preflight exact-main antes de reapertura o repair")
        terminal = PLAN.index("Preflight exact-main antes de cierre/reconciliación terminal")
        announcement = PLAN.index("Antes de bajar, **anuncia tu elección**")
        self.assertLess(preflight, terminal)
        self.assertLess(terminal, announcement)


if __name__ == "__main__":
    unittest.main()
