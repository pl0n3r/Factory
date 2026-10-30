#!/usr/bin/env python3
"""#1812: 17 conductas reales de Knowledge Lifecycle y Knowledge Operations.

Tres limites normativos C se documentan en el PR; el test no lee la matriz.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import runpy
import socket
import subprocess
import unittest
import urllib.request

from evolution.experience_guardrails import compile_guardrail_candidates
from evolution.knowledge_lifecycle import (
    KnowledgeLifecycleError, can_increase_autonomy, effective_state,
    propose_pruning_candidates, revalidate_knowledge, transition_knowledge,
    validate_knowledge_record,
)
from intelligence.context_compiler import compile_mission_context
from intelligence.project_dna import discover_project_dna
from knowledge.postmortem import guardrail_lesson_input
from knowledge.selection import KnowledgeSelectionError, select_knowledge_for_context

ROOT = Path(__file__).resolve().parents[1]
LIFE = runpy.run_path(str(ROOT / "tests/test_knowledge_lifecycle.py"))
E2E = runpy.run_path(str(ROOT / "tests/test_knowledge_operations_e2e.py"))
NOW = "2026-09-29T00:00:00Z"
L = "docs/knowledge-lifecycle.md:"
E = "docs/knowledge-operations-e2e.md:"
A = (
    L + "L26-U1", L + "L30-U1", L + "L30-U2", L + "L30-U3",
    L + "L30-U4", L + "L30-U5", L + "L30-U6", L + "L36-U1",
    L + "L37-U1", L + "L38-U1", L + "L40-U1", L + "L40-U2",
    L + "L42-U1", L + "L9-U1", E + "L13-U1", E + "L14-U1",
    E + "L17-U1",
)
C = {
    L + "L30-U7": "Abrir nueva propuesta requiere flujo de autoridad, no revalidacion automatica.",
    E + "L15-U1": "Prohibicion arquitectonica de redes/store/scheduler/vector DB no se acredita globalmente con test local.",
    E + "L16-U1": "Limite normativo de WorkItems y autoridad, no comportamiento ejercitable en este slice.",
}


def _record(name="rule-alpha", **kwargs):
    return LIFE["record"](name, **kwargs)


def _stale(name="rule-alpha", **kwargs):
    return _record(name, last_validated_at="2026-01-01T00:00:00Z",
                   last_useful_at="2026-01-01T00:00:00Z", **kwargs)


def _pruning():
    first = _stale("rule-alpha", fingerprint="f" * 64)
    second = _stale("rule-beta", fingerprint="f" * 64)
    before = deepcopy([first, second])
    proposals = propose_pruning_candidates([first, second], now_at=NOW)
    return proposals, [first, second] == before


class CoberturaFactory21Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: observaciones de codigo, una por unidad verificable."""
        self.assertEqual((len(A), len(C)), (17, 3))
        self.assertEqual(len(set(A) | set(C)), 20)
        self.assertFalse(set(A) & set(C))

        stale = _stale()
        fresh = _record(last_validated_at="2026-09-28T00:00:00Z",
                        last_useful_at="2026-09-28T00:00:00Z")
        before = deepcopy(stale)
        old_identity = "pl0n3r/factory#243@sha256:" + "a" * 64
        new_identity = "pl0n3r/factory#243@sha256:" + "b" * 64
        versioned = _stale(provenance=[old_identity])
        updated_versioned = revalidate_knowledge(
            versioned, validated_at=NOW, evidence=[new_identity],
            confidence=0.98, evidence_class="verified",
        )
        refreshed = revalidate_knowledge(
            stale, validated_at=NOW, evidence=["pl0n3r/factory#244"],
            confidence=0.96, evidence_class="verified",
        )
        duplicate, unchanged = _pruning()
        single = propose_pruning_candidates([_stale()], now_at=NOW)
        non_autonomous = all(
            not can_increase_autonomy(_record(state=state), NOW)
            for state in ("candidate", "deprecated", "archived")
        )
        archived = transition_knowledge(
            transition_knowledge(
                fresh, target_state="deprecated", at=NOW,
                evidence=["pl0n3r/factory#245"], reason="superseded",
            ),
            target_state="archived", at="2026-09-30T00:00:00Z",
            evidence=["pl0n3r/factory#246"], reason="retained-for-audit",
        )
        lessons = [
            guardrail_lesson_input(E2E["postmortem"]("postmortem-one", "pl0n3r/Factory#320")),
            guardrail_lesson_input(E2E["postmortem"]("postmortem-two", "pl0n3r/Factory#321")),
        ]
        candidates = compile_guardrail_candidates(lessons)
        selection = select_knowledge_for_context(
            mission=E2E["mission"](), knowledge_items=[E2E["knowledge_item"]()]
        )
        package = compile_mission_context(
            project_dna=discover_project_dna(
                paths=["pyproject.toml"], capabilities=["knowledge-operations"]
            ),
            task={"id": "factory-1812", "title": "Knowledge lifecycle regression",
                  "goal": "Use verified knowledge", "tags": ["knowledge"]},
            context_items=selection["context_items"],
        )
        context = selection["context_items"][0]
        observed = {
            L + "L26-U1": effective_state(stale, NOW) == "needs_review"
                            and not can_increase_autonomy(stale, NOW) and non_autonomous,
            L + "L30-U1": refreshed["provenance"] == sorted([
                "pl0n3r/factory#243", "pl0n3r/factory#244",
            ]) and refreshed["state"] == "active",
            L + "L30-U2": new_identity in validate_knowledge_record(updated_versioned)["provenance"]
                            and old_identity in updated_versioned["provenance"],
            L + "L30-U3": len(updated_versioned["provenance"]) == 2
                            and updated_versioned["history"][-1]["evidence"] == [new_identity],
            L + "L30-U4": before == stale,
            L + "L30-U5": refreshed["last_validated_at"] == NOW
                            and refreshed["last_useful_at"] == NOW
                            and refreshed["confidence"] == 0.96
                            and refreshed["evidence_class"] == "verified"
                            and [x["to"] for x in refreshed["history"]] == ["needs_review", "active"],
            L + "L30-U6": archived["state"] == "archived"
                            and not can_increase_autonomy(archived, "2026-10-01T00:00:00Z"),
            L + "L36-U1": len(duplicate) == 1
                            and duplicate[0]["knowledge_ids"] == ["rule-alpha", "rule-beta"]
                            and "duplicate" in duplicate[0]["reasons"],
            L + "L37-U1": "unused" in single[0]["reasons"],
            L + "L38-U1": "aged" in single[0]["reasons"],
            L + "L40-U1": duplicate[0]["action"] == "review-consolidation"
                            and single[0]["action"] == "review-retirement",
            L + "L40-U2": unchanged and all(
                p["delete"] is False and p["history_preserved"] is True
                for p in duplicate + single
            ),
            L + "L42-U1": not can_increase_autonomy(stale, NOW)
                            and refreshed["history"][-1]["reason"] == "revalidated"
                            and len(archived["history"]) >= 2,
            L + "L9-U1": effective_state(_record(state="candidate"), NOW) == "candidate"
                           and not can_increase_autonomy(_record(state="candidate"), NOW),
            E + "L13-U1": len(candidates) == 1
                            and candidates[0]["candidate"]["changes"][0]["value"]["status"] == "candidate"
                            and "promoted" not in candidates[0],
            E + "L14-U1": unchanged and all(p["delete"] is False for p in duplicate),
            E + "L17-U1": set(context) == {"category", "source", "text", "tags"}
                            and len(package["context"]) == 1
                            and selection["bindings"][0]["authority"] == "unchanged",
        }
        self.assertEqual(set(observed), set(A))
        for unit in A:
            with self.subTest(unit=unit):
                self.assertTrue(observed[unit], "comportamiento distinto al contrato")
        for unit, reason in C.items():
            with self.subTest(normative=unit):
                self.assertGreater(len(reason), 45)

    def test_falla_cerrado(self):
        """AC-02: replay, ausencia, retiro, fecha futura y estado no autonomo."""
        stale = _stale()
        with self.assertRaisesRegex(KnowledgeLifecycleError, "identidad de evidencia nueva"):
            revalidate_knowledge(
                stale, validated_at=NOW, evidence=["pl0n3r/factory#243"],
                confidence=0.99, evidence_class="verified",
            )
        with self.assertRaises(KnowledgeLifecycleError):
            revalidate_knowledge(
                stale, validated_at=NOW, evidence=[],
                confidence=0.99, evidence_class="verified",
            )
        with self.assertRaises(KnowledgeLifecycleError):
            revalidate_knowledge(
                stale, validated_at="2025-01-01T00:00:00Z",
                evidence=["pl0n3r/factory#244"],
                confidence=0.99, evidence_class="verified",
            )
        for state in ("deprecated", "archived"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(KnowledgeLifecycleError, "retirado"):
                    revalidate_knowledge(
                        _record(state=state), validated_at=NOW,
                        evidence=["pl0n3r/factory#244"],
                        confidence=0.99, evidence_class="verified",
                    )
        with self.assertRaises(KnowledgeLifecycleError):
            can_increase_autonomy(
                _record(last_validated_at="2026-10-01T00:00:00Z",
                        last_useful_at="2026-10-01T00:00:00Z"), NOW,
            )
        self.assertFalse(can_increase_autonomy(
            _record(last_validated_at="2026-09-28T00:00:00Z",
                    last_useful_at="2026-09-28T00:00:00Z", state="candidate"), NOW,
        ))
        # CodeRabbit FINAL: reject restricted Knowledge Items before compiling context.
        sensitive = E2E["knowledge_item"]()
        sensitive["sensitivity"] = "sensitive_data"
        with self.assertRaisesRegex(KnowledgeSelectionError, "sensible no permitido"):
            select_knowledge_for_context(
                mission=E2E["mission"](), knowledge_items=[sensitive]
            )
        self.assertEqual(_stale()["history"], [])

    def test_sin_datos_reales(self):
        """AC-03: solo fixtures, sin llamadas externas ni cambio de authority."""
        with (
            patch.object(socket, "create_connection", side_effect=AssertionError("red prohibida")),
            patch.object(urllib.request, "urlopen", side_effect=AssertionError("red prohibida")),
            patch.object(subprocess, "run", side_effect=AssertionError("procesos prohibidos")),
        ):
            item = E2E["knowledge_item"]()
            before = deepcopy(item)
            selected = select_knowledge_for_context(
                mission=E2E["mission"](), knowledge_items=[item]
            )
            self.assertEqual(selected["selected_count"], 1)
            self.assertEqual(selected["bindings"][0]["authority"], "unchanged")
            self.assertEqual(item, before)
            pruning = propose_pruning_candidates([_stale()], now_at=NOW)
            self.assertTrue(pruning[0]["history_preserved"])
            self.assertFalse(pruning[0]["delete"])
        self.assertNotIn("token", str(item).lower())
        self.assertNotIn("password", str(item).lower())


if __name__ == "__main__":
    unittest.main()
