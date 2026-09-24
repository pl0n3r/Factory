import unittest
from scripts.ci_retry import operation_command,transient
class T(unittest.TestCase):
 def test_closed_operations(self):
  self.assertEqual(operation_command("npm-ci")[0],"npm")
  with self.assertRaises(ValueError): operation_command("bash")
 def test_transient(self):
  self.assertTrue(transient(1,"HTTP 503")); self.assertFalse(transient(1,"certificate verify failed"))
