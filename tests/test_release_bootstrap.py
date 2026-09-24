"""Regresiones para el bootstrap inicial del tag mayor v1."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
TEMPLATE_RELEASE = ROOT / "template" / ".github" / "workflows" / "release.yml"
GUIDE = ROOT / "docs" / "release-bootstrap.md"


class ReleaseBootstrapTests(unittest.TestCase):
    """Preserva la frontera de seguridad del primer release."""

    @classmethod
    def setUpClass(cls):
        """Carga los artefactos de release una sola vez."""
        cls.release = RELEASE.read_text(encoding="utf-8")
        cls.template_release = TEMPLATE_RELEASE.read_text(encoding="utf-8")
        cls.guide = GUIDE.read_text(encoding="utf-8")

    def test_write_release_stays_on_published_v1(self):
        """AC-01: release ejecuta únicamente el kit publicado v1."""
        self.assertIn("repository: pl0n3r/factory", self.release)
        self.assertIn("ref: v1", self.release)
        self.assertNotIn("inputs.kit_ref", self.release)

    def test_release_api_has_no_dynamic_kit_ref(self):
        """AC-02: workflow_call no ofrece una referencia dinámica del kit."""
        workflow_call = self.release.split("outputs:", 1)[0]
        self.assertNotIn("kit_ref:", workflow_call)

    def test_bootstrap_guide_requires_human_gate(self):
        """AC-03: la guía falla cerrado ante gates humanos pendientes."""
        for required in (
            "#1–#14 cerrados",
            "release-1.0.0",
            "default seguro es **no publicar**",
            "SHA exacto aprobado",
            "Crear manualmente el tag mayor",
            "no crea ningún tag automáticamente",
        ):
            self.assertIn(required, self.guide)

    def test_template_release_stays_on_v1(self):
        """AC-04: el template continúa consumiendo el canal mayor v1."""
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/release.yml@v1",
            self.template_release,
        )


if __name__ == "__main__":
    unittest.main()
