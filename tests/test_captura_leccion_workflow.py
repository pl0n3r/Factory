"""Acceptance checks for the offline lesson-capture workflow."""
from pathlib import Path
import unittest

from scripts.captura_leccion import capture_lessons, CaptureError

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/captura-leccion.yml"


class CaptureLessonWorkflowTests(unittest.TestCase):
    def test_minimal_permissions_and_no_untrusted_checkout(self):
        config = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", config)
        self.assertIn("persist-credentials: false", config)
        self.assertIn("refs/heads/main", config)
        self.assertIn("TRUST_GATE_START", config)
        self.assertIn("GITHUB_EVENT_PATH", config)
        self.assertLess(config.index("TRUST_GATE_START"), config.index("actions/checkout@"))
        self.assertNotIn("pull_request_target", config)
        self.assertNotIn("actions/upload-artifact", config)

    def test_duplicates_failed_events_and_missing_sha_do_not_publish(self):
        config = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('pr.get("merge_commit_sha") != sha', config)
        self.assertIn('pr.get("merged") is not True', config)
        self.assertIn('payload.get("action") != "closed"', config)
        self.assertIn("capture_lessons([candidate, candidate])", config)
        self.assertNotIn("contents: write", config)

        sample = {
            "event_id": "issues-1156-100", "repo": "pl0n3r/Factory",
            "issue": 1156, "sha": "a" * 40,
            "occurred_at": "2026-10-11T09:00:00Z",
            "event": "issue_closed", "summary": "Cierre de issue validado en GitHub",
            "issuer": "github-actions[bot]", "verified": True,
        }
        self.assertEqual(len(capture_lessons([sample, sample])), 1)
        with self.assertRaises(CaptureError):
            capture_lessons([{**sample, "sha": "missing"}])


if __name__ == "__main__":
    unittest.main()
