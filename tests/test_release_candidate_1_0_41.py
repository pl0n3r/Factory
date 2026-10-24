#!/usr/bin/env python3
"""Contrato build-ahead del candidato Factory 1.0.41 (#1493).

Un candidato no publica tags ni autoriza mover Factory@v1.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.generar_revision_juridica import INDEX, PACK, SOURCES, check, metadata


class ReleaseCandidate1041Tests(unittest.TestCase):
    def test_version_and_unreleased_kit_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads((root / "config/version.json").read_text(encoding="utf-8"))
        self.assertEqual(set(payload), {"version"})
        version = payload["version"]
        self.assertIsInstance(version, str)
        self.assertRegex(version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertGreaterEqual(tuple(int(part) for part in version.split(".")), (1, 0, 41))
        for path in (
            ".github/workflows/observador-reservas-consumidor.yml",
            ".github/workflows/bootstrap-coordination.yml",
            "scripts/normalizar_issue.py",
            "tests/test_normalizar_issue.py",
            "tests/test_codeql_evidence_workflow.py",
            "docs/release-runbook.md",
        ):
            with self.subTest(path=path):
                self.assertTrue((root / path).is_file(), path)
        normalizer = (root / "scripts/normalizar_issue.py").read_text(encoding="utf-8")
        self.assertIn("inspect_claim_paths", normalizer)
        codeql = (root / ".github/workflows/codeql-evidence.yml").read_text(encoding="utf-8")
        self.assertRegex(codeql, r"github/codeql-action/init@[a-f0-9]{40}\b")
        self.assertRegex(codeql, r"github/codeql-action/analyze@[a-f0-9]{40}\b")

    def test_legal_package_consistent_and_unapproved(self) -> None:
        root = Path(__file__).resolve().parents[1]
        version = json.loads((root / "config/version.json").read_text(encoding="utf-8"))["version"]
        index = (root / INDEX).read_text(encoding="utf-8")
        package = (root / PACK).read_text(encoding="utf-8")
        self.assertIn(f"Versión del repositorio: {version}.", index)
        self.assertIn("Estado: documented_not_legally_approved", index)
        self.assertIn("Estado: documented_not_legally_approved", package)
        date, sha = metadata(root)
        self.assertIn(f"Origen: {sha} · Fecha: {date}", package)
        self.assertEqual(check(root), [])

        # Una manipulación del índice debe fallar la validación byte-exacta.
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
            tampered = fixture / INDEX
            tampered.write_text(
                index.replace("documented_not_legally_approved", "legally_approved", 1),
                encoding="utf-8",
            )
            self.assertEqual(check(fixture), [INDEX])


if __name__ == "__main__":
    unittest.main()
