#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/observar.yml").read_text(encoding="utf-8")


class ObserverWorkflowContractTests(unittest.TestCase):
    def test_language_input_is_closed_and_catalog_driven(self):
        self.assertIn("label_language: {required: false, default: 'es', type: string}", WF)
        self.assertIn('case "$LABEL_LANGUAGE" in es|en)', WF)
        self.assertIn('catalog=".factory/labels/$LABEL_LANGUAGE.json"', WF)
        for key in ("type_incident", "priority_critical", "state_available"):
            self.assertIn(f"label_by_key {key}", WF)
        self.assertNotIn('--label "tipo: incidente"', WF)
        self.assertNotIn('--label "priority: critical"', WF)

    def test_incident_lifecycle_is_localized_and_singleton(self):
        self.assertIn("<!-- factory-auto-observer -->", WF)
        self.assertIn("issues?state=all&per_page=100", WF)
        self.assertIn("group: observe-${{ github.repository }}", WF)
        self.assertIn("cancel-in-progress: false", WF)
        self.assertIn("incident-create.json", WF)
        self.assertIn("incident-update.json", WF)
        self.assertIn('state:"open"', WF)
        self.assertIn('"$issue_state" == "open"', WF)
        self.assertIn("[AUTO] fallo de observación", WF)
        self.assertIn("[AUTO] observation failure", WF)
        self.assertIn("Observación automática falló sin mutar producción.", WF)
        self.assertIn("Automatic observation failed without mutating production.", WF)
        self.assertIn("🟢 Observación recuperada.", WF)
        self.assertIn("🟢 Observation recovered.", WF)
        self.assertIn('--method PATCH "repos/$REPOSITORY/issues/$issue"', WF)
        self.assertIn('--method POST "repos/$REPOSITORY/issues"', WF)
        self.assertIn("github-actions[bot]", WF)

    def test_trust_boundary_and_permissions_remain_fail_closed(self):
        self.assertIn("schedule|workflow_dispatch", WF)
        self.assertIn('refs/heads/$DEFAULT_BRANCH', WF)
        self.assertIn("contents: read", WF)
        self.assertIn("issues: write", WF)
        self.assertNotIn("contents: write", WF)
        self.assertNotIn("secrets: inherit", WF)
        self.assertIn("timeout-minutes: 10", WF)
        self.assertIn("observe_kit.py", WF)
        actions = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s]+)", WF, flags=re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            if action.startswith("./"):
                continue
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
