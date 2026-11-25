"""Contrato offline de permisos mínimos y triggers Dependabot Factory #2184."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
REUSABLE = (ROOT / ".github/workflows/coordinacion.yml").read_text(encoding="utf-8")
# #2222: los jobs privilegiados viven en su propio reusable; GitHub valida los
# permisos de todos los jobs de un reusable al cargarlo, aunque no se ejecuten.
PRIVILEGED = (ROOT / ".github/workflows/dependabot.yml").read_text(encoding="utf-8")
CALLER = (ROOT / ".github/workflows/dependabot-lane.yml").read_text(encoding="utf-8")
DOC = (ROOT / "docs/dependabot-lane.md").read_text(encoding="utf-8")


def job(yaml, name):
    match = re.search(r"(?ms)^  " + re.escape(name) + r":\n(.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n|\Z)", yaml)
    if not match:
        raise AssertionError(f"Job not found: {name}")
    return match.group(1)


class DependabotLaneWorkflowTests(unittest.TestCase):
    def test_reusable_permissions_are_scoped(self):
        self.assertIn("permissions:\n  contents: read", REUSABLE)
        self.assertIn("permissions:\n  contents: read", PRIVILEGED)
        for name in ("dependabot", "dependabot-sweep"):
            self.assertIn("      contents: write", job(PRIVILEGED, name))
            self.assertIn("      actions: write", job(PRIVILEGED, name))
            self.assertIn("      checks: read", job(PRIVILEGED, name))
            self.assertIn("      issues: write", job(PRIVILEGED, name))
            self.assertIn("      pull-requests: write", job(PRIVILEGED, name))
            # Los callers históricos de coordinacion.yml conservan su envelope.
            self.assertIn("      contents: write", job(REUSABLE, name))
            self.assertNotIn("actions:", job(REUSABLE, name))
        self.assertEqual(PRIVILEGED.count("      actions: write"), 2)
        self.assertNotIn("actions: write", job(PRIVILEGED, "validar-input"))
        # Ningún job de coordinacion.yml puede exigir actions a sus 35 callers.
        self.assertNotIn("      actions:", REUSABLE)
        for name in ("validar-input", "etiqueta", "validar-pr"):
            self.assertNotIn("contents: write", job(REUSABLE, name))
            self.assertNotIn("actions: write", job(REUSABLE, name))
        self.assertIn("contents: read", job(REUSABLE, "validar-pr"))

    def test_caller_is_only_trusted_ci_run_and_daily_schedule(self):
        self.assertIn("workflows: ['CI factory']", CALLER)
        self.assertIn("types: [completed]", CALLER)
        self.assertIn("cron: '29 10 * * *'", CALLER)
        self.assertNotIn("pull_request_target:", CALLER)
        self.assertNotIn("workflow_dispatch:", CALLER)
        self.assertIn("permissions:\n  contents: read", CALLER)
        self.assertIn("cancel-in-progress: false", CALLER)

    def test_caller_requires_exact_head_and_official_bot(self):
        lane = job(CALLER, "dependabot")
        for predicate in (
            "github.event_name == 'workflow_run'",
            "github.event.workflow_run.event == 'pull_request'",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.head_repository.full_name == github.repository",
            "github.event.workflow_run.actor.login == 'dependabot[bot]'",
            "github.event.workflow_run.actor.id == 49699333",
            "github.event.workflow_run.pull_requests[0].number > 0",
            "github.event.workflow_run.pull_requests[1] == null",
            "github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha",
        ):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, lane)
        self.assertIn("pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}", lane)
        self.assertIn("head_sha: ${{ github.event.workflow_run.head_sha }}", lane)
        self.assertNotIn("checkout@", CALLER)
        self.assertIn("uses: ./.github/workflows/dependabot.yml", lane)

    def test_sweep_cannot_run_on_pr_or_workflow_run(self):
        sweep = job(CALLER, "dependabot-sweep")
        self.assertIn("github.event_name == 'schedule'", sweep)
        self.assertIn("github.ref == 'refs/heads/main'", sweep)
        self.assertIn("operation: dependabot-sweep", sweep)
        self.assertNotIn("pr_number:", sweep)
        self.assertNotIn("head_sha:", sweep)

    def test_privileged_callers_grant_actions_write(self):
        self.assertEqual(CALLER.count("      actions: write"), 2)
        for name in ("dependabot", "dependabot-sweep"):
            part = job(CALLER, name)
            self.assertIn("      contents: write", part)
            self.assertIn("      actions: write", part)
            self.assertIn("      checks: read", part)
        self.assertNotIn("actions: write", CALLER.split("jobs:", 1)[0])

    def test_privileged_token_only_two_caller_jobs(self):
        self.assertEqual(CALLER.count("contents: write"), 2)
        for name in ("dependabot", "dependabot-sweep"):
            self.assertIn("contents: write", job(CALLER, name))
            self.assertIn("checks: read", job(CALLER, name))
        self.assertEqual(CALLER.count("uses: ./.github/workflows/dependabot.yml"), 2)
        self.assertNotIn("coordinacion.yml", CALLER)

    def test_reusable_stays_only_workflow_call_and_pinned_kit(self):
        header = REUSABLE.split("\npermissions:", 1)[0]
        self.assertIn("on:\n  workflow_call:", header)
        self.assertNotIn("  workflow_run:", header)
        self.assertNotIn("  schedule:", header)
        for name in ("dependabot", "dependabot-sweep"):
            part = job(REUSABLE, name)
            self.assertIn("repository: pl0n3r/factory", part)
            self.assertIn("ref: v1", part)
            self.assertNotIn("github.event.pull_request.head.sha", part)

    def test_documentation_has_exact_caller_for_each_consumer(self):
        names = {
            "BRVTAL": "BRVTAL CI",
            "GrindFlow": "GrindFlow CI",
            "Condor": "CI Condor (V 0.1.0)",
            "ControlBot": "CI ControlBot",
            "FactoryRunner": "CI",
            "AutoFactory": "Validate",
        }
        for name, ci in names.items():
            with self.subTest(repository=name):
                self.assertIn("### pl0n3r/" + name, DOC)
                self.assertIn("workflows: ['" + ci + "']", DOC)
        # El caller allowlisted para dispatch necesita su propio reusable.
        # Los demás ejemplos conservan el contrato histórico sin actions:write.
        legacy = "uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1"
        privileged = "uses: pl0n3r/factory/.github/workflows/dependabot.yml@v1"
        self.assertEqual(DOC.count(legacy), 10)
        self.assertEqual(DOC.count(privileged), 2)
        grindflow = DOC.split("### pl0n3r/GrindFlow", 1)[1].split(
            "### pl0n3r/Condor", 1)[0]
        self.assertEqual(grindflow.count(privileged), 2)
        self.assertEqual(grindflow.count("      actions: write"), 2)
        self.assertNotIn(legacy, grindflow)
        self.assertIn("pull-requests: write", DOC)
        self.assertIn("Factory#2107", DOC)
        brvtal = DOC.split("### pl0n3r/BRVTAL", 1)[1].split("### pl0n3r/GrindFlow", 1)[0]
        self.assertIn("false &&", brvtal)
        self.assertIn("if: false", brvtal)

    def test_docs_explicitly_prohibit_unsafe_merges(self):
        for phrase in ("major", "pins de workflows", "squash exact-SHA", "Validar",
                       "sin", "sin red", "pull_request_target", "live"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, DOC)

    @staticmethod
    def _pr_step(name):
        """Extraer el Bash que GitHub ejecuta: no simular el comando en el test."""
        section = job(REUSABLE, "pr").split("      - name: " + name + "\n", 1)[1]
        section = section.split("\n      - ", 1)[0]
        script = section.split("        run: |\n", 1)[1]
        commands = []
        for line in script.splitlines():
            if not line.startswith("          "):
                break  # Otro step/comentario YAML: nunca incorporarlo al Bash.
            commands.append(line[10:])
        return section, "\n".join(commands) + "\n"

    @staticmethod
    def _classify_fixture(*, fake_bot=False, code=False, unsigned=False):
        sha = "a" * 40
        user = {
            "login": "dependabot[bot]", "id": 49699333, "type": "Bot",
            "html_url": "https://github.com/apps/dependabot",
            "avatar_url": "https://avatars.githubusercontent.com/in/29110?v=4",
        }
        if fake_bot:
            user["avatar_url"] = "https://avatars.githubusercontent.com/in/99999?v=4"
        return {
            "pr": {
                "number": 99, "state": "open", "user": user, "changed_files": 1,
                "head": {"sha": sha, "repo": {"full_name": "pl0n3r/Factory"}},
                "base": {"sha": "c" * 40, "ref": "main",
                         "repo": {"full_name": "pl0n3r/Factory"}},
            },
            "files": [{
                "filename": "src/main.py" if code else "package-lock.json",
                "status": "modified", "patch": "@@ -1 +1 @@\n-old\n+new",
            }],
            "commit": {
                "author": {"login": "dependabot[bot]", "id": 49699333},
                "commit": {
                    "verification": {"verified": not unsigned},
                    "message": "chore(deps): bump example\n\nupdated-dependencies:\n"
                               "- dependency-name: example\n"
                               "  dependency-version: 1.2.3\n"
                               "  update-type: version-update:semver-minor",
                },
            },
        }

    @staticmethod
    def _mock_api_sitecustomize():
        # Se carga antes del CLI real; intercepta urllib.request.urlopen, no
        # reemplaza el parser ni la clasificación de dependabot_lane.py.
        return '''
import io
import json
import os
from urllib import request
from urllib.error import URLError
from urllib.parse import urlsplit

def mocked_urlopen(req, timeout=None):
    if os.environ.get("FIXTURE_API_ERROR") == "yes":
        raise URLError("API sintética no disponible")
    data = json.loads(os.environ["FIXTURE_JSON"])
    path = urlsplit(req.full_url).path
    if path.endswith("/pulls/99"):
        count = getattr(mocked_urlopen, "count", 0)
        result = json.loads(json.dumps(data["pr"]))
        if count and os.environ.get("FIXTURE_HEAD_DRIFT") == "yes":
            result["head"]["sha"] = "b" * 40
        mocked_urlopen.count = count + 1
    elif path.endswith("/pulls/99/files"):
        result = data["files"]
    elif path.endswith("/commits/" + "a" * 40):
        result = data["commit"]
    else:
        raise AssertionError("URL API no contemplada: " + path)
    return io.BytesIO(json.dumps(result).encode("utf-8"))

request.urlopen = mocked_urlopen
'''

    def _execute_classification(self, fixture, *, api_error=False, drift=False):
        _, shell = self._pr_step("Clasificar Dependabot oficial antes de sincronizar")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kit = root / ".factory/scripts"
            kit.mkdir(parents=True)
            shutil.copyfile(ROOT / "scripts/dependabot_lane.py", kit / "dependabot_lane.py")
            (root / "sitecustomize.py").write_text(self._mock_api_sitecustomize(),
                                                    encoding="utf-8")
            output = root / "output"
            output.write_text("", encoding="utf-8")
            env = {
                **os.environ,
                "PYTHONPATH": str(root),
                "GH_TOKEN": "synthetic-token", "REPOSITORIO": "pl0n3r/Factory",
                "PR": "99", "HEAD": "a" * 40, "GITHUB_OUTPUT": str(output),
                "FIXTURE_JSON": json.dumps(fixture),
                "FIXTURE_API_ERROR": "yes" if api_error else "no",
                "FIXTURE_HEAD_DRIFT": "yes" if drift else "no",
            }
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", shell],
                                    cwd=root, env=env, capture_output=True,
                                    text=True, timeout=15, check=False)
            return result, output.read_text(encoding="utf-8")

    def test_pr_event_classifies_official_dependabot_before_sync(self):
        pr_job = job(REUSABLE, "pr")
        classify_step, classify_run = self._pr_step(
            "Clasificar Dependabot oficial antes de sincronizar")
        sync_step, _ = self._pr_step("Sincronizar PR V3")
        self.assertLess(pr_job.index("dependabot_lane.py classify"),
                        pr_job.index("coordinar_trabajo.py pr-event"))
        self.assertIn("id: dependabot-lane", classify_step)
        self.assertIn("github.event.action != 'closed'", classify_step)
        self.assertIn("github.event.pull_request.user.login == 'dependabot[bot]'",
                      classify_step)
        self.assertIn("HEAD: ${{ github.event.pull_request.head.sha }}", classify_step)
        self.assertIn('dependabot_lane.py classify --repo "$REPOSITORIO" --pr "$PR" --head "$HEAD"',
                      classify_run)
        self.assertIn("echo 'approved=true' >> \"$GITHUB_OUTPUT\"", classify_run)
        self.assertIn("steps.dependabot-lane.outputs.approved != 'true'", sync_step)
        self.assertNotIn("coordinar_trabajo.py", classify_run)
        result, output = self._execute_classification(self._classify_fixture())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "approved=true\n")
        self.assertIn('"policy": "auto"', result.stdout)

    def test_pr_event_preserves_human_and_fail_closed_coordination(self):
        classify_step, _ = self._pr_step(
            "Clasificar Dependabot oficial antes de sincronizar")
        sync_step, sync_run = self._pr_step("Sincronizar PR V3")
        self.assertIn("github.event_name == 'pull_request'", classify_step)
        self.assertIn("github.event.action == 'closed'", sync_step)
        self.assertIn("github.event.pull_request.user.login == 'dependabot[bot]'",
                      sync_step)
        self.assertIn("steps.dependabot-lane.outputs.approved != 'true'", sync_step)
        for name, fixture, options in (
            ("impostor", self._classify_fixture(fake_bot=True), {}),
            ("archivo de código", self._classify_fixture(code=True), {}),
            ("commit no firmado", self._classify_fixture(unsigned=True), {}),
            ("carrera HEAD", self._classify_fixture(), {"drift": True}),
            ("API ilegible", self._classify_fixture(), {"api_error": True}),
        ):
            with self.subTest(case=name):
                result, output = self._execute_classification(fixture, **options)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")
        # Para PR humano y su cierre, clasificador no se activa: el Bash real
        # invoca pr-event. Un cierre de Dependabot no pasa por este camino V3.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kit = root / ".factory/scripts"
            kit.mkdir(parents=True)
            (kit / "coordinar_trabajo.py").write_text(
                'import os,sys,pathlib\n'
                'pathlib.Path(os.environ["CALLED_FILE"]).write_text(" ".join(sys.argv[1:]))\n',
                encoding="utf-8")
            invoked = root / "called"
            for action in ("opened", "closed"):
                with self.subTest(action=action):
                    env = {**os.environ, "GH_TOKEN": "synthetic-token",
                           "REPOSITORIO": "pl0n3r/Factory", "PR": "99",
                           "ACTION": action, "CALLED_FILE": str(invoked)}
                    result = subprocess.run(
                        ["bash", "-euo", "pipefail", "-c", sync_run],
                        cwd=root, env=env, capture_output=True, text=True,
                        timeout=15, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(invoked.read_text(encoding="utf-8"),
                                     "pr-event --repo pl0n3r/Factory --pr 99 --action " + action)


if __name__ == "__main__":
    unittest.main()
