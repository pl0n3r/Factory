import copy
import unittest
from pathlib import Path

from evolution.knowledge_lifecycle import create_knowledge_record
from knowledge.postmortem import (
    KnowledgePostmortemError, canonical_postmortem,
    guardrail_lesson_input, validate_postmortem,
)


def knowledge_item():
    lifecycle = create_knowledge_record(
        knowledge_id="postmortem-cache-outage", knowledge_type="postmortem",
        content_fingerprint="b" * 64, provenance=["pl0n3r/Factory#320"],
        scope={"project": "pl0n3r/Factory", "domain": "knowledge-operations"},
        created_at="2026-09-28T18:00:00Z",
        last_validated_at="2026-09-28T18:30:00Z",
        last_useful_at="2026-09-28T18:30:00Z", confidence=0.9,
        evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state="active",
    )
    return {
        "version": 1, "item_id": "postmortem-cache-outage",
        "item_class": "postmortem", "title": "Cache outage postmortem",
        "summary": "Verified operational postmortem.",
        "tags": ["incident", "operations"], "owner_ref": "role:sre",
        "authority_class": "operational", "sensitivity": "normal",
        "related_refs": ["pl0n3r/Factory#320"], "supersedes": [],
        "superseded_by": [], "lifecycle": lifecycle,
    }


def postmortem(known=True):
    return {
        "version": 1, "knowledge_item": knowledge_item(),
        "incident_ref": "pl0n3r/Factory#320",
        "occurred_at": "2026-09-28T18:00:00Z",
        "impact": "Factory coordination was unavailable for one deployment.",
        "timeline": [
            {"at": "2026-09-28T18:05:00Z",
             "event": "Failure reproduced from the exact workflow run.",
             "evidence_refs": ["run:36500000000"]},
            {"at": "2026-09-28T18:20:00Z",
             "event": "Service recovered after the verified correction.",
             "evidence_refs": ["sha:abcdef1"]},
        ],
        "detection": "CI exposed the failing contract deterministically.",
        "recovery": "The failing fixture was corrected and CI returned green.",
        "root_cause": {
            "status": "known" if known else "unknown",
            "summary": "Fixture timestamp preceded the knowledge creation time." if known else None,
            "evidence_refs": ["run:36500000000"] if known else [],
        },
        "contributing_factors": ["Fixture encoded inconsistent temporal assumptions."],
        "actions": [{"id": "regression-test",
                     "summary": "Keep a regression for temporal ordering.",
                     "evidence_refs": ["test:knowledge-postmortem"]}],
        "guardrail_prevention": (
            "Validate fixture chronology against lifecycle invariants before merge."
            if known else None
        ),
        "evidence_refs": ["pl0n3r/Factory#320", "run:36500000000"],
    }


class KnowledgePostmortemTests(unittest.TestCase):
    def test_postmortem_distinguishes_known_and_unknown_root_cause_with_evidence(self):
        known = validate_postmortem(postmortem())
        self.assertEqual(known["root_cause"]["status"], "known")
        self.assertTrue(known["root_cause"]["evidence_refs"])
        unknown = validate_postmortem(postmortem(False))
        self.assertEqual(unknown["root_cause"]["status"], "unknown")
        self.assertIsNone(unknown["root_cause"]["summary"])
        invalid = postmortem(); invalid["root_cause"]["evidence_refs"] = []
        with self.assertRaisesRegex(KnowledgePostmortemError, "evidencia"):
            validate_postmortem(invalid)

    def test_postmortem_fields_are_closed_bounded_deterministic_and_sensitive_safe(self):
        first, second = postmortem(), postmortem()
        second["timeline"].reverse(); second["evidence_refs"].reverse()
        self.assertEqual(canonical_postmortem(first), canonical_postmortem(second))
        unknown = postmortem(); unknown["extra"] = True
        with self.assertRaises(KnowledgePostmortemError):
            validate_postmortem(unknown)
        sensitive = postmortem()
        sensitive["impact"] = "Contact ops@example.com with incident details."
        with self.assertRaisesRegex(KnowledgePostmortemError, "sensible"):
            validate_postmortem(sensitive)

    def test_postmortem_only_emits_guardrail_input_from_verified_known_cause(self):
        lesson = guardrail_lesson_input(postmortem())
        self.assertEqual(lesson["kind"], "incident")
        self.assertEqual(lesson["project"], "pl0n3r/Factory")
        self.assertEqual(lesson["source"], "pl0n3r/Factory#320")
        self.assertIn("timestamp", lesson["why"])
        self.assertIsNone(guardrail_lesson_input(postmortem(False)))

    def test_postmortem_reuses_knowledge_contract_and_preserves_authority(self):
        validated = validate_postmortem(postmortem())
        self.assertEqual(validated["knowledge_item"]["item_class"], "postmortem")
        self.assertRegex(validated["knowledge_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(validated["authority"], "unchanged")
        wrong = postmortem(); wrong["knowledge_item"]["item_class"] = "runbook"
        with self.assertRaises(KnowledgePostmortemError):
            validate_postmortem(wrong)

    def test_postmortem_output_is_non_executing_and_sanitized(self):
        validated = validate_postmortem(postmortem())
        self.assertFalse(validated["execute_actions"])
        self.assertFalse(validated["emit_work_items"])
        self.assertNotIn("payload", validated)

    def test_docs_keep_postmortem_boundary_without_parallel_engine(self):
        docs = Path("docs/knowledge-postmortem.md").read_text(encoding="utf-8")
        for text in ("#321", "#322", "sin crear un Knowledge Engine", "No existe scheduler/backlog paralelo"):
            self.assertIn(text, docs)


if __name__ == "__main__":
    unittest.main()
