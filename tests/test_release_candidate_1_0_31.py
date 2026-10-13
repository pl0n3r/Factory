#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.31 (#1329).

El inventario dinámico v1...main se documenta en el PR, no se congela como
una cifra en el test ni concede permiso para mover el tag v1.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1031Tests(unittest.TestCase):
    def test_candidate_version_and_file_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 31))

        # Contratos que esta release debe llevar a los consumidores.
        expected_paths = (
            "scripts/automerge_construccion.py",
            "tests/test_essential_gates.py",
            "docs/dieta-factory.md",
            "tests/test_factory_diet_inventory.py",
            "tests/test_plan_issue_budget.py",
        )
        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((root / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
