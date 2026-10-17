"""Regresiones del workflow inerte de auto-merge en Fase 1 (#1364)."""
from pathlib import Path
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
    if lines.count("  automerge:") != 1:
        raise ValidationError("automerge job must be unique")
    # Comments and step-level conditions cannot certify a disabled job.
    effective = [line.strip() for line in source.split("  automerge:\n", 1)[1].splitlines()
                 if line.startswith("    if:")]
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
