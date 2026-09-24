import unittest
from pathlib import Path
W=(Path(__file__).resolve().parents[1]/".github/workflows/release.yml").read_text()
class T(unittest.TestCase):
 def test_outputs_are_yaml_blocks(self):
  self.assertIn("version:\n        description:",W); self.assertNotIn("version: {value:",W)
 def test_existing_tag_must_match_sha(self):
  self.assertIn('existing_sha="$(git rev-parse "refs/tags/$TAG^{commit}")"',W); self.assertIn('"$existing_sha" == "$TARGET_SHA"',W); self.assertIn("409|422",W)
