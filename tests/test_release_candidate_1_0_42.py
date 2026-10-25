#!/usr/bin/env python3
"""Regresiones offline del candidato Factory 1.0.42 (#1508).

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


class ReleaseCandidate1042Tests(unittest.TestCase):
    def test_version_and_new_performance_diagnostics(self) -> None:
        root = Path(__file__).resolve().parents[1]
        version_data = json.loads(
            (root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(version_data), {"version"})
        version = version_data["version"]
        self.assertIsInstance(version, str)
        self.assertRegex(version, r"^[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertGreaterEqual(
            tuple(int(part) for part in version.split(".")), (1, 0, 42)
        )
        for path in (
            "performance/ci_professional_report.py",
            "performance/ci_suite_benchmark.py",
            "performance/team_compiler_bridge.py",
            "tests/test_performance_ci_professional_report.py",
            "tests/test_performance_ci_suite_benchmark.py",
            "tests/test_performance_team_compiler_bridge.py",
            "docs/performance-ci-professional-report.md",
            "docs/performance-ci-suite-benchmark.md",
            "docs/performance-team-compiler-bridge.md",
            "docs/release-runbook.md",
        ):
            with self.subTest(path=path):
                self.assertTrue((root / path).is_file(), path)

        report = (root / "performance/ci_professional_report.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("evaluate_factoryrunner_ci_run", report)
        self.assertIn("compile_performance_team", report)
        for denied in (
            '"authority": "unchanged"',
            '"execute_actions": False',
            '"create_work_item": False',
            '"dispatch": False',
            '"adopt": False',
            '"candidate_terminal": False',
        ):
            with self.subTest(denied=denied):
                self.assertIn(denied, report)
        benchmark = (root / "performance/ci_suite_benchmark.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"causality": "unproven"', benchmark)
        self.assertIn('"adopt": False', benchmark)
        self.assertIn('"execute_actions": False', benchmark)
        bridge = (root / "performance/team_compiler_bridge.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('return {', bridge)
        self.assertIn('"create_work_item": False', bridge)
        self.assertIn('"dispatch": False', bridge)

    def test_legal_index_and_source_package_remain_consistent_unapproved(self) -> None:
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
