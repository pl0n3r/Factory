"""Regresión CLI de rondas de review acotadas por fase verificada.

Sin red ni GitHub: usa cuatro revisiones sintéticas del mismo bot.
El contrato del reviewer-bot sigue siendo una puerta independiente.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "scripts/politica_kit.py"


class PhaseScopedRoundsTests(unittest.TestCase):
    def run_policy(self, rounds, *, phase=None, absent_file=False):
        reviews = [
            {
                "id": i,
                "state": "COMMENTED",
                "body": f"Revisión accionable {i}",
                "user": {"type": "Bot", "login": "review-bot"},
            }
            for i in range(1, rounds + 1)
        ]
        with tempfile.TemporaryDirectory() as directory:
            command = [sys.executable, str(POLICY)]
            if phase is not None or absent_file:
                phase_file = Path(directory) / "datos.yml"
                if not absent_file:
                    phase_file.write_text(phase, encoding="utf-8")
                command.extend(("--phase-file", str(phase_file)))
            return subprocess.run(
                command,
                cwd=ROOT,
                input="\n".join(json.dumps(row) for row in reviews),
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "GITHUB_RUN_ATTEMPT": "1"},
            )

    def test_construction_allows_four_review_rounds_and_preserves_count(self):
        result = self.run_policy(4, phase=json.dumps({"phase": "construccion"}))
        self.assertEqual(0, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["review_rounds"], 4)
        self.assertEqual(report["review_fallback"], False)

    def test_live_rejects_four_rounds_but_accepts_three(self):
        live = json.dumps({"phase": "live"})
        denied = self.run_policy(4, phase=live)
        self.assertNotEqual(0, denied.returncode)
        self.assertIn("supera límite 3", denied.stderr)
        accepted = self.run_policy(3, phase=live)
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["review_rounds"], 3)

    def test_missing_invalid_or_unreadable_phase_never_allows_four_rounds(self):
        cases = (
            ("absent-arg", {}),
            ("missing-file", {"absent_file": True}),
            ("unknown", {"phase": json.dumps({"phase": "unknown"})}),
            ("malformed", {"phase": "{"}),
        )
        for name, options in cases:
            with self.subTest(name=name):
                denied = self.run_policy(4, **options)
                self.assertNotEqual(0, denied.returncode)
                self.assertTrue(denied.stderr.startswith("ERROR:"), denied.stderr)


if __name__ == "__main__":
    unittest.main()
