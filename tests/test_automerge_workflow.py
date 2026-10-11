"""Factory 1143: comprobaciones offline del observador de lectura."""
import re
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/automerge-construccion.yml"
HEAD = "a" * 40
BASE = "b" * 40


def load():
    data = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"          python3 - <<'PY'\n(.*?)\n          PY", data, re.S)
    if match is None:
        raise AssertionError("embedded script missing")
    scope = {"__name__": "offline_fixture"}
    exec(compile(textwrap.dedent(match.group(1)), str(WORKFLOW), "exec"), scope)
    return scope


def evt():
    return {"repository": {"full_name": "pl0n3r/Factory"}, "number": 9,
            "pull_request": {"head": {"sha": HEAD}}}


class Fake:
    def __init__(self, *, pause=False, drift=False, partial=False):
        self.pause, self.drift, self.partial = pause, drift, partial
        self.calls = []

    def __call__(self, route):
        self.calls.append(route)
        if route.endswith("/issues/767"):
            flag = "PAUSED" if self.pause else "RUNNING"
            body = '<!-- factory-unattended-kill-switch {"version":1,"state":"' + flag + '","owner":"pl0n3r"} -->'
            return {"id": 767, "state": "closed",
                    "user": {"login": "pl0n3r"}, "body": body, "updated_at": "2026-10-11T09:00:00Z"}
        if route.endswith("/pulls/9"):
            return {"number": 9, "head": {"sha": HEAD},
                    "base": {"sha": BASE, "ref": "main"}, "draft": False,
                    "mergeable": True, "mergeable_state": "clean", "user": {"login": "author"}}
        if route.endswith("/branches/main"):
            return {"commit": {"sha": "c" * 40 if self.drift else BASE}}
        if route.endswith("/protection/required_status_checks"):
            return {"contexts": ["Validar", "Criterios de aceptación", "Validar coordinación", "Seguridad"]}
        if "/check-runs?" in route:
            records = [{"id": idx, "name": label, "status": "completed", "conclusion": "success",
                        "head_sha": HEAD} for idx, label in enumerate(
                            ("Validar", "Criterios de aceptación", "Validar coordinación", "Seguridad"), 1)]
            if route.endswith("page=2"):
                records = []
            elif self.partial:
                records = records[:3]
            return {"total_count": 4, "check_runs": records}
        if "/reviews?" in route:
            return [] if route.endswith("page=2") else [{
                "id": 7, "user": {"login": "reviewer", "type": "User"},
                "submitted_at": "2026-10-11T09:00:00Z",
                "commit_id": HEAD, "state": "APPROVED",
                "author_association": "COLLABORATOR"}]
        if "/files?" in route:
            return [] if route.endswith("page=2") else [{"id": 8, "filename": "scripts/feature.py"}]
        if route == "/rate_limit":
            return {"resources": {"core": {"remaining": 80}}}
        raise AssertionError("unknown endpoint")


def graph(_repo, _number):
    return {"has_next_page": False, "resolved": [True]}


class AutoMergeWorkflowTests(unittest.TestCase):
    def test_dry_run_workflow_is_read_only_and_never_merges(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("on:\n  pull_request:", text)
        self.assertIn("persist-credentials: false", text)
        self.assertRegex(text, r"actions/checkout@[0-9a-f]{40}")
        for forbidden in ("contents: write", "pull-requests: write",
                          "pull_request_target:", "enablePullRequestAutoMerge"):
            self.assertNotIn(forbidden, text)
        self.assertIn("timeout-minutes: 5", text)

    def test_exact_sha_and_independent_review_snapshot_are_required(self):
        module = load()
        api = Fake()
        self.assertFalse(module["simulate"](api, graph, evt(), "2026-10-11T09:00:00Z")["eligible"])
        self.assertTrue(any("/reviews?" in route for route in api.calls))
        self.assertTrue(any("/check-runs?" in route for route in api.calls))
        drift = module["simulate"](Fake(drift=True), graph, evt(), "2026-10-11T09:00:00Z")
        self.assertEqual(drift["reason"], "sha_mismatch")
        invalid = evt()
        invalid["pull_request"]["head"]["sha"] = "invalid"
        self.assertFalse(module["simulate"](Fake(), graph, invalid, "2026-10-11T09:00:00Z")["eligible"])

    def test_kill_switch_freeze_live_and_sensitive_paths_fail_closed(self):
        module = load()
        result = module["simulate"](Fake(pause=True), graph, evt(), "2026-10-11T09:00:00Z")
        self.assertEqual(result["reason"], "kill_switch_inactive")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('"phase": "UNKNOWN"', text)
        self.assertIn('"freeze_active": True', text)
        self.assertIn('"human_gate_required": True', text)

    def test_diagnostic_only_sanitized_report_and_budget_limits(self):
        module = load()
        result = module["simulate"](Fake(), graph, evt(), "2026-10-11T09:00:00Z")
        self.assertFalse(result["eligible"])
        self.assertEqual(set(result), {"repository", "pr_number", "head_sha", "eligible", "reason"})
        self.assertEqual(result["reason"], "human_gate_required")
        self.assertNotIn("Authorization", str(result))

    def test_workflow_is_idempotent_non_mutating_and_offline_testable(self):
        module = load()
        api = Fake()
        first = module["simulate"](api, graph, evt(), "2026-10-11T09:00:00Z")
        second = module["simulate"](api, graph, evt(), "2026-10-11T09:00:00Z")
        self.assertEqual(first, second)
        self.assertTrue(all(route.startswith("/") for route in api.calls))
        missing = module["simulate"](Fake(partial=True), graph, evt(), "2026-10-11T09:00:00Z")
        self.assertEqual(missing["reason"], "incomplete_evidence")
        self.assertFalse(module["simulate"](Fake(), lambda *_: {"has_next_page": True},
                                            evt(), "2026-10-11T09:00:00Z")["eligible"])


if __name__ == "__main__":
    unittest.main()
