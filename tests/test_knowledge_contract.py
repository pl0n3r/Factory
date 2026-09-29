import copy
import json
import unittest
from pathlib import Path

from evolution.knowledge_lifecycle import create_knowledge_record
from knowledge.contract import (
    ITEM_CLASSES,
    SENSITIVITY_CLASSES,
    KnowledgeContractError,
    canonical_knowledge_item,
    knowledge_item_status,
    validate_knowledge_item,
)

ROOT = Path(__file__).resolve().parents[1]


def lifecycle(
    item_id="runbook-cache",
    item_class="runbook",
    *,
    state="active",
    last_validated_at="2026-09-20T00:00:00Z",
):
    return create_knowledge_record(
        knowledge_id=item_id,
        knowledge_type=item_class,
        content_fingerprint="a" * 64,
        provenance=["pl0n3r/Factory#307", "pl0n3r/Factory#319"],
        scope={"project": "pl0n3r/Factory", "domain": "knowledge-operations"},
        created_at="2026-09-01T00:00:00Z",
        last_validated_at=last_validated_at,
        last_useful_at=last_validated_at,
        confidence=0.9,
        evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


def item(
    item_id="runbook-cache",
    item_class="runbook",
    **overrides,
):
    payload = {
        "version": 1,
        "item_id": item_id,
        "item_class": item_class,
        "title": "Cache recovery runbook",
        "summary": "Operational recovery knowledge with verified provenance.",
        "tags": ["cache", "operations"],
        "owner_ref": "role:sre",
        "authority_class": "operational",
        "sensitivity": "normal",
        "related_refs": ["docs:runbooks/cache", "pl0n3r/Factory#307"],
        "supersedes": [],
        "superseded_by": [],
        "lifecycle": lifecycle(item_id, item_class),
    }
    payload.update(overrides)
    return payload


class KnowledgeContractTests(unittest.TestCase):
    def test_contract_v1_supports_operational_knowledge_classes_with_closed_metadata(self):
        for item_class in sorted(ITEM_CLASSES):
            with self.subTest(item_class=item_class):
                item_id = f"{item_class}-001"
                validated = validate_knowledge_item(
                    item(
                        item_id=item_id,
                        item_class=item_class,
                        lifecycle=lifecycle(item_id, item_class),
                    )
                )
                self.assertEqual(validated["item_class"], item_class)
                self.assertEqual(validated["item_id"], item_id)
                self.assertEqual(validated["authority_class"], "operational")
                self.assertEqual(validated["sensitivity"], "normal")

        first = item(tags=["operations", "cache"])
        second = copy.deepcopy(first)
        second["tags"].reverse()
        second["related_refs"].reverse()
        self.assertEqual(
            canonical_knowledge_item(first),
            canonical_knowledge_item(second),
        )

    def test_contract_reuses_lifecycle_freshness_and_supersession(self):
        current = item(
            supersedes=["runbook-cache-v0"],
            superseded_by=["runbook-cache-v2"],
        )
        status = knowledge_item_status(
            current,
            now_at="2026-09-28T00:00:00Z",
        )
        self.assertEqual(status["state"], "active")
        self.assertTrue(status["current"])
        self.assertEqual(status["source"], "knowledge-lifecycle-v1")
        self.assertEqual(status["authority"], "unchanged")
        self.assertEqual(status["supersedes"], ["runbook-cache-v0"])
        self.assertEqual(status["superseded_by"], ["runbook-cache-v2"])

        stale = item(
            lifecycle=lifecycle(
                last_validated_at="2026-01-01T00:00:00Z",
            )
        )
        stale_status = knowledge_item_status(
            stale,
            now_at="2026-09-28T00:00:00Z",
        )
        self.assertEqual(stale_status["state"], "needs_review")
        self.assertFalse(stale_status["current"])

    def test_contract_fails_closed_for_sensitive_unknown_or_inconsistent_metadata(self):
        cases = []

        unknown = item()
        unknown["extra"] = True
        cases.append(unknown)

        sensitive = item(title="Contact user@example.com for access")
        cases.append(sensitive)

        wrong_id = item()
        wrong_id["item_id"] = "other-item"
        cases.append(wrong_id)

        wrong_class = item()
        wrong_class["item_class"] = "adr"
        cases.append(wrong_class)

        duplicate_tags = item(tags=["cache", "cache"])
        cases.append(duplicate_tags)

        self_relation = item(supersedes=["runbook-cache"])
        cases.append(self_relation)

        contradictory = item(
            supersedes=["old-runbook"],
            superseded_by=["old-runbook"],
        )
        cases.append(contradictory)

        for payload in cases:
            with self.subTest(case=list(payload)):
                with self.assertRaises(KnowledgeContractError):
                    validate_knowledge_item(payload)

        with self.assertRaisesRegex(
            KnowledgeContractError,
            "sensible",
        ) as ctx:
            validate_knowledge_item(
                item(summary="Bearer abcdefghijklmnopqrstuvwxyz")
            )
        self.assertNotIn(
            "abcdefghijklmnopqrstuvwxyz",
            str(ctx.exception),
        )

    def test_schema_validator_and_docs_share_contract_v1_without_authority_expansion(self):
        schema = json.loads(
            (ROOT / "knowledge" / "contract.schema.json").read_text()
        )
        docs = (ROOT / "docs" / "knowledge-operations.md").read_text()

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["version"]["const"], 1)
        self.assertEqual(
            set(schema["properties"]["item_class"]["enum"]),
            ITEM_CLASSES,
        )
        self.assertEqual(
            set(schema["properties"]["sensitivity"]["enum"]),
            SENSITIVITY_CLASSES,
        )
        self.assertEqual(
            set(schema["properties"]["authority_class"]["enum"]),
            {
                "operational",
                "money",
                "legal",
                "personal_data",
                "irreversible_delete",
                "authority_expansion",
            },
        )
        self.assertFalse(
            schema["$defs"]["lifecycle"]["additionalProperties"]
        )
        self.assertIn("Knowledge Lifecycle", docs)
        self.assertIn("no concede autoridad", docs)
        self.assertIn("no crea un **Knowledge Engine** nuevo", docs)


if __name__ == "__main__":
    unittest.main()
