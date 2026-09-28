import copy
import unittest

from readme.progress_readiness import (
    ProgressReadinessError,
    calculate_progress_readiness,
    compare_snapshots,
)


class ReadmeProgressTests(unittest.TestCase):
    def fixture(self):
        return {
            "target": {
                "id": "factory-autonomy",
                "label": "Autonomous Factory Readiness",
                "version": "v1",
                "scope": "factory-v1",
            },
            "dimensions": [
                {
                    "id": "engineering",
                    "label": "Engineering",
                    "weight": 2,
                    "applicability": "APPLICABLE",
                    "milestones": [
                        {
                            "id": "ci",
                            "label": "CI verified",
                            "weight": 3,
                            "freshness": "CURRENT",
                            "progress": {"state": "DEMONSTRATED", "value": 1, "evidence_refs": ["check:ci"]},
                            "readiness": {"state": "PARTIAL", "value": 0.5, "evidence_refs": ["check:ci"]},
                        },
                        {
                            "id": "release",
                            "label": "Release verified",
                            "weight": 1,
                            "freshness": "CURRENT",
                            "progress": {"state": "NOT_DEMONSTRATED", "value": 0, "evidence_refs": []},
                            "readiness": {"state": "NOT_DEMONSTRATED", "value": 0, "evidence_refs": []},
                        },
                    ],
                },
                {
                    "id": "legal",
                    "label": "Legal",
                    "weight": 1,
                    "applicability": "NOT_APPLICABLE",
                    "milestones": [],
                },
            ],
            "blockers": [],
        }

    def test_progress_and_readiness_are_distinct_and_target_bound(self):
        result = calculate_progress_readiness(self.fixture())
        self.assertEqual(result["target"]["id"], "factory-autonomy")
        self.assertEqual(result["progress"]["percent"], 75.0)
        self.assertEqual(result["readiness"]["percent"], 37.5)
        self.assertNotEqual(result["progress"]["percent"], result["readiness"]["percent"])
        self.assertEqual(result["dimensions"][1]["applicability"], "NOT_APPLICABLE")

    def test_unknown_stale_and_not_applicable_are_fail_closed(self):
        data = self.fixture()
        milestone = data["dimensions"][0]["milestones"][0]
        milestone["freshness"] = "STALE"
        result = calculate_progress_readiness(data)
        self.assertEqual(result["progress"]["percent"], 0.0)
        self.assertEqual(result["readiness"]["percent"], 0.0)
        self.assertEqual(result["evidence_freshness"], "STALE")
        self.assertIsNone(result["dimensions"][1]["progress_percent"])

        data = self.fixture()
        data["dimensions"][0]["milestones"][0]["progress"] = {
            "state": "UNKNOWN", "value": 0, "evidence_refs": []
        }
        result = calculate_progress_readiness(data)
        self.assertEqual(result["progress"]["percent"], 0.0)

    def test_critical_blocker_remains_visible_and_prevents_ready(self):
        data = self.fixture()
        for milestone in data["dimensions"][0]["milestones"]:
            milestone["progress"] = {"state": "DEMONSTRATED", "value": 1, "evidence_refs": ["e:p"]}
            milestone["readiness"] = {"state": "DEMONSTRATED", "value": 1, "evidence_refs": ["e:r"]}
        data["blockers"] = [
            {"id": "backup", "severity": "CRITICAL", "status": "OPEN", "evidence_refs": ["gate:backup"]}
        ]
        result = calculate_progress_readiness(data)
        self.assertEqual(result["readiness"]["percent"], 100.0)
        self.assertEqual(result["readiness"]["status"], "BLOCKED")
        self.assertEqual([row["id"] for row in result["critical_blockers"]], ["backup"])

    def test_calculation_is_deterministic_and_weighted_by_milestones(self):
        data = self.fixture()
        first = calculate_progress_readiness(data)
        reordered = copy.deepcopy(data)
        reordered["dimensions"][0]["milestones"].reverse()
        reordered["dimensions"].reverse()
        second = calculate_progress_readiness(reordered)
        self.assertEqual(first, second)

        data["dimensions"][0]["milestones"][0]["weight"] = 9
        weighted = calculate_progress_readiness(data)
        self.assertGreater(weighted["progress"]["percent"], first["progress"]["percent"])
        self.assertNotEqual(weighted["progress"]["percent"], 50.0)

    def test_scope_change_is_rebaseline_not_trend(self):
        before = calculate_progress_readiness(self.fixture())
        data = self.fixture()
        data["target"]["version"] = "v2"
        after = calculate_progress_readiness(data)
        comparison = compare_snapshots(before, after)
        self.assertEqual(comparison["kind"], "REBASELINE")
        self.assertIsNone(comparison["progress_delta"])
        self.assertIsNone(comparison["readiness_delta"])

    def test_payload_explains_contributions_and_real_delta(self):
        before = calculate_progress_readiness(self.fixture())
        data = self.fixture()
        data["dimensions"][0]["milestones"][1]["progress"] = {
            "state": "DEMONSTRATED", "value": 1, "evidence_refs": ["release:v1"]
        }
        after = calculate_progress_readiness(data)
        comparison = compare_snapshots(before, after)
        self.assertEqual(comparison["kind"], "DELTA")
        self.assertEqual(comparison["progress_delta"], 25.0)
        self.assertIn("check:ci", after["evidence_refs"])
        self.assertIn("release:v1", after["evidence_refs"])
        self.assertTrue(any("engineering:progress_percent" in cause for cause in comparison["causes"]))

    def test_invalid_positive_signal_without_current_evidence_fails_closed(self):
        data = self.fixture()
        data["dimensions"][0]["milestones"][0]["progress"]["evidence_refs"] = []
        with self.assertRaises(ProgressReadinessError):
            calculate_progress_readiness(data)


if __name__ == "__main__":
    unittest.main()
