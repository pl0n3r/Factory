"""Regresiones ejecutables F1B: retirar cron mensual sin perder motores ni gates."""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.test_factory_diet_inventory import (
    FactoryDietInventoryTests, inventory_rows,
)
from tests.test_scheduled_entrypoints import (
    EXPECTED, SAFE_ARGS, ScheduledEntrypointTests,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DOC = ROOT / "docs" / "dieta-factory.md"
METRICS = ".github/workflows/metricas.yml"
ENGINE = "metricas/evaluar_agentes.py"
F1A_SHA = "2e20aef7fd8b019c677acec37e18d711341662cc"
METRICS_BLOB = "f76a0bac2f9fc7b3669fbc58b968f1136c05d527"


class DietaFase1BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = DOC.read_text(encoding="utf-8")
        cls.rows = inventory_rows(cls.document)

    @staticmethod
    def workflows() -> set[str]:
        return {
            p.relative_to(ROOT).as_posix()
            for pattern in ("*.yml", "*.yaml")
            for p in WORKFLOWS.glob(pattern)
            if p.is_file()
        }

    def test_only_metrics_trigger_is_removed_and_other_workflows_remain(self):
        """AC-01: inventario exacto, una sola baja y cero callers locales."""
        active = self.workflows()
        self.assertEqual(len(active), 34)
        self.assertEqual(set(self.rows), active)
        self.assertNotIn(METRICS, active)
        self.assertFalse((ROOT / METRICS).exists())
        for name in active:
            with self.subTest(workflow=name):
                self.assertNotIn(
                    METRICS, (ROOT / name).read_text(encoding="utf-8")
                )
        for name in ("costos.yml", "factory-ci.yml", "unattended-watchdog.yml"):
            self.assertIn(".github/workflows/" + name, active)

    def test_metrics_engine_and_offline_ci_regressions_survive(self):
        """AC-02: motor/suites métricas siguen en el CI común sin cron nuevo."""
        for name in (
            ENGINE, "metricas/costos.py", "metricas/test_evaluar_agentes.py",
            "metricas/test_producto_diario.py",
            "tests/test_metricas_integer_bounds.py",
        ):
            with self.subTest(path=name):
                self.assertTrue((ROOT / name).is_file())
        source = (ROOT / ENGINE).read_text(encoding="utf-8")
        compile(source, ENGINE, "exec")
        ci = (WORKFLOWS / "factory-ci.yml").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s metricas", ci)
        self.assertIn("unittest discover -s tests", ci)
        self.assertIn("PYTHONPATH=metricas", ci)
        self.assertIn("persist-credentials: false", ci)

    def test_scheduled_entrypoints_reflect_disabled_monthly_job(self):
        """AC-03: entrada no programada, pero su --help sigue cubierto."""
        self.assertNotIn(ENGINE, EXPECTED)
        self.assertIn(ENGINE, SAFE_ARGS)
        case = ScheduledEntrypointTests(
            "test_all_scheduled_python_path_entrypoints_are_import_safe"
        )
        found = case._scheduled_paths()
        self.assertEqual(found, EXPECTED)
        self.assertNotIn(ENGINE, found)
        self.assertTrue((ROOT / ENGINE).is_file())
        case.test_all_scheduled_python_path_entrypoints_are_import_safe()

    def test_historical_f1a_and_f1b_ledgers_match_exact_workflow_sets(self):
        """AC-04: registrar 38 → 36 → 35 y rechazar baja extra en inventario."""
        for token in ("38 workflows", "36 workflows", "35 workflows"):
            self.assertIn(token, self.document)
        self.assertIn("## Ledger F1A de bajas autorizadas", self.document)
        section = self.document.split(
            "## Ledger F1B de baja del cron de métricas\n", 1
        )[1].split("\n## ", 1)[0]
        self.assertIn("main@" + F1A_SHA, section)
        expected_row = (
            "| F1B | `" + METRICS + "` | `" + METRICS_BLOB
            + "` | 36 → 35 | squash-revert PR F1B |"
        )
        self.assertIn(expected_row, section)
        self.assertEqual(len(self.workflows()), 34)
        # F1A conserva manifiesto inmutable de 38 rutas, veto exact-set
        # y una prueba negativa de swap con cardinalidad idéntica.
        case = FactoryDietInventoryTests(
            "test_f1a_ledger_matches_exact_two_deletions"
        )
        case.__class__.setUpClass()
        case.test_f1a_ledger_matches_exact_two_deletions()

    def test_hard_gates_and_rollback_are_preserved(self):
        """AC-05: presupuesto, seguridad y recuperación siguen bloqueando."""
        for name in (
            "costos.yml", "unattended-watchdog.yml", "factory-ci.yml",
            "seguridad.yml", "sonar.yml", "codeql-evidence.yml",
            "coordinacion-trabajo.yml", "release-window.yml",
            "deploy.yml", "release.yml", "privacidad.yml",
        ):
            with self.subTest(gate=name):
                self.assertTrue((WORKFLOWS / name).is_file())
        costs = (WORKFLOWS / "costos.yml").read_text(encoding="utf-8")
        self.assertIn("presupuesto-pr:", costs)
        self.assertIn("metricas/costos.py pr", costs)
        watchdog = (WORKFLOWS / "unattended-watchdog.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("watchdog:", watchdog)
        self.assertIn("daily-summary:", watchdog)
        ledger = self.document.split(
            "## Ledger F1B de baja del cron de métricas\n", 1
        )[1].split("\n## ", 1)[0]
        self.assertIn("squash-revert solo del PR F1B", ledger)
        for token in ("Factory@v1", "seguridad", "privacidad"):
            self.assertIn(token, self.document)


if __name__ == "__main__":
    unittest.main()
