"""Contrato de copia exacta de mensajes AutoFactory en Factory README (#1208)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TEMPLATE = ROOT / "template" / "docs" / "PROMPT-CONTINUACION.md"


class ReadmeContinuacionTests(unittest.TestCase):
    @staticmethod
    def _block(section: str) -> str:
        blocks = re.findall(r"(?ms)^~~~text\n(.*?)\n~~~[ \t]*$", section)
        if len(blocks) != 1:
            raise AssertionError("El template debe tener un bloque por variante")
        return blocks[0]

    def test_readme_copy_matches_canonical_template(self):
        source = TEMPLATE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        standard = self._block(source.split("## Mensaje estándar", 1)[1]
                               .split("## Variante breve QA/seguridad", 1)[0])
        qa = self._block(source.split("## Variante breve QA/seguridad", 1)[1]
                         .split("## Cuándo usarlo", 1)[0])
        self.assertNotEqual(standard, qa)
        for block in (standard, qa):
            for required in ("Factory #767", "reserva V3", "CI exact-SHA"):
                self.assertIn(required, block)
        self.assertIn("una unidad de trabajo completa", standard)
        self.assertIn("QA o seguridad", qa)
        self.assertIn("prompt personalizado de AutoFactory", source)
        self.assertIn("template/docs/PROMPT-CONTINUACION.md", readme)
        self.assertNotIn("### Mensaje de continuación (AutoFactory)", readme)

if __name__ == "__main__":
    unittest.main()
