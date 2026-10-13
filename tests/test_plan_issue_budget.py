"""Verifica el presupuesto normativo de Issues de Factory #1289."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "PLAN-AGENTES.md"


class PlanIssueBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        full = PLAN.read_text(encoding="utf-8")
        heading = "### Presupuesto de creación de Issues"
        assert full.count(heading) == 1, "sección ausente o duplicada"
        cls.section = full.split(heading, 1)[1].split("\nReglas del despachador:", 1)[0]

    def test_plan_declares_issue_creation_budget(self):
        section = self.section
        self.assertIn("Antes de abrir cualquier Issue nuevo", section)
        self.assertIn("únicos cuatro motivos autorizados", section)
        for reason in (
            "Impacto demostrado en producción",
            "Bloqueo de CI o release en un repositorio ya desplegado",
            "Solicitud explícita del dueño",
            "Hoja de épica del roadmap vigente",
        ):
            self.assertIn(reason, section)
        self.assertEqual(len(re.findall(r"(?m)^[1-4]\.\s+\*\*", section)), 4)

    def test_findings_on_merged_work_go_to_comment_or_debt_backlog(self):
        section = self.section
        for clause in (
            "Hallazgos de QA, hardening o casos extremos de trabajo ya fusionado",
            "comentario en el Issue o PR padre",
            "un único Issue backlog de deuda técnica por repositorio",
            "No abrir un Issue nuevo por cada hallazgo",
        ):
            self.assertIn(clause, section)

    def test_hardening_findings_cannot_chain_into_new_issues(self):
        section = self.section
        self.assertIn("Sin cadenas de endurecimiento", section)
        self.assertIn("un hallazgo sobre un fix de endurecimiento", section)
        self.assertIn("no puede generar otro Issue de endurecimiento", section)
        self.assertIn("comentario o deuda técnica acumulada", section)

    def test_unproven_hardening_is_not_typed_incident_and_cannot_preempt(self):
        section = self.section
        self.assertIn("hardening sin explotación ni impacto demostrado", section)
        self.assertIn("no usa tipo: incidente", section)
        self.assertIn("tipo: mejora, prioridad: baja", section)
        self.assertIn("No preempta HEALTH", section)
        self.assertIn("regla 2", section)

    def test_open_hardening_cap_per_repo(self):
        section = self.section
        self.assertIn("10 o más Issues abiertos de endurecimiento", section)
        self.assertIn("no se abren más", section)
        self.assertIn("backlog de deuda técnica único", section)
        self.assertIn("no autoriza cerrar ni reclasificar Issues existentes", section)


if __name__ == "__main__":
    unittest.main()
