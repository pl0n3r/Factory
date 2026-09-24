#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/roles.yml").read_text(encoding="utf-8")


class RolesWorkflowContractTests(unittest.TestCase):
    def test_modes_language_and_ref_are_closed(self):
        self.assertIn("name: Validar contrato de entrada", WF)
        self.assertIn('case "$MODE" in sync|suggest|validate)', WF)
        self.assertIn('case "$LANGUAGE" in es|en)', WF)
        self.assertIn("needs: preflight", WF)
        self.assertIn("inputs.mode == 'validate'", WF)
        self.assertIn("inputs.mode == 'sync' || inputs.mode == 'suggest'", WF)
        self.assertIn('"es" || "$LANGUAGE" == "en"', WF)
        self.assertNotIn("kit_ref", WF)
        self.assertIn("ref: v1", WF)

    def test_validate_is_read_only_and_mutations_are_isolated(self):
        validate = WF.split("  validate:", 1)[1].split("  mutate:", 1)[0]
        mutate = WF.split("  mutate:", 1)[1]
        self.assertIn("issues: read", validate)
        self.assertNotIn("issues: write", validate)
        self.assertIn("issues: write", mutate)
        self.assertIn("sync solo acepta rama principal", mutate)
        self.assertIn("suggest requiere la entidad del evento", mutate)

    def test_context_enters_python_via_stdin_not_path_input(self):
        self.assertNotIn("--context", WF)
        self.assertNotIn("--catalog", WF)
        self.assertNotIn("--roles-dir", WF)
        self.assertIn("< /tmp/context.json", WF)

    def test_external_actions_are_sha_pinned(self):
        actions = re.findall(
            r"^\s*(?:-\s*)?uses:\s*([^\s]+)",
            WF,
            flags=re.MULTILINE,
        )
        self.assertTrue(actions)
        for action in actions:
            if not action.startswith("./"):
                self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
