"""Regresiones del informe A8: referencias de revisión e inventario auditable."""
from pathlib import Path
import unittest


DOCUMENTO = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "auditoria-autonomia"
    / "11-epicas-sin-partir.md"
)


class AutonomiaDocsReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.informe = DOCUMENTO.read_text(encoding="utf-8")

    def test_factory_pr_reference_and_api_scope(self):
        self.assertIn("HEAD exacto del PR Factory #2142", self.informe)
        self.assertNotIn("PR Factory #2140", self.informe)
        self.assertIn("Uso de APIs de producto/proveedor", self.informe)
        self.assertIn("no se utilizaron APIs de producto/proveedor", self.informe)
        self.assertIn("sí se utilizó la API de GitHub", self.informe)
        self.assertIn("para crear y consultar Issues", self.informe)

    def test_grindflow_inventory_auditable(self):
        self.assertIn("### Inventario auditable del roadmap GrindFlow #2", self.informe)
        self.assertIn("https://github.com/pl0n3r/GrindFlow/issues/2", self.informe)
        self.assertIn(
            "https://github.com/pl0n3r/GrindFlow/issues?q=is%3Aissue+is%3Aclosed",
            self.informe,
        )
        self.assertIn(
            "https://github.com/pl0n3r/GrindFlow/issues?q=is%3Aissue+is%3Aopen",
            self.informe,
        )
        self.assertIn("no constituyen una lista exclusiva de descendientes de #2", self.informe)
        self.assertIn("no se puede demostrar completitud del árbol", self.informe)
        self.assertIn("**Entregas comprobadas:**", self.informe)
        self.assertIn("**Pendientes comprobados:**", self.informe)
        for numero in (260, 270, 271, 1020, 1021, 1022):
            self.assertIn(
                f"https://github.com/pl0n3r/GrindFlow/issues/{numero}",
                self.informe,
            )
        self.assertIn("no declarados hijos directos de #2", self.informe)
        self.assertIn("no una enumeración completa del roadmap", self.informe)
        self.assertIn("**Regla antduplicación:**", self.informe)
        self.assertIn("ni CI verde acreditan despliegue", self.informe)


if __name__ == "__main__":
    unittest.main()
