"""Regresiones offline para los principios de construcción del template Factory #1103."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template" / "AGENTES.md"


def _section(text: str, heading: str) -> str:
    return text.split(f"### {heading} — ", 1)[1].split("\n### ", 1)[0].lower()


class TemplatePrincipiosConstruccionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = TEMPLATE.read_text(encoding="utf-8")

    def test_preserves_core_and_local_customization(self):
        self.assertTrue(self.doc.startswith(
            "# AGENTES.md\n\nEste proyecto consume el núcleo operativo de Factory v1:\n\n"
            "https://github.com/pl0n3r/factory/blob/v1/agentes/NUCLEO.md\n\n"
            "## Capa local\n\n"))
        self.assertEqual(self.doc.count("## Capa local"), 1)
        for required in (
            "- Stack inicial: PHP plano.",
            "- Fuente de versión: `config/version.json`.",
            "- Fase inicial: `construccion`.",
            "- Idioma de etiquetas: español.",
            "- Añade aquí solo reglas técnicas o de producto propias de este proyecto; no copies el núcleo.",
            "## Principios de construcción de la fábrica",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.doc)

    def test_eight_principles_and_safe_parallelism(self):
        headings = re.findall(r"^### (Regla 0|Principio [1-8]) — ", self.doc, re.M)
        self.assertEqual(headings, ["Regla 0"] + [f"Principio {n}" for n in range(1, 9)])
        markers = {
            "Regla 0": ("paralelismo", "reservas v3", "sha", "claims"),
            "Principio 1": ("siete repositorios", "disponible", "requiere recuperación", "no_work"),
            "Principio 2": ("build-ahead", "fakes", "reversión"),
            "Principio 3": ("readme.md", "config/version.php", "package-lock.json", "fallar cerrado"),
            "Principio 4": ("planificado", "bloqueado", "unknown", "validated_in_production"),
            "Principio 5": ("construccion", "go-live", "gasto", "datos reales"),
            "Principio 6": ("[ac-nn]", "factory-acceptance", "factory-plan-task", "uuid v3"),
            "Principio 7": ("rate_limit", "20 %", "polling", "compartido"),
            "Principio 8": ("main", "prs", "approved", "fail-closed"),
        }
        for heading, phrases in markers.items():
            section = _section(self.doc, heading)
            for phrase in phrases:
                with self.subTest(heading=heading, phrase=phrase):
                    self.assertIn(phrase, section)

    def test_human_gates_and_no_fake_propagation(self):
        intro = self.doc.split("### Regla 0", 1)[0].lower()
        footer = self.doc.split("### Límite explícito del template", 1)[1].lower()
        self.assertIn("no otorga permisos de ejecución", intro)
        self.assertIn("no sincroniza ni modifica consumidores", footer)
        self.assertIn("no constituye aprobación humana o revisión independiente", footer)
        for gate in ("go-live", "gasto", "credenciales", "datos reales",
                     "borrados irreversibles", "privacidad", "ci",
                     "revisión independiente", "protección de rama"):
            with self.subTest(gate=gate):
                self.assertIn(gate, self.doc.lower())
        self.assertIn("no autoriza merges, activación, go-live ni publicación automática",
                      _section(self.doc, "Principio 5"))
        self.assertIn("unknown y fail-closed", _section(self.doc, "Principio 8"))


if __name__ == "__main__":
    unittest.main()
