import copy
import subprocess
import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from producto.feedback import (
    FeedbackValidationError,
    execution_feedback_identity,
    validate_execution_feedback,
)
from scripts.work_origin import idempotency_scope, work_fingerprint


class FeedbackContractTests(unittest.TestCase):

    @staticmethod
    def _work_item():
        return {
            "work_id": "work-272",
            "origin_mode": "automatic",
            "origin_system": "factory",
            "group_id": "pl0n3r",
            "project_id": "factory",
            "repository_ref": "pl0n3r/Factory",
            "work_type": "infrastructure",
            "requested_capabilities": ["python"],
            "required_roles": ["qa", "sre"],
            "authority_level": "critical",
            "producer_ref": "factory:queue",
            "priority_class": "critical",
            "depends_on": [],
            "claims": ["producto/feedback.py"],
            "policy_ref": "factory:plan-agentes",
            "evidence_refs": ["issue:272"],
            "observed_at": "2026-09-27T22:00:00+00:00",
            "idempotency_key": "feedback-272",
        }

    @classmethod
    def _feedback(cls):
        item = cls._work_item()
        return {
            "work_id": item["work_id"],
            "work_fingerprint": work_fingerprint(item),
            "idempotency_scope": idempotency_scope(item),
            "executor_ref": "runner:local-test",
            "producer_ref": item["producer_ref"],
            "status": "success",
            "evidence_refs": ["check:ci", "artifact:result"],
            "observed_at": "2026-09-27T22:10:00+00:00",
        }

    def test_execution_feedback_is_attributable_to_work_item(self):
        item = self._work_item()
        payload = self._feedback()
        result = validate_execution_feedback(
            payload,
            item,
            now=datetime(2026, 9, 27, 22, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(result["work_id"], item["work_id"])
        self.assertEqual(result["work_fingerprint"], work_fingerprint(item))
        self.assertEqual(result["idempotency_scope"], idempotency_scope(item))
        self.assertEqual(result["producer_ref"], item["producer_ref"])
        self.assertEqual(
            result["evidence_refs"],
            ["artifact:result", "check:ci"],
        )

    def test_execution_feedback_fails_closed_on_invalid_provenance_or_freshness(self):
        item = self._work_item()
        now = datetime(2026, 9, 27, 22, 20, tzinfo=timezone.utc)
        cases = []

        missing_evidence = self._feedback()
        missing_evidence["evidence_refs"] = []
        cases.append(missing_evidence)

        wrong_fingerprint = self._feedback()
        wrong_fingerprint["work_fingerprint"] = "0" * 64
        cases.append(wrong_fingerprint)

        wrong_producer = self._feedback()
        wrong_producer["producer_ref"] = "factory:other"
        cases.append(wrong_producer)

        non_terminal = self._feedback()
        non_terminal["status"] = "running"
        cases.append(non_terminal)

        stale = self._feedback()
        stale["observed_at"] = (now - timedelta(hours=25)).isoformat()
        cases.append(stale)

        future = self._feedback()
        future["observed_at"] = (now + timedelta(minutes=6)).isoformat()
        cases.append(future)

        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(FeedbackValidationError):
                validate_execution_feedback(payload, item, now=now)

    def test_execution_feedback_is_idempotent(self):
        item = self._work_item()
        now = datetime(2026, 9, 27, 22, 20, tzinfo=timezone.utc)
        first = self._feedback()
        second = copy.deepcopy(first)
        second["evidence_refs"] = list(reversed(second["evidence_refs"]))
        self.assertEqual(
            execution_feedback_identity(first, item, now=now),
            execution_feedback_identity(second, item, now=now),
        )

    def test_execution_feedback_does_not_expand_dispatch_authority(self):
        item = self._work_item()
        now = datetime(2026, 9, 27, 22, 20, tzinfo=timezone.utc)
        forbidden_fields = ("priority_class", "authority_level", "rank", "executor_policy")
        for field in forbidden_fields:
            payload = self._feedback()
            payload[field] = "critical"
            with self.subTest(field=field), self.assertRaises(FeedbackValidationError):
                validate_execution_feedback(payload, item, now=now)

    def test_factory_queue_docs_define_feedback_handoff(self):
        root = Path(__file__).resolve().parents[1]
        docs = (root / "docs" / "factory-queue.md").read_text(encoding="utf-8")
        self.assertIn("WorkItem → readiness/dispatch → ejecución → evidence/feedback", docs)
        self.assertIn("work_fingerprint", docs)
        self.assertIn("idempotency_scope", docs)
        self.assertIn("no concede autoridad", docs)
        self.assertIn("#273", docs)

    def test_producto_feedback_suite_is_part_of_required_ci(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                str(root / "producto"),
                "-p",
                "test_feedback.py",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=result.stdout + "\n" + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
