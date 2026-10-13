"""Contrato de privacidad y retiro del workflow opcional Cabina (F1D)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "cabina.yml"

class CabinaWorkflowContractTests(unittest.TestCase):
    def test_cabina_scheduler_and_pages_workflow_are_retired(self):
        self.assertFalse(WORKFLOW_PATH.exists(), "Cabina no debe volver a programarse ni publicar Pages")
        self.assertTrue((ROOT / "scripts" / "cabina.py").is_file())
        self.assertTrue((ROOT / "tests" / "test_cabina.py").is_file())

    def test_no_automatic_cabina_pages_publication(self):
        self.assertFalse(WORKFLOW_PATH.exists())
        self.assertTrue((ROOT / "scripts" / "cabina.py").is_file())

if __name__ == "__main__":
    unittest.main()
