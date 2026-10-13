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
                                "planned": 0, "in_review": 0,
                                "recovery_required": 0},
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
        self.assertEqual(result["reason"], "zero_available")
        self.assertEqual(result["blocked_cause_totals"]["dependency"], 7)
        self.assertEqual(result["repositories"]["Factory"]["blocked_cause_counts"]["dependency"], 1)
        self.assertEqual(result["repositories"]["Factory"]["blocked_reasons"], [
            {"issue": 17, "cause": "dependency", "roadmap": True}
        ])
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
        self.assertFalse(result["can_dispatch"])
        queue["repositories"][0]["counts"].update(available=1, blocked=0)
        queue["repositories"][0]["blockers"] = []
        self.assertEqual(diagnose_queue(queue)["state"], "below_capacity")
        self.assertEqual(diagnose_queue(queue)["reason"], "fewer_ready_than_capacity")
        self.assertTrue(diagnose_queue(queue)["can_dispatch"])
        queue["agent_capacity"] = None
        self.assertEqual(diagnose_queue(queue)["state"], "unknown_capacity")
        self.assertEqual(diagnose_queue(queue)["reason"], "capacity_not_observed")
        self.assertFalse(diagnose_queue(queue)["can_dispatch"])
        queue["agent_capacity"] = 1
        self.assertEqual(diagnose_queue(queue)["state"], "healthy")
        self.assertTrue(diagnose_queue(queue)["can_dispatch"])
        queue["agent_capacity"] = 0
        self.assertEqual(diagnose_queue(queue)["state"], "below_capacity")
        self.assertEqual(diagnose_queue(queue)["reason"], "zero_execution_capacity")
        self.assertFalse(diagnose_queue(queue)["can_dispatch"])
        queue["agent_capacity"] = None
        queue["repositories"][0]["counts"].update(available=0, blocked=1)
        queue["repositories"][0]["blockers"] = [{"number": 17, "cause": "unknown", "roadmap": False}]
        self.assertEqual(diagnose_queue(queue)["state"], "queue_empty")

    def test_rate_limit_and_untrusted_inputs_fail_closed(self):
        deferred = diagnose_queue(inventory(remaining=999))
        self.assertEqual(deferred["state"], "budget_deferred")
        self.assertEqual(deferred["reason"], "rate_limit_below_20_percent")
        self.assertEqual(deferred["blocked_cause_totals"]["dependency"], 7)
        self.assertFalse(deferred["publication_allowed"])
        self.assertFalse(deferred["can_dispatch"])
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
        # Even a blocker excluded from roadmap remains in the cause summary.
        self.assertEqual(result["blocked_cause_totals"]["dependency"], 6)
        self.assertEqual(result["blocked_cause_totals"]["claims"], 1)
        self.assertEqual(sum(result["blocked_cause_totals"].values()), 7)
        self.assertNotIn("private", json.dumps(result))
        # A non-actionable blocker remains reportable only when it is not
        # deceptively marked as a roadmap candidate.
        for cause in ("human_gate", "unknown", "planned"):
            with self.subTest(cause=cause):
                queue["repositories"][0]["blockers"][0].update(
                    cause=cause, roadmap=False)
                report = diagnose_queue(queue)
                self.assertEqual(
                    report["repositories"]["Factory"]["blocked_reasons"],
                    [{"issue": 109, "cause": cause, "roadmap": False}])
                self.assertEqual(report["blocked_cause_totals"][cause], 1)
                self.assertFalse(report["publication_allowed"])
                self.assertTrue(all(x["issue"] != 109 or x["repository"] != "Factory"
                                    for x in report["roadmap_candidates"]))
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
                {"number": i + 1, "cause": "claims", "roadmap": True}
                for i in range(10)
            ]
            row["counts"]["blocked"] = 10
            row["open_issues"] = 10
        report = diagnose_queue(big)
        self.assertEqual(len(report["roadmap_candidates"]), 32)
        self.assertEqual(report["omitted_candidates"], 38)
        self.assertEqual(report["blocked_cause_totals"]["claims"], 70)
        self.assertEqual(sum(report["blocked_cause_totals"].values()), 70)
        self.assertEqual(len(report["repositories"]["Factory"]["blocked_reasons"]), 10)
        # Refuse massive output rather than silently truncating causes.
        huge = inventory()
        for i in range(2):
            row = huge["repositories"][i]
            row["blockers"] = [{"number": n + 1, "cause": "claims", "roadmap": False}
                               for n in range(5001)]
            row["counts"]["blocked"] = 5001
            row["open_issues"] = 5001
        with self.assertRaisesRegex(QueueHealthError, "blocker_report_too_large"):
            diagnose_queue(huge)


    def test_non_actionable_roadmap_causes_fail_closed(self):
        for cause in ("human_gate", "planned", "unknown"):
            for remaining in (5000, 999):
                with self.subTest(cause=cause, remaining=remaining):
                    bad = inventory(remaining=remaining)
                    bad["repositories"][0]["blockers"][0].update(
                        cause=cause, roadmap=True)
                    with self.assertRaisesRegex(QueueHealthError, "invalid_blocker"):
                        diagnose_queue(bad)

    def test_roadmap_cause_contract_matches_snapshot_and_never_publishes(self):
        from scripts.salud_cola_snapshot import SnapshotError, assemble_inventory

        for cause in ("dependency", "claims", "human_gate", "planned", "unknown"):
            for roadmap in (False, True):
                for remaining in (5000, 999):
                    with self.subTest(cause=cause, roadmap=roadmap,
                                      remaining=remaining):
                        reports = [
                            {"name": repo, "pages": [{
                                "page_number": 1, "has_next": False,
                                "issues": [{
                                    "number": 17, "labels": ["estado: bloqueado"],
                                    "pull_request": False,
                                    "blocker": {"cause": cause, "roadmap": roadmap},
                                }],
                            }]}
                            for repo in REPOSITORIES
                        ]
                        direct = inventory(remaining=remaining)
                        for row in direct["repositories"]:
                            row["blockers"][0].update(cause=cause, roadmap=roadmap)
                        if roadmap and cause in ("human_gate", "planned", "unknown"):
                            with self.assertRaisesRegex(SnapshotError, "invalid_blocker"):
                                assemble_inventory(
                                    reports, 4, {"limit": 5000, "remaining": remaining})
                            with self.assertRaisesRegex(QueueHealthError, "invalid_blocker"):
                                diagnose_queue(direct)
                            continue
                        normalized = assemble_inventory(
                            reports, 4, {"limit": 5000, "remaining": remaining})
                        output = diagnose_queue(normalized)
                        self.assertEqual(output, diagnose_queue(direct))
                        self.assertFalse(output["publication_allowed"])
                        if remaining < 1000:
                            self.assertEqual(output["roadmap_candidates"], [])
                        elif roadmap:
                            self.assertEqual(len(output["roadmap_candidates"]), 7)
                        else:
                            self.assertEqual(output["roadmap_candidates"], [])

    def test_recovery_is_counted_without_promoting_work(self):
        queue = inventory(capacity=1)
        for row in queue["repositories"]:
            row["counts"]["blocked"] = 0
            row["counts"]["recovery_required"] = 1
            row["blockers"] = []
        report = diagnose_queue(queue)
        self.assertEqual(report["state"], "queue_empty")
        self.assertEqual(report["reason"], "zero_available_recovery_pending")
        self.assertEqual(report["recovery_required_total"], 7)
        self.assertEqual(report["open_total"], 7)
        self.assertEqual(report["available_total"], 0)
        self.assertEqual(report["roadmap_candidates"], [])
        self.assertEqual(sum(report["blocked_cause_totals"].values()), 0)
        self.assertFalse(report["can_dispatch"])
        self.assertFalse(report["publication_allowed"])
        self.assertEqual(report["repositories"]["Factory"]["counts"]["recovery_required"], 1)
        queue["repositories"][0]["counts"].update(available=1, recovery_required=0)
        ready = diagnose_queue(queue)
        self.assertEqual(ready["recovery_required_total"], 6)
        self.assertEqual(ready["available_total"], 1)
        self.assertTrue(ready["can_dispatch"])
        self.assertEqual(ready["state"], "healthy")
        self.assertFalse(ready["publication_allowed"])

    def test_recovery_conflicts_and_budget_fail_closed(self):
        queue = inventory()
        queue["repositories"][0]["counts"].update(blocked=0, recovery_required=1)
        queue["repositories"][0]["blockers"] = []
        report = diagnose_queue(queue)
        self.assertEqual(report["recovery_required_total"], 1)
        self.assertEqual(report["blocked_cause_totals"]["dependency"], 6)
        self.assertEqual(report["open_total"], 7)
        self.assertFalse(report["can_dispatch"])
        for mutate in (
            lambda q: q["repositories"][0]["counts"].update(recovery_required=2),
            lambda q: q["repositories"][0]["counts"].update(available=1),
            lambda q: q["repositories"][0]["counts"].pop("recovery_required"),
            lambda q: q["repositories"][0]["counts"].update(recovery_required=True),
            lambda q: q["repositories"][0].update(open_issues=0),
            lambda q: q["repositories"][0]["blockers"].append(
                {"number": 99, "cause": "unknown", "roadmap": False}),
        ):
            with self.subTest(mutate=mutate):
                broken = copy.deepcopy(queue)
                mutate(broken)
                with self.assertRaises(QueueHealthError):
                    diagnose_queue(broken)
        queue["rate_limit"]["remaining"] = 999
        deferred = diagnose_queue(queue)
        self.assertEqual(deferred["state"], "budget_deferred")
        self.assertEqual(deferred["recovery_required_total"], 1)
        self.assertEqual(deferred["roadmap_candidates"], [])
        self.assertFalse(deferred["can_dispatch"])
        self.assertFalse(deferred["publication_allowed"])


if __name__ == "__main__":
    unittest.main()
