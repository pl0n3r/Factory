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
    def test_readme_reports_both_reservation_release_phases(self):
        """El README muestra Fase A incompleta y Fase B sin autoridad."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "liberacion-automatica-de-reservas.md"
                ).read_text(encoding="utf-8")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(readme.count("### Liberación automática de reservas V3 (#1382)"), 1)
        for expected in (
            "Fase A — observación GET-only", "Implementación parcial",
            "Fase B — liberación automática", "NO ACTIVADA",
            "FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'",
            "24 horas", "100 ciclos terminales y válidos por repositorio",
            "cero falsos positivos", "QA individual", "deferred_low_quota",
            "GITHUB_TOKEN", "No se usa un token multi-repositorio",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, readme)
        self.assertIn("24 horas", docs)
        self.assertIn("100 ciclos", docs)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)
        self.assertNotIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'true'", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)

    def test_scheduled_executor_kill_switch_quota_and_shared_lock(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '*/10 * * * *'", text)
        self.assertIn("factory-coordination-{0}", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("permissions:\n  contents: read\n  issues: read", text)
        self.assertNotIn("issues: write", text)
        self.assertNotIn("contents: write", text)
        self.assertIn("pull-requests: read", text)
        self.assertEqual(text.count("      checks: read"), 1)
        self.assertEqual(text.count("      actions: read"), 1)
        self.assertEqual(text.count("  checks: read"), 2)
        self.assertEqual(text.count("  actions: read"), 2)
        self.assertNotIn("checks: write", text)
        self.assertNotIn("actions: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertIn("      - 'scripts/coordinar_trabajo.py'", text)
        for dependency in (
            "scripts/lease_activity_collector.py",
            "tests/test_lease_activity_collector.py",
            "scripts/lease_release_executor.py",
            "tests/test_lease_release_executor.py",
            "scripts/unattended_kill_switch.py",
            "tests/test_unattended_kill_switch.py",
        ):
            with self.subTest(dependency=dependency):
                self.assertIn(f"      - '{dependency}'", text)
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


    def test_low_quota_deferred_green_and_24h_100_cycles_qa_gate(self):
        """La cuota baja aplaza en verde; no concede Fase B sin QA por repo."""
        import os
        import subprocess
        import tempfile
        import textwrap

        workflow = WORKFLOW.read_text(encoding="utf-8")
        anchor = "          if (( remaining * 5 < limit )); then"
        self.assertEqual(workflow.count(anchor), 1)
        branch = workflow.split(anchor, 1)[1].split("\n          fi\n", 1)[0]
        self.assertIn("deferred_low_quota", branch)
        self.assertIn('echo "allow=false" >> "$GITHUB_OUTPUT"', branch)
        self.assertIn('>> "$GITHUB_STEP_SUMMARY"', branch)
        self.assertIn("exit 0", branch)
        self.assertNotIn("exit 1", branch)
        self.assertNotIn("::error::", branch)
        script = ("set -euo pipefail\nremaining=19\nlimit=100\n"
                  + "if (( remaining * 5 < limit )); then\n"
                  + textwrap.dedent(branch) + "\nfi\n")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "output"
            summary = Path(folder) / "summary"
            result = subprocess.run(
                ["bash", "-c", script], cwd=ROOT,
                env={**os.environ, "GITHUB_OUTPUT": str(output),
                     "GITHUB_STEP_SUMMARY": str(summary)},
                capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8").strip(),
                             "allow=false")
            self.assertIn("deferred_low_quota",
                          summary.read_text(encoding="utf-8"))
            self.assertNotIn("::error::", result.stdout)
        self.assertIn("if: steps.budget.outputs.allow == 'true'", workflow)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)
        docs = (ROOT / "docs" / "liberacion-automatica-de-reservas.md"
                ).read_text(encoding="utf-8")
        for requirement in ("24 horas", "100 ciclos", "terminales",
                            "por repositorio", "cero falsos positivos",
                            "QA individual"):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, docs)

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



    def test_unknown_observation_marks_cycle_invalid_but_continues_inventory(self):
        """El cron no puede acreditar como verde un censo con UNKNOWN."""
        import os
        import shutil
        import subprocess
        import tempfile
        import textwrap

        if not shutil.which("jq") or not shutil.which("bash"):
            self.skipTest("bash y jq necesarios para el test del observador")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        anchor = '          jq -e \'type == "array" and length <= 10'
        self.assertEqual(workflow.count(anchor), 1)
        block = textwrap.dedent(workflow[workflow.index(anchor):])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "lease-active-issues.json").write_text(
                "[1364,1372]", encoding="utf-8")
            seen = root / "seen.txt"
            summary = root / "summary.md"
            shim = root / "python3"
            shim.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$3\" >> \"$SEEN_PATH\"\n"
                "if [ \"$3\" = 1364 ] && [ \"$FAIL_FIRST\" = 1 ]; then exit 1; fi\n"
                "exit 0\n", encoding="utf-8")
            shim.chmod(0o755)
            for fail_first in (False, True):
                with self.subTest(fail_first=fail_first):
                    seen.unlink(missing_ok=True)
                    summary.unlink(missing_ok=True)
                    env = {**os.environ, "RUNNER_TEMP": folder,
                           "SEEN_PATH": str(seen),
                           "GITHUB_STEP_SUMMARY": str(summary),
                           "FAIL_FIRST": "1" if fail_first else "0",
                           "PATH": f"{folder}:{os.environ.get('PATH', '')}"}
                    result = subprocess.run(
                        ["bash", "-c", "set -euo pipefail\n" + block],
                        cwd=ROOT, env=env, capture_output=True, text=True,
                        timeout=15, check=False)
                    self.assertEqual(result.returncode == 0, not fail_first, result.stderr)
                    self.assertEqual(
                        seen.read_text(encoding="utf-8").splitlines(),
                        ["1364", "1372"])
                    report = summary.read_text(encoding="utf-8")
                    self.assertIn("liberaciones=0", report)
                    self.assertIn("ciclo válido de Fase A", report)
                    if fail_first:
                        self.assertIn("Observaciones válidas=1; UNKNOWN=1", report)
                        self.assertIn("::notice::Issue #1364", result.stdout)
                        self.assertIn("::error::Censo incompleto", result.stdout)
                    else:
                        self.assertIn("Observaciones válidas=2; UNKNOWN=0", report)
                        self.assertNotIn("::error::", result.stdout)

    def test_observer_jq_failure_propagates(self):
        """No ocultar error de jq dentro de sustitución de proceso Bash."""
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn('done < <(jq -r', workflow)
        self.assertIn('jq -e \'type == "array" and length <= 10', workflow)
        self.assertIn('all(.[]; type == "number" and . > 0 and floor == .)', workflow)
        self.assertIn("length == (unique | length)", workflow)
        self.assertIn('> "$RUNNER_TEMP/lease-active-issue-numbers.txt"', workflow)
        self.assertIn('done < "$RUNNER_TEMP/lease-active-issue-numbers.txt"', workflow)
        self.assertIn('set -euo pipefail', workflow)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)


    def test_shell_inventory_read_is_fail_closed(self):
        """El Bash real no debe ocultar un jq fallido ni ejecutar observaciones."""
        import os
        import shutil
        import subprocess
        import tempfile
        import textwrap

        if not shutil.which("jq") or not shutil.which("bash"):
            self.skipTest("bash y jq necesarios para prueba de shell")
        text = WORKFLOW.read_text(encoding="utf-8")
        anchor = '          jq -e \'type == "array" and length <= 10'
        self.assertEqual(text.count(anchor), 1)
        block = textwrap.dedent(text[text.index(anchor):])
        script = "set -euo pipefail\n" + block

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "lease-active-issues.json"
            numbers = Path(folder) / "lease-active-issue-numbers.txt"
            env = {**os.environ, "RUNNER_TEMP": folder}
            # El caso vacío es válido y no invoca el observador externo.
            source.write_text("[]", encoding="utf-8")
            result = subprocess.run(
                ["bash", "-c", script], cwd=ROOT,
                env=env, capture_output=True, text=True,
                timeout=10, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(numbers.is_file())
            self.assertEqual(numbers.read_text(encoding="utf-8"), "")

            for malformed in (
                "{broken", '{"not": "an-array"}',
                "[1185, 1185]", '[0]', '["1185"]', "[1.5]",
            ):
                with self.subTest(malformed=malformed):
                    numbers.unlink(missing_ok=True)
                    source.write_text(malformed, encoding="utf-8")
                    result = subprocess.run(
                        ["bash", "-c", script], cwd=ROOT,
                        env=env, capture_output=True, text=True,
                        timeout=10, check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(numbers.exists())

if __name__ == "__main__":
    unittest.main()
