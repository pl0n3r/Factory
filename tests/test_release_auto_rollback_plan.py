"""Regresiones puras de rollback: nunca escriben ni invocan GitHub."""
from __future__ import annotations

import copy
import unittest

from scripts.release_auto_rollback_plan import plan_rollback

AFFECTED = "a" * 40
STABLE = "b" * 40


def _snapshot() -> dict:
    return {
        "phase": "construccion",
        "kill_switch_state": "RUNNING",
        "tag_protected": True,
        "evidence_authenticated": True,
        "incident_type": "startup_failure",
        "affected_factory_sha": AFFECTED,
        "current_v1_sha": AFFECTED,
        "stable_factory_sha": STABLE,
        "affected_consumer_runs": [{
            "repository": "pl0n3r/Example", "workflow": "Validate",
            "run_id": 200, "factory_sha": AFFECTED,
            "conclusion": "startup_failure", "authenticated": True,
            "materialized_jobs": False,
        }],
        "stable_consumer_runs": [{
            "repository": "pl0n3r/Example", "workflow": "Validate",
            "run_id": 100, "factory_sha": STABLE,
            "conclusion": "success", "authenticated": True,
            "materialized_jobs": True,
        }],
    }


class ReleaseAutoRollbackPlanTests(unittest.TestCase):
    def assert_safe(self, result: dict) -> None:
        self.assertFalse(result["authorizes_tag_move"])
        self.assertEqual(0, result["mutations"])
        self.assertTrue(result["postrollback_verification_required"])

    def test_authenticated_startup_failure_proposes_only_human_rollback(self) -> None:
        case = _snapshot()
        before = copy.deepcopy(case)
        actual = plan_rollback(case)
        self.assertEqual("HUMAN_GATE_REQUIRED", actual["decision"])
        self.assertEqual(STABLE, actual["proposed_stable_sha"])
        self.assertEqual("owner_must_authorize_v1_rollback", actual["reason"])
        self.assert_safe(actual)
        self.assertEqual(before, case)

    def test_missing_stale_untrusted_or_unprotected_evidence_blocks(self) -> None:
        for change in (
            {"phase": "unknown"}, {"kill_switch_state": "PAUSED"},
            {"tag_protected": False}, {"tag_protected": None},
            {"evidence_authenticated": False}, {"evidence_authenticated": "true"},
            {"incident_type": "timeout"}, {"affected_factory_sha": "notsha"},
            {"affected_factory_sha": AFFECTED.upper()},
            {"current_v1_sha": "c" * 40}, {"stable_factory_sha": AFFECTED},
            {"stable_factory_sha": None}, {"affected_consumer_runs": []},
            {"stable_consumer_runs": []},
        ):
            with self.subTest(change=change):
                case = _snapshot()
                case.update(change)
                self.assertEqual("BLOCKED", plan_rollback(case)["decision"])
                self.assert_safe(plan_rollback(case))
        for value in (None, [], {}, "", 1):
            with self.subTest(value=value):
                self.assertEqual("BLOCKED", plan_rollback(value)["decision"])

    def test_affected_and_stable_consumer_evidence_must_correlate(self) -> None:
        variants = []
        x = _snapshot(); x["stable_consumer_runs"][0]["repository"] = "pl0n3r/Another"; variants.append(x)
        x = _snapshot(); x["stable_consumer_runs"][0]["workflow"] = "Other"; variants.append(x)
        x = _snapshot(); x["stable_consumer_runs"][0]["run_id"] = 201; variants.append(x)
        x = _snapshot(); x["stable_consumer_runs"][0]["materialized_jobs"] = False; variants.append(x)
        x = _snapshot(); x["affected_consumer_runs"][0]["run_id"] = True; variants.append(x)
        x = _snapshot(); x["affected_consumer_runs"][0]["authenticated"] = False; variants.append(x)
        x = _snapshot(); x["affected_consumer_runs"][0]["conclusion"] = "failure"; variants.append(x)
        x = _snapshot(); x["stable_consumer_runs"][0]["factory_sha"] = AFFECTED; variants.append(x)
        x = _snapshot(); x["stable_consumer_runs"][0]["debug"] = "unexpected"; variants.append(x)
        x = _snapshot(); x["affected_consumer_runs"].append(copy.deepcopy(x["affected_consumer_runs"][0])); variants.append(x)
        for case in variants:
            with self.subTest(case=case):
                self.assertEqual("BLOCKED", plan_rollback(case)["decision"])

    def test_no_mutations_live_and_postrollback_requirement(self) -> None:
        case = _snapshot()
        case["phase"] = "live"
        before = copy.deepcopy(case)
        result = plan_rollback(case)
        self.assertEqual("HUMAN_GATE_REQUIRED", result["decision"])
        self.assert_safe(result)
        self.assertEqual(before, case)
        self.assertEqual(3, len(result["postrollback_verification_required"]))
        case["unknown_extra_control"] = True
        blocked = plan_rollback(case)
        self.assertEqual("BLOCKED", blocked["decision"])
        self.assertIsNone(blocked["proposed_stable_sha"])
        self.assert_safe(blocked)


if __name__ == "__main__":
    unittest.main()
