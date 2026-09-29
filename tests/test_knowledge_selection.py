import unittest
from pathlib import Path

from evolution.knowledge_lifecycle import create_knowledge_record
from knowledge.selection import KnowledgeSelectionError, select_knowledge_for_context

NOW = "2026-09-29T00:00:00Z"


def knowledge_item(
    item_id="runbook-db",
    *,
    item_class="runbook",
    project="pl0n3r/Factory",
    domain="operations",
    tags=None,
    authority="operational",
    sensitivity="normal",
    state="active",
    last_validated_at="2026-09-28T00:00:00Z",
):
    lifecycle = create_knowledge_record(
        knowledge_id=item_id,
        knowledge_type=item_class,
        content_fingerprint="a" * 64,
        provenance=["pl0n3r/Factory#319@rev:v1"],
        scope={"project": project, "domain": domain},
        created_at="2026-06-01T00:00:00Z",
        last_validated_at=last_validated_at,
        last_useful_at=last_validated_at,
        confidence=0.9,
        evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )
    return {
        "version": 1,
        "item_id": item_id,
        "item_class": item_class,
        "title": "Runbook database",
        "summary": "Restore procedure verified by operations",
        "tags": tags or ["database", "recovery"],
        "owner_ref": "pl0n3r/Factory#319",
        "authority_class": authority,
        "sensitivity": sensitivity,
        "related_refs": ["pl0n3r/Factory#319"],
        "supersedes": [],
        "superseded_by": [],
        "lifecycle": lifecycle,
    }


def mission(**overrides):
    value = {
        "version": 1,
        "project": "pl0n3r/Factory",
        "domain": "operations",
        "tags": ["database"],
        "categories": ["constraint"],
        "require_current": True,
        "max_items": 12,
        "now_at": NOW,
    }
    value.update(overrides)
    return value


class KnowledgeSelectionTests(unittest.TestCase):
    def test_selection_adapts_current_scoped_items_for_context_compiler(self):
        selected = select_knowledge_for_context(
            mission=mission(max_items=1),
            knowledge_items=[
                knowledge_item("runbook-db"),
                knowledge_item("runbook-other", project="pl0n3r/Condor"),
            ],
        )
        self.assertEqual(selected["selected_count"], 1)
        self.assertEqual(
            set(selected["context_items"][0]),
            {"category", "source", "text", "tags"},
        )
        self.assertEqual(selected["context_items"][0]["category"], "constraint")
        self.assertEqual(selected["bindings"][0]["item_id"], "runbook-db")

    def test_selection_fails_closed_for_stale_sensitive_or_unknown_input(self):
        stale = knowledge_item(last_validated_at="2026-07-01T00:00:00Z")
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(mission=mission(), knowledge_items=[stale])

        unrelated = knowledge_item(project="pl0n3r/Condor")
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(mission=mission(), knowledge_items=[unrelated])

        missing_evidence = knowledge_item()
        missing_evidence["lifecycle"]["provenance"] = []
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(
                mission=mission(),
                knowledge_items=[missing_evidence],
            )

    def test_selection_is_deterministic_without_magic_score(self):
        first = knowledge_item("runbook-a")
        second = knowledge_item(
            "rule-b",
            item_class="product_rule",
            tags=["database"],
        )
        left = select_knowledge_for_context(
            mission=mission(),
            knowledge_items=[second, first],
        )
        right = select_knowledge_for_context(
            mission=mission(),
            knowledge_items=[first, second],
        )
        self.assertEqual(left, right)
        self.assertEqual(
            left["selection_policy"],
            "exact-scope+category+tag;lexical-order;no-score",
        )

    def test_context_adapter_preserves_provenance_and_authority(self):
        item = knowledge_item(authority="legal")
        result = select_knowledge_for_context(
            mission=mission(),
            knowledge_items=[item],
        )
        binding = result["bindings"][0]
        self.assertEqual(binding["authority_class"], "legal")
        self.assertEqual(binding["provenance"], item["lifecycle"]["provenance"])
        self.assertEqual(binding["authority"], "unchanged")
        self.assertEqual(binding["source"], "knowledge-contract-v1")

    def test_unknown_sensitive_or_pii_input_fails_closed_without_echo(self):
        secret = "private@example.com"
        unknown = mission()
        unknown["payload"] = secret
        with self.assertRaises(KnowledgeSelectionError) as ctx:
            select_knowledge_for_context(
                mission=unknown,
                knowledge_items=[knowledge_item()],
            )
        self.assertNotIn(secret, str(ctx.exception))

        sensitive = knowledge_item(sensitivity="personal_data")
        with self.assertRaises(KnowledgeSelectionError):
            select_knowledge_for_context(
                mission=mission(),
                knowledge_items=[sensitive],
            )

        pii = knowledge_item()
        pii["summary"] = secret
        with self.assertRaises(KnowledgeSelectionError) as ctx:
            select_knowledge_for_context(mission=mission(), knowledge_items=[pii])
        self.assertNotIn(secret, str(ctx.exception))

    def test_docs_keep_selection_boundary_without_parallel_engine(self):
        text = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "knowledge-selection.md"
        ).read_text()
        for marker in ("#320", "#322", "vector DB", "scheduler", "Knowledge Engine"):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
