import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "inventario-tecnico-datos-productos.md"


class DocumentationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DOC.read_text(encoding="utf-8")

    def test_audited_shas(self):
        for sha in (
            "02be616b1bb8f33f7da601a0cca33e5c0e4dcc79",
            "8c59ea017b5cb8f90985cf9aae8e32d59f93c65c",
            "138b1babac0ff6797ad9e0f3ccb0fbda0f793452",
        ):
            self.assertIn(sha, self.text)

    def test_condor_inventory(self):
        for value in (
            "## Condor",
            "Customer.notes",
            "NotificationDelivery",
            "Auditoría",
            "Observabilidad y diagnóstico",
            "NullTransactionalEmailGateway",
        ):
            self.assertIn(value, self.text)

    def test_grindflow_inventory(self):
        for value in (
            "## GrindFlow",
            "Google Drive",
            "Dropbox",
            "Supabase",
            "visitor_hash",
            "24 horas",
            "Media vault",
        ):
            self.assertIn(value, self.text)

    def test_brvtal_inventory(self):
        for value in (
            "## BRVTAL",
            "TOTP",
            "Contacto público",
            "Google Tag Manager",
            "analytics_storage",
            "30 días",
            "15 minutos",
        ):
            self.assertIn(value, self.text)

    def test_material_questions(self):
        self.assertGreaterEqual(
            self.text.count("### Preguntas materiales pendientes"),
            3,
        )
        self.assertIn(
            "## Preguntas materiales pendientes transversales",
            self.text,
        )

    def test_legal_boundary(self):
        self.assertIn("no es aprobación jurídica", self.text)
        self.assertIn("no cierra #12", self.text)


if __name__ == "__main__":
    unittest.main()
