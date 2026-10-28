#!/usr/bin/env python3
"""#1646: 16 offline Knowledge Operations/Postmortem coverage contrasts.

Local assertions are not evidence of live service, release, external authority,
CI exact-SHA or an actual postmortem for a real-world incident.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import re
import unittest

from evolution.knowledge_lifecycle import create_knowledge_record
from knowledge.contract import (
    KnowledgeContractError, knowledge_item_status, validate_knowledge_item,
)
from knowledge.postmortem import (
    KnowledgePostmortemError, canonical_postmortem, guardrail_lesson_input,
    validate_postmortem,
)
from knowledge.selection import (
    KnowledgeSelectionError, select_knowledge_for_context,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T00:00:00Z"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
OPS = "docs/knowledge-operations.md"
POST = "docs/knowledge-postmortem.md"
CLAUSES = {
    "docs/knowledge-operations.md:L35-U1": ("item_id", OPS),
    "docs/knowledge-operations.md:L42-U1": ("effective_state()", OPS),
    "docs/knowledge-operations.md:L45-U1": ("candidate", OPS),
    "docs/knowledge-operations.md:L56-U1": ("contrato no permite incluir", OPS),
    "docs/knowledge-operations.md:L58-U1": ("Context Compiler", OPS),
    "docs/knowledge-operations.md:L63-U1": ("sin I/O ni store", OPS),
    "docs/knowledge-operations.md:L64-U1": ("sin búsqueda vectorial", OPS),
    "docs/knowledge-operations.md:L65-U1": ("sin scheduler", OPS),
    "docs/knowledge-operations.md:L67-U1": ("sin mutar Knowledge Lifecycle", OPS),
    "docs/knowledge-operations.md:L68-U1": ("sin ampliar autonomy/authority", OPS),
    "docs/knowledge-operations.md:L69-U1": ("sin convertir README", OPS),
    "docs/knowledge-operations.md:L9-U1": ("Knowledge Lifecycle", OPS),
    "docs/knowledge-postmortem.md:L10-U1": ("root_cause.status=unknown", POST),
    "docs/knowledge-postmortem.md:L10-U2": ("conserva el unknown", POST),
    "docs/knowledge-postmortem.md:L10-U3": ("no inventa causa raíz", POST),
    "docs/knowledge-postmortem.md:L11-U1": ("Texto libre es acotado", POST),
}


def record(*, state: str = "active", item_class: str = "runbook") -> dict:
    return create_knowledge_record(
        knowledge_id="runbook-factory" if item_class == "runbook" else "postmortem-factory",
        knowledge_type=item_class,
        content_fingerprint="a" * 64,
        provenance=["pl0n3r/Factory#319@rev:synthetic"],
        scope={"project": "pl0n3r/Factory", "domain": "knowledge-operations"},
        created_at="2026-09-20T00:00:00Z",
        last_validated_at="2026-09-28T00:00:00Z",
        last_useful_at="2026-09-28T00:00:00Z",
        confidence=0.9,
        evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


def item(*, item_class: str = "runbook", state: str = "active") -> dict:
    r = record(state=state, item_class=item_class)
    return {
        "version": 1, "item_id": r["knowledge_id"],
        "item_class": item_class,
        "title": "Factory recovery runbook",
        "summary": "Local synthetic operational procedure.",
        "tags": ["factory", "operations"],
        "owner_ref": "role:sre",
        "authority_class": "operational",
        "sensitivity": "normal",
        "related_refs": ["pl0n3r/Factory#319"],
        "supersedes": [], "superseded_by": [],
        "lifecycle": r,
    }


def mission(*, require_current: bool = True) -> dict:
    return {
        "version": 1, "project": "pl0n3r/Factory",
        "domain": "knowledge-operations", "tags": ["factory"],
        "categories": ["constraint"], "require_current": require_current,
        "max_items": 2, "now_at": NOW,
    }


def postmortem(*, known: bool = False) -> dict:
    cause = (
        {"status": "known", "summary": "Synthetic lifecycle mismatch.",
         "evidence_refs": ["pl0n3r/Factory#320"]}
        if known else
        {"status": "unknown", "summary": None, "evidence_refs": []}
    )
    return {
        "version": 1, "knowledge_item": item(item_class="postmortem"),
        "incident_ref": "pl0n3r/Factory#320",
        "occurred_at": "2026-09-28T12:00:00Z",
        "impact": "Synthetic coordination interruption.",
        "timeline": [{
            "at": "2026-09-28T12:05:00Z",
            "event": "Synthetic observation recorded.",
            "evidence_refs": ["pl0n3r/Factory#320"],
        }],
        "detection": "An offline test identified the scenario.",
        "recovery": "A synthetic correction restored the fixture.",
        "root_cause": cause,
        "contributing_factors": [], "actions": [],
        "guardrail_prevention": "Validate chronology in regression tests." if known else None,
        "evidence_refs": ["pl0n3r/Factory#320"],
    }


def rejected(fn, exception: type[Exception]) -> bool:
    try:
        fn()
    except exception:
        return True
    return False


def matrix_rows(text: str) -> dict[str, str]:
    """Require one unpromoted full source row per contracted clause."""
    found: dict[str, list[str]] = {key: [] for key in CLAUSES}
    for line in text.splitlines():
        match = re.match(r"^\| `(docs/knowledge-(?:operations|postmortem)\.md:L\d+-U\d+)` \|", line)
        if match and match.group(1) in found:
            found[match.group(1)].append(line)
    result = {}
    for key, matches in found.items():
        if (len(matches) == 1
                and " | NO_VERIFICABLE | " in matches[0]
                and "Contraste #1571" in matches[0]
                and key.split(":")[0] in CLAUSES[key][1]
                and matches[0].count(" | ") >= 5):
            result[key] = "NO_VERIFICABLE"
        else:
            result[key] = UNKNOWN
    return result


def source_boundaries() -> dict[str, bool]:
    """Inspect only versioned source code, never external processes/services."""
    paths = ("knowledge/contract.py", "knowledge/selection.py",
             "knowledge/postmortem.py")
    sources = [(path, (ROOT / path).read_text(encoding="utf-8"))
               for path in paths]
    trees = [ast.parse(text) for _, text in sources]
    forbidden_imports = {
        "requests", "httpx", "urllib", "socket", "subprocess",
        "sqlite3", "sqlalchemy", "faiss", "chromadb", "schedule",
        "apscheduler", "celery",
    }
    imports = set()
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    banned_calls = {"open", "exec", "eval", "os.system", "subprocess.run",
                    "requests.get", "requests.post", "socket.socket"}
    called = set()
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                called.add(f"{node.func.value.id}.{node.func.attr}")
    clean = not (imports & forbidden_imports) and not (called & banned_calls)
    return {"io": clean, "vector": clean and not (imports & {"faiss", "chromadb"}),
            "scheduler": clean and not (imports & {"schedule", "apscheduler", "celery"})}


def contrast() -> dict[str, bool]:
    """Each assertion exercises a distinct local behavior or explicit boundary."""
    base = item()
    validated = validate_knowledge_item(base)
    status = knowledge_item_status(base, now_at=NOW)
    source = deepcopy(base)
    mismatch_id = deepcopy(base)
    mismatch_id["item_id"] = "other-runbook"
    mismatch_type = deepcopy(base)
    mismatch_type["item_class"] = "adr"
    sensitivity = deepcopy(base)
    sensitivity["sensitivity"] = "personal_data"
    with_email = deepcopy(base)
    with_email["title"] = "Send to fake@example.test"
    with_secret = deepcopy(base)
    with_secret["summary"] = "Bearer abcdefghijklmnopqrstuvwxyz"
    selected = select_knowledge_for_context(mission=mission(), knowledge_items=[base])
    with_authority = deepcopy(base)
    with_authority["authority_class"] = "legal"
    selection_authority = select_knowledge_for_context(
        mission=mission(), knowledge_items=[with_authority])
    before = deepcopy(base)
    _ = knowledge_item_status(base, now_at=NOW)
    _ = select_knowledge_for_context(mission=mission(), knowledge_items=[base])
    lifecycle_untouched = base == before
    boundary = source_boundaries()

    valid_unknown = validate_postmortem(postmortem())
    serialized_unknown = canonical_postmortem(postmortem())
    wrong_summary = postmortem()
    wrong_summary["root_cause"]["summary"] = "Inferred root cause"
    wrong_evidence = postmortem()
    wrong_evidence["root_cause"]["evidence_refs"] = ["pl0n3r/Factory#320"]
    sensitive_postmortem = postmortem()
    sensitive_postmortem["impact"] = "Contact fake@example.test"
    huge_postmortem = postmortem()
    huge_postmortem["impact"] = "x" * 281
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    return {
        "docs/knowledge-operations.md:L35-U1": (
            validated["item_id"] == validated["lifecycle"]["knowledge_id"]
            and validated["item_class"] == validated["lifecycle"]["knowledge_type"]
            and rejected(lambda: validate_knowledge_item(mismatch_id), KnowledgeContractError)
            and rejected(lambda: validate_knowledge_item(mismatch_type), KnowledgeContractError)
        ),
        "docs/knowledge-operations.md:L42-U1": (
            status["source"] == "knowledge-lifecycle-v1"
            and status["state"] == "active" and status["current"] is True
        ),
        "docs/knowledge-operations.md:L45-U1": all(
            not knowledge_item_status(item(state=s), now_at=NOW)["current"]
            for s in ("candidate", "needs_review", "deprecated", "archived")
        ),
        "docs/knowledge-operations.md:L56-U1": (
            rejected(lambda: validate_knowledge_item(with_email), KnowledgeContractError)
            and rejected(lambda: validate_knowledge_item(with_secret), KnowledgeContractError)
        ),
        "docs/knowledge-operations.md:L58-U1": (
            selected["selected_count"] == 1
            and rejected(
                lambda: select_knowledge_for_context(
                    mission=mission(), knowledge_items=[sensitivity]),
                KnowledgeSelectionError,
            )
            and rejected(
                lambda: select_knowledge_for_context(
                    mission=mission(), knowledge_items=[item(state="deprecated")]),
                KnowledgeSelectionError,
            )
        ),
        "docs/knowledge-operations.md:L63-U1": boundary["io"] and lifecycle_untouched,
        "docs/knowledge-operations.md:L64-U1": (
            boundary["vector"] and
            selected["selection_policy"] == "exact-scope+category+tag;lexical-order;no-score"
        ),
        "docs/knowledge-operations.md:L65-U1": (
            boundary["scheduler"] and "scheduled_at" not in selected
            and "cron" not in selected
        ),
        "docs/knowledge-operations.md:L67-U1": lifecycle_untouched,
        "docs/knowledge-operations.md:L68-U1": (
            status["authority"] == "unchanged"
            and selection_authority["bindings"][0]["authority"] == "unchanged"
            and selection_authority["bindings"][0]["authority_class"] == "legal"
        ),
        "docs/knowledge-operations.md:L69-U1": all(
            token not in readme for token in (
                "root_cause.status", "guardrail_lesson_input",
                "propose_pruning_candidates(")
        ),
        "docs/knowledge-operations.md:L9-U1": (
            validated["lifecycle"]["provenance"] == source["lifecycle"]["provenance"]
            and validated["lifecycle"]["scope"] == source["lifecycle"]["scope"]
            and validated["lifecycle"]["history"] == source["lifecycle"]["history"]
            and status["source"] == "knowledge-lifecycle-v1"
        ),
        "docs/knowledge-postmortem.md:L10-U1": (
            valid_unknown["root_cause"] ==
            {"status": "unknown", "summary": None, "evidence_refs": []}
            and rejected(lambda: validate_postmortem(wrong_summary), KnowledgePostmortemError)
            and rejected(lambda: validate_postmortem(wrong_evidence), KnowledgePostmortemError)
        ),
        "docs/knowledge-postmortem.md:L10-U2": (
            valid_unknown["root_cause"]["status"] == "unknown"
            and '"status":"unknown"' in serialized_unknown
        ),
        "docs/knowledge-postmortem.md:L10-U3": (
            guardrail_lesson_input(postmortem()) is None
            and valid_unknown["root_cause"]["summary"] is None
            and valid_unknown["execute_actions"] is False
            and valid_unknown["emit_work_items"] is False
        ),
        "docs/knowledge-postmortem.md:L11-U1": (
            rejected(lambda: validate_postmortem(sensitive_postmortem), KnowledgePostmortemError)
            and rejected(lambda: validate_postmortem(huge_postmortem), KnowledgePostmortemError)
        ),
    }


def evidence(key: str, matrix: dict[str, str], docs: dict[str, str],
             observed: dict[str, bool] | None) -> str:
    """Every missing, malformed, promoted or untested clause is UNKNOWN."""
    if (key not in CLAUSES or matrix.get(key) != "NO_VERIFICABLE"
            or not isinstance(observed, dict) or observed.get(key) is not True):
        return UNKNOWN
    needle, filename = CLAUSES[key]
    text = docs.get(filename)
    if not isinstance(text, str) or needle not in text:
        return UNKNOWN
    return LOCAL


def operational_state(_key: str, _claim: object = None) -> str:
    return UNKNOWN


class BrechasFactory28Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: sixteen independent assertions against the real contracts."""
        matrix = matrix_rows(
            (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8"))
        docs = {name: (ROOT / name).read_text(encoding="utf-8")
                for name in (OPS, POST)}
        observed = contrast()
        self.assertEqual(set(CLAUSES), set(observed))
        self.assertEqual(len(CLAUSES), 16)
        for key in CLAUSES:
            with self.subTest(clause=key):
                self.assertTrue(observed[key], f"{key}: missing executable local contrast")
                self.assertEqual(evidence(key, matrix, docs, observed), LOCAL)

    def test_falla_cerrado(self) -> None:
        """AC-02: absent, forged or promoted matrix/evidence cannot imply coverage."""
        matrix_text = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        docs = {name: (ROOT / name).read_text(encoding="utf-8")
                for name in (OPS, POST)}
        matrix = matrix_rows(matrix_text)
        observed = contrast()
        for key in CLAUSES:
            with self.subTest(clause=key):
                self.assertEqual(evidence(key, {}, docs, observed), UNKNOWN)
                self.assertEqual(evidence(key, matrix, {}, observed), UNKNOWN)
                self.assertEqual(evidence(key, matrix, docs, None), UNKNOWN)
                self.assertEqual(
                    evidence(key, matrix, docs, {**observed, key: False}), UNKNOWN)
                text = matrix_text.replace(
                    next(line for line in matrix_text.splitlines()
                         if line.startswith(f"| `{key}` |")),
                    "", 1,
                )
                self.assertEqual(matrix_rows(text)[key], UNKNOWN)
        self.assertEqual(evidence("nonexistent", matrix, docs, observed), UNKNOWN)

    def test_sin_datos_reales(self) -> None:
        """AC-03: no network, secrets, user data or production side effects."""
        self.assertEqual(len(CLAUSES), 16)
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(own, r"(?m)^\s*(?:from|import)\s+(?:requests|httpx|urllib|socket|subprocess)\b")
        self.assertNotIn("-----BEGIN " + "PRIVATE KEY-----", own)
        for path in (OPS, POST, "knowledge/contract.py",
                     "knowledge/postmortem.py", "knowledge/selection.py",
                     "evolution/knowledge_lifecycle.py"):
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertEqual(source_boundaries(), {
            "io": True, "vector": True, "scheduler": True,
        })
        unknown = validate_postmortem(postmortem())
        self.assertEqual(unknown["authority"], "unchanged")
        self.assertFalse(unknown["execute_actions"])
        self.assertFalse(unknown["emit_work_items"])

    def test_estados_unknown_explicitos(self) -> None:
        """AC-04: passing local tests never means live/CI/deploy is verified."""
        matrix = matrix_rows(
            (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8"))
        self.assertEqual(set(matrix), set(CLAUSES))
        self.assertEqual(set(matrix.values()), {"NO_VERIFICABLE"})
        for key in CLAUSES:
            with self.subTest(clause=key):
                for claim in (None, True, "success", "green",
                              {"ci": "success"}, {"production": "healthy"},
                              {"owner_approval": "claimed"},
                              {"run": "completed"}, {"merge": "claimed"}):
                    self.assertEqual(operational_state(key, claim), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
