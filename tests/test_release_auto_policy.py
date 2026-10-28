"""Regresiones sintéticas para una política de release sin ninguna escritura."""
from __future__ import annotations

import copy
import socket
import subprocess
import unittest
from unittest.mock import patch

from scripts.release_auto_policy import REQUIRED_CHECKS, evaluate

SHA = "a" * 40
PREVIOUS = "b" * 40


def _snapshot() -> dict:
    return {
        "candidate_sha": SHA,
        "observed_main_sha": SHA,
        "published_v1_sha": PREVIOUS,
        "v1_tag_protected": True,
        "evidence_authenticated": True,
        "kill_switch_state": "RUNNING",
        "freeze_active": False,
        "security_veto": False,
        "owner_decision": {
            "option": "A", "candidate_sha": SHA,
            "category": "factory-release", "journal_verified": True, "owner": "pl0n3r",
        },
        "checks": [
            {"name": name, "head_sha": SHA, "status": "completed", "conclusion": "success", "authenticated": True}
            for name in sorted(REQUIRED_CHECKS)
        ],
    }


class ReleaseAutoPolicyTests(unittest.TestCase):
    def assertBlocked(self, changes: dict) -> None:  # noqa: N802 - unittest helper
        snapshot = _snapshot()
        snapshot.update(changes)
        result = evaluate(snapshot)
        self.assertEqual("BLOCKED", result["state"], changes)
        self.assertFalse(result["authorizes_release"])
        self.assertEqual(0, result["mutations"])

    def test_exact_sha_and_owner_authority_required(self) -> None:
        for change in (
            {"candidate_sha": "invalid"},
            {"observed_main_sha": PREVIOUS},
            {"published_v1_sha": SHA},
            {"published_v1_sha": "unknown"},
            {"evidence_authenticated": False},
            {"owner_decision": None},
            {"owner_decision": {**_snapshot()["owner_decision"], "option": "B"}},
            {"owner_decision": {**_snapshot()["owner_decision"], "owner": "not-owner"}},
            {"owner_decision": {**_snapshot()["owner_decision"], "category": "product-direction"}},
            {"owner_decision": {**_snapshot()["owner_decision"], "candidate_sha": PREVIOUS}},
            {"owner_decision": {**_snapshot()["owner_decision"], "journal_verified": False}},
            {"owner_decision": {**_snapshot()["owner_decision"], "extra": True}},
        ):
            with self.subTest(change=change):
                self.assertBlocked(change)
        self.assertEqual("BLOCKED", evaluate(None)["state"])
        self.assertEqual("BLOCKED", evaluate([])["state"])
        self.assertBlocked({"unexpected": "extra"})

    def test_freeze_kill_switch_and_security_veto(self) -> None:
        for change in (
            {"kill_switch_state": "PAUSED"},
            {"kill_switch_state": "UNKNOWN"},
            {"freeze_active": True},
            {"freeze_active": None},
            {"security_veto": True},
            {"security_veto": None},
            {"v1_tag_protected": False},
            {"v1_tag_protected": None},
            {"checks": []},
            {"checks": _snapshot()["checks"][:-1]},
            {"checks": _snapshot()["checks"] * 2},
        ):
            with self.subTest(change=change):
                self.assertBlocked(change)
        for key, value in (
            ("status", "in_progress"), ("conclusion", "failure"),
            ("head_sha", PREVIOUS), ("authenticated", False),
        ):
            case = _snapshot()
            case["checks"][0][key] = value
            with self.subTest(key=key):
                self.assertBlocked({"checks": case["checks"]})
        case = _snapshot()
        case["checks"][0]["extra"] = "bad"
        self.assertBlocked({"checks": case["checks"]})

    def test_offline_no_mutation_and_replay_idempotence(self) -> None:
        case = _snapshot()
        original = copy.deepcopy(case)
        first = evaluate(case)
        self.assertEqual("REVIEW_ONLY", first["state"])
        self.assertEqual("offline_preflight_passed", first["reason"])
        for _ in range(8):
            self.assertEqual(first, evaluate(case))
        self.assertEqual(original, case)
        self.assertFalse(first["authorizes_release"])
        self.assertEqual(0, first["mutations"])

    def test_no_runtime_network_tokens_tags_or_release_mutations(self) -> None:
        case = _snapshot()
        with (patch("builtins.open", side_effect=AssertionError("file I/O")),
              patch.object(socket, "create_connection", side_effect=AssertionError("network")),
              patch.object(subprocess, "run", side_effect=AssertionError("process"))):
            for state in (case, {**case, "freeze_active": True}):
                result = evaluate(state)
                self.assertEqual(0, result["network_calls"])
                self.assertEqual(0, result["release_tag_writes"])
                self.assertEqual(0, result["mutations"])
                self.assertFalse(result["authorizes_release"])
                self.assertTrue(set(result).isdisjoint({"token", "secret", "release_url", "tag_write"}))


if __name__ == "__main__":
    unittest.main()
