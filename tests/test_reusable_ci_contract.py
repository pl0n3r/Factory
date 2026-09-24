import re,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]; C=(R/".github/workflows/ci.yml").read_text(); L=(R/".github/workflows/factory-ci.yml").read_text(); S=(R/".github/workflows/reusable-selftest.yml").read_text(); P=r"^\s*(?:-\s*)?uses:\s*([^\s]+)"
class T(unittest.TestCase):
 def test_topology(self):
  self.assertIn("workflow_call:",C); self.assertNotIn("pull_request:",C); self.assertIn("pull_request:",L); self.assertIn("uses: ./.github/workflows/ci.yml",S)
 def test_installs(self):
  self.assertIn("operation: composer-install",C); self.assertIn("operation: npm-ci",C); self.assertNotIn("php_test_command",C)
 def test_pins(self):
  for text in (C,L):
   for a in re.findall(P,text,re.M):
    if not a.startswith("./"): self.assertRegex(a,r"@[0-9a-f]{40}$")
