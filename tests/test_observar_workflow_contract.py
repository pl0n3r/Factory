#!/usr/bin/env python3
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/observar.yml").read_text(encoding="utf-8")


def _indented_block(text: str, header: str, indent: int) -> str:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == " " * indent + header)
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out)


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
        self.assertIn('sort_by((.state != "open"), .number)', WF)

    def test_push_is_allowed_only_with_main_branch_guard(self):
        event_match = re.search(r'case "\$EVENT_NAME" in ([^)]+)\)', WF)
        self.assertIsNotNone(event_match)
        allowed_events = event_match.group(1).split("|")
        self.assertEqual(allowed_events, ["push", "schedule", "workflow_dispatch"])

        branch_guard = '[[ "$REF_NAME" == "refs/heads/$DEFAULT_BRANCH" ]]'
        first_checkout = WF.index("uses: actions/checkout@")
        self.assertLess(WF.index(event_match.group(0)), first_checkout)
        self.assertLess(WF.index(branch_guard), first_checkout)

    def test_untrusted_events_remain_fail_closed_before_checkout(self):
        event_match = re.search(r'case "\$EVENT_NAME" in ([^)]+)\)', WF)
        self.assertIsNotNone(event_match)
        allowed_events = set(event_match.group(1).split("|"))
        self.assertEqual(
            allowed_events,
            {"push", "schedule", "workflow_dispatch"},
        )
        for event in (
            "pull_request",
            "pull_request_target",
            "workflow_run",
            "issue_comment",
            "check_run",
            "issues",
            "repository_dispatch",
        ):
            self.assertNotIn(event, allowed_events)

        first_checkout = WF.index("uses: actions/checkout@")
        self.assertLess(WF.index(event_match.group(0)), first_checkout)
        self.assertLess(
            WF.index('[[ "$REF_NAME" == "refs/heads/$DEFAULT_BRANCH" ]]'),
            first_checkout,
        )

    def test_trust_boundary_and_permissions_remain_fail_closed(self):
        self.assertIn("push|schedule|workflow_dispatch", WF)
        self.assertIn('refs/heads/$DEFAULT_BRANCH', WF)
        workflow_permissions = _indented_block(WF, "permissions:", 0)
        job_permissions = _indented_block(WF, "permissions:", 4)
        self.assertIn("contents: read", workflow_permissions)
        self.assertNotIn("issues: write", workflow_permissions)
        self.assertIn("contents: read", job_permissions)
        self.assertIn("issues: write", job_permissions)
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
