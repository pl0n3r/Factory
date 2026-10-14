#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.33 (#1355).

El inventario dinámico v1...main se documenta en el PR, no se congela como
una cifra en el test ni concede permiso para mover el tag v1.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1033Tests(unittest.TestCase):
    def test_candidate_version_and_file_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 32))

        # Contratos que esta release debe llevar a los consumidores.
        expected_paths = (
            "scripts/lease_github_port.py",
            "scripts/lease_auto_release_run.py",
            "tests/test_lease_github_port.py",
)
        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((root / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
