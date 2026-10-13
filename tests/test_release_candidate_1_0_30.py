#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.30 (#1244).

El inventario dinámico v1...main se documenta en el PR, no se congela
como una cifra en el test ni concede permiso para mover el tag v1.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1030Tests(unittest.TestCase):
    def test_candidate_version_and_file_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 30))

        # Contratos ya integrados: coordinación por archivo y liberación V3
        # puramente offline. La habilitación operativa corresponde a #1175.
        expected_paths = (
            "scripts/coordinar_trabajo.py",
            "tests/test_parallel_coordination.py",
            "tests/test_parallel_grant_exclusivity.py",
            "scripts/lease_auto_release.py",
            "scripts/lease_activity_collector.py",
            "scripts/lease_release_executor.py",
            "tests/test_lease_auto_release.py",
            "tests/test_lease_activity_collector.py",
            "tests/test_lease_release_executor.py",
        )
        for relative_path in expected_paths:
            with self.subTest(path=relative_path):
                self.assertTrue((root / relative_path).is_file(), relative_path)


if __name__ == "__main__":
    unittest.main()
