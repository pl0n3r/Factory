"""Pruebas sintéticas del evaluador de releases: ningún release se publica."""
from __future__ import annotations

import copy
import unittest

from scripts.release_auto_eligibility import REQUIRED_CHECKS, evaluate

SHA = "a" * 40


def _snapshot() -> dict:
    return {
        "phase": "construccion",
        "kill_switch_state": "RUNNING",
        "release_machinery_changed": False,
        "v1_tag_protected": True,
        "evidence_authenticated": True,
        "main_sha": SHA,
        "observed_main_sha": SHA,
        "published_version": "1.0.38",
        "candidate_version": "1.0.39",
        "checks": [
            {
                "name": name,
                "head_sha": SHA,
                "status": "completed",
                "conclusion": "success",
                "authenticated": True,
            }
            for name in sorted(REQUIRED_CHECKS)
        ],
    }


class ReleaseAutoEligibilityTests(unittest.TestCase):
    def test_construction_all_exact_main_gates_yields_dry_run_only(self) -> None:
        case = _snapshot()
        original = copy.deepcopy(case)
        result = evaluate(case)
        self.assertEqual("DRY_RUN_ELIGIBLE", result["decision"])
        self.assertFalse(result["authorizes_release"])
        self.assertEqual(0, result["mutations"])
        self.assertEqual(original, case)

    def test_live_or_release_machinery_requires_human_gate(self) -> None:
        for change in ({"phase": "live"}, {"release_machinery_changed": True}):
            with self.subTest(change=change):
                case = _snapshot()
                case.update(change)
                result = evaluate(case)
                self.assertEqual("HUMAN_GATE_REQUIRED", result["decision"])
                self.assertFalse(result["authorizes_release"])
                self.assertEqual(0, result["mutations"])

    def test_human_gate_does_not_mask_invalid_snapshot(self) -> None:
        combinations = (
            {"phase": "live", "checks": []},
            {"phase": "live", "observed_main_sha": "b" * 40},
            {"release_machinery_changed": True, "evidence_authenticated": False},
            {"release_machinery_changed": True, "candidate_version": "1.0.38"},
            {"release_machinery_changed": True, "v1_tag_protected": False},
        )
        for changes in combinations:
            with self.subTest(changes=changes):
                case = _snapshot()
                case.update(changes)
                result = evaluate(case)
                self.assertEqual("BLOCKED", result["decision"])
                self.assertFalse(result["authorizes_release"])
                self.assertEqual(0, result["mutations"])

    def test_unknown_stale_failed_or_missing_gate_fails_closed(self) -> None:
        variants = [
            {"phase": "unknown"},
            {"kill_switch_state": "PAUSED"},
            {"evidence_authenticated": False},
            {"main_sha": "invalid"},
            {"observed_main_sha": "b" * 40},
            {"release_machinery_changed": None},
            {"checks": []},
            {"checks": _snapshot()["checks"][:-1]},
            {"checks": _snapshot()["checks"] * 2},
        ]
        for row, name, value in [
            (0, "status", "in_progress"),
            (0, "conclusion", "failure"),
            (0, "authenticated", False),
            (0, "head_sha", "b" * 40),
        ]:
            x = _snapshot()
            x["checks"][row][name] = value
            variants.append({"checks": x["checks"]})
        for change in variants:
            with self.subTest(change=str(change)[:120]):
                case = _snapshot()
                case.update(change)
                result = evaluate(case)
                self.assertEqual("BLOCKED", result["decision"])
                self.assertFalse(result["authorizes_release"])
                self.assertEqual(0, result["mutations"])
        self.assertEqual("BLOCKED", evaluate(None)["decision"])
        self.assertEqual("BLOCKED", evaluate([])["decision"])

    def test_version_and_tag_protection_are_strict(self) -> None:
        for changes in (
            {"v1_tag_protected": False},
            {"v1_tag_protected": None},
            {"candidate_version": "1.0.38"},
            {"candidate_version": "1.0.37"},
            {"candidate_version": "2.0.0"},
            {"candidate_version": "1.0.039"},
            {"candidate_version": "1.0.39-rc.1"},
            {"published_version": "1.0.38-beta"},
            {"published_version": None},
        ):
            with self.subTest(changes=changes):
                case = _snapshot()
                case.update(changes)
                result = evaluate(case)
                self.assertEqual("BLOCKED", result["decision"])
                self.assertFalse(result["authorizes_release"])


if __name__ == "__main__":
    unittest.main()
