"""Factory F2A: baja reversible de trigger de sincronización de colores."""
from __future__ import annotations
import unittest
from pathlib import Path
from tests.test_dieta_fase1c import EXPECTED_ACTIVE

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
RETIRED = "sync-label-colors.yml"
BLOB = "7005e0cddab8fe5dfc7635a05f3001cd61497d5f"

class DietaFase2ATests(unittest.TestCase):
    def active(self):
        return {p.name for ext in ("*.yml", "*.yaml") for p in WF.glob(ext) if p.is_file()}

    def test_single_label_color_workflow_retired_without_hard_gate_loss(self):
        active = self.active()
        self.assertEqual(len(active), 31)
        self.assertNotIn(RETIRED, active)
        self.assertEqual(active, set(EXPECTED_ACTIVE))
        for gate in ("factory-ci.yml", "sonar.yml", "codeql-evidence.yml",
                     "coordinacion-trabajo.yml", "costos.yml", "privacidad.yml",
                     "seguridad.yml", "release.yml", "unattended-watchdog.yml"):
            self.assertIn(gate, active)

    def test_offline_label_color_engine_regressions_preserved(self):
        self.assertTrue((ROOT / "scripts/sync_label_colors.py").is_file())
        self.assertTrue((ROOT / "tests/test_sync_label_colors.py").is_file())
        compile((ROOT / "scripts/sync_label_colors.py").read_text(encoding="utf-8"),
                "scripts/sync_label_colors.py", "exec")
        self.assertFalse((WF / RETIRED).exists())

    def test_historical_inventory_and_live_phase_routes_consistent(self):
        doc = (ROOT / "docs/dieta-factory.md").read_text(encoding="utf-8")
        for token in ("38 workflows", "36 workflows", "35 workflows",
                      "34 workflows", "33 workflows", "32 workflows",
                      "## Ledger F1A", "## Ledger F1B", "## Ledger F1C",
                      "## Ledger F1D", "## Ledger F2A"):
            self.assertIn(token, doc)
        self.assertNotIn(RETIRED, set(self.active()))
        phase1 = doc.split("### Fase 1:", 1)[1].split("### Fase 2:", 1)[0]
        self.assertNotIn("`.github/workflows/cabina.yml`", phase1)

    def test_owner_command_runbook_marks_trigger_disabled(self):
        runbook = (ROOT / "docs/label-color-sync.md").read_text(encoding="utf-8")
        self.assertFalse((WF / RETIRED).exists())
        self.assertIn("trigger remoto está desactivado", runbook)
        self.assertIn("ya no ejecuta", runbook)
        self.assertIn("Factory #874", runbook)
        self.assertIn("scripts/sync_label_colors.py", runbook)
        self.assertIn("--dry-run", runbook)
        self.assertIn("No ejecutar `--apply`", runbook)
        self.assertIn("FACTORY_PROVISION_TOKEN", runbook)
        self.assertNotIn("El primer comando ejecuta", runbook)
        self.assertNotIn("El segundo comando requiere", runbook)

    def test_exact_f2a_ledger_single_row_and_revert(self):
        doc = (ROOT / "docs/dieta-factory.md").read_text(encoding="utf-8")
        section = doc.split("## Ledger F2A de baja de Sync Label Colors\n", 1)[1].split("\n## ", 1)[0]
        row = ("| F2A | `.github/workflows/sync-label-colors.yml` | `" +
               BLOB + "` | 33 → 32 | squash-revert PR F2A |")
        def check(candidate):
            rows = [line for line in candidate.splitlines() if line.startswith("| F2A |")]
            if rows != [row]:
                raise AssertionError("F2A requiere exactamente una baja")
        check(section)
        with self.assertRaises(AssertionError):
            check(section + "\n" + row)
        with self.assertRaises(AssertionError):
            check(section + "\n| F2A | `.github/workflows/otro.yml` | `" +
                  "0" * 40 + "` | 33 → 31 | squash-revert PR F2A |")
        self.assertIn("squash-revert solo del PR F2A", section)

if __name__ == "__main__":
    unittest.main()
