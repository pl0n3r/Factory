"""Contrato del template de privacidad como código."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from scripts.privacidad_kit import (
    PLACEHOLDER_TOKEN,
    PrivacyError,
    generate_documents,
    load_rules,
    validate_data_map,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
PRIVACY_DOCS = TEMPLATE / "docs" / "privacidad"


def template_data():
    return json.loads((TEMPLATE / "datos.yml").read_text(encoding="utf-8"))


class TemplatePrivacyTests(unittest.TestCase):
    def test_template_data_map_is_valid(self):
        validated = validate_data_map(template_data(), load_rules())
        self.assertEqual(validated["project"], "example/project")
        self.assertEqual(validated["phase"], "construccion")
        self.assertEqual(validated["treatments"], [])
        self.assertEqual(
            set(validated["controller"].values()),
            {PLACEHOLDER_TOKEN},
        )

    def test_template_workflows_use_factory_with_minimum_permissions(self):
        privacy = (
            TEMPLATE / ".github" / "workflows" / "privacidad.yml"
        ).read_text(encoding="utf-8")
        audit = (
            TEMPLATE / ".github" / "workflows" / "auditoria-privacidad.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/privacidad.yml@v1",
            privacy,
        )
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/auditoria-privacidad.yml@v1",
            audit,
        )
        self.assertIn("permissions:\n  contents: read", privacy)
        self.assertNotIn("issues: write", privacy)
        self.assertIn("permissions:\n  contents: read\n  issues: write", audit)
        self.assertNotIn("contents: write", privacy)
        self.assertNotIn("contents: write", audit)
        self.assertNotIn("secrets:", privacy)
        self.assertNotIn("secrets:", audit)

    def test_template_documents_match_generator(self):
        generated = generate_documents(load_rules(), template_data())
        observed = {
            name: (PRIVACY_DOCS / name).read_text(encoding="utf-8")
            for name in generated
        }
        self.assertEqual(observed, generated)

    def test_template_keeps_owner_placeholders_until_go_live(self):
        data = template_data()
        generated = generate_documents(load_rules(), data)
        self.assertEqual(
            set(data["controller"].values()),
            {PLACEHOLDER_TOKEN},
        )
        self.assertIn(
            PLACEHOLDER_TOKEN,
            generated["politica-tratamiento.md"],
        )

        live = deepcopy(data)
        live["phase"] = "live"
        with self.assertRaisesRegex(PrivacyError, "go-live"):
            validate_data_map(live, load_rules())


if __name__ == "__main__":
    unittest.main()
