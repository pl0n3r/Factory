"""Regression coverage for the read-only F2 reusable-caller preflight."""

from pathlib import Path
import tempfile
import unittest

from scripts.f2_caller_preflight import CONSUMERS, audit


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

    def test_multiple_consumers_and_yaml_extensions(self):
        self.workflow("ControlBot", "roles.yaml", "jobs:\n  one:\n    uses: pl0n3r/factory/.github/workflows/roles.yml@v1\n")
        self.workflow("FactoryRunner", "labels.yml", "  uses: \"pl0n3r/factory/.github/workflows/etiquetas-pr.yml@deafbeef\"\n")
        report = audit(self.root, ["roles.yml", "etiquetas-pr.yml"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertEqual(2, len(report["references"]))
        self.assertEqual({"roles.yml", "etiquetas-pr.yml"}, {item["reusable"] for item in report["references"]})


if __name__ == "__main__":
    unittest.main()
