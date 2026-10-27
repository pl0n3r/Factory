#!/usr/bin/env python3
"""Regresiones offline del candidato Factory 1.0.44 (#1592).

La preparación del candidato es distinta de la publicación de @v1 y de una
autorización para crear WorkItems, modificar proyectos o hacer deploy.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generar_revision_juridica import INDEX, PACK, SOURCES, check, metadata

ROOT = Path(__file__).resolve().parents[1]


class F1583Candidato1044Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        version_data = json.loads((ROOT / "config/version.json").read_text(encoding="utf-8"))
        self.assertEqual(set(version_data), {"version"})
        version = version_data["version"]
        self.assertRegex(version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertGreaterEqual(tuple(int(part) for part in version.split(".")), (1, 0, 44))

        # Condor quedó parado con 76 Issues abiertos bajo el tope de 64 (#1583, PR #1584).
        from scripts.coordinar_trabajo import MAX_OPEN_ISSUES_V3

        self.assertGreaterEqual(MAX_OPEN_ISSUES_V3, 100)

    def test_falla_cerrado(self) -> None:
        from scripts.politica_kit import PolicyError, _latest_checks_by_name

        sha = "a" * 40
        row = {
            "id": 9,
            "name": "CodeRabbit",
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
            "app": {"slug": "coderabbitai", "id": 347564},
        }
        self.assertEqual(_latest_checks_by_name([json.dumps(row)], head_sha=sha)["CodeRabbit"]["id"], 9)
        for spoof in (
            {"slug": "github-actions", "id": 347564},
            {"slug": "coderabbitai", "id": 12526},
            {"slug": "coderabbitai", "id": 0},
        ):
            with self.subTest(spoof=spoof):
                with self.assertRaises(PolicyError):
                    _latest_checks_by_name([json.dumps(dict(row, app=spoof))], head_sha=sha)
        with self.assertRaises(PolicyError):
            _latest_checks_by_name([json.dumps(row)], head_sha="b" * 40)

    def test_sin_datos_reales(self) -> None:
        version = json.loads((ROOT / "config/version.json").read_text(encoding="utf-8"))["version"]
        index = (ROOT / INDEX).read_text(encoding="utf-8")
        package = (ROOT / PACK).read_text(encoding="utf-8")
        self.assertIn(f"Versión del repositorio: {version}.", index)
        self.assertIn("Estado: documented_not_legally_approved", index)
        self.assertIn("Estado: documented_not_legally_approved", package)
        date, sha = metadata(ROOT)
        self.assertIn(f"Origen: {sha} · Fecha: {date}", package)
        self.assertEqual(check(ROOT), [])

    def test_estados_unknown_explicitos(self) -> None:
        index = (ROOT / INDEX).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            for relative in (*SOURCES, INDEX, PACK, "config/version.json"):
                dest = fixture / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, dest)
            for relative in SOURCES:
                dest = fixture / "revision-juridica" / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / "revision-juridica" / relative, dest)
            self.assertEqual(check(fixture), [])
            (fixture / INDEX).write_text(
                index.replace("documented_not_legally_approved", "legally_approved", 1),
                encoding="utf-8",
            )
            self.assertEqual(check(fixture), [INDEX])


if __name__ == "__main__":
    unittest.main()
