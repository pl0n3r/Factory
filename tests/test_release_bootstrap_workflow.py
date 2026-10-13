#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import release_window as rw

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / ".github/workflows/release-bootstrap.yml").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs/release-bootstrap.md").read_text(encoding="utf-8")


class ReleaseBootstrapWorkflowTests(unittest.TestCase):
    def test_candidate_template_runs_before_preflight_read_only(self):
        self.assertIn("uses: ./.github/workflows/ci.yml", BOOTSTRAP)
        self.assertIn("kit_ref: ${{ github.sha }}", BOOTSTRAP)
        self.assertLess(BOOTSTRAP.index("candidate-template:"), BOOTSTRAP.index("preflight:"))
        candidate = BOOTSTRAP.split("candidate-template:", 1)[1].split("preflight:", 1)[0]
        self.assertIn("contents: read", candidate)
        self.assertNotIn("contents: write", candidate)

    def test_reusable_release_dispatch_is_factory_owner_only(self):
        for value in (
            "factory_bootstrap:", "expected_sha:", "workflow_dispatch)",
            '[[ "$REPOSITORY" == "pl0n3r/factory" ]]',
            '[[ "$ACTOR" == "$OWNER" ]]', '[[ "$BOOTSTRAP" == "true" ]]',
            '[[ "$EXPECTED_SHA" == "$GITHUB_SHA" ]]',
        ):
            self.assertIn(value, RELEASE)

    def test_published_v1_is_used_for_release_and_post_selftest(self):
        self.assertIn("uses: pl0n3r/factory/.github/workflows/release.yml@v1", BOOTSTRAP)
        self.assertIn("uses: pl0n3r/factory/.github/workflows/ci.yml@v1", BOOTSTRAP)
        release = BOOTSTRAP.split("\n  release:", 1)[1].split("\n  selftest-published:", 1)[0]
        self.assertNotIn("kit_ref:", release)
        self.assertIn("factory_bootstrap: true", release)

    def test_release_keeps_published_v1_trust_root_before_channel_move(self):
        release = BOOTSTRAP.split("\n  release:", 1)[1].split(
            "\n  channel-ready:", 1
        )[0]
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/release.yml@v1",
            release,
        )
        self.assertNotIn("uses: ./.github/workflows/release.yml", release)
        self.assertLess(
            BOOTSTRAP.index("\n  release:"),
            BOOTSTRAP.index("\n  channel-ready:"),
        )

    def test_channel_gate_blocks_selftest_until_v1_matches_approved_sha(self):
        channel = BOOTSTRAP.split("\n  channel-ready:", 1)[1].split(
            "\n  selftest-published:", 1
        )[0]
        for value in (
            "needs: [preflight, release]",
            "contents: read",
            "repos/$REPOSITORY/git/ref/tags/v1",
            "APPROVED_SHA",
            '[[ "$v1_sha" == "$APPROVED_SHA" ]]',
            "mueve administrativamente v1",
        ):
            self.assertIn(value, channel)
        self.assertNotIn("contents: write", channel)

        selftest = BOOTSTRAP.split("\n  selftest-published:", 1)[1]
        self.assertIn("needs: channel-ready", selftest)
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/ci.yml@v1",
            selftest,
        )

    def test_guide_orders_semantic_release_before_manual_v1_move_and_selftest(self):
        maintenance = GUIDE.split("## Mantenimiento v1.x", 1)[1].split(
            "## Rollback tras startup_failure", 1
        )[0]
        semantic = maintenance.index("release semántico")
        move = maintenance.index("mueve manualmente el tag mayor `v1`")
        selftest = maintenance.index("self-test")
        self.assertLess(semantic, move)
        self.assertLess(move, selftest)
        self.assertIn("reejecuta", maintenance)
        self.assertIn("idempotente", maintenance)
    def test_preflight_revalidates_v1_ruleset_read_only(self):
        preflight = BOOTSTRAP.split("\n  preflight:", 1)[1].split("\n  release:", 1)[0]
        self.assertIn(
            'repos/$REPOSITORY/rulesets?includes_parents=true&per_page=100',
            preflight,
        )
        self.assertIn(
            'repos/$REPOSITORY/rulesets/$ruleset_id?includes_parents=true',
            preflight,
        )
        self.assertIn("python3 scripts/verificar_ruleset_v1.py", preflight)
        self.assertLess(
            preflight.index("python3 scripts/verificar_ruleset_v1.py"),
            preflight.index("python3 -m scripts.release_bootstrap"),
        )
        self.assertIn("contents: read", preflight)
        self.assertIn("issues: read", preflight)
        self.assertNotIn("contents: write", preflight)

    def test_final_preflight_requires_fresh_main_before_approval_output(self):
        """Second main SHA read must reject drift before emitting approval."""
        begin = "# EXACT_MAIN_FINAL_RECHECK_BEGIN"
        end = "# EXACT_MAIN_FINAL_RECHECK_END"
        self.assertEqual(BOOTSTRAP.count(begin), 1)
        self.assertEqual(BOOTSTRAP.count(end), 1)
        block = textwrap.dedent(BOOTSTRAP.split(begin, 1)[1].split(end, 1)[0])
        self.assertIn('gh api "repos/$REPOSITORY/commits/$DEFAULT_BRANCH"', block)
        self.assertIn('echo "approved_sha=$approved_sha" >> "$GITHUB_OUTPUT"', block)
        for name in ("CI factory", "Sonar CI-based",
                     "Evidencia CodeQL", "Unattended Watchdog"):
            self.assertEqual(block.count(f'require_exact_main_success "{name}"'), 1)
        gate_fake = (
            'require_exact_main_success() {\n'
            '  [[ "$1" != "${FAKE_FAILED_WORKFLOW:-}" ]]\n'
            '}\n'
        )
        sha = "a" * 40
        moved = "b" * 40
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            stub = tmpdir / "gh"
            stub.write_text("#!/bin/sh\nprintf '%s\\n' \"$FAKE_MAIN_SHA\"\n", encoding="utf-8")
            stub.chmod(0o700)
            output = tmpdir / "approval"
            for label, current, approved, failed_workflow, expected_success in (
                ("unchanged", sha, sha, "", True),
                ("main advanced", moved, sha, "", False),
                ("approval mismatch", sha, moved, "", False),
                ("malformed remote SHA", "truncated", sha, "", False),
                ("remote call empty", "", sha, "", False),
                ("new CI pending, same SHA", sha, sha, "CI factory", False),
                ("new Sonar failure, same SHA", sha, sha, "Sonar CI-based", False),
                ("new CodeQL pending, same SHA", sha, sha, "Evidencia CodeQL", False),
                ("new Watchdog failure, same SHA", sha, sha, "Unattended Watchdog", False),
            ):
                with self.subTest(case=label):
                    output.write_text("", encoding="utf-8")
                    import os
                    env = dict(os.environ, PATH=str(tmpdir) + ":" + os.environ["PATH"],
                               REPOSITORY="pl0n3r/factory", DEFAULT_BRANCH="main",
                               CURRENT_SHA=sha, default_sha=sha, resolved_sha=sha,
                               approved_sha=approved, GITHUB_OUTPUT=str(output),
                               FAKE_MAIN_SHA=current,
                               FAKE_FAILED_WORKFLOW=failed_workflow)
                    result = subprocess.run(
                        ["bash", "-euo", "pipefail", "-c", gate_fake + block],
                        capture_output=True, text=True, timeout=10, env=env,
                    )
                    if expected_success:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(output.read_text(encoding="utf-8"),
                                         f"approved_sha={sha}\n")
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(output.read_text(encoding="utf-8"), "")

    def test_preflight_command_imports_run_as_in_the_workflow(self):
        """Regresión #102: el comando exacto del workflow debe resolver sus imports."""
        match = re.search(r"python3 (-m [\w.]+|scripts/release_bootstrap\.py)", BOOTSTRAP)
        self.assertIsNotNone(match)
        args = [sys.executable, *match.group(1).split()]
        result = subprocess.run(
            args, cwd=ROOT, input="{}", capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "ERROR: repository inválido.\n")
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertNotIn("ImportError", result.stderr)

    def test_guide_keeps_parent_ruleset_gate_boundary(self):
        for value in (
            "#83",
            "ruleset",
            "creation",
            "update",
            "deletion",
            "bypass",
            "solo estructural",
        ):
            self.assertIn(value, GUIDE)

    def test_v1_0_0_probe_only_treats_404_as_absent(self):
        preflight = BOOTSTRAP.split("\n  preflight:", 1)[1].split("\n  release:", 1)[0]
        self.assertIn("gh api --include --silent", preflight)
        self.assertIn("404([[:space:]]|$)", preflight)
        self.assertIn("No se pudo determinar si existe v1.0.0", preflight)
        self.assertIn("exit 1", preflight)

    def test_release_workflow_and_guide_match_v1_lifecycle(self):
        for value in (
            "name: Release Factory v1.x",
            'repos/$REPOSITORY/git/ref/tags/v1.0.0',
            "--argjson v1_0_0_exists",
        ):
            self.assertIn(value, BOOTSTRAP)
        for value in (
            "Release Factory v1.x", "factory-release-approval",
            "factory-release", "release-1.0.0",
            "expected_sha", "gate_issue", "#83", "self-test", "@v1",
            "nunca crea ni mueve `v1`",
        ):
            self.assertIn(value, GUIDE)


    def _extract_latest_gate_sha(self, body: str) -> subprocess.CompletedProcess[str]:
        """Ejecuta el mismo fragmento Python embebido en el preflight de latest."""
        marker = "gate_sha=\"$(python3 - /tmp/gate.json <<'PY'"
        self.assertEqual(BOOTSTRAP.count(marker), 1)
        script = BOOTSTRAP.split(marker, 1)[1].split("\n          PY", 1)[0]
        script = textwrap.dedent(script)
        with tempfile.TemporaryDirectory() as tmp:
            gate_path = Path(tmp) / "gate.json"
            gate_path.write_text(json.dumps({"body": body}), encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-c", script, str(gate_path)],
                capture_output=True, text=True, timeout=10,
            )

    def test_latest_accepts_repeated_identical_sha_from_generated_release_window_gate(self):
        """AC-01: la puerta real repite el SHA sin crear dos candidatos distintos."""
        sha = "a" * 40
        gate = rw._render_gate(
            "1.0.28", sha, datetime(2026, 10, 9, tzinfo=timezone.utc),
            source_issue=1014,
        )["body"]
        self.assertGreaterEqual(gate.count("main@" + sha), 2)
        result = self._extract_latest_gate_sha(gate)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), sha)
        # Mismo SHA en diferente representación hexadecimal: único valor.
        mixed_case = gate.replace("main@" + sha, "main@" + sha.upper(), 1)
        mixed_result = self._extract_latest_gate_sha(mixed_case)
        self.assertEqual(mixed_result.returncode, 0, mixed_result.stderr)
        self.assertEqual(mixed_result.stdout.strip(), sha)

    def test_latest_rejects_distinct_shas_in_gate_body(self):
        """AC-02: no aceptar puerta sin baseline ni con SHAs contradictorios."""
        sha = "a" * 40
        gate = rw._render_gate(
            "1.0.28", sha, datetime(2026, 10, 9, tzinfo=timezone.utc),
            source_issue=1014,
        )["body"]
        for invalid in (
            "sin main@SHA",
            gate + "\nmain@" + "b" * 40,
            # Segundo valor distinto en HEX mayúsculas jamás debe ignorarse.
            gate + "\nmain@" + "B" * 40,
        ):
            with self.subTest(body=invalid[-50:]):
                result = self._extract_latest_gate_sha(invalid)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("gate sin main@SHA único", result.stderr)


    # #1079: execute the jq filter extracted from the ACTUAL workflow.
    @staticmethod
    def _workflow_path(name):
        return {
            "CI factory": ".github/workflows/factory-ci.yml",
            "Sonar CI-based": ".github/workflows/sonar.yml",
            "Evidencia CodeQL": ".github/workflows/codeql-evidence.yml",
            "Unattended Watchdog": ".github/workflows/unattended-watchdog.yml",
        }.get(name, ".github/workflows/other.yml")

    @staticmethod
    def _exact_run(number, name="CI factory", status="completed",
                   conclusion="success", created="2026-10-11T09:00:00Z",
                   sha=None, attempt=1, started=None, path=None,
                   head_branch="main"):
        if sha is None:
            sha = "a" * 40
        if started is None and status == "completed":
            started = created
        if path is None:
            path = ReleaseBootstrapWorkflowTests._workflow_path(name)
        return {
            "id": number, "run_attempt": attempt, "name": name,
            "path": path, "head_branch": head_branch,
            "head_sha": sha, "created_at": created,
            "run_started_at": started, "updated_at": started or created,
            "status": status, "conclusion": conclusion,
        }

    def _check_latest(self, runs, workflow="CI factory", total=None):
        begin, end = "# EXACT_MAIN_JQ_BEGIN", "# EXACT_MAIN_JQ_END"
        self.assertEqual(BOOTSTRAP.count(begin), 1)
        self.assertEqual(BOOTSTRAP.count(end), 1)
        program = textwrap.dedent(BOOTSTRAP.split(begin, 1)[1].split(end, 1)[0])
        snapshot = {
            "total_count": len(runs) if total is None else total,
            "workflow_runs": runs,
        }
        result = subprocess.run(
            ["jq", "-e", "--arg", "workflow_name", workflow,
             "--arg", "sha", "a" * 40,
             "--arg", "workflow_path", self._workflow_path(workflow),
             program],
            input=json.dumps(snapshot), capture_output=True, text=True, timeout=10,
        )
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode == 0 and result.stdout.strip() == "true"


    def test_latest_accepts_documented_github_rest_workflow_path_at_main(self):
        """REST may report path='.../factory-ci.yml@main', not just a bare path."""
        for name in ("CI factory", "Sonar CI-based",
                     "Evidencia CodeQL", "Unattended Watchdog"):
            path = self._workflow_path(name)
            for ref in ("", "@main"):
                with self.subTest(name=name, ref=ref or "bare"):
                    self.assertTrue(self._check_latest([
                        self._exact_run(100, name=name, path=path + ref)
                    ], workflow=name))
            for ref in ("@dev", "@refs/heads/main", "@MAIN",
                        "@main/evil", "@main@main"):
                with self.subTest(name=name, unsafe_ref=ref):
                    self.assertFalse(self._check_latest([
                        self._exact_run(100, name=name, path=path + ref)
                    ], workflow=name))
            with self.subTest(name=name, case="other_workflow"):
                self.assertFalse(self._check_latest([
                    self._exact_run(100, name=name,
                                    path=".github/workflows/foreign.yml@main")
                ], workflow=name))
            with self.subTest(name=name, case="other_branch"):
                self.assertFalse(self._check_latest([
                    self._exact_run(100, name=name, path=path + "@main",
                                    head_branch="feature")
                ], workflow=name))

    def test_latest_rejects_stale_success_if_newer_run_failed(self):
        old = self._exact_run(100)
        later = "2026-10-11T09:05:00Z"
        for conclusion in ("failure", "cancelled", "timed_out"):
            with self.subTest(conclusion=conclusion):
                self.assertFalse(self._check_latest([
                    old, self._exact_run(101, conclusion=conclusion, created=later),
                ]))
        # Rerun of an older run ID supersedes newer successful creation.
        retried = self._exact_run(
            100, conclusion="failure", attempt=2,
            started="2026-10-11T09:20:00Z",
        )
        self.assertFalse(self._check_latest([
            retried, self._exact_run(101, created=later),
        ]))
        # A real newer success should still supersede an older failure.
        self.assertTrue(self._check_latest([
            self._exact_run(100, conclusion="failure"),
            self._exact_run(101, created=later),
        ]))
        # Created later but finished before older run started: false green.
        self.assertFalse(self._check_latest([
            self._exact_run(100, started="2026-10-11T09:20:00Z"),
            self._exact_run(101, conclusion="failure",
                            created="2026-10-11T09:10:00Z"),
        ]))

    def test_latest_rejects_stale_success_if_newer_run_pending(self):
        old = self._exact_run(100)
        for status in ("queued", "in_progress", "waiting", "pending"):
            with self.subTest(status=status):
                self.assertFalse(self._check_latest([
                    old, self._exact_run(101, status=status, conclusion=None,
                                         created="2026-10-11T09:05:00Z"),
                ]))
        self.assertFalse(self._check_latest([
            self._exact_run(100, status="in_progress", conclusion=None, attempt=2),
            self._exact_run(101, created="2026-10-11T09:05:00Z"),
        ]))
        self.assertFalse(self._check_latest([
            self._exact_run(100, started="2026-10-11T09:20:00Z"),
            self._exact_run(101, status="queued", conclusion=None,
                            created="2026-10-11T09:10:00Z"),
        ]))

    def test_latest_requires_newest_success_per_required_workflow_exact_sha(self):
        names = ("CI factory", "Sonar CI-based", "Evidencia CodeQL",
                 "Unattended Watchdog")
        runs = [self._exact_run(100 + n, name=name)
                for n, name in enumerate(names)]
        for name in names:
            self.assertTrue(self._check_latest(runs, workflow=name))
        unrelated = [
            self._exact_run(200, sha="b" * 40,
                            created="2026-10-11T09:10:00Z"),
            self._exact_run(201, name="Other",
                            created="2026-10-11T09:11:00Z"),
        ]
        for name in names:
            self.assertTrue(self._check_latest(runs + unrelated, workflow=name))
        self.assertFalse(self._check_latest(runs[:-1],
                                            workflow="Unattended Watchdog"))
        bad = runs + [self._exact_run(202, name="Sonar CI-based",
                                    conclusion="failure",
                                    created="2026-10-11T09:12:00Z")]
        self.assertFalse(self._check_latest(bad, workflow="Sonar CI-based"))
        self.assertTrue(self._check_latest(bad, workflow="CI factory"))

        # Misma etiqueta, distinto workflow: no puede suplir CI legitimo rojo.
        spoofed = [
            self._exact_run(100, conclusion="failure"),
            self._exact_run(210, created="2026-10-11T09:20:00Z",
                            path=".github/workflows/foreign-ci.yml"),
        ]
        self.assertFalse(self._check_latest(spoofed))
        self.assertFalse(self._check_latest([
            self._exact_run(100, head_branch="otra-rama")
        ]))

    def test_latest_fails_closed_for_incomplete_ambiguous_or_malformed_runs(self):
        good = self._exact_run(100)
        self.assertIn(
            'repos/$REPOSITORY/actions/workflows/$workflow_file/runs?head_sha=$resolved_sha&per_page=100&page=1',
            BOOTSTRAP,
        )
        self.assertNotIn('repos/$REPOSITORY/actions/runs?head_sha=', BOOTSTRAP)
        for filename in ("factory-ci.yml", "sonar.yml",
                         "codeql-evidence.yml", "unattended-watchdog.yml"):
            self.assertIn(f'"{filename}"', BOOTSTRAP)
        self.assertNotIn('gh run list --commit "$resolved_sha"', BOOTSTRAP)
        cases = (
            ("truncated", [good], 2),
            ("over cap", [self._exact_run(n) for n in range(1, 101)], 100),
            ("duplicate id", [good, dict(good)], None),
            ("invalid id", [dict(good, id=True)], None),
            ("missing attempt", [{k: v for k, v in good.items()
                                 if k != "run_attempt"}], None),
            ("completed with null start", [dict(good, run_started_at=None)], None),
            ("completed without start", [{k: v for k, v in good.items()
                                         if k != "run_started_at"}], None),
            ("missing time", [dict(good, created_at=None)], None),
            ("invalid time", [dict(good, created_at="yesterday")], None),
            ("inverted time", [dict(good,
                                   updated_at="2026-10-11T08:59:00Z")], None),
            ("ambiguous tie", [good, self._exact_run(101,
                                                    conclusion="failure")], None),
            ("malformed status", [dict(good, status=5)], None),
            ("missing path", [dict(good, path=None)], None),
            ("invalid path", [dict(good, path="../foreign.yml")], None),
            ("missing branch", [dict(good, head_branch=None)], None),
        )
        for desc, runs, count in cases:
            with self.subTest(case=desc):
                self.assertFalse(self._check_latest(runs, total=count))



if __name__ == "__main__":
    unittest.main()
