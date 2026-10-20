#!/usr/bin/env python3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import scripts.validar_template as contract
from scripts.validar_template import validate

class TemplateContractTests(unittest.TestCase):
    def test_template_contract(self):
        self.assertEqual(validate(),[])

    def test_factory_caller_case_is_normalized_without_weakening_pins(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            file = workflows / "consumidor.yml"
            with patch.object(contract, "TEMPLATE", root), patch.object(contract, "REQUIRED", []):
                file.write_text(
                    "jobs:\\n  observer:\\n    uses: pl0n3r/Factory/.github/workflows/observador-reservas-consumidor.yml@v1\\n",
                    encoding="utf-8",
                )
                self.assertEqual(contract.validate(), [])
                file.write_text(
                    "jobs:\\n  observer:\\n    uses: pl0n3r/factory/.github/workflows/observador-reservas-consumidor.yml@v1\\n",
                    encoding="utf-8",
                )
                self.assertEqual(contract.validate(), [])
                file.write_text(
                    "jobs:\\n  observer:\\n    uses: pl0n3r/Factory/.github/workflows/observador-reservas-consumidor.yml@main\\n",
                    encoding="utf-8",
                )
                self.assertTrue(any("por @v1" in error for error in contract.validate()))
                file.write_text(
                    "jobs:\\n  observer:\\n    uses: actions/checkout@v4\\n",
                    encoding="utf-8",
                )
                self.assertTrue(any("no fijada a SHA" in error for error in contract.validate()))
                file.write_text(
                    "jobs:\\n  observer:\\n    uses: actions/checkout@" + "a" * 40 + "\\n",
                    encoding="utf-8",
                )
                self.assertEqual(contract.validate(), [])


if __name__=="__main__":
    unittest.main()
