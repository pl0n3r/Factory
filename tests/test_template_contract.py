#!/usr/bin/env python3
import unittest
from scripts.validar_template import validate

class TemplateContractTests(unittest.TestCase):
    def test_template_contract(self):
        self.assertEqual(validate(),[])

if __name__=="__main__":
    unittest.main()
