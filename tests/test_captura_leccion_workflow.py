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

    def test_issue_close_job_logs_unknown_without_checkout(self):
        """The actual issues.closed job emits typed UNKNOWN, no candidate."""
        import os
        import subprocess
        import tempfile
        import textwrap

        config = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  issues:\n    types: [closed]", config)
        self.assertIn("  issue-identity-unknown:", config)
        job = config.split("  issue-identity-unknown:\n", 1)[1].split(
            "\n  candidato-offline:", 1)[0]
        self.assertIn("github.event_name == 'issues'", job)
        self.assertIn("github.event.action == 'closed'", job)
        self.assertIn("github.ref == 'refs/heads/main'", job)
        self.assertIn("permissions:\n      contents: read", job)
        self.assertIn("publication_allowed:", job)
        self.assertNotIn("actions/checkout@", job)
        self.assertNotIn("GITHUB_EVENT_PATH", job)
        self.assertNotIn("secrets.", job)
        self.assertNotIn("contents: write", job)
        self.assertNotIn("actions/upload-artifact", job)
        lines = config.splitlines()
        begin = next(i for i, line in enumerate(lines)
                     if line.strip() == "# ISSUE_UNKNOWN_BEGIN")
        end = next(i for i, line in enumerate(lines)
                   if line.strip() == "# ISSUE_UNKNOWN_END")
        script = textwrap.dedent("\n".join(lines[begin + 1:end]))
        with tempfile.TemporaryDirectory() as path:
            output = Path(path) / "github-output"
            env = {**os.environ, "GITHUB_OUTPUT": str(output)}
            result = subprocess.run(
                ["bash", "-e", "-c", script], env=env,
                capture_output=True, text=True, timeout=5, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"),
                             "status=UNKNOWN\nreason=ambiguous_issue_closure\n"
                             "publication_allowed=false\n")
            self.assertIn("lesson_capture_status=UNKNOWN", result.stdout)
            self.assertIn("publication_allowed=false", result.stdout)
            self.assertNotIn("candidate=", result.stdout)

    def test_duplicates_failed_events_and_missing_sha_do_not_publish(self):
        config = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('not re.fullmatch(r"[0-9a-f]{40}", merge_sha)', config)
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

        for fixture, event in ((pr, "pull_request"),):
            with self.subTest(positive=event):
                rc, candidate = execute(fixture, event=event)
                self.assertEqual(rc, 0)
                self.assertEqual(candidate["sha"], "a" * 40)
                self.assertEqual(len(capture_lessons([candidate, candidate])), 1)

        invalid = [
            (issue, "issues", {}),  # Issue closure lacks an authoritative action ID.
            ({"repository": {"full_name": "outsider/Factory"},
              **{key: value for key, value in issue.items() if key != "repository"}}, "issues", {},),
            ({**issue, "action": "reopened"}, "issues", {}),
            ({**issue, "issue": {**issue["issue"], "number": 0}}, "issues", {}),
            ({**issue, "issue": {**issue["issue"],
                                 "closed_at": "2026-02-30T09:00:00Z"}}, "issues", {}),
            ({**pr, "pull_request": {**pr["pull_request"], "merged": False}},
             "pull_request", {}),
            ({**pr, "pull_request": {**pr["pull_request"],
                                     "merge_commit_sha": "bad"}},
             "pull_request", {}),
            (issue, "issues", {"sha": "missing"}),
            (issue, "issues", {"ref": "refs/pull/12/merge"}),
        ]
        for fixture, event, options in invalid:
            with self.subTest(event=event, options=options, fixture=fixture):
                rc, candidate = execute(fixture, event=event, **options)
                self.assertNotEqual(rc, 0)
                self.assertIsNone(candidate)

    @staticmethod
    def _execute_trust_gate(payload, *, event="issues", run_id="101", sha="a" * 40):
        """Execute the real workflow pre-checkout gate, without network calls."""
        import json
        import os
        import subprocess
        import sys
        import tempfile
        import textwrap

        source = WORKFLOW.read_text(encoding="utf-8").splitlines()
        begin = next(i for i, line in enumerate(source)
                     if line.strip() == "# TRUST_GATE_START")
        end = next(i for i, line in enumerate(source)
                   if line.strip() == "# TRUST_GATE_END")
        gate = textwrap.dedent("\n".join(source[begin + 1:end]))
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "event.json"
            source_path.write_text(json.dumps(payload), encoding="utf-8")
            env = {**os.environ, "GITHUB_REPOSITORY": "pl0n3r/Factory",
                   "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": sha,
                   "GITHUB_EVENT_NAME": event, "GITHUB_RUN_ID": run_id,
                   "GITHUB_EVENT_PATH": str(source_path), "RUNNER_TEMP": directory}
            outcome = subprocess.run([sys.executable, "-c", gate], env=env,
                                     cwd=WORKFLOW.parents[2], text=True,
                                     capture_output=True, timeout=10, check=False)
            record = Path(directory) / "factory-lesson-event.json"
            candidate = (json.loads(record.read_text(encoding="utf-8"))
                         if record.exists() else None)
            return outcome.returncode, candidate

    def test_cross_run_duplicate_closure_has_stable_event_id(self):
        pr = {"repository": {"full_name": "pl0n3r/Factory"},
              "action": "closed",
              "pull_request": {"number": 1164, "state": "closed",
                               "merged": True, "merge_commit_sha": "c" * 40,
                               "merged_at": "2026-10-11T09:00:00Z",
                               "base": {"ref": "main",
                                        "repo": {"full_name": "pl0n3r/Factory"}}}}
        rc_a, first = self._execute_trust_gate(pr, event="pull_request",
                                               run_id="123", sha="a" * 40)
        rc_b, second = self._execute_trust_gate(pr, event="pull_request",
                                                run_id="456", sha="b" * 40)
        self.assertEqual((rc_a, rc_b), (0, 0))
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["sha"], "c" * 40)
        self.assertEqual(first["run_sha"], "a" * 40)
        self.assertEqual(second["run_sha"], "b" * 40)
        self.assertEqual(len(capture_lessons([first, second])), 1)
        self.assertNotIn("123", first["event_id"])
        self.assertNotIn("456", first["event_id"])

    def test_distinct_closures_and_conflicts_fail_closed(self):
        def pr(number, merge_sha):
            return {"repository": {"full_name": "pl0n3r/Factory"},
                    "action": "closed",
                    "pull_request": {"number": number, "state": "closed",
                                     "merged": True, "merge_commit_sha": merge_sha,
                                     "merged_at": "2026-10-11T09:00:00Z",
                                     "base": {"ref": "main",
                                              "repo": {"full_name": "pl0n3r/Factory"}}}}
        rc_a, first = self._execute_trust_gate(pr(1164, "a" * 40),
                                                event="pull_request", run_id="123")
        rc_b, second = self._execute_trust_gate(pr(1165, "b" * 40),
                                                 event="pull_request", run_id="456")
        self.assertEqual((rc_a, rc_b), (0, 0))
        self.assertNotEqual(first["event_id"], second["event_id"])
        self.assertEqual(len(capture_lessons([first, second])), 2)
        self.assertEqual(len(capture_lessons([first, first])), 1)
        with self.assertRaisesRegex(CaptureError, "conflicting_event_id"):
            capture_lessons([first, {**first, "summary": "Conflicto semantico"}])
        rc_bad, no_candidate = self._execute_trust_gate(
            pr(1165, "bad"), event="pull_request", run_id="456")
        self.assertNotEqual(rc_bad, 0)
        self.assertIsNone(no_candidate)

    def test_same_closure_changed_main_sha_fails_closed(self):
        """Compatibility: a different checkout SHA does not split a PR merge."""
        pr = {"repository": {"full_name": "pl0n3r/Factory"},
              "action": "closed",
              "pull_request": {"number": 1164, "state": "closed",
                               "merged": True, "merge_commit_sha": "c" * 40,
                               "merged_at": "2026-10-11T09:00:00Z",
                               "base": {"ref": "main",
                                        "repo": {"full_name": "pl0n3r/Factory"}}}}
        rc_a, first = self._execute_trust_gate(pr, event="pull_request",
                                                run_id="123", sha="a" * 40)
        rc_b, second = self._execute_trust_gate(pr, event="pull_request",
                                                 run_id="456", sha="b" * 40)
        self.assertEqual((rc_a, rc_b), (0, 0))
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["sha"], second["sha"])
        self.assertNotEqual(first["run_sha"], second["run_sha"])
        self.assertEqual(len(capture_lessons([first, second])), 1)

    def test_same_second_closure_without_authoritative_identity_fails_closed(self):
        """A GitHub Issue closure has no unique per-closure action identifier."""
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ambiguous_issue_closure", source)
        self.assertIn("github.event_name == 'pull_request'", source)
        base = {"repository": {"full_name": "pl0n3r/Factory"},
                "action": "closed", "issue": {"number": 1156,
                "state": "closed", "closed_at": "2026-10-11T09:00:00Z"}}
        for run_id in ("123", "456"):
            with self.subTest(run_id=run_id):
                result, candidate = self._execute_trust_gate(
                    base, event="issues", run_id=run_id)
                self.assertNotEqual(result, 0)
                self.assertIsNone(candidate)


if __name__ == "__main__":
    unittest.main()
