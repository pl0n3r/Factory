#!/usr/bin/env python3
import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/observar.yml").read_text(encoding="utf-8")


def _indented_block(text: str, header: str, indent: int) -> str:
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line == " " * indent + header)
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out)


# Cliente gh simulado: ejecuta el Bash del workflow real sin red ni GitHub.
MOCK_GH = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
fixture = json.loads(Path(os.environ["MOCK_API_DATA"]).read_text(encoding="utf-8"))
log_path = Path(os.environ["MOCK_CALLS"])

def log(item):
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(item) + "\n")

if args[0] == "api":
    endpoint = next((arg for arg in args if arg.startswith("repos/")), "")
    if "--method" in args:
        method = args[args.index("--method") + 1]
        payload = json.loads(Path(args[args.index("--input") + 1]).read_text())
        log({"method": method, "endpoint": endpoint, "payload": payload})
    elif endpoint.endswith("issues?state=all&per_page=100"):
        for issue in fixture["issues"]:
            print(json.dumps(issue))
    elif endpoint.endswith("/timeline?per_page=100"):
        number = endpoint.split("/")[-2]
        log({"method": "TIMELINE", "number": number})
        events = fixture["timelines"].get(number, [])
        for event in events:
            print(json.dumps(event))
    else:
        sys.exit("Unrecognized API endpoint: " + endpoint)
elif args[:2] in (["issue", "close"], ["issue", "comment"]):
    action = args[1]
    content_arg = "--comment" if action == "close" else "--body"
    log({
        "method": action.upper(),
        "number": args[2],
        "body": args[args.index(content_arg) + 1],
    })
else:
    sys.exit("Unrecognized gh call: " + repr(args))
'''


class ObserverWorkflowContractTests(unittest.TestCase):
    def test_language_input_is_closed_and_catalog_driven(self):
        self.assertIn("label_language: {required: false, default: 'es', type: string}", WF)
        self.assertIn('case "$LABEL_LANGUAGE" in es|en)', WF)
        self.assertIn('catalog=".factory/labels/$LABEL_LANGUAGE.json"', WF)
        for key in ("type_incident", "priority_critical", "state_available"):
            self.assertIn(f"label_by_key {key}", WF)
        self.assertNotIn('--label "tipo: incidente"', WF)
        self.assertNotIn('--label "priority: critical"', WF)

    def test_convergence_inputs_default_to_one_shot_and_are_bounded(self):
        self.assertIn(
            "convergence_attempts: {required: false, default: 1, type: number}", WF
        )
        self.assertIn(
            "convergence_delay_seconds: {required: false, default: 0, type: number}", WF
        )
        self.assertIn(
            'CONVERGENCE_ATTEMPTS: ${{ inputs.convergence_attempts }}', WF
        )
        self.assertIn(
            'CONVERGENCE_DELAY_SECONDS: ${{ inputs.convergence_delay_seconds }}', WF
        )
        self.assertIn(
            'case "$CONVERGENCE_ATTEMPTS" in 1|2|3|4|5)', WF
        )
        self.assertIn('(( convergence_delay <= 120 ))', WF)

    def test_bounded_convergence_reuses_exact_observation_and_reports_only_final_result(self):
        smoke = _indented_block(WF, "- id: smoke", 6)
        self.assertEqual(smoke.count("observe_kit.py"), 1)
        self.assertIn(
            'args=(--origin "$DOMAIN" --health-path "$HEALTH_PATH" --version "$VERSION" --sha "$sha" --paths "$PATHS")',
            smoke,
        )
        self.assertIn(
            '[[ "$REQUIRE_SCHEMA" == "true" ]] && args+=(--require-schema)', smoke
        )
        self.assertIn(
            'for ((attempt=1; attempt<=attempts; attempt++)); do', smoke
        )
        self.assertIn('[[ "$code" -eq 0 ]] && break', smoke)
        self.assertIn('if (( attempt < attempts )); then', smoke)
        self.assertIn('sleep "$delay_seconds"', smoke)
        self.assertEqual(
            smoke.count('echo "code=$code" >> "$GITHUB_OUTPUT"'), 1
        )
        self.assertNotIn("gh issue", smoke)

    def test_invalid_convergence_inputs_fail_closed_before_checkout(self):
        first_checkout = WF.index("uses: actions/checkout@")
        for guard in (
            'case "$CONVERGENCE_ATTEMPTS" in 1|2|3|4|5)',
            '[[ "$CONVERGENCE_DELAY_SECONDS" =~ ^[0-9]+$ ]]',
            'convergence_delay=$((10#$CONVERGENCE_DELAY_SECONDS))',
            '(( convergence_delay <= 120 ))',
        ):
            self.assertLess(WF.index(guard), first_checkout)

    def test_incident_lifecycle_is_localized_and_singleton(self):
        self.assertIn("<!-- factory-auto-observer -->", WF)
        self.assertIn("issues?state=all&per_page=100", WF)
        self.assertIn("group: observe-${{ github.repository }}", WF)
        self.assertIn("cancel-in-progress: false", WF)
        self.assertIn("incident-create.json", WF)
        self.assertIn("incident-update.json", WF)
        self.assertIn('state:"open"', WF)
        self.assertIn('[[ -n "$open_issue" ]]', WF)
        self.assertIn('gh issue close "$open_issue"', WF)
        self.assertIn("[AUTO] fallo de observación", WF)
        self.assertIn("[AUTO] observation failure", WF)
        self.assertIn("Observación automática falló sin mutar producción.", WF)
        self.assertIn("Automatic observation failed without mutating production.", WF)
        self.assertIn("🟢 Observación recuperada.", WF)
        self.assertIn("🟢 Observation recovered.", WF)
        self.assertIn('--method PATCH "repos/$REPOSITORY/issues/$issue"', WF)
        self.assertIn('--method POST "repos/$REPOSITORY/issues"', WF)
        self.assertIn("github-actions[bot]", WF)
        self.assertIn('and .state == "open"', WF)
        self.assertIn('and .state == "closed"', WF)
        self.assertIn('sort_by(.number)', WF)

    def _simulate_incident(self, issues, timelines=None, recovered=False, language="es"):
        """Ejecuta el paso Bash real con API de issues y timelines simuladas."""
        with tempfile.TemporaryDirectory(prefix="factory-observer-") as directory:
            root = Path(directory)
            labels = root / ".factory" / "labels"
            labels.mkdir(parents=True)
            catalog = [
                {"key": "type_incident", "name": "tipo: incidente"},
                {"key": "priority_critical", "name": "prioridad: crítica"},
                {"key": "state_available", "name": "estado: disponible"},
            ]
            (labels / f"{language}.json").write_text(
                json.dumps(catalog), encoding="utf-8"
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()
            gh = bin_dir / "gh"
            gh.write_text(MOCK_GH, encoding="utf-8")
            gh.chmod(0o755)
            fixture = root / "api.json"
            fixture.write_text(
                json.dumps({"issues": issues, "timelines": timelines or {}}),
                encoding="utf-8",
            )
            calls_path = root / "calls.ndjson"
            calls_path.write_text("", encoding="utf-8")
            (root / "factory-observation.json").write_text(
                '{"error": "synthetic smoke failure"}', encoding="utf-8"
            )
            step = _indented_block(WF, "- name: Gestionar incidente automático", 6)
            script = textwrap.dedent(step.split("        run: |\n", 1)[1])
            # Solo se redirigen rutas temporales; toda la lógica sigue siendo real.
            script = script.replace("/tmp/", f"{root}/")
            env = dict(
                os.environ,
                GH_TOKEN="synthetic",
                REPOSITORY="pl0n3r/synthetic",
                RESULT_CODE="0" if recovered else "1",
                LABEL_LANGUAGE=language,
                PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                MOCK_API_DATA=str(fixture),
                MOCK_CALLS=str(calls_path),
            )
            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script],
                cwd=root, env=env, capture_output=True, text=True, check=False,
            )
            calls = [
                json.loads(line)
                for line in calls_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                result.returncode, 0 if recovered else 1,
                f"stdout={result.stdout}\nstderr={result.stderr}",
            )
            return calls

    @staticmethod
    def _auto_issue(number, state="closed", reason="completed"):
        return {
            "number": number,
            "state": state,
            "state_reason": reason,
            "user": {"login": "github-actions[bot]"},
            "body": "<!-- factory-auto-observer -->\nOriginal observer failure",
        }

    @staticmethod
    def _close(actor):
        return {"event": "closed", "actor": {"login": actor}}

    def test_incident_not_reopened_when_closed_by_non_bot(self):
        calls = self._simulate_incident(
            [self._auto_issue(739)],
            {"739": [
                self._close("github-actions[bot]"),
                {"event": "reopened", "actor": {"login": "github-actions[bot]"}},
                self._close("pl0n3r"),
            ]},
        )
        self.assertEqual([c["method"] for c in calls], ["TIMELINE", "POST"])
        self.assertIn("#739", calls[-1]["payload"]["body"])
        self.assertNotIn("739", [c.get("number") for c in calls if c["method"] != "TIMELINE"])

    def test_incident_not_reopened_when_closed_not_planned(self):
        calls = self._simulate_incident(
            [self._auto_issue(25, reason="not_planned")],
            {"25": [self._close("github-actions[bot]")]},
        )
        self.assertEqual([c["method"] for c in calls], ["POST"])
        self.assertIn("#25", calls[0]["payload"]["body"])

    def test_incident_closed_by_bot_still_reopens(self):
        calls = self._simulate_incident(
            [self._auto_issue(41)],
            {"41": [self._close("pl0n3r"), self._close("github-actions[bot]")]},
        )
        self.assertEqual([c["method"] for c in calls], ["TIMELINE", "PATCH", "COMMENT"])
        self.assertEqual(calls[1]["endpoint"], "repos/pl0n3r/synthetic/issues/41")
        self.assertEqual(calls[1]["payload"]["state"], "open")
        self.assertEqual(calls[2]["number"], "41")

    def test_incident_open_only_comments(self):
        calls = self._simulate_incident([self._auto_issue(42, state="open")])
        self.assertEqual([c["method"] for c in calls], ["COMMENT"])
        self.assertEqual(calls[0]["number"], "42")

    def test_incident_recovery_closes_only_open(self):
        calls = self._simulate_incident(
            [self._auto_issue(11), self._auto_issue(43, state="open")],
            recovered=True,
        )
        self.assertEqual([c["method"] for c in calls], ["CLOSE"])
        self.assertEqual(calls[0]["number"], "43")
        self.assertIn("🟢", calls[0]["body"])
        self.assertEqual(
            self._simulate_incident([self._auto_issue(11)], recovered=True), []
        )

    def test_incident_obsolete_does_not_hide_other_reusable_closed_incident(self):
        calls = self._simulate_incident(
            [self._auto_issue(739), self._auto_issue(800)],
            {
                "739": [self._close("pl0n3r")],
                "800": [self._close("github-actions[bot]")],
            },
        )
        self.assertEqual(
            [c["method"] for c in calls], ["TIMELINE", "TIMELINE", "PATCH", "COMMENT"]
        )
        self.assertEqual(calls[-2]["endpoint"], "repos/pl0n3r/synthetic/issues/800")

    def test_push_is_allowed_only_with_main_branch_guard(self):
        event_match = re.search(r'case "\$EVENT_NAME" in ([^)]+)\)', WF)
        self.assertIsNotNone(event_match)
        allowed_events = event_match.group(1).split("|")
        self.assertEqual(allowed_events, ["push", "schedule", "workflow_dispatch"])

        branch_guard = '[[ "$REF_NAME" == "refs/heads/$DEFAULT_BRANCH" ]]'
        first_checkout = WF.index("uses: actions/checkout@")
        self.assertLess(WF.index(event_match.group(0)), first_checkout)
        self.assertLess(WF.index(branch_guard), first_checkout)

    def test_untrusted_events_remain_fail_closed_before_checkout(self):
        event_match = re.search(r'case "\$EVENT_NAME" in ([^)]+)\)', WF)
        self.assertIsNotNone(event_match)
        allowed_events = set(event_match.group(1).split("|"))
        self.assertEqual(
            allowed_events,
            {"push", "schedule", "workflow_dispatch"},
        )
        for event in (
            "pull_request",
            "pull_request_target",
            "workflow_run",
            "issue_comment",
            "check_run",
            "issues",
            "repository_dispatch",
        ):
            self.assertNotIn(event, allowed_events)

        first_checkout = WF.index("uses: actions/checkout@")
        self.assertLess(WF.index(event_match.group(0)), first_checkout)
        self.assertLess(
            WF.index('[[ "$REF_NAME" == "refs/heads/$DEFAULT_BRANCH" ]]'),
            first_checkout,
        )

    def test_trust_boundary_and_permissions_remain_fail_closed(self):
        self.assertIn("push|schedule|workflow_dispatch", WF)
        self.assertIn('refs/heads/$DEFAULT_BRANCH', WF)
        workflow_permissions = _indented_block(WF, "permissions:", 0)
        job_permissions = _indented_block(WF, "permissions:", 4)
        self.assertIn("contents: read", workflow_permissions)
        self.assertNotIn("issues: write", workflow_permissions)
        self.assertIn("contents: read", job_permissions)
        self.assertIn("issues: write", job_permissions)
        self.assertNotIn("contents: write", WF)
        self.assertNotIn("secrets: inherit", WF)
        self.assertIn("timeout-minutes: 10", WF)
        self.assertIn("observe_kit.py", WF)
        actions = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s]+)", WF, flags=re.MULTILINE)
        self.assertTrue(actions)
        for action in actions:
            if action.startswith("./"):
                continue
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
