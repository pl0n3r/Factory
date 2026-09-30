#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.12."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import bootstrap_coordination as bootstrap


SHA = "a" * 40
CURRENT = "0.1.148"
NEXT = "0.1.149"


class ReleaseCandidate1012Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.template = (
            cls.root / "template/.github/workflows/coordinacion.yml"
        ).read_text(encoding="utf-8")

    def _fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "config").mkdir()
        (root / "scripts").mkdir()
        (root / "config/version.php").write_text(
            "<?php\nreturn ['number' => '0.1.148'];\n",
            encoding="utf-8",
        )
        (root / "package.json").write_text(
            json.dumps({"version": CURRENT}) + "\n",
            encoding="utf-8",
        )
        (root / "package-lock.json").write_text(
            json.dumps(
                {"version": CURRENT, "packages": {"": {"version": CURRENT}}}
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "# GrindFlow\n\nv0.1.148\n",
            encoding="utf-8",
        )
        (root / bootstrap.README_UPDATER_PATH).write_text(
            "# README dashboard\n# --update\n",
            encoding="utf-8",
        )
        return tmp, root

    @staticmethod
    def _completed(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        stdout = SHA + "\n" if args[:3] == ["git", "rev-parse", "HEAD"] else ""
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    def test_candidate_is_at_least_1_0_12(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        self.assertRegex(payload["version"], r"^\\d+\\.\\d+\\.\\d+$")
        version = tuple(int(part) for part in payload["version"].split("."))
        self.assertGreaterEqual(version, (1, 0, 12))

    def test_candidate_contains_grindflow_readme_contract_fix(self) -> None:
        v1_tmp, v1_root = self._fixture()
        legacy_tmp, legacy_root = self._fixture()
        unknown_tmp, unknown_root = self._fixture()
        self.addCleanup(v1_tmp.cleanup)
        self.addCleanup(legacy_tmp.cleanup)
        self.addCleanup(unknown_tmp.cleanup)

        v1_readme = (
            "# GrindFlow\n\n"
            "<!-- factory:status:start -->\n"
            "| versión | UNKNOWN |\n"
            "<!-- factory:status:end -->\n"
        )
        (v1_root / "README.md").write_text(v1_readme, encoding="utf-8")
        (v1_root / "readme").mkdir()
        (v1_root / bootstrap.README_METADATA_PATH).write_text(
            '{"name":"GrindFlow","phase":"construction"}\n',
            encoding="utf-8",
        )
        (v1_root / bootstrap.README_UPDATER_PATH).unlink()

        with mock.patch.object(
            bootstrap.subprocess, "run", side_effect=self._completed
        ) as run:
            v1_patch = bootstrap.grindflow_delivery_patch(
                self.template, v1_root, SHA
            )
        self.assertEqual(v1_patch[bootstrap.README_PATH], v1_readme)
        self.assertFalse(
            any(
                bootstrap.README_UPDATER_PATH in call.args[0]
                for call in run.call_args_list
            )
        )

        with mock.patch.object(
            bootstrap.subprocess, "run", side_effect=self._completed
        ) as run:
            legacy_patch = bootstrap.grindflow_delivery_patch(
                self.template, legacy_root, SHA
            )
        self.assertNotIn(f"v{CURRENT}", legacy_patch[bootstrap.README_PATH])
        self.assertIn(f"v{NEXT}", legacy_patch[bootstrap.README_PATH])
        self.assertTrue(
            any(
                bootstrap.README_UPDATER_PATH in call.args[0]
                for call in run.call_args_list
            )
        )

        (unknown_root / "README.md").write_text("# GrindFlow\n", encoding="utf-8")
        with mock.patch.object(
            bootstrap.subprocess, "run", side_effect=self._completed
        ):
            with self.assertRaisesRegex(
                bootstrap.BootstrapError, "Contract v1 ni legacy"
            ):
                bootstrap.grindflow_delivery_patch(
                    self.template, unknown_root, SHA
                )

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: preflight",
        ):
            self.assertIn(token, workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
