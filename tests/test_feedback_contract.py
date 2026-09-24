import subprocess
import sys
import unittest
from pathlib import Path


class FeedbackContractTests(unittest.TestCase):
    def test_producto_feedback_suite_is_part_of_required_ci(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(root / "producto"),
                "-p",
                "test_feedback.py",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=result.stdout + "\n" + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
