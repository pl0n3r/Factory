"""Factory #1645: regresiones sintéticas para 16 unidades Knowledge Operations.

No convierte evidencia offline en estado live, permisos o autoridad nuevos.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from evolution.experience_guardrails import compile_guardrail_candidates
from evolution.knowledge_lifecycle import (
    create_knowledge_record, effective_state, propose_pruning_candidates,
)
from intelligence.context_compiler import compile_mission_context
from intelligence.project_dna import discover_project_dna
from knowledge.contract import (
    KnowledgeContractError, knowledge_item_status, validate_knowledge_item,
)
from knowledge.postmortem import guardrail_lesson_input, validate_postmortem
from knowledge.selection import (
    KnowledgeSelectionError, select_knowledge_for_context,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
E2E = "docs/knowledge-operations-e2e.md"
OPS = "docs/knowledge-operations.md"
IDS = (
    f"{E2E}:L7-U1", f"{E2E}:L9-U1", f"{E2E}:L15-U1",
    f"{E2E}:L16-U1", f"{E2E}:L17-U1", f"{E2E}:L18-U1",
    f"{E2E}:L20-U1", f"{OPS}:L11-U1", f"{OPS}:L13-U1",
    f"{OPS}:L20-U1", f"{OPS}:L21-U1", f"{OPS}:L22-U1",
    f"{OPS}:L23-U1", f"{OPS}:L25-U1", f"{OPS}:L26-U1",
    f"{OPS}:L27-U1",
)
UNKNOWN = "UNKNOWN"
NOW = "2026-09-29T00:00:00Z"


def read_matrix():
    return MATRIX.read_text(encoding="utf-8")


def extract_rows(text):
    """Una fila ausente, duplicada, malformada o promovida falla cerrado."""
    if not isinstance(text, str):
        raise ValueError("Matriz ilegible")
    result = {}
    for line in text.splitlines():
        cells = tuple(part.strip() for part in line.strip().strip("|").split("|"))
        key = cells[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in result or len(cells) != 5 or not all(cells[:4]):
            raise ValueError("Fila ambigua: " + key)
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError("Promoción sin PR y evidencia: " + key)
        result[key] = cells
    if set(result) != set(IDS):
        raise ValueError("Unidades ausentes")
    return result


def assess(text, evidence):
    result = {unit: UNKNOWN for unit in IDS}
    try:
        extract_rows(text)
    except ValueError:
        return result
    if type(evidence) is not dict or set(evidence) != set(IDS):
        return result
    if any(type(value) is not bool for value in evidence.values()):
        return result
    return {unit: "OFFLINE_VERIFIED" if evidence[unit] else UNKNOWN
            for unit in IDS}


def lifecycle(item_id="runbook-1645", kind="runbook",
              *, validated="2026-09-28T00:00:00Z"):
    return create_knowledge_record(
        knowledge_id=item_id, knowledge_type=kind,
        content_fingerprint="a"*64,
        provenance=[f"pl0n3r/Factory#1645@rev:{item_id}"],
        scope={"project": "pl0n3r/Factory", "domain": "operations"},
        created_at="2025-01-01T00:00:00Z",
        last_validated_at=validated, last_useful_at=validated,
        confidence=0.9, evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state="active",
    )


def item(item_id="runbook-1645", kind="runbook", **changes):
    payload = {
        "version": 1, "item_id": item_id, "item_class": kind,
        "title": "Synthetic operations runbook",
        "summary": "Verified local runbook used for regression",
        "tags": ["knowledge", "operations"], "owner_ref": "role:sre",
        "authority_class": "operational", "sensitivity": "normal",
        "related_refs": ["pl0n3r/Factory#1645"],
        "supersedes": [], "superseded_by": [],
        "lifecycle": lifecycle(item_id, kind),
    }
    payload.update(changes)
    return payload


def mission(**changes):
    payload = {
        "version": 1, "project": "pl0n3r/Factory", "domain": "operations",
        "tags": ["knowledge"], "categories": ["constraint"],
        "require_current": True, "max_items": 4, "now_at": NOW,
    }
    payload.update(changes)
    return payload


def incident(name, ref, *, known=True):
    return {
        "version": 1,
        "knowledge_item": item(name, "postmortem", related_refs=[ref]),
        "incident_ref": ref, "occurred_at": "2026-09-28T12:00:00Z",
        "impact": "Synthetic coordination failure in offline test",
        "timeline": [{
            "at": "2026-09-28T12:05:00Z",
            "event": "Reproduced with synthetic evidence",
            "evidence_refs": [ref],
        }],
        "detection": "Contract test detected mismatch",
        "recovery": "Synthetic test restored contract",
        "root_cause": {
            "status": "known" if known else "unknown",
            "summary": "Fixture chronology violated contract" if known else None,
            "evidence_refs": [ref] if known else [],
        },
        "contributing_factors": [], "actions": [],
        "guardrail_prevention": "Validate chronology before promotion" if known else None,
        "evidence_refs": [ref],
    }


def offline_evidence():
    """Predicado distinto por unidad, sin I/O de red y sin autoridad productiva."""
    current = item()
    selected = select_knowledge_for_context(
        mission=mission(), knowledge_items=[current],
    )
    binding = selected["bindings"][0]
    minimal = select_knowledge_for_context(
        mission=mission(max_items=1),
        knowledge_items=[current, item("runbook-1646")],
    )
    package = compile_mission_context(
        project_dna=discover_project_dna(
            paths=["pyproject.toml"], capabilities=["knowledge-operations"],
        ),
        task={"id": "factory-1645", "title": "Knowledge tests",
              "goal": "Use local knowledge safely", "tags": ["knowledge"]},
        context_items=selected["context_items"],
    )
    lessons = [
        guardrail_lesson_input(incident("postmortem-1645", "pl0n3r/Factory#320")),
        guardrail_lesson_input(incident("postmortem-1646", "pl0n3r/Factory#321")),
    ]
    candidates = compile_guardrail_candidates(lessons)
    candidate = candidates[0]
    unknown_lesson = guardrail_lesson_input(
        incident("postmortem-1647", "pl0n3r/Factory#322", known=False),
    )
    stale_record = lifecycle("runbook-old", validated="2026-01-01T00:00:00Z")
    proposals = propose_pruning_candidates([stale_record], now_at=NOW)
    normalized = validate_knowledge_item(current)
    relation = validate_knowledge_item(item(
        "runbook-new", supersedes=["runbook-previous"],
        superseded_by=["runbook-next"],
    ))
    status = knowledge_item_status(current, now_at=NOW)
    code = "".join(
        (ROOT / path).read_text(encoding="utf-8") for path in (
            "knowledge/selection.py", "knowledge/postmortem.py",
            "intelligence/context_compiler.py",
        )
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs = (ROOT / E2E).read_text(encoding="utf-8")
    return {
        f"{E2E}:L7-U1": bool(
            lessons[0] and lessons[1] and len(candidates) == 1
            and candidate["occurrences"] == 2
            and candidate["candidate"]["changes"][0]["value"]["status"] == "candidate"
            and unknown_lesson is None
        ),
        f"{E2E}:L9-U1": bool(
            proposals and all(p["delete"] is False
                              and p["history_preserved"] is True for p in proposals)
        ),
        f"{E2E}:L15-U1": not any(x in code for x in (
            "import requests", "import socket", "import subprocess",
            "import httpx", "import urllib", "schedule.every(",
        )),
        f"{E2E}:L16-U1": (
            binding["authority"] == "unchanged"
            and validate_postmortem(incident(
                "postmortem-1648", "pl0n3r/Factory#320",
            ))["emit_work_items"] is False
        ),
        f"{E2E}:L17-U1": (
            set(selected["context_items"][0]) ==
            {"category", "source", "text", "tags"}
            and set(package["context"][0]) ==
            {"category", "source", "text", "tags"}
        ),
        f"{E2E}:L18-U1": (
            binding["provenance"] == current["lifecycle"]["provenance"]
            and "provenance" not in package["context"][0]
            and binding["source"] == "knowledge-contract-v1"
        ),
        f"{E2E}:L20-U1": (
            all(word in docs for word in (
                "README", "root cause", "lifecycle", "guardrails", "pruning",
            ))
            and all(word not in readme for word in (
                "root_cause.status", "guardrail_lesson_input",
                "propose_pruning_candidates(",
            ))
        ),
        f"{OPS}:L11-U1": (
            minimal["selected_count"] == 1
            and len(minimal["context_items"]) == 1
            and minimal["selection_policy"].startswith("exact-scope")
        ),
        f"{OPS}:L13-U1": (
            candidate["candidate"]["changes"][0]["value"]["status"] == "candidate"
            and all(p["delete"] is False for p in proposals)
            and "promoted" not in candidate
        ),
        f"{OPS}:L20-U1": (
            normalized["item_id"] == "runbook-1645"
            and normalized["item_class"] == "runbook"
            and normalized["lifecycle"]["knowledge_id"] == normalized["item_id"]
        ),
        f"{OPS}:L21-U1": (
            normalized["title"] == "Synthetic operations runbook"
            and normalized["summary"].startswith("Verified local")
            and normalized["tags"] == ["knowledge", "operations"]
        ),
        f"{OPS}:L22-U1": normalized["owner_ref"] == "role:sre",
        f"{OPS}:L23-U1": (
            normalized["authority_class"] == "operational"
            and binding["authority"] == "unchanged"
            and status["authority"] == "unchanged"
        ),
        f"{OPS}:L25-U1": normalized["related_refs"] == ["pl0n3r/Factory#1645"],
        f"{OPS}:L26-U1": (
            relation["supersedes"] == ["runbook-previous"]
            and relation["superseded_by"] == ["runbook-next"]
        ),
        f"{OPS}:L27-U1": (
            status["source"] == "knowledge-lifecycle-v1"
            and status["current"] is True
            and status["state"] == effective_state(current["lifecycle"], NOW)
        ),
    }


class BrechasFactory27Tests(unittest.TestCase):
    def test_contrato_principal(self):
        rows = extract_rows(read_matrix())
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(IDS), len(set(IDS)))
        evidence = offline_evidence()
        self.assertEqual(set(evidence), set(IDS))
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual(rows[unit][2], "NO_VERIFICABLE")
                self.assertTrue(rows[unit][3])
                self.assertTrue((ROOT / unit.split(":")[0]).is_file())
                self.assertIs(evidence[unit], True)
        self.assertEqual(
            set(assess(read_matrix(), evidence).values()), {"OFFLINE_VERIFIED"},
        )

    def test_falla_cerrado(self):
        matrix = read_matrix()
        first = next(line for line in matrix.splitlines()
                     if chr(96) + IDS[0] + chr(96) in line)
        for invalid in (
            None, "", matrix.replace(first, "", 1), matrix + "\n" + first,
            matrix.replace(first, first.replace("NO_VERIFICABLE", "CUBIERTO", 1)),
        ):
            with self.subTest(corrupted=str(invalid)[:40]):
                with self.assertRaises(ValueError):
                    extract_rows(invalid)
                self.assertEqual(
                    set(assess(invalid, {i: True for i in IDS}).values()), {UNKNOWN},
                )
        for invalid in (
            None, {}, {IDS[0]: True}, {i: 1 for i in IDS},
            {**{i: True for i in IDS}, "extra": True},
        ):
            self.assertEqual(set(assess(matrix, invalid).values()), {UNKNOWN})
        for invalid in (
            item(tags=["duplicate", "duplicate"]), item(owner_ref=""),
            item(item_id="runbook-other", lifecycle=lifecycle()),
            item(supersedes=["runbook-1645"]),
            item(supersedes=["item-old"], superseded_by=["item-old"]),
        ):
            with self.subTest(invalid=list(invalid)):
                with self.assertRaises(KnowledgeContractError):
                    validate_knowledge_item(invalid)
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(
                mission=mission(), knowledge_items=[
                    item(lifecycle=lifecycle(validated="2026-01-01T00:00:00Z"))
                ],
            )
        self.assertIsNone(guardrail_lesson_input(
            incident("postmortem-unknown", "pl0n3r/Factory#322", known=False),
        ))

    def test_sin_datos_reales(self):
        sample = item()
        self.assertEqual(sample["sensitivity"], "normal")
        self.assertTrue(all(ref.startswith("pl0n3r/Factory#")
                            for ref in sample["related_refs"]))
        self.assertEqual(
            sample["lifecycle"]["provenance"],
            ["pl0n3r/Factory#1645@rev:runbook-1645"],
        )
        source = (ROOT / "tests/test_brechas_factory_27.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0] for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
        self.assertFalse(imports & {"requests", "socket", "subprocess", "urllib"})
        calls = {
            node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse(calls & {"urlopen", "connect", "system", "popen"})
        for word in ("password", "access_token", "private_key", "credential"):
            self.assertNotIn(word, sample)

    def test_estados_unknown_explicitos(self):
        verified = offline_evidence()
        rows = extract_rows(read_matrix())
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual(rows[unit][2], "NO_VERIFICABLE")
                self.assertEqual(assess(read_matrix(), {unit: True})[unit], UNKNOWN)
                self.assertEqual(
                    assess(read_matrix(), {**verified, unit: False})[unit], UNKNOWN,
                )
                self.assertNotEqual(
                    assess(read_matrix(), verified)[unit], "PRODUCTION_GREEN",
                )
        self.assertIs(
            knowledge_item_status(
                item(lifecycle=lifecycle(validated="2026-01-01T00:00:00Z")),
                now_at=NOW,
            )["current"],
            False,
        )
        self.assertTrue(all(
            p["delete"] is False for p in propose_pruning_candidates(
                [lifecycle(validated="2026-01-01T00:00:00Z")],
                now_at=NOW,
            )
        ))


if __name__ == "__main__":
    unittest.main()
