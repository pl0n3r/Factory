#!/usr/bin/env python3
"""Regresiones del pin de aceptación al cerrar reservas de PR."""

from __future__ import annotations

import unittest

from scripts import coordinar_trabajo as coordinator


OWNER = "pl0n3r"
BRANCH = "trabajo/issue-655"
RID = "72210439-1337-4656-99cf-51b465d1c45d"
PIN = "d" * 64
TASK_PIN = "e" * 64


class FakeApi:
    def __init__(self) -> None:
        self.comments: list[dict] = []
        self.statuses: list[str] = []

    def comment(self, _issue_number: int, body: str) -> None:
        self.comments.append({
            "user": {"login": coordinator.TRUSTED_MARKER_LOGIN},
            "body": body,
        })

    def issue_comments(self, _issue_number: int) -> list[dict]:
        return list(self.comments)

    def delete_branch(self, _branch: str) -> None:
        pass

    def try_unassign(self, _issue_number: int, _owner: str) -> None:
        pass

    def issue(self, _issue_number: int) -> dict:
        return {"state": "open", "labels": []}

    def set_status(self, _issue_number: int, status: str) -> None:
        self.statuses.append(status)


def current_v2() -> dict:
    return {
        "version": 2,
        "owner": OWNER,
        "reservation_id": RID,
        "branch": BRANCH,
        "active": True,
        "reason": "tomar",
        "acceptance_sha256": PIN,
    }


def current_v3() -> dict:
    value = current_v2()
    value.update({
        "version": 3,
        "task_marker_sha256": TASK_PIN,
        "task_paths": ["scripts/coordinar_trabajo.py"],
        "task_depends_on": [],
    })
    return value


class AcceptancePinHistoryTests(unittest.TestCase):
    def _close(self, current: dict, *, merged: bool) -> tuple[FakeApi, dict]:
        api = FakeApi()
        coordinator.close_pr_reservation(
            api,
            655,
            BRANCH,
            {"merged": merged},
            current,
        )
        latest = coordinator.latest_reservation(api.comments)
        self.assertIsNotNone(latest)
        return api, latest

    def test_merged_v2_terminal_preserves_acceptance_pin(self) -> None:
        _api, latest = self._close(current_v2(), merged=True)
        self.assertEqual(latest["version"], 2)
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "pr-merged")
        self.assertEqual(latest["acceptance_sha256"], PIN)
        self.assertEqual(latest["reservation_id"], RID)
        self.assertEqual(latest["branch"], BRANCH)
        self.assertEqual(latest["owner"], OWNER)

    def test_merged_terminal_remains_inactive(self) -> None:
        api, latest = self._close(current_v2(), merged=True)
        self.assertFalse(latest["active"])
        self.assertIsNone(coordinator.active_reservation(api, 655))

    def test_merged_v3_terminal_preserves_task_snapshot(self) -> None:
        _api, latest = self._close(current_v3(), merged=True)
        self.assertEqual(latest["version"], 3)
        self.assertEqual(latest["acceptance_sha256"], PIN)
        self.assertEqual(latest["task_marker_sha256"], TASK_PIN)
        self.assertEqual(
            latest["task_paths"],
            ["scripts/coordinar_trabajo.py"],
        )
        self.assertEqual(latest["task_depends_on"], [])

    def test_legacy_terminal_remains_unpinned(self) -> None:
        legacy = {
            "version": 1,
            "owner": OWNER,
            "reservation_id": RID,
            "branch": BRANCH,
            "active": True,
            "reason": "tomar",
        }
        _api, latest = self._close(legacy, merged=True)
        self.assertEqual(latest["version"], 1)
        self.assertNotIn("acceptance_sha256", latest)

    def test_unmerged_close_does_not_preserve_pin(self) -> None:
        _api, latest = self._close(current_v3(), merged=False)
        self.assertEqual(latest["version"], 1)
        self.assertFalse(latest["active"])
        self.assertEqual(latest["reason"], "pr-cerrado-sin-merge")
        self.assertNotIn("acceptance_sha256", latest)
        self.assertNotIn("task_marker_sha256", latest)


if __name__ == "__main__":
    unittest.main()
