#!/usr/bin/env python3
"""Contrato offline del candidato Factory 1.0.40 (#1465).

Valida la versión y el kit de revisión SRE documental. No aprueba
release, movimiento de @v1 ni un estado de producción.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.generar_revision_juridica import check, metadata


class ReleaseCandidate1040Tests(unittest.TestCase):
    def test_candidate_version_and_roles_inventory(self) -> None:
        root = Path(__file__).resolve().parents[1]
        payload = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        self.assertIsInstance(payload["version"], str)
        self.assertGreaterEqual(
            tuple(int(part) for part in payload["version"].split(".")),
            (1, 0, 40),
        )
        paths = (
            ".github/workflows/roles.yml",
            "scripts/roles_kit.py",
            "tests/test_roles_kit.py",
            "docs/release-runbook.md",
        )
        for relative_path in paths:
            with self.subTest(path=relative_path):
                self.assertTrue((root / relative_path).is_file(), relative_path)
        kit = (root / "scripts/roles_kit.py").read_text(encoding="utf-8")
        self.assertIn("_verified_offline_legal_sre_items", kit)
        self.assertIn("OFFLINE_LEGAL_DOC_FILES", kit)
        self.assertIn("Falta render canónico de documentos jurídicos.", kit)

    def test_legal_package_is_synced_and_unapproved(self) -> None:
        root = Path(__file__).resolve().parents[1]
        version = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )["version"]
        index = (root / "revision-juridica/00-LEEME.md").read_text(
            encoding="utf-8"
        )
        package = (root / "revision-juridica/paquete-completo.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"Versión del repositorio: {version}.", index)
        self.assertIn("documented_not_legally_approved", index)
        self.assertIn("documented_not_legally_approved", package)
        fecha, sha = metadata(root)
        self.assertIn(f"Origen: {sha} · Fecha: {fecha}", package)
        self.assertEqual(check(root), [])


if __name__ == "__main__":
    unittest.main()
