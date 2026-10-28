#!/usr/bin/env python3
"""Factory #1647: sixteen offline contrasts; never live/merge evidence."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import re
import unittest

from evolution.knowledge_lifecycle import create_knowledge_record, propose_pruning_candidates
from knowledge.contract import KnowledgeContractError, knowledge_item_status, validate_knowledge_item
from knowledge.postmortem import KnowledgePostmortemError, guardrail_lesson_input, validate_postmortem
from knowledge.selection import KnowledgeSelectionError, select_knowledge_for_context
from lecciones.memoria import validate_lesson
from scripts.labels_kit import (
    LabelError, catalog_for_language, planned_state_decision,
    planned_state_migration_plan, validate_selection,
)
from scripts.sync_label_colors import SyncError, assert_safe_plan, load_catalogs, plan_repository

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T00:00:00Z"
UNKNOWN, LOCAL = "UNKNOWN", "LOCAL_CONTRACT"
POST, SELECT, LABEL = "docs/knowledge-postmortem.md", "docs/knowledge-selection.md", "docs/label-color-sync.md"
CLAUSES = {
    f"{POST}:L12-U1": (POST, "authority: unchanged"),
    f"{POST}:L16-U1": (POST, "guardrail_lesson_input()"),
    f"{POST}:L20-U1": (POST, "#319:"),
    f"{POST}:L21-U1": (POST, "#320:"),
    f"{POST}:L22-U1": (POST, "#321:"),
    f"{POST}:L23-U1": (POST, "#322:"),
    f"{POST}:L25-U1": (POST, "No existe scheduler/backlog paralelo"),
    f"{POST}:L9-U1": (POST, "root_cause.status=known"),
    f"{SELECT}:L5-U1": (SELECT, "knowledge_item_status()"),
    f"{SELECT}:L7-U1": (SELECT, "solo proyecta items current"),
    f"{SELECT}:L7-U2": (SELECT, "require_current=true"),
    f"{LABEL}:L10-U1": (LABEL, "No crea, borra, renombra"),
    f"{LABEL}:L11-U1": (LABEL, "BRVTAL conserva sus nombres en inglés"),
    f"{LABEL}:L17-U1": (LABEL, "estado: bloqueado"),
    f"{LABEL}:L18-U1": (LABEL, "estado: planificado"),
    f"{LABEL}:L18-U2": (LABEL, "No está atascado"),
}


def record(*, state="active", kind="postmortem"):
    return create_knowledge_record(
        knowledge_id="postmortem-factory" if kind == "postmortem" else "runbook-factory",
        knowledge_type=kind, content_fingerprint="a" * 64,
        provenance=["pl0n3r/Factory#319@rev:synthetic"],
        scope={"project": "pl0n3r/Factory", "domain": "knowledge-operations"},
        created_at="2026-09-20T00:00:00Z",
        last_validated_at="2026-09-28T00:00:00Z",
        last_useful_at="2026-09-28T00:00:00Z",
        confidence=0.9, evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


def item(*, state="active"):
    lifecycle = record(state=state)
    return {
        "version": 1, "item_id": lifecycle["knowledge_id"],
        "item_class": "postmortem", "title": "Synthetic Factory postmortem",
        "summary": "Offline coordination lesson, never live evidence.",
        "tags": ["factory", "operations"], "owner_ref": "role:sre",
        "authority_class": "operational", "sensitivity": "normal",
        "related_refs": ["pl0n3r/Factory#319"], "supersedes": [],
        "superseded_by": [], "lifecycle": lifecycle,
    }


def postmortem(*, known=True):
    return {
        "version": 1, "knowledge_item": item(),
        "incident_ref": "pl0n3r/Factory#320",
        "occurred_at": "2026-09-28T12:00:00Z",
        "impact": "Synthetic coordination interruption.",
        "timeline": [{"at": "2026-09-28T12:05:00Z",
                      "event": "Synthetic observation recorded.",
                      "evidence_refs": ["pl0n3r/Factory#320"]}],
        "detection": "An offline test found a coordination mismatch.",
        "recovery": "Synthetic fixture was reconciled.",
        "root_cause": (
            {"status": "known", "summary": "Synthetic contract mismatch.",
             "evidence_refs": ["pl0n3r/Factory#320"]}
            if known else
            {"status": "unknown", "summary": None, "evidence_refs": []}
        ),
        "contributing_factors": [], "actions": [],
        "guardrail_prevention": "Test the contract before merging." if known else None,
        "evidence_refs": ["pl0n3r/Factory#320"],
    }


def mission(*, required=True, domain="knowledge-operations"):
    return {"version": 1, "project": "pl0n3r/Factory",
            "domain": domain, "tags": ["factory"], "categories": ["evidence"],
            "require_current": required, "max_items": 2, "now_at": NOW}


def issue(*, planned=True):
    return {"number": 9999, "title": "Roadmap: synthetic plan",
            "body": "Synthetic planning fixture.",
            "labels": ["estado: bloqueado"],
            "dependencies_open": [] if planned else [321],
            "executable": False, "has_ready_leaf": False}


def denied(action, error):
    try:
        action()
    except error:
        return True
    return False


def matrix_states(text):
    """Rows missing, repeated or promoted are UNKNOWN, not passing evidence."""
    matches = {key: [] for key in CLAUSES}
    for line in text.splitlines():
        match = re.match(r"^\| " + re.escape(chr(96)) + r"(docs/[^" +
                         re.escape(chr(96)) + r"]+:L\d+-U\d+)" +
                         re.escape(chr(96)) + r" \|", line)
        if match and match.group(1) in matches:
            matches[match.group(1)].append(line)
    return {
        key: "NO_VERIFICABLE" if (
            len(rows) == 1 and " | NO_VERIFICABLE | " in rows[0]
            and "Contraste #1571" in rows[0] and rows[0].count(" | ") >= 4
        ) else UNKNOWN for key, rows in matches.items()
    }


def local_evidence(key, states, docs, checks):
    if (key not in CLAUSES or states.get(key) != "NO_VERIFICABLE"
            or not isinstance(checks, dict) or checks.get(key) is not True):
        return UNKNOWN
    path, phrase = CLAUSES[key]
    return LOCAL if isinstance(docs.get(path), str) and phrase in docs[path] else UNKNOWN


def operational_state(_key, _evidence=None):
    return UNKNOWN


def pure_source(path):
    """Pure contract boundary, no new network/database/scheduler executor."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    banned = {"subprocess", "requests", "httpx", "socket", "sqlite3", "apscheduler", "celery", "schedule"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] in banned for a in node.names):
            return False
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in banned:
            return False
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"open", "exec", "eval"}:
            return False
    return True


def contrast():
    base = item()
    good = postmortem()
    output = validate_postmortem(good)
    lesson = guardrail_lesson_input(good)
    selected = select_knowledge_for_context(mission=mission(), knowledge_items=[base])
    bad_identity = deepcopy(base)
    bad_identity["item_id"] = "incorrect-identity"
    bad_cause = deepcopy(good)
    bad_cause["root_cause"]["summary"] = None
    no_evidence = deepcopy(good)
    no_evidence["root_cause"]["evidence_refs"] = []
    no_prevention = deepcopy(good)
    no_prevention["guardrail_prevention"] = None
    baseline = deepcopy(base["lifecycle"])
    pruning = propose_pruning_candidates([baseline], now_at=NOW)
    catalogs = load_catalogs(ROOT)
    es = {x["key"]: x for x in catalogs["es"]}
    en = {x["key"]: x for x in catalogs["en"]}
    colors = plan_repository("pl0n3r/Factory", [
        {"name": "prioridad: media", "color": "FFFFFF"},
        {"name": "custom: untouched", "color": "000000"},
    ], catalogs)
    brvtal = plan_repository("pl0n3r/brvtal", [
        {"name": "priority: medium", "color": "FFFFFF"},
        {"name": "prioridad: media", "color": "FFFFFF"},
    ], catalogs)
    planned = issue()
    blocked = issue(planned=False)
    migration = planned_state_migration_plan(catalog_for_language("es"), [planned])
    labels = {"tipo: pruebas", "prioridad: media", "estado: planificado"}
    return {
        f"{POST}:L12-U1": (output["authority"] == "unchanged"
                           and output["execute_actions"] is False
                           and output["emit_work_items"] is False),
        f"{POST}:L16-U1": (lesson is not None and lesson["kind"] == "incident"
                           and validate_lesson(lesson, "fixture")["why"] == good["root_cause"]["summary"]
                           and guardrail_lesson_input(postmortem(known=False)) is None),
        f"{POST}:L20-U1": (validate_knowledge_item(base)["item_id"] == base["lifecycle"]["knowledge_id"]
                           and denied(lambda: validate_knowledge_item(bad_identity), KnowledgeContractError)),
        f"{POST}:L21-U1": (output["knowledge_item"]["item_class"] == "postmortem"
                           and lesson["source"] == output["incident_ref"] == "pl0n3r/Factory#320"),
        f"{POST}:L22-U1": (selected["selected_count"] == 1
                           and selected["context_items"][0]["category"] == "evidence"
                           and selected["bindings"][0]["authority"] == "unchanged"
                           and denied(lambda: select_knowledge_for_context(
                               mission=mission(domain="foreign-domain"), knowledge_items=[base]
                           ), KnowledgeSelectionError)),
        f"{POST}:L23-U1": (bool(output["knowledge_fingerprint"])
                           and selected["bindings"][0]["state"] == "active"
                           and isinstance(pruning, list)
                           and base["lifecycle"] == baseline
                           and lesson["prevention"] == good["guardrail_prevention"]),
        f"{POST}:L25-U1": (all(pure_source(path) for path in (
                               "knowledge/contract.py", "knowledge/postmortem.py", "knowledge/selection.py"))
                           and not output["execute_actions"] and not output["emit_work_items"]),
        f"{POST}:L9-U1": (output["root_cause"]["status"] == "known"
                          and bool(output["root_cause"]["summary"])
                          and bool(output["root_cause"]["evidence_refs"])
                          and denied(lambda: validate_postmortem(bad_cause), KnowledgePostmortemError)
                          and denied(lambda: validate_postmortem(no_evidence), KnowledgePostmortemError)
                          and denied(lambda: validate_postmortem(no_prevention), KnowledgePostmortemError)),
        f"{SELECT}:L5-U1": (knowledge_item_status(base, now_at=NOW)["source"] == "knowledge-lifecycle-v1"
                             and selected["bindings"][0]["state"] == "active"
                             and denied(lambda: select_knowledge_for_context(
                                 mission=mission(), knowledge_items=[bad_identity]
                             ), KnowledgeSelectionError)),
        f"{SELECT}:L7-U1": (selected["selected_count"] == 1
                             and select_knowledge_for_context(mission=mission(required=False),
                                 knowledge_items=[item(state="needs_review")])["context_items"] == []),
        f"{SELECT}:L7-U2": denied(lambda: select_knowledge_for_context(
            mission=mission(), knowledge_items=[item(state="needs_review")]
        ), KnowledgeSelectionError),
        f"{LABEL}:L10-U1": (len(colors) == 1
                            and set(colors[0]) == {"action", "repository", "label", "color_before", "color_after"}
                            and colors[0]["action"] == "update_color"
                            and colors[0]["label"] == "prioridad: media"
                            and denied(lambda: assert_safe_plan([{**colors[0], "action": "create"}]), SyncError)),
        f"{LABEL}:L11-U1": (len(brvtal) == 1
                            and brvtal[0]["label"] == "priority: medium"
                            and en["priority_medium"]["name"] == "priority: medium"
                            and es["priority_medium"]["name"] == "prioridad: media"),
        f"{LABEL}:L17-U1": (planned_state_decision(blocked)["planned"] is False
                            and planned_state_decision(blocked)["reason"] == "real_dependency_block"),
        f"{LABEL}:L18-U1": (planned_state_decision(planned)["planned"] is True
                            and planned_state_decision(planned)["reason"] == "planning_title"
                            and es["state_planned"]["name"] == "estado: planificado"
                            and en["state_planned"]["name"] == "status: planned"),
        f"{LABEL}:L18-U2": (
            not denied(lambda: validate_selection(catalog_for_language("es"), labels), LabelError)
            and migration == [{"action": "relabel", "issue": 9999,
                               "from": "estado: bloqueado", "to": "estado: planificado",
                               "reason": "planning_title"}]
            and planned_state_migration_plan(catalog_for_language("es"),
                [{**planned, "labels": ["estado: planificado"]}]) == []
            and denied(lambda: validate_selection(catalog_for_language("es"),
                labels | {"estado: bloqueado"}), LabelError)),
    }


class BrechasFactory29Tests(unittest.TestCase):
    def test_contrato_principal(self):
        states = matrix_states((ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8"))
        docs = {p: (ROOT / p).read_text(encoding="utf-8") for p in (POST, SELECT, LABEL)}
        checked = contrast()
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(set(CLAUSES), set(checked))
        for key, passed in checked.items():
            with self.subTest(clause=key):
                self.assertIs(passed, True, key)
                self.assertEqual(local_evidence(key, states, docs, checked), LOCAL)

    def test_falla_cerrado(self):
        raw = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        states = matrix_states(raw)
        docs = {p: (ROOT / p).read_text(encoding="utf-8") for p in (POST, SELECT, LABEL)}
        checked = contrast()
        for key in CLAUSES:
            with self.subTest(clause=key):
                self.assertEqual(local_evidence(key, {}, docs, checked), UNKNOWN)
                self.assertEqual(local_evidence(key, states, {}, checked), UNKNOWN)
                self.assertEqual(local_evidence(key, states, docs, None), UNKNOWN)
                self.assertEqual(local_evidence(key, states, docs, {**checked, key: False}), UNKNOWN)
                row = next(s for s in raw.splitlines() if s.startswith("| " + chr(96) + key + chr(96) + " |"))
                self.assertEqual(matrix_states(raw + "\n" + row)[key], UNKNOWN)
                self.assertEqual(matrix_states(raw.replace(row, "", 1))[key], UNKNOWN)
                self.assertEqual(matrix_states(raw.replace(row, row.replace("NO_VERIFICABLE", "VERIFICADO"), 1))[key], UNKNOWN)
        self.assertEqual(local_evidence("invented", states, docs, checked), UNKNOWN)
        self.assertTrue(denied(lambda: validate_postmortem({}), KnowledgePostmortemError))
        self.assertTrue(denied(lambda: select_knowledge_for_context(
            mission={}, knowledge_items=[item()]), KnowledgeSelectionError))
        self.assertTrue(denied(lambda: plan_repository(
            "unknown/repo", [], load_catalogs(ROOT)), SyncError))

    def test_sin_datos_reales(self):
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(own, r"(?m)^\s*(?:from|import)\s+(?:requests|httpx|urllib|socket|subprocess)\b")
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(validate_postmortem(postmortem())["authority"], "unchanged")
        for path in ("knowledge/contract.py", "knowledge/postmortem.py", "knowledge/selection.py"):
            self.assertTrue(pure_source(path))
        self.assertTrue(denied(lambda: validate_postmortem(
            {**postmortem(), "impact": "contact fake@example.test"}
        ), KnowledgePostmortemError))
        self.assertEqual(planned_state_migration_plan(catalog_for_language("es"), []), [])

    def test_estados_unknown_explicitos(self):
        states = matrix_states((ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8"))
        self.assertEqual(set(states), set(CLAUSES))
        self.assertEqual(set(states.values()), {"NO_VERIFICABLE"})
        self.assertIsNone(guardrail_lesson_input(postmortem(known=False)))
        for key in CLAUSES:
            with self.subTest(clause=key):
                for claim in (None, True, "GREEN", "success", {"ci": "success"},
                              {"prod": "healthy"}, {"owner": "approved"}, {"merge": "yes"}):
                    self.assertEqual(operational_state(key, claim), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
