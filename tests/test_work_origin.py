#!/usr/bin/env python3
import copy
import unittest

from scripts.work_origin import (
    ORIGIN_SYSTEMS,
    WORK_TYPES,
    WorkOriginError,
    canonical_payload,
    idempotency_scope,
    validate_work_item,
    work_fingerprint,
)


def work_item(**overrides):
    payload = {
        "work_id": "work-001",
        "origin_mode": "directed",
        "origin_system": "human",
        "group_id": "pl0n3r-group",
        "venture_id": "venture-a",
        "project_id": "factory",
        "repository_ref": "pl0n3r/factory",
        "work_type": "engineering",
        "requested_capabilities": ["coding", "code_review"],
        "required_roles": ["qa", "ingenieria-software"],
        "authority_level": "operational",
        "producer_ref": "owner:pl0n3r",
        "priority_class": "critical",
        "depends_on": [],
        "claims": ["scripts/work_origin.py"],
        "budget_ref": "capital:factory-default",
        "policy_ref": "factory:constitution-v1",
        "approval_ref": "owner-decision:269",
        "evidence_refs": ["github:factory#269"],
        "idempotency_key": "factory-queue-work-origin-v1",
    }
    payload.update(overrides)
    return payload


class WorkOriginTests(unittest.TestCase):
    def test_directed_and_automatic_share_origin_contract(self):
        directed = validate_work_item(work_item())
        automatic = validate_work_item(
            work_item(
                work_id="work-002",
                origin_mode="automatic",
                origin_system="aegis",
                observed_at="2026-09-27T15:30:00-05:00",
            )
        )
        self.assertEqual(directed["origin_mode"], "directed")
        self.assertEqual(automatic["origin_mode"], "automatic")
        self.assertEqual(automatic["observed_at"], "2026-09-27T20:30:00Z")
        self.assertIn("aegis", ORIGIN_SYSTEMS)
        for field, value in (
            ("origin_mode", "scheduled"),
            ("origin_system", "private_scheduler"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(WorkOriginError):
                    validate_work_item(work_item(**{field: value}))

    def test_schema_requires_minimum_and_rejects_execution_fields(self):
        payload = work_item()
        del payload["policy_ref"]
        with self.assertRaisesRegex(WorkOriginError, "Campos requeridos ausentes"):
            validate_work_item(payload)

        alias = work_item()
        alias["requested_by"] = alias.pop("producer_ref")
        self.assertEqual(validate_work_item(alias)["producer_ref"], "owner:pl0n3r")

        for field in ("provider", "model", "executor"):
            with self.subTest(field=field):
                candidate = work_item()
                candidate[field] = "should-not-be-here"
                with self.assertRaisesRegex(WorkOriginError, "Campos desconocidos"):
                    validate_work_item(candidate)

    def test_non_code_work_types_do_not_require_repository(self):
        for work_type in sorted(WORK_TYPES):
            with self.subTest(work_type=work_type):
                payload = work_item(work_type=work_type)
                payload.pop("repository_ref")
                normalized = validate_work_item(payload)
                self.assertEqual(normalized["work_type"], work_type)
                self.assertNotIn("repository_ref", normalized)

        content = validate_work_item(
            work_item(
                work_type="content",
                requested_capabilities=["marketing_copy"],
                required_roles=["contenido"],
                repository_ref=None,
            )
        )
        self.assertEqual(content["work_type"], "content")

    def test_collections_are_bounded_deduplicated_and_secret_safe(self):
        normalized = validate_work_item(
            work_item(
                requested_capabilities=["coding", "coding", "code_review"],
                required_roles=["qa", "qa", "ingenieria-software"],
                depends_on=["work-z", "work-a", "work-z"],
                evidence_refs=["github:b", "github:a", "github:b"],
            )
        )
        self.assertEqual(normalized["requested_capabilities"], ["code_review", "coding"])
        self.assertEqual(normalized["required_roles"], ["ingenieria-software", "qa"])
        self.assertEqual(normalized["depends_on"], ["work-a", "work-z"])
        self.assertEqual(normalized["evidence_refs"], ["github:a", "github:b"])

        for bad in ({}, {"password": "value"}, {1: "non-string-key"}):
            with self.subTest(bad=bad):
                with self.assertRaises(WorkOriginError):
                    validate_work_item(bad)

        too_many = work_item(claims=[f"path-{n}" for n in range(51)])
        with self.assertRaisesRegex(WorkOriginError, "lista acotada"):
            validate_work_item(too_many)

        secret_value = work_item(policy_ref="Bearer abcdefghijklmnopqrstuvwxyz")
        with self.assertRaisesRegex(WorkOriginError, "forma de secreto"):
            validate_work_item(secret_value)

        oversized = work_item(evidence_refs=["x" * 100_001])
        with self.assertRaisesRegex(WorkOriginError, "tamaño máximo"):
            validate_work_item(oversized)

    def test_canonical_payload_and_fingerprint_are_deterministic(self):
        first = work_item(
            requested_capabilities=["coding", "code_review"],
            required_roles=["qa", "ingenieria-software"],
            claims=["b", "a"],
        )
        second = copy.deepcopy(first)
        second["requested_capabilities"].reverse()
        second["required_roles"].reverse()
        second["claims"].reverse()

        self.assertEqual(canonical_payload(first), canonical_payload(second))
        self.assertEqual(work_fingerprint(first), work_fingerprint(second))

        changed = copy.deepcopy(first)
        changed["priority_class"] = "high"
        self.assertNotEqual(work_fingerprint(first), work_fingerprint(changed))

    def test_idempotency_scope_is_stable_and_isolated(self):
        first = work_item(origin_system="human", work_id="work-human")
        second = work_item(
            origin_mode="automatic",
            origin_system="controlbot",
            work_id="work-controlbot",
            evidence_refs=["controlbot:event-123"],
        )
        self.assertEqual(idempotency_scope(first), idempotency_scope(second))

        other_project = work_item(project_id="controlbot")
        other_type = work_item(work_type="security")
        self.assertNotEqual(idempotency_scope(first), idempotency_scope(other_project))
        self.assertNotEqual(idempotency_scope(first), idempotency_scope(other_type))


if __name__ == "__main__":
    unittest.main()
