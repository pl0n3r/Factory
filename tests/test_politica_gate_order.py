#!/usr/bin/env python3
"""Regresiones offline del cierre acotado de checks de Policy reusable."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/politica.yml"
HEAD = "a" * 40
APPS = {
    "github-actions": 15368,
    "sonarqubecloud": 12526,
    "github-advanced-security": 57789,
}


class PolicyGateOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        found = re.search(
            r"(?ms)^          # POLICY_GATE_READINESS_BEGIN\n.*?<<'PY'\n"
            r"(?P<script>.*?)^          PY$",
            cls.workflow,
        )
        if not found:
            raise AssertionError("Falta verificador canónico ejecutable de gates")
        cls.script = "\n".join(
            line[10:] if line.startswith(" " * 10) else line
            for line in found.group("script").splitlines()
        )
        wait = re.search(
            r"(?ms)^          # POLICY_GATE_WAIT_BEGIN\n"
            r"(?P<body>.*?)^          # POLICY_GATE_WAIT_END",
            cls.workflow,
        )
        if not wait:
            raise AssertionError("Falta espera temporal de gates")
        cls.wait_script = wait.group("body")

    def checks(self):
        names = [
            ("Factory CI reusable / Validar", "github-actions"),
            ("SonarCloud Code Analysis", "sonarqubecloud"),
            ("CodeQL", "github-advanced-security"),
            ("fast", "github-actions"),
            ("Validar coordinación", "github-actions"),
            ("Privacidad / Privacidad como código", "github-actions"),
            ("Factory CI reusable / Preflight reusable", "github-actions"),
        ]
        return [
            {
                "id": idx,
                "name": name,
                "head_sha": HEAD,
                "status": "completed",
                "conclusion": "success",
                "app": {"slug": app, "id": APPS[app]},
            }
            for idx, (name, app) in enumerate(names, 1)
        ]

    def run_gate(self, checks, *, head=HEAD):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "checks.ndjson"
            source.write_text(
                "".join(json.dumps(item) + "\n" for item in checks),
                encoding="utf-8",
            )
            env = dict(os.environ, PYTHONPATH=str(ROOT / "scripts"))
            return subprocess.run(
                [sys.executable, "-c", self.script, str(source), head],
                cwd=ROOT, env=env, capture_output=True, text=True, check=False,
            )

    def run_wait(self, ready_at: int, *, budget: int = 420, mode: str = "pending"):
        """Run the actual bash wait loop with only API snapshots/time simulated.

        No real sleeping or network. The production readiness evaluator has
        separate integration tests above, including forged app/HEAD checks.
        """
        stubbed, count = re.subn(
            r"(?ms)^            # POLICY_CHECK_SNAPSHOT_BEGIN\n"
            r".*?^            # POLICY_CHECK_SNAPSHOT_END\n",
            "            : # snapshot validated by independent test\n",
            self.wait_script,
            count=1,
        )
        self.assertEqual(count, 1, "No puede omitirse la seguridad del snapshot")
        script = r"""
set -euo pipefail
GATE_WAIT_SECONDS="$1"
READY_AT="$2"
MODE="$3"
SECONDS=0
gate_readiness() {
  if [[ "$MODE" == "red" ]]; then return 1; fi
  if [[ "$MODE" == "missing" ]]; then return 75; fi
  if (( SECONDS >= READY_AT )); then return 0; fi
  return 75
}
recheck_pr_identity() { [[ "$MODE" != "stale" ]]; }
sleep() { SECONDS=$(( SECONDS + $1 )); }
""" + stubbed + '\nprintf "elapsed=%s\\n" "$SECONDS"\n'
        return subprocess.run(
            ["bash", "-c", script, "policy-wait",
             str(budget), str(ready_at), mode],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )

    def test_la_espera_cubre_un_gate_lento(self):
        """A real 5-minute gate must not be misread as a failure after ~48 s."""
        for ready_at in (0, 305, 345):
            with self.subTest(ready_at=ready_at):
                result = self.run_wait(ready_at)
                self.assertEqual(result.returncode, 0, result.stderr)
                elapsed = int(result.stdout.strip().split("elapsed=")[-1])
                self.assertGreaterEqual(elapsed, ready_at)
                self.assertLessEqual(elapsed, 420)
        self.assertIn("gate_wait_seconds: {required: false, type: number, default: 420}",
                      self.workflow)
        self.assertIn("timeout-minutes: 15", self.workflow)
        self.assertIn("gate_wait_started=$SECONDS", self.workflow)
        self.assertIn("while true; do", self.wait_script)
        self.assertIn("recheck_pr_identity ||", self.wait_script)
        self.assertIn("POLICY_CHECK_SNAPSHOT_BEGIN", self.workflow)
        self.assertIn("POLICY_CHECK_SNAPSHOT_END", self.workflow)
        self.assertIn("gate_sleep=$(( GATE_WAIT_SECONDS", self.workflow)
        self.assertNotIn("for gate_attempt in 1 2 3 4 5 6; do", self.wait_script)

    def test_un_gate_rojo_o_ausente_falla_cerrado(self):
        """A terminal failure exits immediately; UNKNOWN times out within cap."""
        terminal_red = self.run_wait(999, mode="red")
        self.assertNotEqual(terminal_red.returncode, 0)
        self.assertNotIn("elapsed=", terminal_red.stdout)
        missing = self.run_wait(999, mode="missing")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("Gates requeridos sin evidencia terminal verde", missing.stderr)
        for budget in (0, -1, 299, 541, 9999):
            with self.subTest(budget=budget):
                invalid = self.run_wait(10, budget=budget)
                self.assertNotEqual(invalid.returncode, 0)
                self.assertIn("gate_wait_seconds inválido", invalid.stderr)
        stale = self.run_wait(999, mode="stale")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("Identidad HEAD/BASE cambió", stale.stderr)

    def test_rerun_por_gate_lento_no_es_reintento_owner(self):
        """Rerun without verified reviewer rate-limit must not use timeline."""
        self.assertIn(
            'if (( GITHUB_RUN_ATTEMPT > 1 )) && [[ "$reviewer_rate_limited" == true ]]; then',
            self.workflow,
        )
        self.assertIn('(.user.login // "") == $bot', self.workflow)
        self.assertIn('reviewer_rate_limited=false', self.workflow)
        self.assertIn('[[ -n "$REQUIRED_REVIEW_BOT" ]]', self.workflow)
        self.assertIn('--timeline-file "$timeline_file"', self.workflow)

    def test_pending_required_checks_are_not_misclassified_as_final_failure(self):
        original = self.checks()
        for pending_name in ("Factory CI reusable / Preflight reusable", "fast"):
            with self.subTest(check=pending_name):
                interim = [dict(check) for check in original]
                target = next(item for item in interim if item["name"] == pending_name)
                target["status"] = "in_progress"
                target["conclusion"] = None
                self.assertEqual(self.run_gate(interim).returncode, 75)
                target["status"] = "completed"
                target["conclusion"] = "success"
                self.assertEqual(self.run_gate(interim).returncode, 0)
        self.assertIn("while true; do", self.wait_script)
        self.assertIn("(( gate_exit == 75 )) || exit 1", self.workflow)
        self.assertIn('sleep "$gate_sleep"', self.workflow)

    def test_terminal_non_green_and_unverifiable_checks_still_fail_closed(self):
        failed = self.checks()
        failed[3]["conclusion"] = "failure"
        self.assertEqual(self.run_gate(failed).returncode, 1)
        spoof = self.checks()
        spoof[1]["app"] = {"slug": "github-actions", "id": 15368}
        self.assertEqual(self.run_gate(spoof).returncode, 1)
        incomplete = [c for c in self.checks() if c["name"] != "CodeQL"]
        self.assertEqual(self.run_gate(incomplete).returncode, 75)
        self.assertIn("Gates requeridos sin evidencia terminal verde", self.workflow)
        self.assertIn("No se pudieron leer check-runs autenticados", self.workflow)
        self.assertIn("(( current_total <= MAX_PUBLIC_CHECKS ))", self.workflow)
        self.assertIn("MAX_EVIDENCE_BYTES", self.workflow)

    def test_exact_head_identity_and_security_gates_remain_mandatory(self):
        wrong_sha = self.checks()
        wrong_sha[0]["head_sha"] = "b" * 40
        self.assertEqual(self.run_gate(wrong_sha).returncode, 1)
        self.assertEqual(self.run_gate(self.checks(), head="b" * 40).returncode, 1)
        for required in (
            "recheck_pr_identity",
            "PR_BASE_SHA",
            "PR_HEAD_SHA",
            "CURRENT_HEAD",
            "CURRENT_BASE",
            "POLICY_CHECK_SNAPSHOT_BEGIN",
            "POLICY_CHECK_SNAPSHOT_END",
            "kit.validate_other_gates_green",
            "Política reusable",
            "pull-requests: read",
            "timeout-minutes: 15",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.workflow)


if __name__ == "__main__":
    unittest.main()
