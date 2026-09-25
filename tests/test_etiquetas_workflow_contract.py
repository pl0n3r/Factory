#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/etiquetas.yml").read_text(encoding="utf-8")

class EtiquetasWorkflowContractTests(unittest.TestCase):
    def test_modes_and_language_are_closed(self):
        self.assertIn('case "$MODE" in sync|validate|sweep)', WF)
        self.assertIn('case "$LANGUAGE" in es|en)', WF)
        self.assertIn("issues: write", WF)

    def test_uses_published_factory_catalog_by_language_not_path(self):
        self.assertIn("repository: pl0n3r/factory", WF)
        self.assertIn("labels_kit.py", WF)
        self.assertIn("ref: v1", WF)
        self.assertIn("--language", WF)
        self.assertNotIn("--catalog", WF)
        self.assertNotIn("inputs.kit_ref", WF)

    def test_validate_and_sweep_lifecycle_remains_metadata_only(self):
        self.assertIn("name: Labels", WF)
        self.assertIn("plan-validation", WF)
        self.assertIn("sweep-plan", WF)
        self.assertIn("<!-- factory-label-validation -->", WF)
        self.assertIn("<!-- factory-auto-unlabeled -->", WF)
        self.assertIn("pull-requests: read", WF)
        self.assertIn("linked_issue:$linked[0]", WF)
        self.assertIn("group: labels-${{ github.repository }}-${{ inputs.mode }}-${{ inputs.issue_number }}", WF)
        self.assertNotIn("github.run_id", WF)
        self.assertIn("select(.number != $auto)", WF)
        self.assertIn("auto-create.json", WF)
        self.assertIn("auto-update.json", WF)
        self.assertIn("auto-close.json", WF)
        self.assertNotIn('-f state=open --input', WF)
        self.assertNotIn("contents: write", WF)
        self.assertNotIn("secrets: inherit", WF)
        self.assertIn("repository: pl0n3r/factory", WF)

    def test_external_actions_are_sha_pinned(self):
        actions = re.findall(r"^\s*uses:\s*([^\s]+)", WF, flags=re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"@[0-9a-f]{40}$")

if __name__ == "__main__":
    unittest.main()
