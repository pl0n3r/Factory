"""Contrato offline de permisos mínimos y triggers Dependabot Factory #2184."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REUSABLE = (ROOT / ".github/workflows/coordinacion.yml").read_text(encoding="utf-8")
CALLER = (ROOT / ".github/workflows/dependabot-lane.yml").read_text(encoding="utf-8")
DOC = (ROOT / "docs/dependabot-lane.md").read_text(encoding="utf-8")


def job(yaml, name):
    match = re.search(r"(?ms)^  " + re.escape(name) + r":\n(.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n|\Z)", yaml)
    if not match:
        raise AssertionError(f"Job not found: {name}")
    return match.group(1)


class DependabotLaneWorkflowTests(unittest.TestCase):
    def test_reusable_permissions_are_scoped(self):
        self.assertIn("permissions:\n  contents: read", REUSABLE)
        for name in ("dependabot", "dependabot-sweep"):
            self.assertIn("      contents: write", job(REUSABLE, name))
            self.assertIn("      checks: read", job(REUSABLE, name))
            self.assertIn("      issues: write", job(REUSABLE, name))
            self.assertIn("      pull-requests: write", job(REUSABLE, name))
        for name in ("validar-input", "etiqueta", "validar-pr"):
            self.assertNotIn("contents: write", job(REUSABLE, name))
        self.assertIn("contents: read", job(REUSABLE, "validar-pr"))

    def test_caller_is_only_trusted_ci_run_and_daily_schedule(self):
        self.assertIn("workflows: ['CI factory']", CALLER)
        self.assertIn("types: [completed]", CALLER)
        self.assertIn("cron: '29 10 * * *'", CALLER)
        self.assertNotIn("pull_request_target:", CALLER)
        self.assertNotIn("workflow_dispatch:", CALLER)
        self.assertIn("permissions:\n  contents: read", CALLER)
        self.assertIn("cancel-in-progress: false", CALLER)

    def test_caller_requires_exact_head_and_official_bot(self):
        lane = job(CALLER, "dependabot")
        for predicate in (
            "github.event_name == 'workflow_run'",
            "github.event.workflow_run.event == 'pull_request'",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.head_repository.full_name == github.repository",
            "github.event.workflow_run.actor.login == 'dependabot[bot]'",
            "github.event.workflow_run.actor.id == 49699333",
            "github.event.workflow_run.pull_requests[0].number > 0",
            "github.event.workflow_run.pull_requests[1] == null",
            "github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha",
        ):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, lane)
        self.assertIn("pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}", lane)
        self.assertIn("head_sha: ${{ github.event.workflow_run.head_sha }}", lane)
        self.assertNotIn("checkout@", CALLER)
        self.assertIn("uses: ./.github/workflows/coordinacion.yml", lane)

    def test_sweep_cannot_run_on_pr_or_workflow_run(self):
        sweep = job(CALLER, "dependabot-sweep")
        self.assertIn("github.event_name == 'schedule'", sweep)
        self.assertIn("github.ref == 'refs/heads/main'", sweep)
        self.assertIn("operation: dependabot-sweep", sweep)
        self.assertNotIn("pr_number:", sweep)
        self.assertNotIn("head_sha:", sweep)

    def test_privileged_token_only_two_caller_jobs(self):
        self.assertEqual(CALLER.count("contents: write"), 2)
        for name in ("dependabot", "dependabot-sweep"):
            self.assertIn("contents: write", job(CALLER, name))
            self.assertIn("checks: read", job(CALLER, name))
        self.assertEqual(CALLER.count("uses: ./.github/workflows/coordinacion.yml"), 2)

    def test_reusable_stays_only_workflow_call_and_pinned_kit(self):
        header = REUSABLE.split("\npermissions:", 1)[0]
        self.assertIn("on:\n  workflow_call:", header)
        self.assertNotIn("  workflow_run:", header)
        self.assertNotIn("  schedule:", header)
        for name in ("dependabot", "dependabot-sweep"):
            part = job(REUSABLE, name)
            self.assertIn("repository: pl0n3r/factory", part)
            self.assertIn("ref: v1", part)
            self.assertNotIn("github.event.pull_request.head.sha", part)

    def test_documentation_has_exact_caller_for_each_consumer(self):
        names = {
            "BRVTAL": "BRVTAL CI",
            "GrindFlow": "GrindFlow CI",
            "Condor": "CI Condor (V 0.1.0)",
            "ControlBot": "CI ControlBot",
            "FactoryRunner": "CI",
            "AutoFactory": "Validate",
        }
        for name, ci in names.items():
            with self.subTest(repository=name):
                self.assertIn("### pl0n3r/" + name, DOC)
                self.assertIn("workflows: ['" + ci + "']", DOC)
        self.assertEqual(DOC.count("uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1"), 12)
        self.assertIn("pull-requests: write", DOC)
        self.assertIn("Factory#2107", DOC)

    def test_docs_explicitly_prohibit_unsafe_merges(self):
        for phrase in ("major", "pins de workflows", "squash exact-SHA", "Validar",
                       "sin", "sin red", "pull_request_target", "live"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DOC)


if __name__ == "__main__":
    unittest.main()
