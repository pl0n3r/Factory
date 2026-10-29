#!/usr/bin/env python3
"""Factory #1814: pruebas conductuales del Knowledge Operations existente.

Los límites documentales y referencias a otros Issues se clasifican C, no
se convierten en falsos tests. Esta hoja usa fixtures sintéticos, sin I/O.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import runpy
import unittest

from evolution.knowledge_lifecycle import validate_knowledge_record
from knowledge.contract import (
    KnowledgeContractError, knowledge_item_status, validate_knowledge_item,
)
from knowledge.postmortem import (
    KnowledgePostmortemError, guardrail_lesson_input, validate_postmortem,
)
from knowledge.selection import KnowledgeSelectionError, select_knowledge_for_context
from lecciones.memoria import validate_lesson

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T00:00:00Z"

# Reutiliza los fixtures canónicos de pruebas, no los resultados de esas pruebas.
CONTRACT = runpy.run_path(str(ROOT / "tests/test_knowledge_contract.py"))
POSTMORTEM = runpy.run_path(str(ROOT / "tests/test_knowledge_postmortem.py"))
SELECTION = runpy.run_path(str(ROOT / "tests/test_knowledge_selection.py"))


class CoberturaFactory23Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """Trece unidades offline: ejecutar módulos de lifecycle/postmortem/selection."""
        # knowledge-operations L9-U1: Lifecycle valida provenance, scope,
        # timestamps, review/expiry, evidencia, estado e historial.
        original = CONTRACT["item"]()
        immutable = deepcopy(original)
        lifecycle = validate_knowledge_record(original["lifecycle"])
        self.assertEqual(["pl0n3r/Factory#307", "pl0n3r/Factory#319"],
                         lifecycle["provenance"])
        self.assertEqual({"project": "pl0n3r/Factory", "domain": "knowledge-operations"},
                         lifecycle["scope"])
        self.assertEqual("verified", lifecycle["evidence_class"])
        self.assertEqual("active", lifecycle["state"])
        self.assertEqual({"review_after_days": 30, "expires_after_days": 90},
                         lifecycle["review_policy"])
        self.assertIsInstance(lifecycle["history"], list)

        # knowledge-operations L67-U1: validar y consultar NO muta Lifecycle.
        valid = validate_knowledge_item(original)
        state = knowledge_item_status(original, now_at=NOW)
        self.assertEqual(immutable, original)
        self.assertEqual(immutable["lifecycle"], valid["lifecycle"])
        self.assertEqual("active", state["state"])
        self.assertTrue(state["current"])

        # knowledge-operations L68-U1: la clase de autoridad solo es metadata.
        # Una referencia privilegiada nunca confiere autorización de ejecución.
        privileged = CONTRACT["item"](authority_class="legal")
        privileged_status = knowledge_item_status(privileged, now_at=NOW)
        self.assertEqual("unchanged", privileged_status["authority"])
        self.assertEqual("legal", valid["authority_class"]
                         if valid["authority_class"] == "legal" else
                         validate_knowledge_item(privileged)["authority_class"])

        # postmortem L9-U1: causa conocida exige resumen, evidencia y prevención.
        known = POSTMORTEM["postmortem"]()
        known_out = validate_postmortem(known)
        self.assertEqual("known", known_out["root_cause"]["status"])
        self.assertTrue(known_out["root_cause"]["summary"])
        self.assertEqual(["run:36500000000"], known_out["root_cause"]["evidence_refs"])
        self.assertTrue(known_out["guardrail_prevention"])

        # postmortem L10-U1/U2/U3: unknown preservado, sin resumen ni causa inferida.
        unknown = POSTMORTEM["postmortem"](False)
        unknown_out = validate_postmortem(unknown)
        self.assertEqual("unknown", unknown_out["root_cause"]["status"])
        self.assertIsNone(unknown_out["root_cause"]["summary"])
        self.assertEqual([], unknown_out["root_cause"]["evidence_refs"])
        self.assertIsNone(unknown_out["guardrail_prevention"])
        self.assertIsNone(guardrail_lesson_input(unknown))

        # postmortem L12-U1: la validación no ejecuta acciones ni genera backlog.
        for out in (known_out, unknown_out):
            self.assertEqual("unchanged", out["authority"])
            self.assertIs(out["execute_actions"], False)
            self.assertIs(out["emit_work_items"], False)

        # postmortem L16-U1: solamente causa conocida produce una lección
        # comprobada por el validador real lecciones.memoria.validate_lesson.
        lesson = guardrail_lesson_input(known)
        self.assertIsNotNone(lesson)
        self.assertEqual("incident", lesson["kind"])
        self.assertEqual("pl0n3r/Factory", lesson["project"])
        self.assertEqual("pl0n3r/Factory#320", lesson["source"])
        self.assertEqual(lesson["id"], validate_lesson(lesson, "fixture-1814")["id"])

        # selection L5-U1: contrato validado y freshness única desde Lifecycle.
        current = SELECTION["knowledge_item"]("runbook-current")
        self.assertEqual(current["item_id"], validate_knowledge_item(current)["item_id"])
        status = knowledge_item_status(current, now_at=NOW)
        self.assertEqual("knowledge-lifecycle-v1", status["source"])
        self.assertTrue(status["current"])

        # selection L7-U1: solamente un item current, scoped, apto llega a contexto.
        stale = SELECTION["knowledge_item"](
            "runbook-stale", last_validated_at="2026-07-01T00:00:00Z"
        )
        selected = select_knowledge_for_context(
            mission=SELECTION["mission"](), knowledge_items=[stale, current]
        )
        self.assertEqual(1, selected["selected_count"])
        self.assertEqual(["runbook-current"],
                         [item["item_id"] for item in selected["bindings"]])
        self.assertEqual({"category", "source", "text", "tags"},
                         set(selected["context_items"][0]))
        self.assertEqual("unchanged", selected["bindings"][0]["authority"])
        self.assertEqual(current["lifecycle"]["provenance"],
                         selected["bindings"][0]["provenance"])

        # selection L7-U2: require_current=True no convierte vacío en aprobado.
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(
                mission=SELECTION["mission"](), knowledge_items=[stale]
            )

    def test_falla_cerrado(self) -> None:
        """Missing, ambigüedad, PII, alcance y metadata privilegiada."""
        # knowledge-operations L9/L67: source y scope incompletos no validan.
        missing = CONTRACT["item"]()
        missing["lifecycle"]["provenance"] = []
        with self.assertRaises(KnowledgeContractError):
            validate_knowledge_item(missing)
        mismatch = CONTRACT["item"]()
        mismatch["item_id"] = "wrong-id"
        with self.assertRaises(KnowledgeContractError):
            validate_knowledge_item(mismatch)

        # postmortem L9/L10: ni causas conocidas sin pruebas ni unknown falsos.
        bad_known = POSTMORTEM["postmortem"]()
        bad_known["root_cause"]["evidence_refs"] = []
        with self.assertRaises(KnowledgePostmortemError):
            validate_postmortem(bad_known)
        for patch in (
            {"summary": "Invented explanation."},
            {"evidence_refs": ["run:36500000000"]},
        ):
            candidate = POSTMORTEM["postmortem"](False)
            candidate["root_cause"].update(patch)
            with self.subTest(patch=patch):
                with self.assertRaises(KnowledgePostmortemError):
                    validate_postmortem(candidate)

        # postmortem L11-U1: contenido libre muy largo o sensible es rechazado.
        for fragment in ("A" * 281, "Please email agent@example.invalid"):
            candidate = POSTMORTEM["postmortem"]()
            candidate["impact"] = fragment
            with self.subTest(impact=fragment[:18]):
                with self.assertRaises(KnowledgePostmortemError):
                    validate_postmortem(candidate)

        # selection L5/L7: sin provenance, tenant ajeno o datos sensibles
        # no pasan silenciosamente a Context Compiler.
        broken = SELECTION["knowledge_item"]()
        broken["lifecycle"]["provenance"] = []
        foreign = SELECTION["knowledge_item"](project="pl0n3r/Condor")
        sensitive = SELECTION["knowledge_item"](sensitivity="personal_data")
        for candidate in (broken, foreign, sensitive):
            with self.subTest(item_id=candidate["item_id"],
                              scope=candidate["lifecycle"]["scope"]):
                with self.assertRaises(KnowledgeSelectionError):
                    select_knowledge_for_context(
                        mission=SELECTION["mission"](), knowledge_items=[candidate]
                    )
        duplicate = SELECTION["knowledge_item"]()
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(
                mission=SELECTION["mission"](),
                knowledge_items=[duplicate, deepcopy(duplicate)],
            )

    def test_sin_datos_reales(self) -> None:
        """Probar entradas sintéticas y ausencia de autoridad operativa."""
        before = POSTMORTEM["postmortem"]()
        snapshot = deepcopy(before)
        result = validate_postmortem(before)
        self.assertEqual(snapshot, before)
        self.assertIs(result["execute_actions"], False)
        self.assertIs(result["emit_work_items"], False)
        self.assertNotIn("password", result["impact"].lower())
        item = SELECTION["knowledge_item"](authority="money")
        saved = deepcopy(item)
        selected = select_knowledge_for_context(
            mission=SELECTION["mission"](), knowledge_items=[item]
        )
        self.assertEqual(saved, item)
        self.assertEqual("money", selected["bindings"][0]["authority_class"])
        self.assertEqual("unchanged", selected["bindings"][0]["authority"])
        self.assertNotIn("token", selected["context_items"][0]["text"].lower())
        for module in ("knowledge/contract.py", "knowledge/postmortem.py",
                       "knowledge/selection.py"):
            text = (ROOT / module).read_text(encoding="utf-8")
            for forbidden in ("import requests", "import socket", "import subprocess",
                              "import httpx"):
                self.assertNotIn(forbidden, text, module)

    def test_ci_gate_contract(self) -> None:
        """AC-04: el workflow real mantiene el gate Validar, nunca un self-check."""
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: Validar", workflow)
        self.assertIn("workflow_call:", workflow)
        # El estado verde exact-HEAD lo certifica Actions, no esta aserción.
        self.assertEqual("tests/test_cobertura_factory_23.py",
                         Path(__file__).relative_to(ROOT).as_posix())


if __name__ == "__main__":
    unittest.main()
