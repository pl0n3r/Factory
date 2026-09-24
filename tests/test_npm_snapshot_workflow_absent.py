"""Regresión: el generador temporal de evidencia npm no llega a main."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NpmSnapshotWorkflowTests(unittest.TestCase):
    def test_generation_workflow_is_not_persisted(self):
        self.assertFalse(
            (ROOT / ".github/workflows/npm-snapshot-brvtal-temporal.yml").exists()
        )


if __name__ == "__main__":
    unittest.main()
