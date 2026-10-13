"""F1E: workflow retirement preserves offline engine and historical identity QA."""
from __future__ import annotations
import unittest
from pathlib import Path
from tests.test_dieta_fase1c import EXPECTED_ACTIVE
from tests.test_captura_leccion_workflow import HISTORICAL_WORKFLOW

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
RETIRED = "captura-leccion.yml"
BLOB = "df7cdd904b9370600a897f174d28322e5a99d84e"
HARD_GATES = ("factory-ci.yml", "sonar.yml", "codeql-evidence.yml",
              "costos.yml", "coordinacion-trabajo.yml", "seguridad.yml",
              "privacidad.yml", "unattended-watchdog.yml", "release.yml", "deploy.yml")

class DietaFase1ETests(unittest.TestCase):
    @staticmethod
    def active():
        return {p.name for extension in ("*.yml", "*.yaml")
                for p in WF.glob(extension) if p.is_file()}

    def test_only_offline_capture_trigger_is_retired_after_lease_dependency(self):
        active = self.active()
        self.assertEqual(len(active), 31)
        self.assertEqual(active, set(EXPECTED_ACTIVE))
        self.assertNotIn(RETIRED, active)
        self.assertFalse((WF / RETIRED).exists())
        for gate in HARD_GATES:
            self.assertIn(gate, active)
        for name in active:
            self.assertNotIn("captura-leccion.yml", (WF / name).read_text(encoding="utf-8"))

    def test_lesson_engine_and_security_regressions_survive_without_scheduler(self):
        for path in ("scripts/captura_leccion.py", "tests/test_captura_leccion.py",
                     "tests/test_captura_leccion_workflow.py"):
            self.assertTrue((ROOT / path).is_file())
        compile((ROOT / "scripts/captura_leccion.py").read_text(encoding="utf-8"),
                "scripts/captura_leccion.py", "exec")
        for token in ("TRUST_GATE_START", "ambiguous_issue_closure",
                      "merge_identity_invalid", "permissions:\n  contents: read"):
            self.assertIn(token, HISTORICAL_WORKFLOW)
        self.assertNotIn("contents: write", HISTORICAL_WORKFLOW)
        self.assertNotIn("pull_request_target", HISTORICAL_WORKFLOW)

    def test_historical_38_36_35_34_33_32_31_inventory_and_unique_ledger(self):
        doc = (ROOT / "docs/dieta-factory.md").read_text(encoding="utf-8")
        for value in (38, 36, 35, 34, 33, 32, 31):
            self.assertIn(f"{value} workflows", doc)
        for phase in ("F1A", "F1B", "F1C", "F1D", "F2A", "F1E"):
            self.assertIn("## Ledger " + phase, doc)
        section = doc.split("## Ledger F1E de baja de Captura de lecciones\n", 1)[1].split("\n## ", 1)[0]
        row = ("| F1E | `.github/workflows/captura-leccion.yml` | `" +
               BLOB + "` | 32 → 31 | squash-revert PR F1E |")
        def verify(text):
            rows = [line for line in text.splitlines() if line.startswith("| F1E |")]
            if rows != [row]:
                raise AssertionError("F1E requires exactly one authorized retirement")
        verify(section)
        with self.assertRaises(AssertionError):
            verify(section + "\n" + row)
        with self.assertRaises(AssertionError):
            verify(section + "\n| F1E | `.github/workflows/extra.yml` | `" +
                   "0" * 40 + "` | 32 → 30 | squash-revert PR F1E |")
        self.assertIn("squash-revert solo del PR F1E", section)

    def test_no_live_phase_one_trigger_paths_and_exact_set_negative_swap(self):
        doc = (ROOT / "docs/dieta-factory.md").read_text(encoding="utf-8")
        phase1 = doc.split("### Fase 1:", 1)[1].split("### Fase 2:", 1)[0]
        self.assertNotIn("`.github/workflows/captura-leccion.yml`", phase1)
        self.assertNotIn("`.github/workflows/cabina.yml`", phase1)
        active = self.active()
        self.assertEqual(active, set(EXPECTED_ACTIVE))
        victim = next(iter(sorted(active)))
        swapped = (active - {victim}) | {"trigger-no-autorizado.yml"}
        self.assertEqual(len(swapped), 31)
        self.assertNotEqual(swapped, set(EXPECTED_ACTIVE))


if __name__ == "__main__":
    unittest.main()
