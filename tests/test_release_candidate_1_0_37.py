#!/usr/bin/env python3
"""Contrato offline para el candidato de distribución Factory 1.0.37.

Este candidato no mueve Factory@v1, no aprueba su publicación y no convierte
un roadmap parcial en completado. La revisión de los commits v1...main se
presenta al dueño de forma separada antes de abrir la puerta de release.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReleaseCandidate1037Tests(unittest.TestCase):
    def test_candidate_version_and_partial_roadmap_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 37))

        contracts = (
            ("scripts/coordinar_trabajo.py", "roadmap_partial"),
            (
                "tests/test_coordinar_trabajo.py",
                "test_planned_partial_roadmap_merged_keeps_issue_open_and_uncompleted",
            ),
            ("docs/orquestador.md", "roadmap_partial"),
        )
        for path, contract in contracts:
            with self.subTest(path=path):
                source = root / path
                self.assertTrue(source.is_file(), path)
                self.assertIn(contract, source.read_text(encoding="utf-8"))

    def test_legal_review_version_is_synced(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        readme = (root / "revision-juridica/00-LEEME.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "Versión del repositorio: " + payload["version"] + ".", readme
        )
        self.assertIn("documented_not_legally_approved", readme)


if __name__ == "__main__":
    unittest.main()
