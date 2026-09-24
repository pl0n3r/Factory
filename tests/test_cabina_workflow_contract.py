import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/cabina.yml").read_text(encoding="utf-8")


class CabinaWorkflowContractTests(unittest.TestCase):
    def test_pages_permissions_are_job_scoped_and_actions_pinned(self):
        self.assertIn("permissions:\n  contents: read", WORKFLOW)
        self.assertIn("permissions:\n      pages: write\n      id-token: write", WORKFLOW)
        self.assertIn("schedule:", WORKFLOW)
        self.assertIn("cron: '7 * * * *'", WORKFLOW)
        uses = re.findall(r"uses:\s+([^\s]+)", WORKFLOW)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
