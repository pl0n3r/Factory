from pathlib import Path
import unittest

from evolution.experience_guardrails import compile_guardrail_candidates
from evolution.knowledge_lifecycle import (
    create_knowledge_record, propose_pruning_candidates, transition_knowledge,
)
from intelligence.context_compiler import compile_mission_context
from intelligence.project_dna import discover_project_dna
from knowledge.postmortem import guardrail_lesson_input
from knowledge.selection import KnowledgeSelectionError, select_knowledge_for_context


NOW = "2026-09-29T00:00:00Z"


def lifecycle(knowledge_id, knowledge_type, *, validated="2026-09-28T00:00:00Z",
              fingerprint="a" * 64):
    return create_knowledge_record(
        knowledge_id=knowledge_id, knowledge_type=knowledge_type,
        content_fingerprint=fingerprint,
        provenance=[f"pl0n3r/Factory#322@rev:{knowledge_id}"],
        scope={"project": "pl0n3r/Factory", "domain": "operations"},
        created_at="2025-01-01T00:00:00Z",
        last_validated_at=validated, last_useful_at=validated,
        confidence=0.9, evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state="active",
    )


def knowledge_item(item_id="runbook-e2e", *, validated="2026-09-28T00:00:00Z"):
    return {
        "version": 1, "item_id": item_id, "item_class": "runbook",
        "title": "Recovery runbook", "summary": "Verified recovery sequence",
        "tags": ["knowledge", "operations"], "owner_ref": "role:sre",
        "authority_class": "operational", "sensitivity": "normal",
        "related_refs": ["pl0n3r/Factory#322"], "supersedes": [],
        "superseded_by": [],
        "lifecycle": lifecycle(item_id, "runbook", validated=validated),
    }


def mission():
    return {
        "version": 1, "project": "pl0n3r/Factory", "domain": "operations",
        "tags": ["knowledge"], "categories": ["constraint"],
        "require_current": True, "max_items": 4, "now_at": NOW,
    }


def postmortem(item_id, incident_ref, *, known=True):
    item = {
        "version": 1, "item_id": item_id, "item_class": "postmortem",
        "title": "Coordination incident", "summary": "Verified incident analysis",
        "tags": ["incident", "operations"], "owner_ref": "role:sre",
        "authority_class": "operational", "sensitivity": "normal",
        "related_refs": [incident_ref], "supersedes": [], "superseded_by": [],
        "lifecycle": lifecycle(item_id, "postmortem", fingerprint=("b" if known else "c") * 64),
    }
    return {
        "version": 1, "knowledge_item": item, "incident_ref": incident_ref,
        "occurred_at": "2026-09-28T12:00:00Z",
        "impact": "Coordination failed for one controlled execution.",
        "timeline": [{
            "at": "2026-09-28T12:05:00Z",
            "event": "Failure reproduced from canonical evidence.",
            "evidence_refs": [incident_ref],
        }],
        "detection": "CI exposed the contract failure.",
        "recovery": "The verified correction restored the contract.",
        "root_cause": {
            "status": "known" if known else "unknown",
            "summary": "Temporal fixture violated lifecycle ordering." if known else None,
            "evidence_refs": [incident_ref] if known else [],
        },
        "contributing_factors": ["Fixture chronology was inconsistent."],
        "actions": [],
        "guardrail_prevention": (
            "Validate lifecycle chronology before merging fixtures." if known else None
        ),
        "evidence_refs": [incident_ref],
    }


class KnowledgeOperationsE2ETests(unittest.TestCase):
    def test_current_scoped_knowledge_reaches_context_compiler_without_authority_expansion(self):
        item = knowledge_item()
        selection = select_knowledge_for_context(
            mission=mission(), knowledge_items=[item]
        )
        package = compile_mission_context(
            project_dna=discover_project_dna(
                paths=["pyproject.toml", ".github/workflows/ci.yml"],
                capabilities=["knowledge-operations"],
            ),
            task={
                "id": "factory-322", "title": "Knowledge E2E",
                "goal": "Use verified operational knowledge", "tags": ["knowledge"],
            },
            context_items=selection["context_items"],
        )
        self.assertEqual(len(package["context"]), 1)
        self.assertEqual(selection["bindings"][0]["authority"], "unchanged")
        self.assertEqual(
            selection["bindings"][0]["provenance"],
            item["lifecycle"]["provenance"],
        )

    def test_verified_postmortems_can_feed_guardrail_candidate_without_promotion(self):
        lessons = [
            guardrail_lesson_input(postmortem("postmortem-one", "pl0n3r/Factory#320")),
            guardrail_lesson_input(postmortem("postmortem-two", "pl0n3r/Factory#321")),
        ]
        candidates = compile_guardrail_candidates(lessons)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["occurrences"], 2)
        self.assertEqual(candidate["candidate"]["changes"][0]["operation"], "add")
        self.assertEqual(candidate["candidate"]["changes"][0]["value"]["status"], "candidate")
        self.assertNotIn("promoted", candidate)

    def test_unknown_root_cause_never_becomes_lesson_or_guardrail(self):
        unknown = guardrail_lesson_input(
            postmortem("postmortem-unknown", "pl0n3r/Factory#322", known=False)
        )
        self.assertIsNone(unknown)

    def test_stale_knowledge_is_excluded_and_pruning_is_non_destructive(self):
        stale = knowledge_item(validated="2026-01-01T00:00:00Z")
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(mission=mission(), knowledge_items=[stale])
        proposals = propose_pruning_candidates([stale["lifecycle"]], now_at=NOW)
        self.assertTrue(proposals)
        self.assertTrue(all(proposal["delete"] is False for proposal in proposals))
        self.assertTrue(all(proposal["history_preserved"] is True for proposal in proposals))

    def test_e2e_preserves_provenance_authority_and_has_no_external_runtime(self):
        item = knowledge_item()
        selection = select_knowledge_for_context(mission=mission(), knowledge_items=[item])
        binding = selection["bindings"][0]
        self.assertEqual(binding["authority"], "unchanged")
        self.assertEqual(binding["provenance"], item["lifecycle"]["provenance"])
        root = Path(__file__).resolve().parents[1]
        sources = (
            (root / "knowledge" / "selection.py").read_text()
            + (root / "knowledge" / "postmortem.py").read_text()
        )
        for forbidden in ("import requests", "import socket", "import subprocess", "import httpx"):
            self.assertNotIn(forbidden, sources)

    def test_docs_describe_single_knowledge_operations_loop_without_parallel_engine(self):
        docs = Path("docs/knowledge-operations-e2e.md").read_text(encoding="utf-8")
        for marker in (
            "#319", "#320", "#321", "delete=false",
            "No promoción automática", "No crea un Knowledge Engine paralelo",
        ):
            self.assertIn(marker, docs)

    def test_pruning_and_supersession_preserve_history_without_delete(self):
        first = lifecycle(
            "runbook-old", "runbook",
            validated="2026-01-01T00:00:00Z", fingerprint="d" * 64,
        )
        second = lifecycle(
            "runbook-new", "runbook",
            validated="2026-01-02T00:00:00Z", fingerprint="d" * 64,
        )
        deprecated = transition_knowledge(
            first, target_state="deprecated", at="2026-09-28T00:00:00Z",
            evidence=["pl0n3r/Factory#322@event:supersession"], reason="superseded",
        )
        proposals = propose_pruning_candidates([deprecated, second], now_at=NOW)
        self.assertTrue(proposals)
        self.assertTrue(all(row["delete"] is False for row in proposals))
        self.assertTrue(all(row["history_preserved"] is True for row in proposals))
        self.assertTrue(deprecated["history"])
        self.assertEqual(first["provenance"], deprecated["provenance"])

    def test_capture_lifecycle_context_and_guardrail_flow_is_traceable(self):
        item = knowledge_item("runbook-trace")
        selection = select_knowledge_for_context(mission=mission(), knowledge_items=[item])
        package = compile_mission_context(
            project_dna=discover_project_dna(
                paths=["pyproject.toml"], capabilities=["knowledge-operations"]
            ),
            task={
                "id": "factory-322-trace", "title": "Trace Knowledge E2E",
                "goal": "Use verified knowledge", "tags": ["knowledge"],
            },
            context_items=selection["context_items"],
        )
        lessons = [
            guardrail_lesson_input(postmortem("postmortem-trace-a", "pl0n3r/Factory#320")),
            guardrail_lesson_input(postmortem("postmortem-trace-b", "pl0n3r/Factory#321")),
        ]
        candidate = compile_guardrail_candidates(lessons)[0]
        self.assertEqual(package["context"][0]["source"], "knowledge:runbook-trace")
        self.assertEqual(
            selection["bindings"][0]["provenance"], item["lifecycle"]["provenance"]
        )
        self.assertEqual(candidate["sources"], ["pl0n3r/Factory#320", "pl0n3r/Factory#321"])
        self.assertEqual(candidate["candidate"]["changes"][0]["value"]["status"], "candidate")

    def test_readme_boundary_keeps_deep_knowledge_outside_operational_portada(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        docs = (root / "docs" / "knowledge-operations-e2e.md").read_text(encoding="utf-8")
        self.assertIn("README", docs)
        for deep_term in (
            "root_cause.status", "guardrail_lesson_input", "propose_pruning_candidates(",
        ):
            self.assertNotIn(deep_term, readme)


if __name__ == "__main__":
    unittest.main()
