#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from scripts.dispatch_inventory import dispatch_record_with_inventory
from scripts.dispatcher_v2 import Candidate
from scripts.work_inventory import (
    CANONICAL_REPOSITORIES,
    PROJECT_STATES,
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
            elif factory_state == "FUTURE_ONLY":
                leaves = []
                narrative = [{
                    "identity": "roadmap:factory:future",
                    "title": "Idea futura sin contrato ejecutable",
                    "kind": "future_idea",
                    "source_ref": "roadmap:Factory",
                }]
            elif factory_state == "NO_WORK":
                leaves = [_leaf("Factory#done", "completed")]
            elif factory_state == "WAITING_DECISION":
                leaves = []
                narrative = [{
                    "identity": "decision:factory:owner",
                    "title": "Decisión humana pendiente",
                    "kind": "decision_required",
                    "source_ref": "issue:Factory#decision",
                }]
            elif factory_state == "LIVE_GATED":
                leaves = []
                narrative = [{
                    "identity": "live:factory:release",
                    "title": "Trabajo reservado para live",
                    "kind": "live_only",
                    "source_ref": "issue:Factory#live",
                }]
            elif factory_state == "READY":
                leaves = [_leaf("Factory#ready", "available", priority="critical")]
            elif factory_state == "RESERVED_ONLY":
                leaves = [_leaf("Factory#reserved", "reserved", priority="critical")]
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
        for expected in ("ALL_BLOCKED", "UNMATERIALIZED_WORK", "NO_WORK"):
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
                self.assertIn(expected, handoff["states_present"])
                action = record["next_action"]
                self.assertEqual(action["state"], expected)
                self.assertFalse(action["mutates"])
                self.assertEqual(
                    action["step"],
                    "materialize_inventory"
                    if expected == "UNMATERIALIZED_WORK"
                    else "inventory_state",
                )
                self.assertEqual(action["project_states"], handoff["project_states"])

    def test_future_only_inventory_never_requests_materialization(self):
        inventory = _inventory("FUTURE_ONLY")
        factory = next(
            project
            for project in inventory["projects"]
            if project["repository_ref"] == "pl0n3r/Factory"
        )
        self.assertEqual(factory["state"], "NO_WORK")
        self.assertEqual(factory["counts"]["future_idea"], 1)
        self.assertIsNone(factory["next_work"])

        record = dispatch_record_with_inventory([], work_inventory=inventory)
        action = record["next_action"]
        self.assertEqual(action["state"], "NO_WORK")
        self.assertEqual(action["step"], "inventory_state")
        self.assertFalse(action["mutates"])
        self.assertNotEqual(action["step"], "materialize_inventory")

        executable = dispatch_record_with_inventory(
            [],
            work_inventory=_inventory("UNMATERIALIZED_WORK"),
        )
        self.assertEqual(executable["next_action"]["step"], "materialize_inventory")

    def test_human_or_live_inventory_states_never_materialize(self):
        for expected in ("WAITING_DECISION", "LIVE_GATED"):
            with self.subTest(expected=expected):
                record = dispatch_record_with_inventory(
                    [],
                    work_inventory=_inventory(expected),
                )
                action = record["next_action"]
                self.assertEqual(action["step"], "inventory_state")
                self.assertEqual(action["state"], expected)
                self.assertFalse(action["mutates"])
                self.assertNotEqual(action["step"], "materialize_inventory")

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
        self.assertEqual(record["next_action"]["state"], "NO_WORK")
        with self.assertRaisesRegex(WorkInventoryError, "READY"):
            dispatch_record_with_inventory(
                [],
                work_inventory=_inventory("READY"),
            )

    def test_ready_inventory_without_dispatch_candidate_fails_closed(self):
        with self.assertRaisesRegex(WorkInventoryError, "READY"):
            dispatch_record_with_inventory(
                [],
                work_inventory=_inventory("READY"),
            )

    def test_reserved_only_ready_inventory_without_candidate_returns_non_mutating_handoff(self):
        record = dispatch_record_with_inventory(
            [],
            work_inventory=_inventory("RESERVED_ONLY"),
        )
        handoff = record["inventory_no_candidate"]
        action = record["next_action"]
        self.assertIsNone(record["selected"])
        self.assertEqual(
            handoff["reserved_only_projects"],
            ("pl0n3r/Factory",),
        )
        self.assertEqual(action["state"], "READY")
        self.assertEqual(action["step"], "reserved_inventory")
        self.assertEqual(action["reason"], "reserved_only_no_selectable_candidate")
        self.assertEqual(
            action["reserved_only_projects"],
            ("pl0n3r/Factory",),
        )
        self.assertFalse(action["session_selectable"])
        self.assertFalse(action["mutates"])

    def test_available_ready_inventory_without_candidate_still_fails_closed(self):
        with self.assertRaisesRegex(
            WorkInventoryError,
            "trabajo disponible sin candidato seleccionado",
        ):
            dispatch_record_with_inventory(
                [],
                work_inventory=_inventory("READY"),
            )

    def test_reserved_only_handoff_preserves_canonical_ready_projection(self):
        inventory = _inventory("RESERVED_ONLY")
        record = dispatch_record_with_inventory([], work_inventory=inventory)
        factory = next(
            project
            for project in record["work_inventory"]["projects"]
            if project["repository_ref"] == "pl0n3r/Factory"
        )
        action = record["next_action"]
        self.assertIs(record["work_inventory"], inventory)
        self.assertEqual(factory["state"], "READY")
        self.assertEqual(factory["counts"]["available"], 0)
        self.assertEqual(factory["counts"]["reserved"], 1)
        self.assertEqual(factory["next_work"], "Factory#reserved")
        self.assertIsNone(record["selected"])
        self.assertFalse(action["session_selectable"])
        self.assertEqual(action["work"]["key"], "factory:work-inventory")
        self.assertNotEqual(action["work"]["key"], factory["next_work"])

    def test_uninterpretable_inventory_state_fails_closed(self):
        inventory = _inventory("NO_WORK")
        for project in inventory["projects"]:
            project["state"] = "UNKNOWN"
        with patch(
            "scripts.dispatch_inventory.PROJECT_STATES",
            PROJECT_STATES | {"UNKNOWN"},
        ):
            with self.assertRaisesRegex(
                WorkInventoryError,
                "no contiene un estado interpretable",
            ):
                dispatch_record_with_inventory([], work_inventory=inventory)


if __name__ == "__main__":
    unittest.main()
