"""Criterios ejecutables del diagnóstico puro de salud de cola Factory #1098."""
from __future__ import annotations

import copy
import json
import unittest

from scripts.salud_cola import QueueHealthError, REPOSITORIES, diagnose_queue


def inventory(*, capacity=4, remaining=5000, limit=5000):
    rows = []
    for repo in REPOSITORIES:
        rows.append({"name": repo, "complete": True, "open_issues": 1,
                     "counts": {"available": 0, "reserved": 0, "blocked": 1,
                                "planned": 0, "in_review": 0},
                     "blockers": [{"number": 17, "cause": "dependency", "roadmap": True}]})
    return {"version": 1, "repositories": rows, "agent_capacity": capacity,
            "rate_limit": {"remaining": remaining, "limit": limit}}


class SaludColaTests(unittest.TestCase):
    def test_inventory_is_complete_unique_and_validated(self):
        raw = inventory()
        result = diagnose_queue(raw)
        self.assertEqual(set(result["repositories"]), set(REPOSITORIES))
        self.assertEqual(result["open_total"], 7)
        self.assertEqual(result["available_total"], 0)
        for mutate in (
            lambda x: x["repositories"].pop(),
            lambda x: x["repositories"][-1].update(name="Factory"),
            lambda x: x["repositories"][0].update(complete=False),
            lambda x: x["repositories"][0].update(open_issues=2),
            lambda x: x["repositories"][0]["counts"].update(blocked=0),
            lambda x: x["repositories"][0]["blockers"].clear(),
            lambda x: x["repositories"][0]["blockers"][0].update(cause="token=private"),
        ):
            with self.subTest(mutate=mutate):
                bad = inventory()
                mutate(bad)
                with self.assertRaises(QueueHealthError):
                    diagnose_queue(bad)

    def test_queue_empty_capacity_and_unknown_are_distinct(self):
        queue = inventory(capacity=4)
        result = diagnose_queue(queue)
        self.assertEqual(result["state"], "queue_empty")
        self.assertEqual(result["open_total"], 7)
        self.assertFalse(result["publication_allowed"])
        queue["repositories"][0]["counts"].update(available=1, blocked=0)
        queue["repositories"][0]["blockers"] = []
        self.assertEqual(diagnose_queue(queue)["state"], "below_capacity")
        queue["agent_capacity"] = None
        self.assertEqual(diagnose_queue(queue)["state"], "unknown_capacity")
        queue["agent_capacity"] = 1
        self.assertEqual(diagnose_queue(queue)["state"], "healthy")
        queue["agent_capacity"] = 0
        self.assertEqual(diagnose_queue(queue)["state"], "healthy")
        queue["agent_capacity"] = None
        queue["repositories"][0]["counts"].update(available=0, blocked=1)
        queue["repositories"][0]["blockers"] = [{"number": 17, "cause": "unknown", "roadmap": True}]
        self.assertEqual(diagnose_queue(queue)["state"], "queue_empty")

    def test_rate_limit_and_untrusted_inputs_fail_closed(self):
        self.assertEqual(diagnose_queue(inventory(remaining=999))["state"], "budget_deferred")
        self.assertEqual(diagnose_queue(inventory(remaining=1000))["state"], "queue_empty")
        self.assertEqual(diagnose_queue(inventory(remaining=0))["roadmap_candidates"], [])
        for path, value in (("agent_capacity", True), ("agent_capacity", -1),
                            ("rate_limit", {"remaining": 60, "limit": 0}),
                            ("rate_limit", {"remaining": 6000, "limit": 5000}),
                            ("rate_limit", {"remaining": "100", "limit": 5000})):
            with self.subTest(path=path, value=value):
                bad = inventory()
                bad[path] = value
                with self.assertRaises(QueueHealthError):
                    diagnose_queue(bad)
        bad = inventory()
        bad["repositories"][0]["private_token"] = "private-data"
        with self.assertRaises(QueueHealthError):
            diagnose_queue(bad)

    def test_roadmap_candidates_are_grounded_and_bounded(self):
        queue = inventory()
        queue["repositories"][0]["blockers"] = [
            {"number": 109, "cause": "claims", "roadmap": True}
        ]
        queue["repositories"][1]["blockers"][0]["roadmap"] = False
        result = diagnose_queue(queue)
        self.assertEqual(result["roadmap_candidates"][0],
                         {"repository": "Factory", "issue": 109, "cause": "claims"})
        self.assertEqual(len(result["roadmap_candidates"]), 6)
        self.assertNotIn("private", json.dumps(result))
        self.assertTrue(all(set(x) == {"repository", "issue", "cause"}
                            for x in result["roadmap_candidates"]))
        bad = copy.deepcopy(queue)
        bad["repositories"][0]["blockers"].append(bad["repositories"][0]["blockers"][0])
        bad["repositories"][0]["counts"]["blocked"] += 1
        bad["repositories"][0]["open_issues"] += 1
        with self.assertRaises(QueueHealthError):
            diagnose_queue(bad)
        # Bounded, stable output; no input free text is echoed.
        big = inventory()
        for row in big["repositories"]:
            row["blockers"] = [
                {"number": i + 1, "cause": "planned", "roadmap": True}
                for i in range(10)
            ]
            row["counts"]["blocked"] = 10
            row["open_issues"] = 10
        report = diagnose_queue(big)
        self.assertEqual(len(report["roadmap_candidates"]), 32)
        self.assertEqual(report["omitted_candidates"], 38)


if __name__ == "__main__":
    unittest.main()
