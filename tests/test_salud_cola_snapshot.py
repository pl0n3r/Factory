"""Tests sin I/O del adaptador de snapshots de salud de cola #1100."""
from __future__ import annotations

import copy
import json
import unittest

from scripts.salud_cola_snapshot import (
    REPOSITORIES, SnapshotError, assemble_inventory,
)


def issue(number, label, *, blocker=None, pull_request=False):
    return {"number": number, "labels": [label] if label else [],
            "pull_request": pull_request, "blocker": blocker}


def reports():
    return [{"name": name, "pages": [{"page_number": 1, "issues": [],
                                         "has_next": False}]}
            for name in REPOSITORIES]


class SaludColaSnapshotTests(unittest.TestCase):
    def test_seven_repositories_and_terminal_pagination_required(self):
        sample = reports()
        result = assemble_inventory(sample, None, {"limit": 5000, "remaining": 5000})
        self.assertEqual(result["version"], 1)
        self.assertEqual([r["name"] for r in result["repositories"]], list(REPOSITORIES))
        self.assertTrue(all(r["complete"] for r in result["repositories"]))
        for mutate in (
            lambda x: x.pop(),
            lambda x: x[-1].update(name="Factory"),
            lambda x: x[0].update(name="unlisted"),
            lambda x: x[0].update(pages=[]),
            lambda x: x[0]["pages"][0].update(has_next=True),
            lambda x: x[0].update(pages=[{"page_number": 1, "issues": [], "has_next": False},
                                          {"page_number": 2, "issues": [], "has_next": False}]),
            lambda x: x[0].update(pages=[{"page_number": 1, "issues": [], "has_next": True},
                                          {"page_number": 2, "issues": [], "has_next": True}]),
            # A missing page 2 cannot be hidden between pages 1 and 3.
            lambda x: x[0].update(pages=[{"page_number": 1, "issues": [], "has_next": True},
                                          {"page_number": 3, "issues": [], "has_next": False}]),
            lambda x: x[0]["pages"][0].update(page_number=2),
            lambda x: x[0]["pages"][0].update(page_number=0),
            lambda x: x[0]["pages"][0].update(page_number=True),
            lambda x: x[0]["pages"][0].pop("page_number"),
        ):
            with self.subTest(mutate=mutate):
                raw = reports()
                mutate(raw)
                with self.assertRaises(SnapshotError):
                    assemble_inventory(raw, 4, {"limit": 5000, "remaining": 4000})

        raw = reports()
        raw[0]["pages"] = [
            {"page_number": 1, "issues": [issue(1, "estado: disponible")],
             "has_next": True},
            {"page_number": 2, "issues": [issue(2, "status: blocked")],
             "has_next": False},
        ]
        data = assemble_inventory(raw, 4, {"limit": 5000, "remaining": 4000})
        self.assertEqual(data["repositories"][0]["open_issues"], 2)

    def test_issue_state_mapping_and_pr_exclusion(self):
        raw = reports()
        raw[0]["pages"] = [{
            "page_number": 1,
            "has_next": False,
            "issues": [
                issue(1, "estado: disponible"),
                issue(2, "status: reserved"),
                issue(3, "estado: bloqueado"),
                issue(4, "status: planned"),
                issue(5, "status: in review"),
                issue(6, None, pull_request=True),
            ],
        }]
        data = assemble_inventory(raw, 2, {"limit": 5000, "remaining": 5000})
        row = data["repositories"][0]
        self.assertEqual(row["open_issues"], 5)
        self.assertEqual(row["counts"],
                         {"available": 1, "reserved": 1, "blocked": 1,
                          "planned": 1, "in_review": 1})
        self.assertEqual(row["blockers"],
                         [{"number": 3, "cause": "unknown", "roadmap": False}])
        variants = [
            lambda x: x["pages"][0]["issues"].append(issue(1, "status: available")),
            lambda x: x["pages"][0]["issues"][0].update(labels=[]),
            lambda x: x["pages"][0]["issues"][0].update(
                labels=["estado: disponible", "status: available"]),
            lambda x: x["pages"][0]["issues"][0].update(
                labels=["estado: disponible", "estado: bloqueado"]),
            lambda x: x["pages"][0]["issues"][0].update(labels=["status: snoozed"]),
            lambda x: x["pages"][0]["issues"][0].update(
                labels=["estado: requiere recuperación"]),
            lambda x: x["pages"][0]["issues"][0].update(
                labels=["status: recovery required"]),
            lambda x: x["pages"][0]["issues"][0].update(labels=["estado: disponible"] * 2),
            lambda x: x["pages"][0]["issues"][0].update(pull_request="false"),
        ]
        for mutate in variants:
            with self.subTest(mutate=mutate):
                broken = copy.deepcopy(raw)
                mutate(broken[0])
                with self.assertRaises(SnapshotError):
                    assemble_inventory(broken, 2, {"limit": 5000, "remaining": 5000})

    def test_missing_blocker_evidence_is_unknown_and_private_fields_excluded(self):
        raw = reports()
        raw[0]["pages"][0]["issues"] = [
            issue(11, "estado: bloqueado"),
            issue(12, "status: blocked",
                  blocker={"cause": "claims", "roadmap": True}),
        ]
        data = assemble_inventory(raw, 4, {"limit": 5000, "remaining": 1000})
        self.assertEqual(data["repositories"][0]["blockers"], [
            {"number": 11, "cause": "unknown", "roadmap": False},
            {"number": 12, "cause": "claims", "roadmap": True},
        ])
        self.assertNotIn("password", json.dumps(data))
        # A typed cause does not grant permission to promote uncertain work.
        for cause in ("unknown", "human_gate", "planned"):
            with self.subTest(unpromotable_cause=cause):
                broken = copy.deepcopy(raw)
                broken[0]["pages"][0]["issues"][0]["blocker"] = {
                    "cause": cause, "roadmap": True}
                with self.assertRaisesRegex(SnapshotError, "invalid_blocker"):
                    assemble_inventory(broken, 4, {"limit": 5000, "remaining": 1000})
        for change in (
            lambda i: i.update(body="password=PRIVATE"),
            lambda i: i.update(blocker={"cause": "token=PRIVATE", "roadmap": True}),
            lambda i: i.update(blocker={"cause": "dependency", "roadmap": "true"}),
            lambda i: i.update(blocker={"cause": "dependency", "roadmap": True,
                                        "private_id": "secret"}),
        ):
            with self.subTest(change=change):
                broken = copy.deepcopy(raw)
                change(broken[0]["pages"][0]["issues"][0])
                with self.assertRaises(SnapshotError):
                    assemble_inventory(broken, 4, {"limit": 5000, "remaining": 1000})
        broken = copy.deepcopy(raw)
        broken[0]["pages"][0]["issues"][0]["labels"] = ["estado: disponible"]
        with self.assertRaises(SnapshotError):
            # Non-blocked has no blocker; an ordinary row is valid,
            # but the second row still proves strict evidence separation.
            broken[0]["pages"][0]["issues"][0]["blocker"] = {
                "cause": "claims", "roadmap": True}
            assemble_inventory(broken, 4, {"limit": 5000, "remaining": 1000})

    def test_adapter_shape_capacity_budget_and_size_fail_closed(self):
        raw = reports()
        data = assemble_inventory(raw, None, {"limit": 5000, "remaining": 999})
        self.assertEqual(set(data), {"version", "repositories",
                                      "agent_capacity", "rate_limit"})
        self.assertIsNone(data["agent_capacity"])
        self.assertEqual(data["rate_limit"]["remaining"], 999)
        self.assertEqual(set(data["repositories"][0]),
                         {"name", "complete", "open_issues", "counts", "blockers"})
        for capacity in (True, -1, "4", 1001):
            with self.subTest(capacity=capacity), self.assertRaises(SnapshotError):
                assemble_inventory(raw, capacity, {"limit": 5000, "remaining": 2000})
        for budget in (None, {}, {"limit": 0, "remaining": 0},
                       {"limit": 5000, "remaining": 6000},
                       {"limit": 5000, "remaining": True},
                       {"limit": 5000, "remaining": 5, "token": "SECRET"}):
            with self.subTest(budget=budget), self.assertRaises(SnapshotError):
                assemble_inventory(raw, 3, budget)
        raw[0]["pages"][0]["issues"] = [
            issue(i + 1, "estado: reservado") for i in range(101)
        ]
        with self.assertRaises(SnapshotError):
            assemble_inventory(raw, 3, {"limit": 5000, "remaining": 3000})


if __name__ == "__main__":
    unittest.main()
