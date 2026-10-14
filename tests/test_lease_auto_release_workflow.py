"""Protecciones del workflow de reservas V3, sin ejecución de GitHub real."""
import unittest
from pathlib import Path

from scripts.lease_auto_release_run import run_cycle


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "liberar-reservas.yml"


class DenyTransport:
    def __getattr__(self, name):
        raise AssertionError("OFF must never read or write the Port")


class LeaseAutoReleaseWorkflowTests(unittest.TestCase):
    def test_scheduled_executor_kill_switch_quota_and_shared_lock(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '*/10 * * * *'", text)
        self.assertIn("factory-coordination-{0}", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("permissions:\n  contents: read\n  issues: read", text)
        self.assertNotIn("issues: write", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("pull-requests: read", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertIn("Observador integrado autenticado V3", text)
        self.assertIn("gh api --paginate --slurp", text)
        self.assertIn("inventory_after_switch_recheck", text)
        self.assertIn("lease-observer-switch-before.json", text)
        self.assertIn("lease-observer-switch-after.json", text)
        self.assertIn("lease-observer-issues.json", text)
        self.assertNotIn("unique | sort", text)
        self.assertIn("lease-active-issues.json", text)
        self.assertIn("estado: requiere recuperación", text)
        self.assertIn("len(managed) > 10", text)
        self.assertIn('python3 -m scripts.lease_auto_release_integration "$issue_number"', text)
        self.assertNotIn("scripts.lease_auto_release_integration 1185", text)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", text)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", text)

        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", text)
        self.assertIn("GH_TOKEN: ${{ github.token }}", text)
        self.assertIn("/repos/pl0n3r/Factory/issues/767", text)
        self.assertIn("inventory_after_switch_recheck", text)
        self.assertIn("remaining * 5 < limit", text)
        self.assertIn("test_lease_auto_release.py", text)
        self.assertIn("run_cycle([1175], NoAccessPort())", text)
        self.assertNotIn("gh api -X POST", text)
        self.assertNotIn("gh api -X PATCH", text)
        self.assertNotIn("gh api -X DELETE", text)
        result = run_cycle([1185], DenyTransport())
        self.assertEqual(result.state, "feature_disabled")
        self.assertEqual(result.results[0][1].reason, "feature_disabled")
        self.assertFalse(result.results[0][1].wrote)


    def test_inline_observer_inventory_executes_fail_closed(self):
        """Regresión real del Python embebido en el workflow, sin API ni mutaciones."""
        import json
        import subprocess
        import sys
        import tempfile
        import textwrap

        workflow = WORKFLOW.read_text(encoding="utf-8")
        anchor = '          python3 - "$RUNNER_TEMP/lease-observer-switch-before.json"'
        self.assertEqual(workflow.count(anchor), 1)
        inline = workflow.split(anchor, 1)[1].split(" <<'PY'\n", 1)[1]
        inline = inline.split("\n          PY\n", 1)[0]
        script = textwrap.dedent(inline)
        self.assertIn("inventory_after_switch_recheck", script)

        from scripts.unattended_kill_switch import (
            CANONICAL_SOURCE_URL, CANONICAL_REPOSITORY_URL,
        )
        running = {
            "number": 767, "state": "closed",
            "url": CANONICAL_SOURCE_URL,
            "repository_url": CANONICAL_REPOSITORY_URL,
            "user": {"login": "pl0n3r"},
            "body": '<!-- factory-unattended-kill-switch '
                    '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->',
        }

        def issue(number, status="estado: en revisión", *, pr=False):
            data = {"number": number, "state": "open",
                    "labels": [{"name": status}]}
            if pr:
                data["pull_request"] = {"url": "https://example.invalid/pr"}
            return data

        def execute(pages, after=None):
            with tempfile.TemporaryDirectory() as folder:
                paths = [Path(folder) / f"{name}.json" for name in
                         ("before", "after", "pages", "result")]
                for path, payload in zip(
                    paths, (running, running if after is None else after, pages),
                ):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                run = subprocess.run(
                    [sys.executable, "-c", script, *map(str, paths)],
                    cwd=ROOT, capture_output=True, text=True,
                    timeout=15, check=False,
                )
                result = (json.loads(paths[3].read_text(encoding="utf-8"))
                          if paths[3].exists() else None)
                return run, result

        valid = [[issue(8), issue(3, "estado: reservado"),
                  issue(11, "estado: requiere recuperación"),
                  issue(42, pr=True), issue(99, "tipo: producto")]]
        run, result = execute(valid)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(result, [3, 8, 11])

        invalid = [
            [valid[0], valid[0]],  # página parcial intermedia
            [[issue(8), issue(8)]],  # duplicate V3
            [[issue(8, "ESTADO: en revisión")]],  # alias de estado ambiguo
            [[issue(8), issue(9, "estado: reservado"), issue(9)]],
            [[issue(n) for n in range(1, 12)]],  # >10 observaciones
            [[issue(n) for n in range(1, 101)]],  # EOF no probado
        ]
        for pages in invalid:
            with self.subTest(case=str(pages)[:90]):
                run, result = execute(pages)
                self.assertNotEqual(run.returncode, 0)
                self.assertIsNone(result)
        paused = {**running,
                  "body": running["body"].replace("RUNNING", "PAUSED")}
        run, result = execute(valid, after=paused)
        self.assertNotEqual(run.returncode, 0)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
