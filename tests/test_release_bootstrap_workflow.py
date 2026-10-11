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


if __name__ == "__main__":
    unittest.main()
