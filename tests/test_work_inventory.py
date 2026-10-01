import json
import unittest
from pathlib import Path

from scripts.work_inventory import (
    CANONICAL_REPOSITORIES,
    WorkInventoryError,
    build_factory_inventory,
    controlbot_projection,
    project_inventory,
    validate_initial_sweep,
)

ROOT = Path(__file__).resolve().parents[1]


def snapshot(repo, *, leaves=None, narrative=None):
    return {"repository_ref": repo, "leaves": leaves or [], "narrative": narrative or []}


def leaf(key, state="available", *, parent=None, identity=None, priority="medium"):
    row = {
        "key": key,
        "title": key,
        "state": state,
        "priority": priority,
        "source_refs": [f"issue:{key}"],
    }
    if parent:
        row["parent_ref"] = parent
    if identity:
        row["source_identity"] = identity
    return row


def narrative(identity, kind="executable", *, leaf_key=None):
    row = {
        "identity": identity,
        "title": identity,
        "kind": kind,
        "source_ref": f"roadmap:{identity}",
    }
    if leaf_key:
        row["expected_leaf_key"] = leaf_key
    return row


class WorkInventoryTests(unittest.TestCase):
    def test_project_state_is_classified_deterministically(self):
        repo = "pl0n3r/Factory"
        cases = (
            (snapshot(repo, leaves=[leaf("a")]), "READY"),
            (snapshot(repo, leaves=[leaf("a", "blocked")]), "ALL_BLOCKED"),
            (snapshot(repo, narrative=[narrative("hidden")]), "UNMATERIALIZED_WORK"),
            (snapshot(repo, narrative=[narrative("decision", "decision_required")]), "WAITING_DECISION"),
            (snapshot(repo, narrative=[narrative("live", "live_only")]), "LIVE_GATED"),
            (snapshot(repo, leaves=[leaf("done", "completed")]), "NO_WORK"),
        )
        for source, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(project_inventory(source)["state"], expected)

    def test_detects_unmaterialized_executable_work_without_duplicates(self):
        source = snapshot(
            "pl0n3r/Factory",
            leaves=[leaf("Factory#10", identity="roadmap:a")],
            narrative=[
                narrative("roadmap:a", leaf_key="Factory#10"),
                narrative("roadmap:b"),
            ],
        )
        result = project_inventory(source)
        self.assertEqual(result["counts"]["already_materialized"], 1)
        self.assertEqual(result["counts"]["unmaterialized"], 1)
        self.assertEqual(result["unmaterialized_identities"], ["roadmap:b"])

    def test_all_automatic_projects_expose_remaining_work_summary(self):
        sources = [
            snapshot(repo, leaves=[leaf(f"{repo}#next")])
            for repo in CANONICAL_REPOSITORIES
        ]
        result = build_factory_inventory(list(reversed(sources)))
        self.assertEqual(
            [p["repository_ref"] for p in result["projects"]],
            list(CANONICAL_REPOSITORIES),
        )
        self.assertTrue(
            all(p["counts"]["available"] == 1 and p["next_work"] for p in result["projects"])
        )

    def test_parent_progress_is_derived_from_children_without_duplicate_checklist_state(self):
        result = project_inventory(
            snapshot(
                "pl0n3r/Factory",
                leaves=[
                    leaf("Factory#1", "completed", parent="Factory#parent"),
                    leaf("Factory#2", "blocked", parent="Factory#parent"),
                ],
                narrative=[narrative("parent-checklist", "future_idea")],
            )
        )
        self.assertEqual(
            result["parent_progress"],
            [{"parent_ref": "Factory#parent", "completed": 1, "total": 2, "percent": 50}],
        )

    def test_controlbot_projection_reuses_canonical_inventory(self):
        inventory = build_factory_inventory(
            [snapshot(repo) for repo in CANONICAL_REPOSITORIES]
        )
        self.assertIs(controlbot_projection(inventory), inventory)

    def test_fail_closed_validation_paths_are_covered(self):
        bad_snapshots = [
            {"repository_ref": "pl0n3r/Factory", "leaves": []},
            snapshot("other/repo"),
            snapshot("pl0n3r/Factory", leaves=[leaf("dup"), leaf("dup")]),
            snapshot(
                "pl0n3r/Factory",
                narrative=[narrative("dup"), narrative("dup")],
            ),
        ]
        for source in bad_snapshots:
            with self.subTest(source=source), self.assertRaises(WorkInventoryError):
                project_inventory(source)

        incomplete = [snapshot(repo) for repo in CANONICAL_REPOSITORIES[:-1]]
        with self.assertRaises(WorkInventoryError):
            build_factory_inventory(incomplete)
        with self.assertRaises(WorkInventoryError):
            controlbot_projection({"version": 1, "projects": []})

    def test_reserved_priority_and_future_idea_are_deterministic(self):
        result = project_inventory(
            snapshot(
                "pl0n3r/Factory",
                leaves=[
                    leaf("Factory#medium", "reserved", priority="medium"),
                    leaf("Factory#critical", "available", priority="critical"),
                ],
                narrative=[narrative("later", "future_idea")],
            )
        )
        self.assertEqual(result["state"], "READY")
        self.assertEqual(result["next_work"], "Factory#critical")
        self.assertEqual(result["counts"]["future_idea"], 1)

        future_only = project_inventory(
            snapshot(
                "pl0n3r/Factory",
                narrative=[narrative("later-only", "future_idea")],
            )
        )
        self.assertEqual(future_only["state"], "UNMATERIALIZED_WORK")

    def test_initial_sweep_rejects_missing_sources_and_wrong_order(self):
        payload = json.loads(
            (ROOT / "config" / "work_inventory_initial.json").read_text(encoding="utf-8")
        )
        missing_source = json.loads(json.dumps(payload))
        missing_source["projects"][0]["source_refs"] = []
        with self.assertRaises(WorkInventoryError):
            validate_initial_sweep(missing_source)

        wrong_order = json.loads(json.dumps(payload))
        wrong_order["projects"][0], wrong_order["projects"][1] = (
            wrong_order["projects"][1],
            wrong_order["projects"][0],
        )
        with self.assertRaises(WorkInventoryError):
            validate_initial_sweep(wrong_order)

    def test_initial_sweep_evidence_covers_all_automatic_projects(self):
        payload = json.loads(
            (ROOT / "config" / "work_inventory_initial.json").read_text(encoding="utf-8")
        )
        validate_initial_sweep(payload)
        self.assertEqual(
            [row["repository_ref"] for row in payload["projects"]],
            list(CANONICAL_REPOSITORIES),
        )
        self.assertTrue(all(row["source_refs"] for row in payload["projects"]))


if __name__ == "__main__":
    unittest.main()
