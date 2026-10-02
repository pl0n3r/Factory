#!/usr/bin/env python3
import unittest

from scripts.dispatch_inventory import dispatch_record_with_inventory
from scripts.dispatcher_v2 import Candidate
from scripts.work_inventory import (
    CANONICAL_REPOSITORIES,
    WorkInventoryError,
    build_factory_inventory,
    controlbot_projection,
)


def _leaf(key, state, *, priority="medium"):
    return {
        "key": key,
        "title": key,
        "state": state,
        "priority": priority,
        "source_refs": [f"issue:{key}"],
    }


def _inventory(factory_state):
    snapshots = []
    for repo in CANONICAL_REPOSITORIES:
        leaves = [_leaf(f"{repo}#done", "completed")]
        narrative = []
        if repo == "pl0n3r/Factory":
            if factory_state == "ALL_BLOCKED":
                leaves = [_leaf("Factory#blocked", "blocked", priority="critical")]
            elif factory_state == "UNMATERIALIZED_WORK":
                leaves = []
                narrative = [{
                    "identity": "roadmap:factory:hidden",
                    "title": "Trabajo narrativo ejecutable",
                    "kind": "executable",
                    "source_ref": "roadmap:Factory",
                }]
            elif factory_state == "WAITING_DECISION":
                leaves = []
                narrative = [{
                    "identity": "decision:factory:pending",
                    "title": "Decisión pendiente",
                    "kind": "decision_required",
                    "source_ref": "decision:Factory",
                }]
            elif factory_state == "LIVE_GATED":
                leaves = []
                narrative = [{
                    "identity": "live:factory:gated",
                    "title": "Trabajo reservado para live",
                    "kind": "live_only",
                    "source_ref": "live:Factory",
                }]
            elif factory_state == "NO_WORK":
                leaves = [_leaf("Factory#done", "completed")]
            elif factory_state == "READY":
                leaves = [_leaf("Factory#ready", "available", priority="critical")]
            else:
                raise AssertionError(factory_state)
        snapshots.append({
            "repository_ref": repo,
            "leaves": leaves,
            "narrative": narrative,
        })
    return build_factory_inventory(snapshots)


class DispatcherV2Tests(unittest.TestCase):
    def test_dispatch_distinguishes_blocked_unmaterialized_and_no_work(self):
        expected_actions = {
            "ALL_BLOCKED": "inventory_state",
            "UNMATERIALIZED_WORK": "materialize_inventory",
            "NO_WORK": "inventory_state",
        }
        for expected, expected_step in expected_actions.items():
            with self.subTest(expected=expected):
                inventory = _inventory(expected)
                record = dispatch_record_with_inventory(
                    [],
                    work_inventory=inventory,
                )
                handoff = record["inventory_no_candidate"]
                self.assertIsNone(record["selected"])
                self.assertEqual(
                    handoff["project_states"]["pl0n3r/Factory"],
                    expected,
                )
                self.assertEqual(handoff["fallback_state"], expected)
                self.assertIn(expected, handoff["states_present"])
                self.assertEqual(record["next_action"]["step"], expected_step)
                self.assertEqual(record["next_action"]["reason"], expected)
                self.assertNotEqual(
                    record["next_action"]["step"],
                    "declare_idle_reason",
                )

    def test_inventory_state_never_preempts_ready_candidate(self):
        inventory = _inventory("ALL_BLOCKED")
        record = dispatch_record_with_inventory(
            [Candidate(key="Factory#ready", priority="critical")],
            work_inventory=inventory,
        )
        self.assertEqual(record["selected"], "Factory#ready")
        self.assertEqual(record["selected_class"], "critical")
        self.assertIsNone(record["inventory_no_candidate"])
        self.assertEqual(record["next_action"]["work"]["key"], "Factory#ready")

    def test_dispatch_exposes_canonical_work_inventory_projection(self):
        inventory = _inventory("NO_WORK")
        record = dispatch_record_with_inventory([], work_inventory=inventory)
        self.assertIs(record["work_inventory"], inventory)
        self.assertIs(controlbot_projection(record["work_inventory"]), inventory)

    def test_ready_inventory_without_dispatch_candidate_fails_closed(self):
        with self.assertRaisesRegex(WorkInventoryError, "READY"):
            dispatch_record_with_inventory(
                [],
                work_inventory=_inventory("READY"),
            )

    def test_human_or_live_inventory_states_never_materialize(self):
        for state in ("WAITING_DECISION", "LIVE_GATED"):
            with self.subTest(state=state):
                record = dispatch_record_with_inventory(
                    [],
                    work_inventory=_inventory(state),
                )
                self.assertEqual(record["next_action"]["step"], "inventory_state")
                self.assertEqual(record["next_action"]["reason"], state)


if __name__ == "__main__":
    unittest.main()
