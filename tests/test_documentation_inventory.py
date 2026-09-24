"""Contrato ejecutable del inventario técnico de datos por producto."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "inventario-tecnico-datos-productos.md"


class DocumentationInventoryTests(unittest.TestCase):
    """Verifica contenido y separación por producto del inventario técnico."""

    @classmethod
    def setUpClass(cls):
        """Carga una sola vez el documento auditado."""
        cls.text = DOC.read_text(encoding="utf-8")

    def product_section(self, heading, next_heading):
        """Devuelve únicamente el bloque comprendido entre dos headings."""
        start_marker = f"## {heading}"
        end_marker = f"## {next_heading}"
        self.assertIn(start_marker, self.text)
        self.assertIn(end_marker, self.text)
        return self.text.split(start_marker, 1)[1].split(end_marker, 1)[0]

    def test_audited_shas(self):
        """AC-01: asocia cada producto con su SHA exacto auditado."""
        snapshot = self.text.split("## Snapshot auditado", 1)[1].split(
            "## Cómo leer este mapa",
            1,
        )[0]
        expected = {
            "Condor": "02be616b1bb8f33f7da601a0cca33e5c0e4dcc79",
            "GrindFlow": "8c59ea017b5cb8f90985cf9aae8e32d59f93c65c",
            "BRVTAL": "138b1babac0ff6797ad9e0f3ccb0fbda0f793452",
        }
        for product, sha in expected.items():
            self.assertIn(f"- {product}: `{sha}`", snapshot)

    def test_condor_inventory(self):
        """AC-02: los términos de Condor viven dentro de su sección."""
        section = self.product_section("Condor", "GrindFlow")
        for value in (
            "Customer.notes",
            "NotificationDelivery",
            "Auditoría",
            "Observabilidad y diagnóstico",
            "NullTransactionalEmailGateway",
            "### Preguntas materiales pendientes",
        ):
            self.assertIn(value, section)

    def test_grindflow_inventory(self):
        """AC-03: los términos de GrindFlow viven dentro de su sección."""
        section = self.product_section("GrindFlow", "BRVTAL")
        for value in (
            "Google Drive",
            "Dropbox",
            "Supabase",
            "visitor_hash",
            "24 horas",
            "Media vault",
            "### Preguntas materiales pendientes",
        ):
            self.assertIn(value, section)

    def test_brvtal_inventory(self):
        """AC-04: los términos de BRVTAL viven dentro de su sección."""
        section = self.product_section("BRVTAL", "Matriz de terceros identificados")
        for value in (
            "TOTP",
            "Contacto público",
            "Google Tag Manager",
            "analytics_storage",
            "30 días",
            "15 minutos",
            "### Preguntas materiales pendientes",
        ):
            self.assertIn(value, section)

    def test_material_questions(self):
        """AC-05: exige preguntas por producto y una lista transversal."""
        self.assertGreaterEqual(
            self.text.count("### Preguntas materiales pendientes"),
            3,
        )
        self.assertIn(
            "## Preguntas materiales pendientes transversales",
            self.text,
        )

    def test_legal_boundary(self):
        """AC-06: preserva la frontera entre evidencia y aprobación legal."""
        self.assertIn("no es aprobación jurídica", self.text)
        self.assertIn("no cierra #12", self.text)


if __name__ == "__main__":
    unittest.main()
