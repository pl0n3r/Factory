"""Regresiones del evento no privilegiado del auto-merge (#1344)."""

from pathlib import Path
import unittest

from seguridad.resiliencia import ValidationError, audit_workflow


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "automerge.yml"
)


class AutoMergeEventSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_no_untrusted_privileged_trigger_or_global_write(self):
        source = self.source
        job_if = source.split("    if: >-", 1)[1].split("\n    runs-on:", 1)[0]
        review_gate = job_if.split("(github.event_name == 'pull_request_review' &&", 1)[1].split(") ||", 1)[0]
        workflow_gate = job_if.split("(github.event_name == 'workflow_run' &&", 1)[1].split(")", 1)[0]
        for required in (
            "github.event.pull_request.draft == false",
            "github.event.pull_request.head.repo.full_name == github.repository",
            "github.event.pull_request.base.ref == 'main'",
        ):
            self.assertIn(required, review_gate)
        for required in (
            "github.event.action == 'completed'",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'pull_request'",
            "github.event.workflow_run.head_repository.full_name == github.repository",
        ):
            self.assertIn(required, workflow_gate)
        self.assertIn("on:\n  pull_request:\n", source)
        self.assertIn("pull_request_review:\n    types: [submitted]", source)
        self.assertIn('workflow_run:\n    workflows: ["CI factory", "Sonar CI-based", "Evidencia CodeQL"]', source)
        self.assertIn("api.github.com/repos/", source)
        self.assertIn("authenticated_pr_identity_changed", source)
        self.assertIn("trusted_runs = {\"CI factory\", \"Sonar CI-based\", \"Evidencia CodeQL\"}", source)
        self.assertNotIn("--resolve-pull-request-review", source)
        self.assertNotIn("--resolve-workflow-run", source)
        self.assertNotIn("gh pr merge --auto", source)
        self.assertNotIn("gh pr merge --disable-auto", source)
        self.assertIn('-f sha="$PR_SHA" -f merge_method=squash', source)
        self.assertNotIn("pull_request_target", source)
        self.assertIn("permissions:\n  contents: read\njobs:", source)
        self.assertNotIn("permissions:\n  contents: write", source)
        audit_workflow(source)
        with self.assertRaisesRegex(ValidationError, "pull_request_target prohibido"):
            audit_workflow(
                source.replace("  pull_request:\n", "  pull_request_target:\n", 1)
            )
        with self.assertRaisesRegex(ValidationError, "permisos de escritura"):
            audit_workflow(
                source.replace(
                    "permissions:\n  contents: read\njobs:",
                    "permissions:\n  contents: write\njobs:",
                    1,
                )
            )

    def test_job_write_is_scoped_and_fork_denied(self):
        source = self.source
        self.assertIn("  automerge:\n", source)
        job = source.split("  automerge:\n", 1)[1]
        # Enabling auto-merge needs both rights, constrained to this job.
        self.assertIn(
            "    permissions:\n      contents: write\n      pull-requests: write",
            job,
        )
        for required in (
            "github.event.pull_request.draft == false",
            "github.event.pull_request.head.repo.full_name == github.repository",
            "github.event.pull_request.head.repo.fork == false",
            "github.event.pull_request.base.ref == 'main'",
            "github.actor != 'dependabot[bot]'",
            "GH_TOKEN:",
            "gh api --method PUT",
            "steps.target.outputs.pr_number",
            "steps.target.outputs.pr_sha",
            "steps.target.outputs.pr_url",
        ):
            with self.subTest(required=required):
                self.assertIn(required, job)
        self.assertNotIn("pull_request_target", source)
        audit_workflow(source)


if __name__ == "__main__":
    unittest.main()
