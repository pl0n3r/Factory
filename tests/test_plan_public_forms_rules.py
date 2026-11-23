"""Contrato durable de formularios públicos y robustez de guardado en PLAN-AGENTES.md."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "PLAN-AGENTES.md"


class PlanPublicFormsRulesTests(unittest.TestCase):
    """Evita que los productos pierdan las defensas transversales en el plan."""

    @classmethod
    def setUpClass(cls):
        cls.lines = PLAN.read_text(encoding="utf-8").splitlines()

    @classmethod
    def rule(cls, prefix):
        matching = [line for line in cls.lines if line.startswith(prefix)]
        if len(matching) != 1:
            raise AssertionError(
                f"Se esperaba una sola regla {prefix}: {len(matching)}"
            )
        return matching[0]

    def test_public_forms_rule_requires_abuse_controls_and_burst_discovery(self):
        """AC-01: toda ruta pública de escritura conserva defensas anti-bots."""
        rule = self.rule("- **Formularios públicos")
        required = (
            "endpoint público de escritura",
            "`POST`",
            "`PUT`",
            "`PATCH`",
            "`DELETE`",
            "por IP",
            "identificador estable",
            "`429`",
            "`Retry-After`",
            "`honeypot`",
            "tiempo mínimo",
            "CAPTCHA",
            "creen cuentas",
            "envíen correos",
            "prueba de ráfaga",
            "router/código",
            "ruta nueva",
            "debe hacer fallar CI",
            "[BRVTAL #1877]",
            "https://github.com/pl0n3r/brvtal/issues/1877",
            "[Condor #1967]",
            "https://github.com/pl0n3r/Condor/issues/1967",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, rule)

    def test_save_robustness_rule_runs_fuzzing_in_ci_with_known_findings_baseline(self):
        """AC-02: endpoints autenticados usan fuzzing y línea base sin ocultar regresiones."""
        rule = self.rule("- **Robustez de guardado en CI")
        required = (
            "endpoint autenticado de escritura",
            "`POST`",
            "`PUT`",
            "`PATCH`",
            "`DELETE`",
            "batería automatizada de entradas raras",
            "CI",
            "router/código",
            "UTF-8 inválido",
            "estructuras profundas",
            "sobredimensionadas",
            "5xx",
            "trazas/SQL/rutas internas",
            "ida/vuelta",
            "línea base versionada",
            "endpoint, problema e Issue",
            "hallazgo nuevo",
            "hace fallar CI",
            "corregirse antes de fusionar",
            "[Condor #1955]",
            "https://github.com/pl0n3r/Condor/issues/1955",
            "[BRVTAL #1868]",
            "https://github.com/pl0n3r/brvtal/issues/1868",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, rule)


if __name__ == "__main__":
    unittest.main()
