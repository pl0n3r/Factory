"""Contrato AC-01 del mensaje de continuación de Factory #1196 (offline)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "template" / "docs" / "PROMPT-CONTINUACION.md"
SECRET_PREFIX_RE = re.compile(r"(?i)\b(?:gh[pousr]_|github_pat_|sk-[A-Za-z0-9]{8})")


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
        self.assertNotRegex(text, SECRET_PREFIX_RE)
        self.assertNotRegex(text, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

    def test_privacy_guard_rejects_synthetic_token_prefixes(self) -> None:
        # Fixtures sintéticos: comprueban el detector, nunca contienen secretos reales.
        synthetic = (
            "ghp_TESTFIXTURE", "gho_TESTFIXTURE", "ghu_TESTFIXTURE",
            "ghs_TESTFIXTURE", "ghr_TESTFIXTURE", "github_pat_TESTFIXTURE",
            "sk-TESTFIXTURE123",
        )
        for candidate in synthetic:
            with self.subTest(token_prefix=candidate.split("_")[0]):
                self.assertRegex(candidate, SECRET_PREFIX_RE)

    @staticmethod
    def _copyable_messages(text: str) -> tuple[str, str]:
        sections = (
            text.split("## Mensaje estándar", 1)[1].split(
                "## Variante breve QA/seguridad", 1
            )[0],
            text.split("## Variante breve QA/seguridad", 1)[1].split(
                "## Cuándo usarlo", 1
            )[0],
        )
        blocks = []
        for section in sections:
            matches = re.findall(r"(?ms)^~~~text\n(.*?)\n~~~\s*$", section)
            if len(matches) != 1:
                raise AssertionError("Cada variante debe tener un solo bloque copiable")
            blocks.append(matches[0])
        return blocks[0], blocks[1]

    def _assert_copyable_global_pause(self, text: str) -> None:
        for role, prompt in zip(
            ("estándar", "QA/seguridad"), self._copyable_messages(text)
        ):
            for required in (
                "Factory #767", "RUNNING", "PAUSED", "UNKNOWN",
                "detén el turno", "no tomes otro Issue", "no mutas",
                "reserva V3", "CI exact-SHA", "bloqueo local",
            ):
                self.assertIn(required, prompt, f"{role}: falta {required}")

    def test_copyable_prompts_require_global_pause_preflight(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        self._assert_copyable_global_pause(text)

    def test_pause_gate_must_be_inside_each_copyable_block(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        self._assert_copyable_global_pause(text)
        for prompt in self._copyable_messages(text):
            # Una advertencia en la prosa de fuera no satisface el bloque copiable.
            without_gate = text.replace(
                prompt, "Continúa y elige otro frente disponible.", 1
            )
            with self.assertRaises(AssertionError):
                self._assert_copyable_global_pause(without_gate)

    def test_scope_and_operational_gates_remain_explicit(self) -> None:
        text = DOCUMENT.read_text(encoding="utf-8")
        for concept in ("reserva V3", "CI exact-SHA", "interruptor global",
                        "pausa manual", "presupuesto horario", "sin adjuntar mensajes privados"):
            with self.subTest(concept=concept):
                self.assertIn(concept, text)


if __name__ == "__main__":
    unittest.main()
