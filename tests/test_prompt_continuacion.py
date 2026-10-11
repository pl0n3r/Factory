"""Contrato AC-01 del mensaje de continuación de Factory #1196 (offline)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "template" / "docs" / "PROMPT-CONTINUACION.md"


class PromptContinuacionTests(unittest.TestCase):
    def test_standard_and_qa_continuation_contract(self) -> None:
        self.assertTrue(DOCUMENT.is_file(), "Falta el documento del template")
        text = DOCUMENT.read_text(encoding="utf-8")

        self.assertIn("## Mensaje estándar", text)
        self.assertIn("## Variante breve QA/seguridad", text)
        self.assertIn("## Cómo configurarlo en AutoFactory", text)
        self.assertIn("## Privacidad y límites", text)
        self.assertIn("prompt personalizado", text)
        self.assertIn("contenido de chats", text)
        self.assertIn("tokens", text)

        standard = text.split("## Mensaje estándar", 1)[1].split(
            "## Variante breve QA/seguridad", 1
        )[0]
        steps = re.findall(r"(?m)^\(([1-5])\)\s+(.+)$", standard)
        self.assertEqual([str(n) for n in range(1, 6)], [n for n, _ in steps])
        for step, phrase in zip(
            (line for _, line in steps),
            ("relee el estado", "si no tienes reserva", "implementa, prueba",
             "fusiónalo (squash)", "pasa de inmediato"),
        ):
            self.assertIn(phrase, step)
        self.assertIn("comenta solo hitos", standard)
        self.assertIn("bloqueado de verdad", standard)

        qa = text.split("## Variante breve QA/seguridad", 1)[1].split(
            "## Cuándo usarlo", 1
        )[0]
        self.assertIn("relee el issue y el PR", qa)
        self.assertIn("regresión concreta", qa)
        self.assertIn("reserva ajena", qa)

        self.assertNotIn("NO MERGE", text)
        self.assertNotRegex(text, r"(?i)\b(?:ghp_|github_pat_|sk-[A-Za-z0-9]{8})")
        self.assertNotRegex(text, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def test_scope_and_operational_gates_remain_explicit(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        for concept in ("reserva V3", "CI exact-SHA", "interruptor global",
                        "pausa manual", "presupuesto horario", "sin adjuntar mensajes privados"):
            with self.subTest(concept=concept):
                self.assertIn(concept, text)


if __name__ == "__main__":
    unittest.main()
