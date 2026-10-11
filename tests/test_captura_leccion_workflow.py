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


    def test_event_gate_executed_against_fixtures(self):
        """Execute the actual pre-checkout trust gate using synthetic events."""
        import json
        import os
        import subprocess
        import sys
        import tempfile
        import textwrap

        source = WORKFLOW.read_text(encoding="utf-8").splitlines()
        start = next(i for i, line in enumerate(source)
                     if line.strip() == "# TRUST_GATE_START")
        end = next(i for i, line in enumerate(source)
                   if line.strip() == "# TRUST_GATE_END")
        gate = textwrap.dedent("\n".join(source[start + 1:end]))

        issue = {"repository": {"full_name": "pl0n3r/Factory"},
                 "action": "closed",
                 "issue": {"number": 1156, "state": "closed",
                           "closed_at": "2026-10-11T09:00:00Z"}}
        pr = {"repository": {"full_name": "pl0n3r/Factory"},
              "action": "closed",
              "pull_request": {"number": 1164, "state": "closed",
                               "merged": True, "merge_commit_sha": "a" * 40,
                               "merged_at": "2026-10-11T09:00:00Z",
                               "base": {"ref": "main",
                                        "repo": {"full_name": "pl0n3r/Factory"}}}}

        def execute(payload, event="issues", sha="a" * 40,
                    ref="refs/heads/main"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "event.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                env = {**os.environ, "GITHUB_REPOSITORY": "pl0n3r/Factory",
                       "GITHUB_REF": ref, "GITHUB_SHA": sha,
                       "GITHUB_EVENT_NAME": event, "GITHUB_RUN_ID": "987",
                       "GITHUB_EVENT_PATH": str(path),
                       "RUNNER_TEMP": directory}
                result = subprocess.run([sys.executable, "-c", gate],
                                        env=env, cwd=WORKFLOW.parents[2],
                                        capture_output=True, text=True,
                                        timeout=10, check=False)
                record = Path(directory) / "factory-lesson-event.json"
                emitted = json.loads(record.read_text(encoding="utf-8")) if record.exists() else None
                return result.returncode, emitted

        for fixture, event in ((issue, "issues"), (pr, "pull_request")):
            with self.subTest(positive=event):
                rc, candidate = execute(fixture, event=event)
                self.assertEqual(rc, 0)
                self.assertEqual(candidate["sha"], "a" * 40)
                self.assertEqual(len(capture_lessons([candidate, candidate])), 1)

        invalid = [
            ({"repository": {"full_name": "outsider/Factory"},
              **{key: value for key, value in issue.items() if key != "repository"}}, "issues", {},),
            ({**issue, "action": "reopened"}, "issues", {}),
            ({**issue, "issue": {**issue["issue"], "number": 0}}, "issues", {}),
            ({**issue, "issue": {**issue["issue"],
                                 "closed_at": "2026-02-30T09:00:00Z"}}, "issues", {}),
            ({**pr, "pull_request": {**pr["pull_request"], "merged": False}},
             "pull_request", {}),
            ({**pr, "pull_request": {**pr["pull_request"],
                                     "merge_commit_sha": "b" * 40}},
             "pull_request", {}),
            (issue, "issues", {"sha": "missing"}),
            (issue, "issues", {"ref": "refs/pull/12/merge"}),
        ]
        for fixture, event, options in invalid:
            with self.subTest(event=event, options=options, fixture=fixture):
                rc, candidate = execute(fixture, event=event, **options)
                self.assertNotEqual(rc, 0)
                self.assertIsNone(candidate)


if __name__ == "__main__":
    unittest.main()
