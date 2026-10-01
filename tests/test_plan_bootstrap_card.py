#!/usr/bin/env python3
"""Regresiones de la tarjeta de arranque de PLAN-AGENTES.md."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "PLAN-AGENTES.md"
README = ROOT / "README.md"

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


class PlanBootstrapCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = PLAN.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")

    def _card(self) -> str:
        start = self.plan.index("## Tarjeta de arranque del agente")
        end = self.plan.index(
            "## 0. Dónde trabajar: modo dirigido o modo despachador"
        )
        return self.plan[start:end]

    def test_readme_dispatch_prompts_remain_exact(self) -> None:
        self.assertIn(f"```\n{DIRECTED_PROMPT}\n```", self.readme)
        self.assertIn(f"```\n{DISPATCH_PROMPT}\n```", self.readme)
        self.assertEqual(self.readme.count(DIRECTED_PROMPT), 1)
        self.assertEqual(self.readme.count(DISPATCH_PROMPT), 1)

    def test_bootstrap_card_precedes_existing_operational_sections_and_is_complete(self) -> None:
        card = self._card()
        self.assertLess(
            self.plan.index("## Tarjeta de arranque del agente"),
            self.plan.index("## 0. Dónde trabajar: modo dirigido o modo despachador"),
        )
        for required in (
            "**Misión:**",
            "### Preflight de capacidades",
            "### Fuentes exactas para obtener estado",
            "### Árbol de despacho vigente",
            "Despacho (<id>)",
            "### Prohibiciones esenciales",
        ):
            with self.subTest(required=required):
                self.assertIn(required, card)

    def test_preflight_fails_closed_and_documents_authenticated_github_path(self) -> None:
        card = self._card()
        self.assertIn(
            "PARADO: falta acceso a GitHub para abrir URLs exactas, "
            "leer estado y comentar Issues.",
            card,
        )
        self.assertIn("conector autenticado de GitHub", card)
        self.assertIn("60 solicitudes por hora por IP", card)
        for repo in (
            "Factory",
            "Condor",
            "GrindFlow",
            "brvtal",
            "ControlBot",
            "AutoFactory",
            "FactoryRunner",
        ):
            with self.subTest(repo=repo):
                base = f"https://api.github.com/repos/pl0n3r/{repo}"
                self.assertIn(f"{base}/issues?state=open", card)
                self.assertIn(f"{base}/pulls?state=open", card)

    def test_bootstrap_card_references_existing_non_idle_ladder_without_redefining_priority(self) -> None:
        card = self._card()
        self.assertIn("No redefine prioridades", card)
        self.assertIn("Factory#699/#702", card)
        self.assertIn("escalera no ociosa", card)
        self.assertIn("aplica la sección 0", card)
        self.assertIn(
            "### Escalera cuando no existe trabajo `ready`",
            self.plan,
        )


if __name__ == "__main__":
    unittest.main()
