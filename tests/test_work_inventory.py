#!/usr/bin/env python3
import unittest
from scripts.work_inventory import (
    CANONICAL_REPOSITORIES, classify_project_state, controlbot_projection,
    detect_unmaterialized_executable_work, initial_sweep_artifact,
    parent_progress, remaining_work_summary,
)


def leaf(key, status, evidence="issue:1", source=None):
    return {"key": key, "source_key": source or key, "status": status, "evidence_ref": evidence}


def narrative(key, classification, evidence="roadmap:1"):
    return {"source_key": key, "classification": classification, "evidence_ref": evidence}


class WorkInventoryTests(unittest.TestCase):
    def test_project_state_is_classified_deterministically(self):
        cases = (
            ("READY", [leaf("a", "available")], []),
            ("ALL_BLOCKED", [leaf("a", "blocked")], []),
            ("UNMATERIALIZED_WORK", [], [narrative("a", "leaf_ready")]),
            ("WAITING_DECISION", [], [narrative("a", "decision_required")]),
            ("LIVE_GATED", [], [narrative("a", "live_only")]),
            ("NO_WORK", [], [narrative("a", "future_idea")]),
        )
        for expected, leaves, narrative_rows in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_project_state(leaves, narrative_rows), expected)

    def test_detects_unmaterialized_executable_work_without_duplicates(self):
        rows = [narrative("existing", "leaf_ready"), narrative("new", "leaf_ready")]
        hidden = detect_unmaterialized_executable_work(
            rows, [leaf("issue-9", "blocked", source="existing")]
        )
        self.assertEqual([row["source_key"] for row in hidden], ["new"])

    def test_all_automatic_projects_expose_remaining_work_summary(self):
        projects = {repo: {"leaves": [], "narrative": [narrative(repo, "future_idea", f"{repo}#roadmap")]}
                    for repo in CANONICAL_REPOSITORIES}
        artifact = initial_sweep_artifact(projects, "2026-10-01T22:20:00Z")
        self.assertEqual(set(artifact["projects"]), set(CANONICAL_REPOSITORIES))
        self.assertTrue(all("counts" in row and "next_work" in row
                            for row in artifact["projects"].values()))

    def test_parent_progress_is_derived_from_children_without_duplicate_checklist_state(self):
        result = parent_progress([
            leaf("a", "completed"), leaf("b", "completed"), leaf("c", "blocked")
        ])
        self.assertEqual(result, {"completed": 2, "total": 3, "percent": 66})
        self.assertNotIn("checklist", result)

    def test_controlbot_projection_reuses_canonical_inventory(self):
        projects = {repo: {"leaves": [leaf(repo, "blocked", f"{repo}#1")], "narrative": []}
                    for repo in CANONICAL_REPOSITORIES}
        artifact = initial_sweep_artifact(projects, "2026-10-01T22:20:00Z")
        projection = controlbot_projection(artifact)
        self.assertIs(projection["projects"], artifact["projects"])

    def test_initial_sweep_evidence_covers_all_automatic_projects(self):
        projects = {repo: {"leaves": [leaf(repo, "completed", f"{repo}#evidence")], "narrative": []}
                    for repo in CANONICAL_REPOSITORIES}
        artifact = initial_sweep_artifact(projects, "2026-10-01T22:20:00Z")
        self.assertEqual(len(artifact["projects"]), 7)
        for repo, summary in artifact["projects"].items():
            self.assertEqual(summary["evidence_refs"], [f"{repo}#evidence"])


if __name__ == "__main__":
    unittest.main()
