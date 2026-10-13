"""Historical lesson-capture trust-gate regressions after F1E retirement."""
from pathlib import Path
import unittest

from scripts.captura_leccion import capture_lessons, CaptureError

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/captura-leccion.yml"
# Frozen fixture: original F1E YAML; NOT a live scheduler or workflow.
HISTORICAL_WORKFLOW = r'''name: Captura de lecciones (offline)

on:
  issues:
    types: [closed]
  pull_request:
    types: [closed]

# Solo lectura: ningún permiso para publicar, comentar, cerrar o modificar.
permissions:
  contents: read

concurrency:
  group: captura-leccion-${{ github.event_name }}-${{ github.event.issue.number || github.event.pull_request.number }}
  cancel-in-progress: false

jobs:
  issue-identity-unknown:
    name: Identidad de cierre de Issue no acreditada
    if: github.repository == 'pl0n3r/Factory' && github.ref == 'refs/heads/main' && github.event_name == 'issues' && github.event.action == 'closed'
    runs-on: ubuntu-latest
    timeout-minutes: 2
    permissions:
      contents: read
    outputs:
      status: ${{ steps.unknown.outputs.status }}
      publication_allowed: ${{ steps.unknown.outputs.publication_allowed }}
    steps:
      - id: unknown
        name: Registrar UNKNOWN sin candidato ni checkout
        run: |
          set -euo pipefail
          # ISSUE_UNKNOWN_BEGIN
          printf 'status=UNKNOWN\nreason=ambiguous_issue_closure\npublication_allowed=false\n' >> "$GITHUB_OUTPUT"
          printf 'lesson_capture_status=UNKNOWN reason=ambiguous_issue_closure publication_allowed=false\n'
          # ISSUE_UNKNOWN_END

  candidato-offline:
    name: Verificar evento y preparar candidato
    if: github.repository == 'pl0n3r/Factory' && github.ref == 'refs/heads/main' && github.event_name == 'pull_request' && github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - name: Validar identidad, evento y SHA ANTES del checkout
        run: |
          set -euo pipefail
          python3 - <<'PY'
          # TRUST_GATE_START
          import json
          import os
          import re
          from datetime import datetime
          from pathlib import Path

          def validate():
              repo = os.environ["GITHUB_REPOSITORY"]
              event = os.environ["GITHUB_EVENT_NAME"]
              sha = os.environ["GITHUB_SHA"]
              ref = os.environ["GITHUB_REF"]
              run_id = os.environ["GITHUB_RUN_ID"]
              if (repo != "pl0n3r/Factory" or ref != "refs/heads/main"
                      or not re.fullmatch(r"[0-9a-f]{40}", sha)
                      or not re.fullmatch(r"[1-9][0-9]*", run_id)
                      or event not in ("issues", "pull_request")):
                  raise ValueError("invalid_context")

              path = Path(os.environ["GITHUB_EVENT_PATH"])
              if path.stat().st_size > 512_000:
                  raise ValueError("oversize_event")
              payload = json.loads(path.read_text(encoding="utf-8"))
              if (not isinstance(payload, dict)
                      or not isinstance(payload.get("repository"), dict)
                      or payload["repository"].get("full_name") != repo
                      or payload.get("action") != "closed"):
                  raise ValueError("foreign_or_unclosed_event")

              if event == "issues":
                  # GitHub's issue.closed payload has only second-resolution
                  # closed_at; two real closures can share this timestamp.
                  # GITHUB_RUN_ID is delivery context, not an event identity.
                  # Do not claim a unique business event without evidence.
                  raise ValueError("ambiguous_issue_closure")
              else:
                  pr = payload.get("pull_request")
                  merge_sha = pr.get("merge_commit_sha") if isinstance(pr, dict) else None
                  if (not isinstance(pr, dict) or type(pr.get("number")) is not int
                          or pr["number"] < 1 or pr.get("merged") is not True
                          or pr.get("state") != "closed"
                          or not isinstance(pr.get("base"), dict)
                          or pr["base"].get("ref") != "main"
                          or not isinstance(pr["base"].get("repo"), dict)
                          or pr["base"]["repo"].get("full_name") != repo
                          or type(merge_sha) is not str
                          or not re.fullmatch(r"[0-9a-f]{40}", merge_sha)):
                      raise ValueError("merge_identity_invalid")
                  number = pr["number"]
                  when = pr.get("merged_at")
                  event_kind = "pr_merged"
                  summary = "Fusion de PR verificada en GitHub"

              if (not isinstance(when, str)
                      or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", when)):
                  raise ValueError("time_invalid")
              closed_time = datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ")

              candidate = {
                  "event_id": f"{event_kind}-{number}-{merge_sha}",
                  "repo": repo, "issue": number, "sha": merge_sha,
                  "run_sha": sha,
                  "occurred_at": when, "event": event_kind, "summary": summary,
                  "issuer": "github-actions[bot]", "verified": True,
              }
              out = Path(os.environ["RUNNER_TEMP"]) / "factory-lesson-event.json"
              out.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")

          try:
              validate()
          except (OSError, KeyError, TypeError, ValueError, OverflowError):
              raise SystemExit("trusted_event_rejected")
          # TRUST_GATE_END
          PY

      - name: Descargar exclusivamente commit main autenticado
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.sha }}
          persist-credentials: false
          fetch-depth: 1

      - name: Validar candidato offline sin publicar ni escribir remotamente
        run: |
          set -euo pipefail
          python3 - <<'PY'
          import json
          import os
          from pathlib import Path
          from scripts.captura_leccion import capture_lessons

          source = Path(os.environ["RUNNER_TEMP"]) / "factory-lesson-event.json"
          candidate = json.loads(source.read_text(encoding="utf-8"))
          records = capture_lessons([candidate, candidate])
          if len(records) != 1 or records[0]["event_id"] != candidate["event_id"]:
              raise SystemExit("deduplication_failed")
          print("validated_offline_lesson_candidate=1")
          PY
'''


class CaptureLessonWorkflowTests(unittest.TestCase):
    def test_minimal_permissions_and_no_untrusted_checkout(self):
        self.assertFalse(WORKFLOW.exists(), 'F1E trigger remains disabled')
        config = HISTORICAL_WORKFLOW
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

        config = HISTORICAL_WORKFLOW
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
        config = HISTORICAL_WORKFLOW
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

        source = HISTORICAL_WORKFLOW.splitlines()
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

        source = HISTORICAL_WORKFLOW.splitlines()
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
        source = HISTORICAL_WORKFLOW
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
