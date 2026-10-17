"""Regresiones del workflow inerte de auto-merge en Fase 1 (#1364)."""
from pathlib import Path
import re
import unittest

from seguridad.resiliencia import ValidationError, audit_workflow


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "automerge.yml"
)


def audit_phase_one_workflow(source: str) -> None:
    """Apply generic auditing plus the exact Fase 1 auto-merge job gate."""
    audit_workflow(source)
    lines = source.splitlines()
    # Fase 1 permits exactly one inert job. An additional active job could
    # request id-token/issues/actions:write while the disabled automerge job
    # still satisfies its own condition.
    if lines.count("jobs:") != 1:
        raise ValidationError("automerge fase 1 requiere un bloque jobs único")
    jobs = lines[lines.index("jobs:") + 1:]
    active_jobs = []
    for line in jobs:
        if line.strip() and not line.lstrip().startswith("#"):
            if not line[0].isspace():
                break
            if re.match(r"^  \S", line):
                active_jobs.append(line.rstrip())
    if active_jobs != ["  automerge:"]:
        raise ValidationError("automerge fase 1 requiere un único job inerte")
    # Scope the condition to this job, not to any later job in the YAML.
    start = lines.index("  automerge:") + 1
    job_lines = []
    for raw in lines[start:]:
        if raw.strip() and not raw.lstrip().startswith("#"):
            indent = len(raw) - len(raw.lstrip(" "))
            if indent <= 2:
                break
        job_lines.append(raw)
    # Comments and step-level conditions cannot certify a disabled job.
    effective = [line.strip() for line in job_lines if line.startswith("    if:")]
    if effective != ["if: ${{ false }}"]:
        raise ValidationError("automerge fase 1 requiere una única condición if: false")

class AutoMergeEventSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_phase_one_workflow_is_inert(self):
        source = self.source
        self.assertIn("permissions:\n  contents: read\njobs:", source)
        self.assertIn("  automerge:\n", source)
        job = source.split("  automerge:\n", 1)[1]
        self.assertEqual(
            [line.strip() for line in job.splitlines() if line.startswith("    if:")],
            ["if: ${{ false }}"],
        )
        self.assertIn("      contents: read", job)
        self.assertNotIn("contents: write", source)
        self.assertNotIn("pull-requests: write", source)
        self.assertNotIn("MERGE_TOKEN", source)
        self.assertNotIn("AUTOMERGE_TOKEN", source)
        self.assertNotIn("gh pr merge", source)
        self.assertNotIn("gh api --method PUT", source)
        self.assertNotIn("/pulls/${number}/merge", source)
        self.assertNotIn("pull_request_target", source)
        self.assertIn("pull_request_review:\n    types: [submitted]", source)
        self.assertIn(
            'workflow_run:\n    workflows: ["CI factory", "Sonar CI-based", "Evidencia CodeQL"]',
            source,
        )
        audit_phase_one_workflow(source)

    def test_comment_only_false_does_not_hide_executable_true_condition(self):
        source = self.source.replace(
            "    if: ${{ false }}",
            "    if: ${{ true }}\n    # if: ${{ false }}",
            1,
        )
        job = source.split("  automerge:\n", 1)[1]
        self.assertEqual(
            [line.strip() for line in job.splitlines() if line.startswith("    if:")],
            ["if: ${{ true }}"],
        )
        self.assertNotEqual(
            [line.strip() for line in job.splitlines() if line.startswith("    if:")],
            ["if: ${{ false }}"],
        )
        with self.assertRaisesRegex(ValidationError, "condición"):
            audit_phase_one_workflow(source)

    def test_false_condition_in_another_job_does_not_certify_automerge(self):
        # A decoy job with if:false must not mask an enabled automerge job.
        source = self.source.replace("    if: ${{ false }}\n", "", 1) + (
            "  dummy:\n"
            "    if: ${{ false }}\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: echo dummy\n"
        )
        with self.assertRaisesRegex(ValidationError, "único job|condición"):
            audit_phase_one_workflow(source)

    def test_additional_active_job_with_write_permissions_is_denied(self):
        # A sibling job with default true can acquire write privileges even
        # when jobs.automerge stays disabled.
        source = self.source + (
            "  unattended_diagnostics:\n"
            "    runs-on: ubuntu-latest\n"
            "    permissions:\n"
            "      id-token: write\n"
            "      issues: write\n"
            "    steps:\n"
            "      - run: echo active\n"
        )
        with self.assertRaisesRegex(ValidationError, "único job"):
            audit_phase_one_workflow(source)

    def test_attempt_to_restore_merge_authority_is_detected(self):
        source = self.source
        with self.assertRaisesRegex(ValidationError, "permisos de escritura"):
            audit_workflow(
                source.replace(
                    "permissions:\n  contents: read\njobs:",
                    "permissions:\n  contents: write\njobs:",
                    1,
                )
            )
        self.assertNotIn("gh pr merge", source)
        self.assertNotIn("gh api --method PUT", source)


if __name__ == "__main__":
    unittest.main()
