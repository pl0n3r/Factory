"""Regresiones del workflow inerte de auto-merge en Fase 1 (#1364)."""
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

    def test_phase_one_workflow_is_inert(self):
        source = self.source
        self.assertIn("permissions:\\n  contents: read\\njobs:", source)
        self.assertIn("  automerge:\\n", source)
        job = source.split("  automerge:\\n", 1)[1]
        self.assertIn("    if: false", job)
        self.assertIn("      contents: read", job)
        self.assertNotIn("contents: write", source)
        self.assertNotIn("pull-requests: write", source)
        self.assertNotIn("MERGE_TOKEN", source)
        self.assertNotIn("AUTOMERGE_TOKEN", source)
        self.assertNotIn("gh pr merge", source)
        self.assertNotIn("gh api --method PUT", source)
        self.assertNotIn("/pulls/${number}/merge", source)
        self.assertNotIn("pull_request_target", source)
        self.assertIn("pull_request_review:\\n    types: [submitted]", source)
        self.assertIn(
            'workflow_run:\\n    workflows: ["CI factory", "Sonar CI-based", "Evidencia CodeQL"]',
            source,
        )
        audit_workflow(source)

    def test_attempt_to_restore_merge_authority_is_detected(self):
        source = self.source
        with self.assertRaisesRegex(ValidationError, "permisos de escritura"):
            audit_workflow(
                source.replace(
                    "permissions:\\n  contents: read\\njobs:",
                    "permissions:\\n  contents: write\\njobs:",
                    1,
                )
            )
        self.assertNotIn("gh pr merge", source)
        self.assertNotIn("gh api --method PUT", source)


if __name__ == "__main__":
    unittest.main()
