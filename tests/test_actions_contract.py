import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]

class T(unittest.TestCase):
    def test_retry_closed(self):
        text = (R / "actions/retry/action.yml").read_text()
        self.assertIn("operation:", text)
        self.assertNotIn("command-json", text)

    def test_comment_updates_only_own_repository_and_bot_comment(self):
        text = (R / "actions/idempotent-comment/action.yml").read_text()
        self.assertIn("github-actions[bot]", text)
        self.assertIn('repository="$GITHUB_REPOSITORY"', text)
        self.assertNotIn("INPUT_REPOSITORY", text)

    def test_version_does_not_execute_php_source(self):
        text = (R / "actions/read-version/action.yml").read_text()
        self.assertIn("read_version.py", text)
        self.assertNotIn("php -r", text)
