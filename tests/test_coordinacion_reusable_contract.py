import re,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]; W=(R/".github/workflows/coordinacion.yml").read_text()
class T(unittest.TestCase):
 def test_profile_input_is_allowlisted(self):
  """El reusable acepta solo los perfiles ES/EN definidos por Factory."""
  self.assertIn("profile:",W); self.assertIn("default: 'es'",W)
  self.assertRegex(W,r'case "\$PROFILE" in es\|en\)')
  self.assertNotIn("profile_prefix",W)
 def test_pins(self):
  a=re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s]+)",W,re.M); self.assertTrue(a)
  for x in a: self.assertRegex(x,r"@[0-9a-f]{40}$")
