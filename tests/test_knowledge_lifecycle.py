import unittest

from evolution.experience_guardrails import compile_guardrail_candidates
from evolution.knowledge_lifecycle import (
    KnowledgeLifecycleError,
    can_increase_autonomy,
    create_knowledge_record,
    effective_state,
    revalidate_knowledge,
    transition_knowledge,
    validate_knowledge_record,
)
from evolution.pruning import propose_knowledge_pruning


def record(
    knowledge_id="rule-alpha",
    *,
    fingerprint="a" * 64,
    state="active",
    created_at="2026-01-01T00:00:00Z",
    last_validated_at="2026-06-01T00:00:00Z",
    last_useful_at="2026-06-01T00:00:00Z",
    provenance=None,
):
    return create_knowledge_record(
        knowledge_id=knowledge_id,
        knowledge_type="guardrail",
        content_fingerprint=fingerprint,
        provenance=provenance or ["pl0n3r/factory#243"],
        scope={
            "project": "pl0n3r/factory",
            "domain": "living-software",
        },
        created_at=created_at,
        last_validated_at=last_validated_at,
        last_useful_at=last_useful_at,
        confidence=0.90,
        evidence_class="verified",
        review_policy={
            "review_after_days": 30,
            "expires_after_days": 90,
        },
        state=state,
    )


class KnowledgeLifecycleTests(unittest.TestCase):
    def test_promotable_knowledge_requires_provenance_scope_and_review_policy(self):
        item = record()
        validated = validate_knowledge_record(item)
        self.assertEqual(validated["scope"]["project"], "pl0n3r/factory")
        self.assertEqual(validated["provenance"], ["pl0n3r/factory#243"])
        self.assertEqual(
            validated["review_policy"],
            {"review_after_days": 30, "expires_after_days": 90},
        )

        lessons = [
            {
                "id": "lifecycle-001",
                "project": "pl0n3r/factory",
                "kind": "process",
                "occurred_at": "2026-09-01T00:00:00Z",
                "what": "Repeated contract drift.",
                "why": "Learned rule was not revalidated.",
                "prevention": "Revalidate learned rules before promotion.",
                "source": "pl0n3r/factory#241",
            },
            {
                "id": "lifecycle-002",
                "project": "pl0n3r/factory",
                "kind": "process",
                "occurred_at": "2026-09-02T00:00:00Z",
                "what": "Repeated contract drift.",
                "why": "Learned rule was not revalidated.",
                "prevention": "Revalidate learned rules before promotion.",
                "source": "pl0n3r/factory#242",
            },
        ]
        guardrail = compile_guardrail_candidates(lessons)[0]
        lifecycle = guardrail["candidate"]["changes"][0]["value"]["lifecycle"]
        self.assertEqual(lifecycle["state"], "candidate")
        self.assertEqual(lifecycle["evidence_class"], "multi-source")
        self.assertEqual(
            lifecycle["provenance"],
            ["pl0n3r/factory#241", "pl0n3r/factory#242"],
        )

    def test_expired_rule_cannot_increase_autonomy(self):
        item = record(
            last_validated_at="2026-01-01T00:00:00Z",
            last_useful_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(
            effective_state(item, "2026-09-28T00:00:00Z"),
            "needs_review",
        )
        self.assertFalse(
            can_increase_autonomy(item, "2026-09-28T00:00:00Z")
        )

        future = record(
            last_validated_at="2026-10-01T00:00:00Z",
            last_useful_at="2026-10-01T00:00:00Z",
        )
        with self.assertRaisesRegex(
            KnowledgeLifecycleError,
            "fechado en el futuro",
        ):
            can_increase_autonomy(future, "2026-09-28T00:00:00Z")

    def test_revalidation_restores_active_state_with_new_evidence(self):
        stale = record(
            last_validated_at="2026-01-01T00:00:00Z",
            last_useful_at="2026-01-01T00:00:00Z",
        )
        refreshed = revalidate_knowledge(
            stale,
            validated_at="2026-09-28T00:00:00Z",
            evidence=["pl0n3r/factory#244"],
            confidence=0.95,
            evidence_class="verified",
        )
        self.assertEqual(refreshed["state"], "active")
        self.assertEqual(
            refreshed["provenance"],
            ["pl0n3r/factory#243", "pl0n3r/factory#244"],
        )
        self.assertEqual(
            [event["to"] for event in refreshed["history"]],
            ["needs_review", "active"],
        )
        self.assertEqual(
            refreshed["history"][-1],
            {
                "at": "2026-09-28T00:00:00Z",
                "from": "needs_review",
                "to": "active",
                "reason": "revalidated",
                "evidence": ["pl0n3r/factory#244"],
            },
        )
        self.assertTrue(
            can_increase_autonomy(refreshed, "2026-09-28T00:00:00Z")
        )

    def test_archive_preserves_history(self):
        active = record()
        deprecated = transition_knowledge(
            active,
            target_state="deprecated",
            at="2026-09-28T00:00:00Z",
            evidence=["pl0n3r/factory#245"],
            reason="superseded",
        )
        archived = transition_knowledge(
            deprecated,
            target_state="archived",
            at="2026-09-29T00:00:00Z",
            evidence=["pl0n3r/factory#246"],
            reason="retained-for-audit",
        )
        self.assertEqual(archived["state"], "archived")
        self.assertEqual(len(archived["history"]), 3)
        self.assertEqual(
            [event["to"] for event in archived["history"]],
            ["needs_review", "deprecated", "archived"],
        )
        self.assertEqual(archived["provenance"], active["provenance"])
        self.assertFalse(
            can_increase_autonomy(archived, "2026-09-30T00:00:00Z")
        )

    def test_pruning_proposes_without_deleting_history(self):
        duplicate_a = record(
            "rule-alpha",
            fingerprint="b" * 64,
            last_validated_at="2026-01-01T00:00:00Z",
            last_useful_at="2026-01-01T00:00:00Z",
        )
        duplicate_b = record(
            "rule-beta",
            fingerprint="b" * 64,
            last_validated_at="2026-01-01T00:00:00Z",
            last_useful_at="2026-01-01T00:00:00Z",
        )
        proposals = propose_knowledge_pruning(
            [duplicate_a, duplicate_b],
            now_at="2026-09-28T00:00:00Z",
        )
        self.assertEqual(len(proposals), 1)
        proposal = proposals[0]
        self.assertEqual(
            proposal["knowledge_ids"],
            ["rule-alpha", "rule-beta"],
        )
        self.assertEqual(proposal["action"], "review-consolidation")
        self.assertEqual(
            proposal["reasons"],
            ["aged", "duplicate", "unused"],
        )
        self.assertFalse(proposal["delete"])
        self.assertTrue(proposal["history_preserved"])

        future_use = record(
            "rule-future",
            fingerprint="c" * 64,
            last_validated_at="2026-01-01T00:00:00Z",
            last_useful_at="2026-10-01T00:00:00Z",
        )
        with self.assertRaisesRegex(
            KnowledgeLifecycleError,
            "fechado en el futuro",
        ):
            propose_knowledge_pruning(
                [future_use],
                now_at="2026-09-28T00:00:00Z",
            )

        reversed_proposals = propose_knowledge_pruning(
            [duplicate_b, duplicate_a],
            now_at="2026-09-28T00:00:00Z",
        )
        self.assertEqual(reversed_proposals, proposals)


if __name__ == "__main__":
    unittest.main()
