"""Factory #1311 F1D: baja única y reversible de Cabina programada."""
from __future__ import annotations
import unittest
from pathlib import Path
from tests.test_dieta_fase1c import EXPECTED_ACTIVE
from tests.test_scheduled_entrypoints import EXPECTED, SAFE_ARGS

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
CANDIDATE = "cabina.yml"
BLOB = "8fbbd85b5697a43d196223292961c77976d45f96"

class DietaFase1DTests(unittest.TestCase):
    def active(self):
        return {p.name for ext in ("*.yml", "*.yaml") for p in WF.glob(ext) if p.is_file()}

    def test_cabina_optional_workflow_removed_after_consumers_preflight(self):
        active = self.active()
        self.assertEqual(active, set(EXPECTED_ACTIVE) - {CANDIDATE})
        self.assertEqual(len(active), 33)
        self.assertNotIn(CANDIDATE, active)
        for name in active:
            content = (WF / name).read_text(encoding="utf-8")
            self.assertNotIn("workflow_call: cabina", content)
        for name in ("ci.yml", "factory-ci.yml", "sonar.yml",
                     "seguridad.yml", "codeql-evidence.yml", "privacidad.yml"):
            self.assertIn(name, active)

    def test_offline_cabina_and_sentry_regressions_preserved(self):
        for file in ("scripts/cabina.py", "tests/test_cabina.py",
                     "tests/test_cabina_sentry.py", "tests/test_cabina_workflow_contract.py"):
            self.assertTrue((ROOT / file).is_file())
        source = (ROOT / "scripts/cabina.py").read_text(encoding="utf-8")
        compile(source, "scripts/cabina.py", "exec")
        self.assertIn("inicializar_sentry", source)
        self.assertIn("send_default_pii", source)
        self.assertFalse((WF / CANDIDATE).exists())

    def test_scheduled_entrypoints_and_previous_diet_ledgers_are_consistent(self):
        self.assertNotIn("scripts/cabina.py", EXPECTED)
        self.assertTrue((ROOT / "scripts/cabina.py").is_file())
        doc = (ROOT / "docs/dieta-factory.md").read_text(encoding="utf-8")
        for token in ("38 workflows", "36 workflows", "35 workflows",
                      "34 workflows", "33 workflows", "## Ledger F1A",
                      "## Ledger F1B", "## Ledger F1C", "## Ledger F1D"):
            self.assertIn(token, doc)

    def test_f1d_ledger_has_one_exact_deletion_and_squash_revert(self):
        doc = (ROOT / "docs/dieta-factory.md").read_text(encoding="utf-8")
        ledger = doc.split("## Ledger F1D de baja de Cabina\n", 1)[1].split("\n## ", 1)[0]
        row = ("| F1D | `.github/workflows/cabina.yml` | `" + BLOB
               + "` | 34 → 33 | squash-revert PR F1D |")
        def check(value):
            rows = [line for line in value.splitlines()
                    if line.startswith("| F1D |")]
            if rows != [row]:
                raise AssertionError("La baja F1D debe ser única y exacta")
        check(ledger)
        with self.assertRaises(AssertionError):
            check(ledger + "\n" + row)
        with self.assertRaises(AssertionError):
            check(ledger + "\n| F1D | `.github/workflows/otro.yml` | `" +
                  "0" * 40 + "` | 34 → 32 | squash-revert PR F1D |")
        self.assertIn("no publicar Pages", ledger)
        self.assertIn("squash-revert solo del PR F1D", ledger)

if __name__ == "__main__":
    unittest.main()
