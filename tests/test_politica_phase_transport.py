"""Contract test: transport of datos.yml from exact BASE into reusable Policy.

A fake gh CLI exercises the real shell block of politica.yml without network.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/politica.yml"
BASE_SHA = "a" * 40


class PhaseTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")
        anchor = "          phase_args=()\n"
        terminator = "          HEAD_COMMIT_JSON="
        if cls.source.count(anchor) != 1:
            raise AssertionError("El transporte de fase no tiene un único comienzo")
        beginning = cls.source.index(anchor)
        ending = cls.source.index(terminator, beginning)
        cls.transport = cls.source[beginning:ending]
        if shutil.which("jq") is None:
            raise RuntimeError("jq es obligatorio para ejecutar el caller Policy")

    def exercise(self, mode):
        with tempfile.TemporaryDirectory() as temp:
            tool = Path(temp) / "gh"
            tool.write_text(textwrap.dedent("""\
                #!/usr/bin/env python3
                import os
                import sys

                expected = "repos/pl0n3r/Factory/contents/datos.yml?ref=" + "a" * 40
                if not sys.argv or sys.argv[-1] != expected:
                    print("gh: unexpected URL", file=sys.stderr)
                    sys.exit(42)
                mode = os.environ["FAKE_GH_MODE"]
                if mode == "construccion":
                    print('{"phase":"construccion"}')
                elif mode == "live":
                    print('{"phase":"live"}')
                elif mode == "invalid":
                    print('{"phase":"production"}')
                elif mode == "malformed":
                    print("{bad json")
                elif mode == "large":
                    print("x" * (524288 + 1))
                elif mode.startswith("http"):
                    code = mode[4:]
                    print(f"gh: simulated upstream rejection (HTTP {code})", file=sys.stderr)
                    sys.exit(1)
                else:
                    print("unexpected fixture", file=sys.stderr)
                    sys.exit(43)
            """), encoding="utf-8")
            tool.chmod(0o755)
            script = (
                "set -euo pipefail\n"
                "REPOSITORY=pl0n3r/Factory\n"
                "PR_BASE_SHA=" + BASE_SHA + "\n"
                'phase_file="$(mktemp)"\n'
                'phase_err="$(mktemp)"\n'
                'trap \'rm -f "$phase_file" "$phase_err"\' EXIT\n'
                + self.transport
                + "\nprintf 'ARR='; declare -p phase_args\n"
            )
            env = {
                **os.environ,
                "FAKE_GH_MODE": mode,
                "PATH": temp + os.pathsep + os.environ.get("PATH", ""),
            }
            return subprocess.run(
                ["bash", "-c", script],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_valid_phase_is_passed_from_exact_base(self):
        for phase in ("construccion", "live"):
            with self.subTest(phase=phase):
                result = self.exercise(phase)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--phase-file", result.stdout)
                self.assertIn("ARR=declare -a phase_args=(", result.stdout)

    def test_existing_invalid_or_oversized_phase_fails_closed(self):
        for mode in ("invalid", "malformed", "large"):
            with self.subTest(mode=mode):
                result = self.exercise(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::datos.yml BASE es inválido", result.stderr)
                self.assertNotIn("ARR=", result.stdout)

    def test_missing_404_stays_legacy_strict_but_other_transport_errors_fail(self):
        missing = self.exercise("http404")
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertIn("ARR=declare -a phase_args=()", missing.stdout)
        self.assertIn("fase desconocida, política estricta", missing.stdout)
        for mode in ("http403", "http429", "http500"):
            with self.subTest(mode=mode):
                denied = self.exercise(mode)
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn("No se pudo verificar datos.yml", denied.stderr)
                self.assertNotIn("ARR=", denied.stdout)


if __name__ == "__main__":
    unittest.main()
