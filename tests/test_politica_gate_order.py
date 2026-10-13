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
        self.assertIn("for gate_attempt in 1 2 3 4 5 6; do", self.workflow)
        self.assertIn("(( gate_exit == 75 )) || exit 1", self.workflow)
        self.assertIn("sleep 8", self.workflow)

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
            "timeout-minutes: 5",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.workflow)


if __name__ == "__main__":
    unittest.main()
