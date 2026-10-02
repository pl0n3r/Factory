#!/usr/bin/env python3
"""Regresiones del archivo histórico de PLAN-AGENTES."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
ARCHIVE = (ROOT / "docs" / "archivo" / "plan-agentes-tandas-1-2.md").read_text(encoding="utf-8")
LIVING = (ROOT / "docs" / "factory-living-software.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

DIRECTED_PROMPT = (
    "Trabajas en el repositorio pl0n3r/Condor. Lee y ejecuta "
    "https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md "
    "para este repositorio."
)
DISPATCH_PROMPT = (
    "Lee y ejecuta "
    "https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md "
    "en modo despachador."
)


class PlanArchiveTests(unittest.TestCase):
    def test_tanda1_and_tanda2_live_only_in_archived_document(self):
        self.assertIn("ARCHIVADO · ya cumplido · no aplicar", ARCHIVE)
        self.assertIn("## TANDA 1", ARCHIVE)
        self.assertIn("## TANDA 2: adoptar el kit", ARCHIVE)
        for historical in (
            "PR #205",
            "Production Smoke (#121, #73)",
            "Orden: #14 arranque",
            "Cierra como resueltos por el kit",
        ):
            with self.subTest(historical=historical):
                self.assertIn(historical, ARCHIVE)
                self.assertNotIn(historical, PLAN)
        self.assertNotIn("\n## TANDA 1\n", PLAN)
        self.assertNotIn("\n## TANDA 2: adoptar el kit", PLAN)

    def test_plan_points_to_estado_and_archive_without_changing_tanda_gate(self):
        self.assertIn("[ESTADO.md](ESTADO.md)", PLAN)
        self.assertIn(
            "[docs/archivo/plan-agentes-tandas-1-2.md]"
            "(docs/archivo/plan-agentes-tandas-1-2.md)",
            PLAN,
        )
        self.assertIn("## 6. Cómo determinar tu tanda", PLAN)
        self.assertIn("### Definición de VERDE", PLAN)
        self.assertIn("## TANDA 3: desarrollo normal", PLAN)
        self.assertIn("Condor#192, GrindFlow#129, brvtal#630 y **FactoryRunner#1**", PLAN)

    def test_living_software_detail_is_canonical_in_docs_not_duplicated_in_plan(self):
        self.assertIn("docs/factory-living-software.md", PLAN)
        self.assertIn("#209–#227", PLAN)
        self.assertNotIn("### Estado de hardening de fronteras de evidencia", PLAN)
        self.assertNotIn("1. **Project DNA**", PLAN)
        self.assertIn("Project DNA", LIVING)
        for issue in ("#209", "#211", "#213", "#215", "#221", "#223", "#227"):
            with self.subTest(issue=issue):
                self.assertIn(issue, LIVING)
        self.assertIn("no amplía autoridad", PLAN)
        self.assertIn("no sustituye puertas humanas", PLAN)
        self.assertIn("continúa fallando cerrado", PLAN)

    def test_bootstrap_prompts_and_dispatch_ranking_stay_frozen(self):
        self.assertEqual(README.count(DIRECTED_PROMPT), 1)
        self.assertEqual(README.count(DISPATCH_PROMPT), 1)
        ordered = (
            "HEALTH degradado",
            "Issue abierto de incidente",
            "reparación activa válida",
            "decisión del dueño ya respondida",
            "prioridad: crítica",
            "prioridad: alta",
            "media",
        )
        positions = [PLAN.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Despacho: elegí <repo>#<n> porque <regla N>", PLAN)


if __name__ == "__main__":
    unittest.main()
