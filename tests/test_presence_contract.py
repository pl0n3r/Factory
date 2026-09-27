#!/usr/bin/env python3
import copy
import unittest
from pathlib import Path

from scripts.presence_contract import (
    PresenceValidationError,
    classify_presence,
    validate_presence_snapshot,
)


def snapshot():
    return {
        "version": 1,
        "source": "controlbot-runtime",
        "observed_at": "2026-09-27T23:10:00Z",
        "sessions": [],
        "capacity": {
            "known_slots": 1,
            "eligible_free_slots": 0,
            "degraded_slots": 0,
            "freshness": "fresh",
        },
    }


def fresh_session(session_id="session-1", state="working"):
    return {
        "session_id": session_id,
        "agent_id": f"agent-{session_id}",
        "project": "factory",
        "repo": "pl0n3r/Factory",
        "work_item": "Factory#280",
        "issue_ref": "#280",
        "pr_ref": None,
        "state": state,
        "assignment": "presence-contract",
        "claims": ["scripts/presence_contract.py"],
        "capabilities": ["python"],
        "heartbeat_at": "2026-09-27T23:09:30Z",
        "freshness": "fresh",
        "generation": 2,
        "attempt": 1,
        "safe_point": True,
        "preemptibility": "preemptible",
    }


class PresenceContractTests(unittest.TestCase):
    def test_one_fresh_working_session_classifies_solo(self):
        """AC-01: una sesión activa fresca conserva identidad y clasifica solo."""
        payload = snapshot()
        payload["sessions"] = [fresh_session()]
        result = classify_presence(payload)
        normalized = validate_presence_snapshot(payload)

        self.assertEqual(result.classifications, ("solo", "saturated"))
        self.assertEqual(result.active_sessions, 1)
        self.assertEqual(normalized["sessions"][0]["assignment"], "presence-contract")
        self.assertEqual(normalized["sessions"][0]["generation"], 2)

    def test_multi_and_idle_capacity_are_derived_from_fresh_snapshot(self):
        """AC-02: multi e idle_capacity pueden coexistir sin perder conteo."""
        payload = snapshot()
        payload["sessions"] = [fresh_session("one"), fresh_session("two", "reviewing")]
        payload["capacity"] = {
            "known_slots": 3,
            "eligible_free_slots": 1,
            "degraded_slots": 0,
            "freshness": "fresh",
        }

        result = classify_presence(payload)
        self.assertEqual(result.classifications, ("multi", "idle_capacity"))
        self.assertEqual(result.active_sessions, 2)
        self.assertEqual(result.eligible_free_slots, 1)

    def test_stale_or_unknown_freshness_fails_closed(self):
        """AC-03: stale/unknown/heartbeat ausente nunca generan capacidad positiva."""
        cases = []

        stale = snapshot()
        stale["sessions"] = [fresh_session()]
        stale["sessions"][0]["freshness"] = "stale"
        cases.append(stale)

        unknown = snapshot()
        unknown["sessions"] = [fresh_session()]
        unknown["sessions"][0]["freshness"] = "unknown"
        cases.append(unknown)

        missing = snapshot()
        missing["sessions"] = [fresh_session()]
        missing["sessions"][0]["heartbeat_at"] = None
        cases.append(missing)

        capacity_unknown = snapshot()
        capacity_unknown["capacity"]["freshness"] = "unknown"
        capacity_unknown["capacity"]["eligible_free_slots"] = 1
        cases.append(capacity_unknown)

        for payload in cases:
            with self.subTest(payload=payload):
                result = classify_presence(payload)
                self.assertEqual(result.classifications, ("unknown",))
                self.assertEqual(result.eligible_free_slots, 0)

    def test_saturated_and_degraded_capacity_are_distinct(self):
        """AC-04: saturated y degraded son señales distintas y compatibles."""
        saturated = snapshot()
        self.assertEqual(classify_presence(saturated).classifications, ("saturated",))

        degraded = snapshot()
        degraded["sessions"] = [fresh_session()]
        degraded["capacity"] = {
            "known_slots": 2,
            "eligible_free_slots": 0,
            "degraded_slots": 1,
            "freshness": "fresh",
        }
        result = classify_presence(degraded)
        self.assertEqual(result.classifications, ("solo", "saturated", "degraded"))
        self.assertEqual(result.degraded_slots, 1)

    def test_sensitive_or_unknown_fields_are_rejected(self):
        """AC-05: campos sensibles o no declarados fallan cerrado."""
        for field in ("access_token", "password", "transcript", "surprise"):
            payload = snapshot()
            payload["sessions"] = [fresh_session()]
            payload["sessions"][0][field] = "forbidden"
            with self.subTest(field=field):
                with self.assertRaises(PresenceValidationError):
                    validate_presence_snapshot(payload)

    def test_classification_is_deterministic(self):
        """AC-06: mismo snapshot produce exactamente la misma salida."""
        payload = snapshot()
        payload["sessions"] = [fresh_session("b"), fresh_session("a")]
        payload["capacity"]["known_slots"] = 3
        payload["capacity"]["eligible_free_slots"] = 1

        first = classify_presence(copy.deepcopy(payload))
        second = classify_presence(copy.deepcopy(payload))
        self.assertEqual(first, second)

    def test_docs_define_external_authority_and_no_parallel_persistence(self):
        """AC-07: la documentación conserva autoridad runtime fuera de Factory."""
        docs = Path("docs/adaptive-orchestration.md").read_text(encoding="utf-8")
        self.assertIn("ControlBot", docs)
        self.assertIn("fuente autoritativa", docs)
        self.assertIn("Factory consume snapshots", docs)
        self.assertIn("no persiste Sessions", docs)


if __name__ == "__main__":
    unittest.main()
