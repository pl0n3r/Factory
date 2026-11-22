#!/usr/bin/env python3
"""Regresion offline del candidato Factory 1.0.57 (#2168).

Preparar el candidato no aprueba los documentos juridicos ni autoriza
abrir una ventana de release, publicar o mover el canal protegido v1.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.generar_revision_juridica import INDEX, PACK, check, metadata

ROOT = Path(__file__).resolve().parents[1]


class ReleaseCandidate1057Tests(unittest.TestCase):
    def test_candidate_version_and_legal_index(self) -> None:
        version_data = json.loads(
            (ROOT / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(version_data), {"version"})
        self.assertGreaterEqual(tuple(int(v) for v in version_data["version"].split(".")), (1, 0, 57))

        index = (ROOT / INDEX).read_text(encoding="utf-8")
        package = (ROOT / PACK).read_text(encoding="utf-8")
        self.assertIn("Versión del repositorio: " + version_data["version"] + ".", index)
        self.assertIn("Estado: documented_not_legally_approved", index)
        self.assertIn("Estado: documented_not_legally_approved", package)
        self.assertNotIn("Estado: legally_approved", index)
        self.assertNotIn("Estado: legally_approved", package)

        date, sha = metadata(ROOT)
        self.assertIn(f"Origen: {sha} · Fecha: {date}", package)
        self.assertEqual(check(ROOT), [])


if __name__ == "__main__":
    unittest.main()
