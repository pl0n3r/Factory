import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from producto.feedback import FeedbackValidationError, validate_execution_feedback
from scripts.dispatcher_v2 import WorkItemReadinessContext, candidate_from_work_item, select_next
from scripts.work_origin import idempotency_scope, work_fingerprint


class FactoryQueueE2ETests(unittest.TestCase):
    """E2E puro del flujo Factory Queue v1 sin IO ni ejecución real."""

    @staticmethod
    def _work_item(origin_system: str, work_id: str, producer_ref: str) -> dict[str, object]:
        """Construye observaciones equivalentes del mismo trabajo desde instituciones distintas."""
        return {
            "work_id": work_id,
            "origin_mode": "automatic",
            "origin_system": origin_system,
            "group_id": "pl0n3r",
            "project_id": "factory-queue-v1",
            "repository_ref": "pl0n3r/Factory",
            "work_type": "infrastructure",
            "requested_capabilities": ["python"],
            "required_roles": ["qa", "sre"],
            "authority_level": "critical",
            "producer_ref": producer_ref,
            "priority_class": "critical",
            "depends_on": [],
            "claims": ["docs/factory-queue.md"],
            "policy_ref": "factory:plan-agentes",
            "evidence_refs": ["issue:273"],
            "observed_at": "2026-09-27T22:50:00Z",
            "idempotency_key": "queue-e2e-273",
        }

    @staticmethod
    def _ready_context() -> WorkItemReadinessContext:
        """Entrega evidencia externa suficiente para readiness positivo."""
        return WorkItemReadinessContext(
            authority_valid=True,
            policy_valid=True,
            freshness_valid=True,
            evidence_valid=True,
        )

    def test_multi_origin_equivalent_work_deduplicates_by_scope(self):
        """AC-01: orígenes distintos comparten scope y solo una unidad queda ejecutable."""
        factory_item = self._work_item("factory", "work-factory-273", "factory:queue")
        controlbot_item = self._work_item(
            "controlbot",
            "work-controlbot-273",
            "controlbot:queue",
        )
        self.assertEqual(
            idempotency_scope(factory_item),
            idempotency_scope(controlbot_item),
        )

        scope = idempotency_scope(factory_item)
        first = candidate_from_work_item(factory_item, self._ready_context())
        duplicate = candidate_from_work_item(
            controlbot_item,
            WorkItemReadinessContext(
                authority_valid=True,
                policy_valid=True,
                freshness_valid=True,
                evidence_valid=True,
                active_idempotency_scopes=frozenset({scope}),
            ),
        )

        selected = select_next([first, duplicate])
        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, factory_item["work_id"])
        self.assertIsNone(select_next([duplicate]))

    def test_ready_work_flows_through_existing_dispatcher(self):
        """AC-02: readiness y selección usan exclusivamente Dispatcher V2 existente."""
        item = self._work_item("factory", "work-ready-273", "factory:queue")
        candidate = candidate_from_work_item(item, self._ready_context())
        selected = select_next([candidate])

        self.assertIsNotNone(selected)
        self.assertEqual(selected.key, item["work_id"])
        self.assertEqual(selected.metadata["idempotency_scope"], idempotency_scope(item))
        self.assertEqual(selected.metadata["work_fingerprint"], work_fingerprint(item))
        self.assertEqual(selected.priority, item["priority_class"])

    def test_terminal_outcome_produces_attributable_feedback(self):
        """AC-03: outcome terminal conserva fingerprint y scope del WorkItem."""
        item = self._work_item("factory", "work-feedback-273", "factory:queue")
        candidate = candidate_from_work_item(item, self._ready_context())
        selected = select_next([candidate])
        self.assertIsNotNone(selected)

        now = datetime(2026, 9, 27, 23, 0, tzinfo=timezone.utc)
        payload = {
            "work_id": item["work_id"],
            "work_fingerprint": work_fingerprint(item),
            "idempotency_scope": idempotency_scope(item),
            "executor_ref": "runner:factory-e2e",
            "producer_ref": item["producer_ref"],
            "status": "success",
            "evidence_refs": ["check:ci", "artifact:e2e"],
            "observed_at": "2026-09-27T22:58:00+00:00",
        }
        feedback = validate_execution_feedback(payload, item, now=now)

        self.assertEqual(feedback["work_id"], selected.key)
        self.assertEqual(feedback["work_fingerprint"], selected.metadata["work_fingerprint"])
        self.assertEqual(feedback["idempotency_scope"], selected.metadata["idempotency_scope"])
        self.assertEqual(feedback["status"], "success")

    def test_invalid_feedback_evidence_fails_closed(self):
        """AC-04: provenance, evidencia o freshness inválidas no atraviesan el E2E."""
        item = self._work_item("factory", "work-invalid-273", "factory:queue")
        now = datetime(2026, 9, 27, 23, 0, tzinfo=timezone.utc)
        base = {
            "work_id": item["work_id"],
            "work_fingerprint": work_fingerprint(item),
            "idempotency_scope": idempotency_scope(item),
            "executor_ref": "runner:factory-e2e",
            "producer_ref": item["producer_ref"],
            "status": "success",
            "evidence_refs": ["check:ci"],
            "observed_at": "2026-09-27T22:58:00+00:00",
        }

        cases = []
        wrong_scope = copy.deepcopy(base)
        wrong_scope["idempotency_scope"] = "0" * 64
        cases.append(wrong_scope)

        no_evidence = copy.deepcopy(base)
        no_evidence["evidence_refs"] = []
        cases.append(no_evidence)

        wrong_producer = copy.deepcopy(base)
        wrong_producer["producer_ref"] = "factory:other"
        cases.append(wrong_producer)

        stale = copy.deepcopy(base)
        stale["observed_at"] = (now - timedelta(hours=25)).isoformat()
        cases.append(stale)

        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(FeedbackValidationError):
                validate_execution_feedback(payload, item, now=now)

    def test_docs_describe_complete_factory_queue_v1_flow(self):
        """AC-05: docs declaran el flujo E2E y el cierre funcional del épico #269."""
        root = Path(__file__).resolve().parents[1]
        docs = (root / "docs" / "factory-queue.md").read_text(encoding="utf-8")
        self.assertIn(
            "WorkItem → readiness → Dispatcher V2 → ejecución terminal → evidence/feedback",
            docs,
        )
        self.assertIn("multi-origen", docs)
        self.assertIn("idempotency_scope", docs)
        self.assertIn("cierre funcional de Factory Queue v1", docs)
        self.assertIn("#269", docs)


if __name__ == "__main__":
    unittest.main()
