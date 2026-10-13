"""Factory #1301: F1A elimina dos triggers sin retirar controles ni dominio."""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from tests.test_factory_diet_inventory import REQUIRED_KEEP, inventory_rows

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DOC = ROOT / "docs" / "dieta-factory.md"
REMOVED = {
    ".github/workflows/evolution-lab.yml": (
        "645cd08c9d9f79e23e945f798d14b225eaf0e95d",
        "tests/test_factory_lab_contract.py",
    ),
    ".github/workflows/feedback-producto.yml": (
        "fe107d7f3a39a30d4fecefd0ca1c9ece68f5e490",
        "tests/test_feedback_contract.py",
    ),
}
BASELINE_SHA = "173519bde16498a796afd6a5af96b517d7e3a091"
ALLOWED_CHANGE_PATHS = {
    *REMOVED,
    "tests/test_factory_lab_contract.py",
    "tests/test_dieta_fase1a.py",
    "docs/dieta-factory.md",
    "tests/test_factory_diet_inventory.py",
    "tests/test_scheduled_entrypoints.py",
}
LEDGER_ROW = re.compile(
    r"^\| ([12]) \| \x60(\.github/workflows/[^\x60]+\.yml)\x60 \| "
    r"\x60([0-9a-f]{40})\x60 \| F1A / fase 1 \| "
    r"squash-revert PR F1A \| \x60([^\x60]+)\x60 \|$",
    re.MULTILINE,
)


class DietaFase1ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = DOC.read_text(encoding="utf-8")
        cls.rows = inventory_rows(cls.document)

    @staticmethod
    def actual_workflows() -> set[str]:
        return {
            path.relative_to(ROOT).as_posix()
            for ext in ("*.yml", "*.yaml")
            for path in WORKFLOWS.glob(ext)
            if path.is_file()
        }

    def test_optional_triggers_removed_only_after_dependency_and_consumer_preflight(self):
        """AC-01: solo desaparecen triggers opcionales sin callers vivos."""
        actual = self.actual_workflows()
        self.assertEqual(len(actual), 31)
        self.assertEqual(set(self.rows), actual)
        for name in REMOVED:
            with self.subTest(removed=name):
                self.assertNotIn(name, actual)
                self.assertFalse((ROOT / name).exists())
                for workflow in actual:
                    self.assertNotIn(
                        name,
                        (ROOT / workflow).read_text(encoding="utf-8"),
                        f"Caller todavía utiliza {name}: {workflow}",
                    )
        self.assertIn(f"main@{BASELINE_SHA}", self.document)
        self.assertIn("88 workflows de consumidores", self.document)

    def test_lab_and_feedback_offline_regressions_survive(self):
        """AC-02: validación Lab, producto, métricas y suites offline."""
        required = (
            "lab/factory_lab.py",
            "evolution/constitution.py",
            "producto/feedback.py",
            "producto/metricas.json",
            "tests/test_factory_lab_contract.py",
            "tests/test_experiment_evidence.py",
            "tests/test_feedback_contract.py",
            "producto/test_feedback.py",
        )
        for path in required:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), f"Suite/motor perdido: {path}")
        lab = sorted((ROOT / "lab").glob("*.py"))
        self.assertTrue(lab)
        for source in lab + [ROOT / "producto" / "feedback.py"]:
            with self.subTest(compilation=source.name):
                compile(source.read_text(encoding="utf-8"), str(source), "exec")
        values = json.loads((ROOT / "producto" / "metricas.json").read_text(encoding="utf-8"))
        self.assertIsInstance(values, (dict, list))

    def test_ci_preserves_read_only_lab_suite_execution(self):
        """La suite Lab sigue bajo el runner CI sin privilegios de escritura."""
        workflow = (WORKFLOWS / "factory-ci.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("  scripts:\n", workflow)
        scripts = workflow.split("  scripts:\n", 1)[1].split("\n  release_window:", 1)[0]
        self.assertIn(
            "python3 -m unittest discover -s tests -p 'test_*.py'", scripts
        )
        self.assertRegex(scripts, r"uses: actions/checkout@[0-9a-f]{40}")
        self.assertIn("persist-credentials: false", scripts)
        self.assertNotRegex(
            scripts,
            r"(?m)^\s*(?:contents|checks|issues|actions|pull-requests):\s*write\s*$",
        )
        self.assertNotIn("secrets.", scripts)
        self.assertTrue((ROOT / "tests" / "test_factory_lab_contract.py").is_file())
        self.assertTrue((ROOT / "tests" / "test_experiment_evidence.py").is_file())

    def test_hard_gates_and_lease_authority_remain_unchanged(self):
        """AC-03: seguridad, presupuesto y locks no son objeto de F1A."""
        for workflow in REQUIRED_KEEP | {
            "seguridad.yml", "sonar.yml", "codeql-evidence.yml",
            "costos.yml", "coordinacion-trabajo.yml", "coordinacion.yml",
            "unattended-watchdog.yml", "deploy.yml", "release.yml",
            "privacidad.yml", "liberar-reservas.yml",
        }:
            with self.subTest(gate=workflow):
                self.assertTrue((WORKFLOWS / workflow).is_file())
        costs = (WORKFLOWS / "costos.yml").read_text(encoding="utf-8")
        self.assertIn("presupuesto-pr:", costs)
        watchdog = (WORKFLOWS / "unattended-watchdog.yml").read_text(encoding="utf-8")
        # F1G cambia el contrato accesorio con runbook explícito, no el
        # watchdog ni sus puertas duras heredadas de F1A.
        runbook = (ROOT / "docs" / "unattended-watchdog-runtime.md").read_text(
            encoding="utf-8")
        f1g_enabled = "## F1G: resumen diario accesorio suspendido" in runbook
        self.assertIn("watchdog:", watchdog)
        self.assertIn("scripts.unattended_watchdog_runtime", watchdog)
        self.assertIn("cron: '*/15 * * * *'", watchdog)
        self.assertIn("group: unattended-watchdog-${{ github.repository_id }}",
                      watchdog)
        self.assertIn("issues: write", watchdog)
        if f1g_enabled:
            self.assertNotIn("  daily-summary:", watchdog)
            self.assertNotIn("cron: '0 13 * * *'", watchdog)
            self.assertNotIn("python3 -m scripts.unattended_daily_summary",
                             watchdog)
        else:
            self.assertIn("  daily-summary:", watchdog)
            self.assertIn("cron: '0 13 * * *'", watchdog)
            self.assertIn("python3 -m scripts.unattended_daily_summary",
                          watchdog)
        self.assertTrue((ROOT / "scripts" / "unattended_kill_switch.py").is_file())
        self.assertTrue((ROOT / "scripts" / "coordinar_trabajo.py").is_file())
        for token in ("CodeQL", "Sonar", "CodeRabbit", "#767", "go-live"):
            self.assertIn(token, self.document)

    def test_phase1a_changes_are_reversible_and_bounded(self):
        """AC-04: baseline 38 → 36, ledger 2/2 y revert acotado."""
        self.assertEqual(len(ALLOWED_CHANGE_PATHS), 7)
        self.assertIn(f"main@{BASELINE_SHA}", self.document)
        self.assertIn("38 workflows", self.document)
        self.assertIn("36 workflows", self.document)
        section = self.document.split("## Ledger F1A de bajas autorizadas\n", 1)[1].split(
            "\n## ", 1
        )[0]
        rows = LEDGER_ROW.findall(section)
        self.assertEqual(len(rows), 2)
        self.assertEqual({number for number, *_ in rows}, {"1", "2"})
        self.assertEqual({path: (sha, suite) for _, path, sha, suite in rows}, REMOVED)
        self.assertEqual(len(self.actual_workflows()) + len(rows) + 5, 38)
        self.assertIn("squash-revert PR F1A", section)
        self.assertEqual(set(self.rows), self.actual_workflows())
        for _, suite in REMOVED.values():
            self.assertTrue((ROOT / suite).is_file())


if __name__ == "__main__":
    unittest.main()
