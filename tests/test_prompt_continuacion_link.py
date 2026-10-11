"""Contrato offline Factory #1203: enlace local y autoridad no ampliada."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template"
AGENTS = TEMPLATE / "AGENTES.md"
LINK = "[Prompt de continuación](docs/PROMPT-CONTINUACION.md)"


class PromptContinuacionLinkTests(unittest.TestCase):
    def _assert_valid_link(self, text: str) -> Path:
        refs = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        candidates = [r for r in refs if "PROMPT-CONTINUACION.md" in r]
        self.assertEqual(candidates, ["docs/PROMPT-CONTINUACION.md"])
        self.assertEqual(text.count(LINK), 1)
        target = (TEMPLATE / candidates[0]).resolve()
        self.assertTrue(target.is_relative_to(TEMPLATE.resolve()))
        self.assertTrue(target.is_file(), "El enlace debe resolver al documento local")
        return target

    def test_template_agents_links_versioned_prompt_without_policy_override(self) -> None:
        self.assertTrue(AGENTS.is_file())
        text = AGENTS.read_text(encoding="utf-8")
        target = self._assert_valid_link(text)
        self.assertIn("## Mensaje estándar", target.read_text(encoding="utf-8"))
        with self.assertRaises(AssertionError):
            self._assert_valid_link(text + "\n" + LINK)
        with self.assertRaises(AssertionError):
            self._assert_valid_link(text.replace(LINK, "[Prompt de continuación](docs/otra/PROMPT-CONTINUACION.md)"))

    def test_prompt_link_is_advisory_not_authority(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        self._assert_valid_link(text)
        self.assertEqual(text.count("### Mensaje de continuación (guía opcional)"), 1)
        section = text.split("### Mensaje de continuación (guía opcional)", 1)[1].split(
            "## Principios de construcción de la fábrica", 1
        )[0]
        for phrase in ("guía opcional", "No habilita envíos automáticos",
                       "reserva V3", "CI exact-SHA", "D-069",
                       "datos reales", "releases", "live", "PLAN-AGENTES.md"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)
        for existing_guard in (
            "Principio 5 — autonomía de construcción, no autoridad de producción",
            "En fase `live` no se fusiona automáticamente.",
            "no activa el orquestador",
        ):
            with self.subTest(existing_guard=existing_guard):
                self.assertIn(existing_guard, text)


if __name__ == "__main__":
    unittest.main()
