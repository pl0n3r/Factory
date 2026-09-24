"""Regresiones para el bootstrap inicial del tag mayor v1."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
TEMPLATE_RELEASE = ROOT / "template" / ".github" / "workflows" / "release.yml"
GUIDE = ROOT / "docs" / "release-bootstrap.md"


class ReleaseBootstrapTests(unittest.TestCase):
    """Mantiene el primer release desacoplado de un tag v1 inexistente."""

    @classmethod
    def setUpClass(cls):
        """Carga los artefactos de release una sola vez."""
        cls.release = RELEASE.read_text(encoding="utf-8")
        cls.template_release = TEMPLATE_RELEASE.read_text(encoding="utf-8")
        cls.guide = GUIDE.read_text(encoding="utf-8")

    def test_release_checkout_uses_kit_ref(self):
        """AC-01: el checkout interno usa la referencia configurable."""
        self.assertIn("ref: ${{ inputs.kit_ref }}", self.release)
        self.assertNotRegex(
            self.release,
            r"repository:\s*pl0n3r/factory[\s\S]{0,160}?ref:\s*v1(?:\s|$)",
        )

    def test_kit_ref_default_remains_v1(self):
        """AC-02: consumidores normales conservan v1 como default."""
        self.assertRegex(
            self.release,
            r"kit_ref:\s*\n\s*required:\s*false\s*\n\s*default:\s*'v1'",
        )

    def test_bootstrap_guide_requires_human_gate(self):
        """AC-03: la guía falla cerrado ante gates humanos pendientes."""
        for required in (
            "#1–#14 cerrados",
            "release-1.0.0",
            "default seguro es **no publicar**",
            "no crea ningún tag automáticamente",
            "SHA exacto",
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
