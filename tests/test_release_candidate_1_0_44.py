#!/usr/bin/env python3
"""Regresiones offline del candidato Factory 1.0.44 (#1592).

La preparación del kit es distinta de la publicación de @v1 y de una
autorización para crear WorkItems, modificar proyectos o hacer deploy.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generar_revision_juridica import INDEX, PACK, SOURCES, check, metadata


class ReleaseCandidate1044Tests(unittest.TestCase):
    def test_candidate_version_includes_scoped_coderabbit_policy(self) -> None:
        root = Path(__file__).resolve().parents[1]
        version_data = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(version_data), {"version"})
        version = version_data["version"]
        self.assertIsInstance(version, str)
        self.assertRegex(version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertGreaterEqual(
            tuple(int(part) for part in version.split(".")), (1, 0, 44)
        )

        # Regresión directa del fix #1543 (no solo búsqueda textual).
        from scripts.politica_kit import (
            PolicyError,
            _latest_checks_by_name,
            _required_bot_review_satisfied,
        )

        sha = "a" * 40
        check_row = {
            "id": 9,
            "name": "CodeRabbit",
            "head_sha": sha,
            "status": "completed",
            "conclusion": "success",
            "app": {"slug": "coderabbitai", "id": 347564},
        }
        evidence = _latest_checks_by_name(
            [json.dumps(check_row)], head_sha=sha
        )
        self.assertEqual(evidence["CodeRabbit"]["id"], 9)
        self.assertFalse(
            _required_bot_review_satisfied([], "coderabbitai[bot]", sha)
        )

        for spoof in (
            {"slug": "github-actions", "id": 347564},
            {"slug": "coderabbitai", "id": 12526},
            {"slug": "coderabbitai", "id": 0},
        ):
            with self.subTest(spoof=spoof):
                row = dict(check_row, app=spoof)
                with self.assertRaises(PolicyError):
                    _latest_checks_by_name(
                        [json.dumps(row)], head_sha=sha
                    )

        with self.assertRaises(PolicyError):
            _latest_checks_by_name(
                [json.dumps(check_row)], head_sha="b" * 40
            )

    def test_v3_open_issue_budget_is_100(self) -> None:
        # Condor quedó parado con 76 Issues abiertos bajo el tope de 64 (#1583, PR #1584).
        from scripts.coordinar_trabajo import MAX_OPEN_ISSUES_V3

        self.assertGreaterEqual(MAX_OPEN_ISSUES_V3, 100)

    def test_legal_index_stays_unapproved_and_consistent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        version = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )["version"]
        index = (root / INDEX).read_text(encoding="utf-8")
        package = (root / PACK).read_text(encoding="utf-8")
        self.assertIn(f"Versión del repositorio: {version}.", index)
        self.assertIn("Estado: documented_not_legally_approved", index)
        self.assertIn("Estado: documented_not_legally_approved", package)
        date, sha = metadata(root)
        self.assertIn(f"Origen: {sha} · Fecha: {date}", package)
        self.assertEqual(check(root), [])

        # El checker debe rechazar alteraciones del índice o del paquete;
        # las ocho fuentes del repositorio permanecen byte-idénticas.
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            for relative in (*SOURCES, INDEX, PACK, "config/version.json"):
                dest = fixture / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, dest)
            for relative in SOURCES:
                dest = fixture / "revision-juridica" / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / "revision-juridica" / relative, dest)
            self.assertEqual(check(fixture), [])
            target = fixture / INDEX
            target.write_text(
                index.replace("documented_not_legally_approved", "legally_approved", 1),
                encoding="utf-8",
            )
            self.assertEqual(check(fixture), [INDEX])


if __name__ == "__main__":
    unittest.main()
