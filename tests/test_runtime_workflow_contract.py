import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]

class T(unittest.TestCase):
    def test_deploy_has_no_arbitrary_command_inputs(self):
        text = (R / ".github/workflows/deploy.yml").read_text()
        for value in ("build_script:", "backup_script:", "deploy_script:", "rollback_script:"):
            self.assertNotIn(value, text)
        self.assertIn("live_migration_approved:", text)
        self.assertIn("workflow_dispatch|push", text)
        self.assertIn("refs/heads/$DEFAULT_BRANCH", text)

    def test_template_does_not_inherit_all_secrets(self):
        text = (R / "template/.github/workflows/deploy.yml").read_text()
        self.assertNotIn("secrets: inherit", text)
        self.assertIn("DEPLOY_TOKEN:", text)

    def test_fixed_adapter_contract(self):
        text = (R / "scripts/deploy_kit.py").read_text()
        self.assertIn('"build": Path("ops/factory/build")', text)
        self.assertNotIn("shell=True", text)
        self.assertIn("symlinks", text)

    def test_observer_requires_trusted_default_branch_context(self):
        text = (R / ".github/workflows/observar.yml").read_text()
        self.assertIn("schedule|workflow_dispatch", text)
        self.assertIn('refs/heads/$DEFAULT_BRANCH', text)
