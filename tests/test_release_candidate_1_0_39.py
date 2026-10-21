#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.39 (#1446).

El contrato acredita inventario GET-only y versión; NO publica @v1,
ni certifica ciclos Fase A ni activa liberación automática.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1039Tests(unittest.TestCase):
    def test_candidate_version_and_observer_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 39))

        paths = (
            ".github/workflows/observador-reservas-consumidor.yml",
            "template/.github/workflows/observador-reservas-consumidor.yml",
            "scripts/lease_auto_release_integration.py",
            "tests/test_lease_consumer_observer.py",
            "docs/observador-reservas-consumidor.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue((root / path).is_file(), path)

        reusable = (
            root / ".github/workflows/observador-reservas-consumidor.yml"
        ).read_text(encoding="utf-8")
        caller = (
            root / "template/.github/workflows/observador-reservas-consumidor.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_call:", reusable)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", reusable)
        self.assertIn("terminal_certified", reusable)
        self.assertIn("release_authorized", reusable)
        self.assertIn("schedule:", caller)
        self.assertIn("observador-reservas-consumidor.yml@v1", caller)


if __name__ == "__main__":
    unittest.main()
