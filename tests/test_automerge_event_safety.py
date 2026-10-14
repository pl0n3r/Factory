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
        self.assertIn("on:\n  pull_request:\n", source)
        self.assertIn("pull_request_review:\n    types: [submitted]", source)
        self.assertIn('workflow_run:\n    workflows: ["CI factory", "Sonar CI-based", "Evidencia CodeQL"]', source)
        self.assertIn("--resolve-pull-request-review", source)
        self.assertIn("--resolve-workflow-run", source)
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
            "gh pr merge --auto --squash",
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
