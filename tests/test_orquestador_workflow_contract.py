import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github/workflows/orquestador.yml").read_text(encoding="utf-8")


class OrchestratorWorkflowContractTests(unittest.TestCase):
    def test_trusted_plan_command_and_permissions(self):
        self.assertIn("github.event.comment.body == '/planificar'", WF)
        for association in ("OWNER", "MEMBER", "COLLABORATOR"):
            self.assertIn(association, WF)
        self.assertIn("contents: read", WF)
        self.assertIn("issues: write", WF)
        self.assertNotIn("contents: write", WF)

    def test_uses_default_branch_and_pinned_checkout(self):
        self.assertIn("github.event.repository.default_branch", WF)
        self.assertRegex(
            WF,
            r"uses: actions/checkout@[0-9a-f]{40}",
        )
        self.assertIn("concurrency:", WF)


if __name__ == "__main__":
    unittest.main()
