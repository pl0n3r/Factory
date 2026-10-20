"""Regression coverage for the read-only F2 reusable-caller preflight."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.f2_caller_preflight import CONSUMERS, audit, main


class F2CallerPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for consumer in CONSUMERS:
            (self.root / consumer / ".github" / "workflows").mkdir(parents=True)

    def workflow(self, consumer, name, contents):
        path = self.root / consumer / ".github" / "workflows" / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_missing_consumer_blocks_removal(self):
        (self.root / "ControlBot" / ".github" / "workflows").rmdir()
        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(["ControlBot"], report["missing_consumers"])
        self.assertEqual([], report["references"])

    def test_pinned_and_v1_callers_are_reported(self):
        self.workflow("Condor", "readme-contract.yml", "jobs:\n  readme:\n    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n")
        self.workflow("GrindFlow", "readme-contract.yaml", "  - uses: 'pl0n3r/factory/.github/workflows/readme.yml@f7661bc123'\n")
        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual({"v1", "f7661bc123"}, {item["ref"] for item in report["references"]})
        self.assertEqual({"Condor", "GrindFlow"}, {item["consumer"] for item in report["references"]})

    def test_symlinked_consumer_checkout_blocks_even_when_contents_look_safe(self):
        checkout = self.root / "Condor"
        relocated = self.root / "different-condor"
        checkout.rename(relocated)
        checkout.symlink_to(relocated, target_is_directory=True)
        self.assertTrue((checkout / ".github" / "workflows").is_dir())
        self.assertFalse((checkout / ".github" / "workflows").is_symlink())

        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(["Condor"], report["missing_consumers"])
        self.assertNotIn("Condor", report["scanned_consumers"])
        self.assertEqual([], report["references"])

    def test_symlinked_github_ancestor_blocks_even_when_contents_look_safe(self):
        github_dir = self.root / "GrindFlow" / ".github"
        relocated = self.root / "GrindFlow" / "different-github"
        github_dir.rename(relocated)
        github_dir.symlink_to(relocated, target_is_directory=True)
        self.assertTrue((github_dir / "workflows").is_dir())
        self.assertFalse((github_dir / "workflows").is_symlink())

        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(["GrindFlow"], report["missing_consumers"])
        self.assertNotIn("GrindFlow", report["scanned_consumers"])
        self.assertEqual([], report["references"])

    def test_all_scanned_with_no_references_can_be_safe(self):
        self.workflow("Condor", "normal.yml", "jobs:\n  build:\n    uses: actions/checkout@v4\n")
        report = audit(self.root, ["readme.yml"])
        self.assertEqual("SAFE", report["status"])
        self.assertEqual(list(CONSUMERS), report["scanned_consumers"])
        self.assertEqual([], report["references"])
        self.assertIn("no autoriza", report["scope"])

    def test_missing_workflow_directory_blocks_removal(self):
        (self.root / "AutoFactory" / ".github" / "workflows").rmdir()
        report = audit(self.root, ["roles.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertIn("AutoFactory", report["missing_consumers"])

    def test_unrecognized_caller_form_fails_closed(self):
        self.workflow(
            "Condor", "folded.yml",
            "jobs:\n  test:\n    uses: >-\n      pl0n3r/factory/.github/workflows/readme.yml@v1\n",
        )
        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual([], report["references"])
        self.assertTrue(any("caller_ambiguo" in x for x in report["unreadable_files"]))

    def test_unreadable_utf8_and_symlink_block_removal(self):
        unreadable = self.root / "Condor" / ".github" / "workflows" / "unreadable.yml"
        unreadable.write_bytes(b"\xff")
        link = self.root / "Condor" / ".github" / "workflows" / "external.yml"
        link.symlink_to(unreadable)
        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(2, len(report["unreadable_files"]))

    def test_invalid_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "targets"):
            audit(self.root, ["../other.yml"])
        with self.assertRaisesRegex(ValueError, "targets"):
            audit(self.root, [])

    def test_cli_reports_safe_and_blocked_with_exit_codes(self):
        args = ["preflight", "--root", str(self.root), "--target", "readme.yml"]
        with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()) as out:
            status = main()
        self.assertEqual(0, status)
        self.assertEqual("SAFE", json.loads(out.getvalue())["status"])
        self.workflow("brvtal", "reader.yml", "jobs:\n  read:\n    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n")
        with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()) as out:
            status = main()
        self.assertEqual(2, status)
        self.assertEqual("BLOCKED", json.loads(out.getvalue())["status"])

    def test_cli_invalid_target_fails_closed(self):
        args = ["preflight", "--root", str(self.root), "--target", "../invalid.yml"]
        with patch("sys.argv", args), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                main()
        self.assertEqual(2, stopped.exception.code)

    def test_multiple_consumers_and_yaml_extensions(self):
        self.workflow("ControlBot", "roles.yaml", "jobs:\n  one:\n    uses: pl0n3r/factory/.github/workflows/roles.yml@v1\n")
        self.workflow("FactoryRunner", "labels.yml", "  uses: \"pl0n3r/factory/.github/workflows/etiquetas-pr.yml@deafbeef\"\n")
        report = audit(self.root, ["roles.yml", "etiquetas-pr.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(2, len(report["references"]))
        self.assertEqual({"roles.yml", "etiquetas-pr.yml"}, {item["reusable"] for item in report["references"]})


    def test_nested_symlink_directory_with_hidden_caller_blocks_removal(self):
        outside = self.root / "untrusted-workflows"
        outside.mkdir()
        (outside / "caller.yml").write_text(
            "jobs:\n  check:\n    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n",
            encoding="utf-8",
        )
        symlink = self.root / "Condor" / ".github" / "workflows" / "shared"
        symlink.symlink_to(outside, target_is_directory=True)

        report = audit(self.root, ["readme.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertIn("Condor:shared:symlink", report["unreadable_files"])
        self.assertEqual([], report["references"])
        self.assertEqual([], report["missing_consumers"])

    def test_nested_symlink_directory_without_callers_still_blocks_removal(self):
        outside = self.root / "empty-workflows"
        outside.mkdir()
        symlink = self.root / "GrindFlow" / ".github" / "workflows" / "nested"
        symlink.symlink_to(outside, target_is_directory=True)

        report = audit(self.root, ["roles.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertIn("GrindFlow:nested:symlink", report["unreadable_files"])
        self.assertEqual([], report["references"])



if __name__ == "__main__":
    unittest.main()
