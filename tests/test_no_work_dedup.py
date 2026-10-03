#!/usr/bin/env python3
"""Regresiones de deduplicación NO_WORK global (Factory#904)."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts.no_work_dedup import (
    CANONICAL_SINK,
    NoWorkInventoryError,
    NoWorkPublicationState,
    decide_no_work,
    inventory_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]
REPOS = (
    "Factory",
    "Condor",
    "GrindFlow",
    "brvtal",
    "ControlBot",
    "AutoFactory",
    "FactoryRunner",
)


def repo_state() -> dict[str, object]:
    return {
        "available": [],
        "recovery": [],
        "reservations": [],
        "blockers": [],
        "pull_requests": [],
    }


def inventory() -> dict[str, object]:
    repos = {name: repo_state() for name in REPOS}
    repos["Factory"]["blockers"] = [{"issue": 860, "reason": "human-gate"}]
    repos["ControlBot"]["reservations"] = [
        {
            "issue": 634,
            "reservation_id": "lease-634",
            "owner": "pl0n3r",
            "branch": "trabajo/issue-634",
            "active": True,
        }
    ]
    repos["Condor"]["pull_requests"] = [
        {"number": 448, "state": "open", "head_sha": "a" * 40}
    ]
    return {
        "kill_switch": {"state": "RUNNING", "owner": "pl0n3r"},
        "repositories": repos,
        "observed_at": "ignored-by-fingerprint",
    }


def state_after(
    decision,
    *,
    comment_id: int,
    published_at: int,
) -> NoWorkPublicationState:
    return NoWorkPublicationState(
        comment_id=comment_id,
        fingerprint=decision.fingerprint,
        published_at=published_at,
    )


class NoWorkDedupTests(unittest.TestCase):
    def test_ten_identical_cycles_create_one_comment(self):
        snapshot = inventory()
        previous = None
        actions: list[str] = []
        comment_ids: list[int | None] = []

        for cycle in range(10):
            now = 1_000 + cycle * 60
            decision = decide_no_work(snapshot, previous, now)
            actions.append(decision.action)
            comment_ids.append(decision.comment_id)
            if decision.action == "create":
                previous = state_after(
                    decision,
                    comment_id=904_001,
                    published_at=now,
                )
            elif decision.action == "update":
                previous = state_after(
                    decision,
                    comment_id=previous.comment_id,
                    published_at=now,
                )

        self.assertEqual(actions.count("create"), 1)
        self.assertEqual(actions.count("update"), 0)
        self.assertEqual(actions.count("omit"), 9)
        self.assertEqual(comment_ids[1:], [904_001] * 9)
        self.assertEqual(decision.sink, CANONICAL_SINK)

        refresh = decide_no_work(snapshot, previous, 1_000 + 30 * 60)
        self.assertEqual(
            (refresh.action, refresh.comment_id, refresh.reason),
            ("update", 904_001, "refresh_interval_elapsed"),
        )

    def test_inventory_change_updates_same_canonical_comment(self):
        base = inventory()
        first = decide_no_work(base, None, 10_000)
        previous = state_after(first, comment_id=904_777, published_at=10_000)

        changed = inventory()
        changed["repositories"]["FactoryRunner"]["available"] = [905]
        decision = decide_no_work(changed, previous, 10_060)

        self.assertEqual(decision.action, "update")
        self.assertEqual(decision.comment_id, 904_777)
        self.assertEqual(decision.reason, "inventory_changed")
        self.assertNotEqual(decision.fingerprint, previous.fingerprint)

    def test_fingerprint_tracks_queue_leases_prs_and_kill_switch(self):
        base = inventory()
        base_fingerprint = inventory_fingerprint(base)

        incidental = inventory()
        incidental["observed_at"] = "different"
        incidental["kill_switch"]["owner"] = "ignored-after-canonical-validation"
        incidental["repositories"]["Condor"]["pull_requests"][0]["title"] = "noise"
        incidental["repositories"]["Condor"]["pull_requests"][0]["updated_at"] = "noise"
        self.assertEqual(inventory_fingerprint(incidental), base_fingerprint)

        mutations = []

        available = inventory()
        available["repositories"]["Factory"]["available"] = [904]
        mutations.append(available)

        recovery = inventory()
        recovery["repositories"]["brvtal"]["recovery"] = [700]
        mutations.append(recovery)

        lease = inventory()
        lease["repositories"]["ControlBot"]["reservations"][0]["reservation_id"] = "lease-new"
        mutations.append(lease)

        blocker = inventory()
        blocker["repositories"]["Factory"]["blockers"][0]["reason"] = "other-gate"
        mutations.append(blocker)

        pr_head = inventory()
        pr_head["repositories"]["Condor"]["pull_requests"][0]["head_sha"] = "b" * 40
        mutations.append(pr_head)

        switch = inventory()
        switch["kill_switch"]["state"] = "PAUSED"
        mutations.append(switch)

        for changed in mutations:
            with self.subTest(changed=changed):
                self.assertNotEqual(
                    inventory_fingerprint(changed),
                    base_fingerprint,
                )

        incomplete = inventory()
        del incomplete["repositories"]["AutoFactory"]
        with self.assertRaises(NoWorkInventoryError):
            inventory_fingerprint(incomplete)

    def test_plan_routes_global_no_work_to_factory_904(self):
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("Factory#904", plan)
        self.assertIn("scripts/no_work_dedup.py", plan)
        self.assertIn("create | update | omit", plan)
        self.assertIn("30 min", plan)
        self.assertIn("no se publican nuevos", plan)
        self.assertIn("NO_WORK", plan)

    def test_measurement_caps_new_comments_for_unchanged_inventory(self):
        snapshot = inventory()
        first = decide_no_work(snapshot, None, 0)
        previous = state_after(first, comment_id=904_123, published_at=0)

        decisions = [first]
        for now in (60, 120, 1_799, 1_800, 1_801, 3_600, 3_601):
            decision = decide_no_work(snapshot, previous, now)
            decisions.append(decision)
            if decision.action == "update":
                previous = state_after(
                    decision,
                    comment_id=previous.comment_id,
                    published_at=now,
                )

        self.assertEqual(
            sum(decision.action == "create" for decision in decisions),
            1,
        )
        self.assertTrue(
            all(
                decision.comment_id == 904_123
                for decision in decisions[1:]
                if decision.action in {"update", "omit"}
            )
        )
        self.assertEqual(
            sum(decision.action == "update" for decision in decisions),
            2,
        )


if __name__ == "__main__":
    unittest.main()
