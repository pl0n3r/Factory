#!/usr/bin/env python3
"""Factory #1813: contrastes ejecutables Knowledge Operations, sin mundo real.

17 unidades verifican el comportamiento de código existente con fixtures
sintéticos; tres límites normativos C quedan clasificados en el PR, no en tests.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import runpy
import socket
import subprocess
import unittest

from evolution.experience_guardrails import compile_guardrail_candidates
from evolution.knowledge_lifecycle import (
    effective_state, propose_pruning_candidates, validate_knowledge_record,
)
from intelligence.context_compiler import compile_mission_context
from intelligence.project_dna import discover_project_dna
from knowledge.contract import (
    KnowledgeContractError, knowledge_item_status, validate_knowledge_item,
)
from knowledge.postmortem import (
    KnowledgePostmortemError, guardrail_lesson_input, validate_postmortem,
)
from knowledge.selection import KnowledgeSelectionError, select_knowledge_for_context

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T00:00:00Z"
CONTRACT = runpy.run_path(str(ROOT / "tests/test_knowledge_contract.py"))
SELECTION = runpy.run_path(str(ROOT / "tests/test_knowledge_selection.py"))
E2E = runpy.run_path(str(ROOT / "tests/test_knowledge_operations_e2e.py"))
D = "docs/knowledge-operations.md:"
E = "docs/knowledge-operations-e2e.md:"
A = (
    E + "L7-U1", E + "L9-U1", E + "L18-U1",
    D + "L11-U1", D + "L13-U1", D + "L20-U1", D + "L21-U1",
    D + "L22-U1", D + "L23-U1", D + "L25-U1", D + "L26-U1",
    D + "L27-U1", D + "L35-U1", D + "L42-U1", D + "L45-U1",
    D + "L56-U1", D + "L58-U1",
)
C = {
    E + "L20-U1": "README es una portada derivada, no contrato de runtime.",
    D + "L63-U1": "Ausencia de I/O/store es un limite arquitectonico.",
    D + "L64-U1": "Ausencia de busqueda vectorial es un limite arquitectonico.",
}


def _rows(text):
    if not isinstance(text, str):
        raise ValueError("UNKNOWN: matriz ausente")
    expected = set(A) | set(C)
    found = {}
    for line in text.splitlines():
        fields = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        if len(fields) != 6 or not fields[0].startswith(chr(96)):
            continue
        key = fields[0].strip(chr(96))
        if key not in expected:
            continue
        if key in found or not all(fields) or fields[2] not in (
            "NO_VERIFICABLE", "EN_CURSO", "CUBIERTO", "DESCARTADO",
        ):
            raise ValueError("UNKNOWN: fila duplicada o invalida: " + key)
        found[key] = fields
    if set(found) != expected:
        raise ValueError("UNKNOWN: no existen todas las 20 filas")
    return found


def _selection(item=None, mission=None):
    return select_knowledge_for_context(
        mission=mission if mission is not None else E2E["mission"](),
        knowledge_items=[item if item is not None else E2E["knowledge_item"]()],
    )


def _lessons():
    return [
        guardrail_lesson_input(E2E["postmortem"]("postmortem-one", "pl0n3r/Factory#320")),
        guardrail_lesson_input(E2E["postmortem"]("postmortem-two", "pl0n3r/Factory#321")),
    ]


class CoberturaFactory22Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: cada unidad A tiene una observacion del codigo real."""
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        self.assertEqual(len(_rows(matrix)), 20)
        self.assertEqual((len(A), len(C)), (17, 3))
        self.assertFalse(set(A) & set(C))

        item = CONTRACT["item"]()
        valid = validate_knowledge_item(item)
        lifecycle = validate_knowledge_record(item["lifecycle"])
        status = knowledge_item_status(item, now_at=NOW)
        selection = _selection()
        binding = selection["bindings"][0]
        source = E2E["knowledge_item"]()
        package = compile_mission_context(
            project_dna=discover_project_dna(
                paths=["pyproject.toml"], capabilities=["knowledge-operations"]
            ),
            task={"id": "factory-1813", "title": "Knowledge coverage",
                  "goal": "Use verified operational knowledge", "tags": ["knowledge"]},
            context_items=selection["context_items"],
        )
        known = E2E["postmortem"]("postmortem-one", "pl0n3r/Factory#320")
        lesson = guardrail_lesson_input(known)
        candidates = compile_guardrail_candidates(_lessons())
        stale = E2E["knowledge_item"](validated="2026-01-01T00:00:00Z")
        pruning = propose_pruning_candidates([stale["lifecycle"]], now_at=NOW)
        before = deepcopy(stale["lifecycle"])
        legal = SELECTION["knowledge_item"](authority="legal")
        legal_binding = _selection(legal, SELECTION["mission"]())["bindings"][0]
        successors = validate_knowledge_item(CONTRACT["item"](
            supersedes=["runbook-cache-v0"], superseded_by=["runbook-cache-v2"]
        ))
        refs = validate_knowledge_item(CONTRACT["item"](
            related_refs=["pl0n3r/Factory#319", "docs:runbooks/cache"]
        ))
        candidate = CONTRACT["item"](lifecycle=CONTRACT["lifecycle"](state="candidate"))

        observed = {
            E + "L7-U1": (
                validate_postmortem(known)["authority"] == "unchanged"
                and lesson["kind"] == "incident"
                and candidates[0]["candidate"]["changes"][0]["value"]["status"] == "candidate"
            ),
            E + "L9-U1": bool(pruning) and all(
                p["delete"] is False and p["history_preserved"] is True for p in pruning
            ),
            E + "L18-U1": (
                binding["provenance"] == source["lifecycle"]["provenance"]
                and binding["authority"] == "unchanged"
                and "provenance" not in selection["context_items"][0]
            ),
            D + "L11-U1": (
                selection["selected_count"] == 1
                and len(package["context"]) == 1
                and package["context"][0]["source"] == "knowledge:runbook-e2e"
            ),
            D + "L13-U1": len(candidates) == 1 and candidates[0]["occurrences"] == 2
                           and "promoted" not in candidates[0],
            D + "L20-U1": valid["item_id"] == lifecycle["knowledge_id"]
                           and valid["item_class"] == lifecycle["knowledge_type"],
            D + "L21-U1": bool(valid["title"]) and bool(valid["summary"])
                           and valid["tags"] == ["cache", "operations"],
            D + "L22-U1": valid["owner_ref"] == "role:sre",
            D + "L23-U1": legal_binding["authority_class"] == "legal"
                           and legal_binding["authority"] == "unchanged",
            D + "L25-U1": refs["related_refs"] == sorted(
                ["pl0n3r/Factory#319", "docs:runbooks/cache"]
            ),
            D + "L26-U1": successors["supersedes"] == ["runbook-cache-v0"]
                           and successors["superseded_by"] == ["runbook-cache-v2"],
            D + "L27-U1": lifecycle["state"] == "active"
                           and lifecycle["evidence_class"] == "verified"
                           and bool(lifecycle["provenance"])
                           and isinstance(lifecycle["history"], list),
            D + "L35-U1": valid["item_id"] == valid["lifecycle"]["knowledge_id"]
                           and valid["item_class"] == valid["lifecycle"]["knowledge_type"],
            D + "L42-U1": status["state"] == effective_state(item["lifecycle"], NOW)
                           and status["source"] == "knowledge-lifecycle-v1"
                           and status["current"] is True,
            D + "L45-U1": knowledge_item_status(stale, now_at=NOW)["current"] is False
                           and knowledge_item_status(candidate, now_at=NOW)["current"] is False,
            D + "L56-U1": valid["sensitivity"] == "normal"
                           and valid["authority_class"] == "operational",
            D + "L58-U1": binding["state"] == "active"
                           and selection["selection_policy"] == "exact-scope+category+tag;lexical-order;no-score",
        }
        self.assertEqual(set(observed), set(A))
        for key in A:
            with self.subTest(unit=key):
                self.assertTrue(observed[key], "UNKNOWN: comportamiento incorrecto")
        self.assertEqual(before, stale["lifecycle"])
        for key, reason in C.items():
            with self.subTest(normative=key):
                self.assertIn(key, _rows(matrix))
                self.assertGreater(len(reason), 35)

    def test_falla_cerrado(self):
        """AC-02: ausencias, metadata inconsistente, PII y privilegios."""
        text = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        row = next(x for x in text.splitlines() if x.startswith(
            "| " + chr(96) + E + "L7-U1" + chr(96) + " |"
        ))
        with self.assertRaises(ValueError):
            _rows(text.replace(row + "\n", "", 1))
        with self.assertRaises(ValueError):
            _rows(text + "\n" + row)

        for patch_values in (
            {"item_id": "other-item"}, {"item_class": "adr"},
            {"authority_class": "root"}, {"owner_ref": ""},
            {"supersedes": ["runbook-cache"]}, {"tags": ["cache", "cache"]},
            {"summary": "Contact analyst@example.invalid for credentials"},
            {"title": "X" * 161}, {"related_refs": ["invalid@example.invalid"]},
        ):
            with self.subTest(changes=patch_values):
                with self.assertRaises(KnowledgeContractError):
                    validate_knowledge_item(CONTRACT["item"](**patch_values))

        wrong = E2E["postmortem"]("postmortem-bad", "pl0n3r/Factory#320")
        wrong["root_cause"]["evidence_refs"] = []
        with self.assertRaises(KnowledgePostmortemError):
            validate_postmortem(wrong)
        self.assertIsNone(guardrail_lesson_input(
            E2E["postmortem"]("postmortem-unknown", "pl0n3r/Factory#322", known=False)
        ))
        for forbidden_item in (
            E2E["knowledge_item"](validated="2026-01-01T00:00:00Z"),
            SELECTION["knowledge_item"](sensitivity="personal_data"),
            SELECTION["knowledge_item"](project="pl0n3r/Condor"),
        ):
            with self.subTest(item=forbidden_item["item_id"]):
                mission = SELECTION["mission"]() if forbidden_item["item_id"].startswith("runbook-db") else None
                with self.assertRaises(KnowledgeSelectionError):
                    _selection(forbidden_item, mission)

    def test_sin_datos_reales(self):
        """AC-03: input sintético y ninguna salida de red o proceso."""
        original = E2E["knowledge_item"]()
        before = deepcopy(original)
        with (
            patch.object(socket, "create_connection",
                         side_effect=AssertionError("red prohibida")),
            patch.object(subprocess, "run",
                         side_effect=AssertionError("proceso externo prohibido")),
        ):
            output = _selection(original)
            self.assertEqual(output["bindings"][0]["authority"], "unchanged")
            self.assertEqual(validate_knowledge_item(original)["item_id"],
                             original["item_id"])
        self.assertEqual(original, before)
        contents = Path(__file__).read_text(encoding="utf-8")
        for forbidden in ("-----BEGIN " + "PRIVATE KEY-----",
                          "GITHUB_" + "TOKEN=", "sk-" + "abcdefghij"):
            self.assertNotIn(forbidden, contents)

    def test_validar_exigido(self):
        """AC-04: el gate CI externo no se reemplaza por una aserción."""
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("name: Validar", workflow)
        self.assertIn("workflow_call:", workflow)
        self.assertIn("pull_request", workflow)
        self.assertEqual(Path(__file__).relative_to(ROOT).as_posix(),
                         "tests/test_cobertura_factory_22.py")


if __name__ == "__main__":
    unittest.main()
