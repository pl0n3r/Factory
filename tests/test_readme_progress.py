import copy
import json
import unittest
from pathlib import Path

from intelligence.derived_views import DerivedViewDriftError
from readme.generate_readme import ReadmeEngineError, generate_readme
from readme.validate_readme import validate_readme
from readme.progress_readiness import (
    ProgressReadinessError,
    calculate_progress_readiness,
    canonical_payload,
    compare_progress_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "readme" / "contract.json"
TEMPLATE_PATH = ROOT / "readme" / "template.md"

LEGACY_TEMPLATE = """# Legacy README v1

## Operational Cockpit

<!-- factory:status:start -->
legacy status
<!-- factory:status:end -->

### Progress + Readiness

<!-- factory:progress-readiness:start -->
legacy progress
<!-- factory:progress-readiness:end -->
"""


class ReadmeProgressTests(unittest.TestCase):
    def payload(self):
        return {
            "version": 1,
            "target": {
                "id": "factory-autonomous-v1",
                "label": "Autonomous Factory Readiness",
                "scope": "pl0n3r/factory",
                "version": "1",
            },
            "dimensions": [
                {
                    "id": "engineering",
                    "label": "Engineering",
                    "weight": 3,
                    "milestones": [
                        {
                            "id": "core",
                            "label": "Core contract",
                            "weight": 3,
                            "progress_state": "SATISFIED",
                            "readiness_state": "UNSATISFIED",
                            "evidence_refs": ["test:core"],
                        }
                    ],
                },
                {
                    "id": "operations",
                    "label": "Operations",
                    "weight": 2,
                    "milestones": [
                        {
                            "id": "release",
                            "label": "Release path",
                            "weight": 2,
                            "progress_state": "SATISFIED",
                            "readiness_state": "SATISFIED",
                            "evidence_refs": ["check:release"],
                        }
                    ],
                },
            ],
            "blockers": [],
            "observed_at": "2026-09-28T11:30:00-05:00",
        }

    def test_progress_and_readiness_are_distinct_and_target_bound(self):
        result = calculate_progress_readiness(self.payload())

        self.assertEqual("factory-autonomous-v1", result["target"]["id"])
        self.assertEqual("pl0n3r/factory", result["target"]["scope"])
        self.assertEqual("2026-09-28T16:30:00Z", result["observed_at"])
        self.assertEqual(10_000, result["progress"]["basis_points"])
        self.assertEqual("100.00", result["progress"]["percent"])
        self.assertEqual(4_000, result["readiness"]["basis_points"])
        self.assertEqual("40.00", result["readiness"]["percent"])
        self.assertEqual("BUILDING", result["readiness"]["status"])
        self.assertNotEqual(
            result["progress"]["basis_points"],
            result["readiness"]["basis_points"],
        )

        invalid = self.payload()
        invalid["progress_percent"] = 100
        with self.assertRaises(ProgressReadinessError):
            calculate_progress_readiness(invalid)

    def test_unknown_stale_and_not_applicable_are_fail_closed(self):
        payload = self.payload()
        payload["dimensions"] = [
            {
                "id": "quality",
                "label": "Quality",
                "weight": 1,
                "milestones": [
                    {
                        "id": "proven",
                        "label": "Proven",
                        "weight": 4,
                        "progress_state": "SATISFIED",
                        "readiness_state": "SATISFIED",
                        "evidence_refs": ["test:proven"],
                    },
                    {
                        "id": "unknown",
                        "label": "Unknown",
                        "weight": 3,
                        "progress_state": "UNKNOWN",
                        "readiness_state": "UNKNOWN",
                        "evidence_refs": [],
                    },
                    {
                        "id": "stale",
                        "label": "Stale",
                        "weight": 2,
                        "progress_state": "STALE",
                        "readiness_state": "STALE",
                        "evidence_refs": ["check:stale"],
                    },
                    {
                        "id": "na",
                        "label": "Not applicable",
                        "weight": 10,
                        "progress_state": "NOT_APPLICABLE",
                        "readiness_state": "NOT_APPLICABLE",
                        "evidence_refs": ["policy:not-applicable"],
                    },
                ],
            }
        ]

        result = calculate_progress_readiness(payload)

        self.assertEqual(4_444, result["progress"]["basis_points"])
        self.assertEqual(4_444, result["readiness"]["basis_points"])
        self.assertEqual("44.44", result["progress"]["percent"])
        self.assertEqual("DEGRADED", result["evidence_freshness"])
        dimension = result["dimensions"][0]
        self.assertEqual(9, dimension["progress"]["applicable_weight"])
        self.assertEqual(["stale", "unknown"], dimension["progress"]["unknown_or_stale"])

    def test_critical_blocker_remains_visible_and_prevents_ready(self):
        payload = self.payload()
        for dimension in payload["dimensions"]:
            for milestone in dimension["milestones"]:
                milestone["readiness_state"] = "SATISFIED"
        payload["blockers"] = [
            {
                "id": "legal-gate",
                "label": "Legal launch gate",
                "severity": "critical",
                "state": "OPEN",
                "evidence_refs": ["gate:legal-42"],
            }
        ]

        result = calculate_progress_readiness(payload)

        self.assertEqual(10_000, result["readiness"]["basis_points"])
        self.assertEqual("BLOCKED", result["readiness"]["status"])
        self.assertEqual(1, len(result["critical_blockers"]))
        self.assertEqual("legal-gate", result["critical_blockers"][0]["id"])

        unknown = copy.deepcopy(payload)
        unknown["blockers"][0]["state"] = "UNKNOWN"
        unknown["blockers"][0]["evidence_refs"] = []
        unknown_result = calculate_progress_readiness(unknown)
        self.assertEqual("BLOCKED", unknown_result["readiness"]["status"])
        self.assertEqual("DEGRADED", unknown_result["evidence_freshness"])

    def test_calculation_is_deterministic_and_weighted_by_milestones(self):
        payload = self.payload()
        payload["dimensions"] = [
            {
                "id": "product",
                "label": "Product",
                "weight": 1,
                "milestones": [
                    {
                        "id": "major",
                        "label": "Major capability",
                        "weight": 90,
                        "progress_state": "SATISFIED",
                        "readiness_state": "SATISFIED",
                        "evidence_refs": ["test:major"],
                    },
                    {
                        "id": "minor",
                        "label": "Minor capability",
                        "weight": 10,
                        "progress_state": "UNSATISFIED",
                        "readiness_state": "UNSATISFIED",
                        "evidence_refs": ["test:minor"],
                    },
                ],
            }
        ]

        first = calculate_progress_readiness(payload)
        shuffled = copy.deepcopy(payload)
        shuffled["dimensions"][0]["milestones"].reverse()
        second = calculate_progress_readiness(shuffled)

        self.assertEqual(9_000, first["progress"]["basis_points"])
        self.assertNotEqual(5_000, first["progress"]["basis_points"])
        self.assertEqual(first, second)
        self.assertEqual(canonical_payload(first), canonical_payload(second))

    def test_scope_change_is_rebaseline_not_trend(self):
        previous = calculate_progress_readiness(self.payload())

        same_target_payload = self.payload()
        same_target_payload["dimensions"][0]["milestones"][0]["readiness_state"] = "SATISFIED"
        current = calculate_progress_readiness(same_target_payload)
        trend = compare_progress_readiness(previous, current)
        self.assertEqual("TREND", trend["kind"])
        self.assertTrue(trend["comparable"])
        self.assertGreater(trend["readiness_delta_basis_points"], 0)

        changed_target_payload = self.payload()
        changed_target_payload["target"]["version"] = "2"
        changed_target = calculate_progress_readiness(changed_target_payload)
        rebaseline = compare_progress_readiness(previous, changed_target)
        self.assertEqual("REBASELINE", rebaseline["kind"])
        self.assertFalse(rebaseline["comparable"])
        self.assertIsNone(rebaseline["progress_delta_basis_points"])
        self.assertIsNone(rebaseline["readiness_delta_basis_points"])
        self.assertEqual("target_change", rebaseline["causes"][0]["type"])

        reweighted_payload = self.payload()
        reweighted_payload["dimensions"][0]["weight"] = 30
        reweighted = calculate_progress_readiness(reweighted_payload)
        self.assertEqual(
            "REBASELINE",
            compare_progress_readiness(previous, reweighted)["kind"],
        )

        applicability_payload = self.payload()
        applicability_payload["dimensions"][0]["milestones"][0][
            "progress_state"
        ] = "NOT_APPLICABLE"
        applicability_payload["dimensions"][0]["milestones"][0][
            "readiness_state"
        ] = "NOT_APPLICABLE"
        applicability = calculate_progress_readiness(applicability_payload)
        self.assertEqual(
            "REBASELINE",
            compare_progress_readiness(previous, applicability)["kind"],
        )

    def test_payload_explains_contributions_and_real_delta(self):
        previous = calculate_progress_readiness(self.payload())
        changed = self.payload()
        changed["dimensions"][0]["milestones"][0]["readiness_state"] = "SATISFIED"
        changed["dimensions"][0]["milestones"][0]["evidence_refs"].append(
            "check:core-ready"
        )

        result = calculate_progress_readiness(changed, previous=previous)

        engineering = next(
            row
            for row in result["readiness"]["contributions"]
            if row["dimension_id"] == "engineering"
        )
        self.assertEqual(10_000, engineering["basis_points"])
        self.assertEqual(
            ["check:core-ready", "test:core"],
            engineering["evidence_refs"],
        )
        self.assertEqual("TREND", result["trend"]["kind"])
        self.assertEqual(6_000, result["trend"]["readiness_delta_basis_points"])
        cause = next(
            row
            for row in result["trend"]["causes"]
            if row["type"] == "milestone_change"
        )
        self.assertEqual("engineering", cause["dimension_id"])
        self.assertEqual("core", cause["milestone_id"])
        self.assertIn("check:core-ready", cause["evidence_refs"])

    def test_canonical_payload_is_json_and_rejects_non_snapshot(self):
        snapshot = calculate_progress_readiness(self.payload())
        decoded = json.loads(canonical_payload(snapshot))
        self.assertEqual(snapshot, decoded)

        with self.assertRaises(ProgressReadinessError):
            canonical_payload({"version": 1})


    def readme_inputs(self):
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        contract["version"] = 1
        template = LEGACY_TEMPLATE
        metadata = {
            "name": "Factory",
            "tagline": "Gobernanza reproducible",
            "role": "governance/kit",
            "phase": "construction",
            "roadmap": "GitHub Issues",
            "stack": "Python + GitHub Actions",
        }
        return contract, template, metadata

    def test_readme_contract_declares_progress_readiness_block(self):
        contract, template, _ = self.readme_inputs()
        block = contract["derived_blocks"]["progress_readiness"]

        self.assertEqual("derived", block["ownership"])
        self.assertTrue(block["consumers_must_not_recalculate"])
        self.assertEqual(
            "readme/progress_readiness.schema.json",
            block["source_contract"],
        )
        self.assertEqual(1, template.count(block["start_marker"]))
        self.assertEqual(1, template.count(block["end_marker"]))
        self.assertIn("### Progress + Readiness", template)

    def test_readme_generator_consumes_canonical_snapshot_without_recalculation(self):
        contract, template, metadata = self.readme_inputs()
        snapshot = calculate_progress_readiness(self.payload())
        snapshot["progress"]["basis_points"] = 1_234
        snapshot["progress"]["percent"] = "12.34"

        generated = generate_readme(
            template,
            contract,
            metadata,
            {},
            snapshot,
        )

        self.assertIn("| Progress | 12.34% |", generated)
        self.assertNotIn("| Progress | 100.00% |", generated)
        self.assertIn("Autonomous Factory Readiness", generated)
        self.assertIn("| Readiness | 40.00% · BUILDING |", generated)

    def test_readme_preserves_fail_closed_states_and_critical_blockers(self):
        contract, template, metadata = self.readme_inputs()
        payload = self.payload()
        for dimension in payload["dimensions"]:
            for milestone in dimension["milestones"]:
                milestone["readiness_state"] = "SATISFIED"
        payload["dimensions"][0]["milestones"][0]["progress_state"] = "STALE"
        payload["blockers"] = [
            {
                "id": "legal-gate",
                "label": "Legal launch gate",
                "severity": "critical",
                "state": "UNKNOWN",
                "evidence_refs": [],
            }
        ]
        snapshot = calculate_progress_readiness(payload)

        generated = generate_readme(
            template,
            contract,
            metadata,
            {},
            snapshot,
        )

        self.assertIn("| Evidence freshness | DEGRADED |", generated)
        self.assertIn("100.00% · BLOCKED", generated)
        self.assertIn("1 · Legal launch gate [UNKNOWN]", generated)
        self.assertNotIn("· READY |", generated)

    def test_progress_readiness_block_preserves_human_content(self):
        contract, template, metadata = self.readme_inputs()
        block = contract["derived_blocks"]["progress_readiness"]
        prefix, rest = template.split(block["start_marker"], 1)
        _, suffix = rest.split(block["end_marker"], 1)
        snapshot = calculate_progress_readiness(self.payload())

        generated = generate_readme(
            template,
            contract,
            metadata,
            {},
            snapshot,
        )
        generated_prefix, generated_rest = generated.split(
            block["start_marker"],
            1,
        )
        _, generated_suffix = generated_rest.split(block["end_marker"], 1)

        self.assertEqual(prefix, generated_prefix)
        self.assertEqual(suffix, generated_suffix)

    def test_readme_validator_detects_progress_readiness_drift(self):
        contract, template, metadata = self.readme_inputs()
        original = calculate_progress_readiness(self.payload())
        committed = generate_readme(
            template,
            contract,
            metadata,
            {},
            original,
        )
        validate_readme(committed, contract, metadata, {}, original)

        changed_payload = self.payload()
        changed_payload["dimensions"][0]["milestones"][0][
            "readiness_state"
        ] = "SATISFIED"
        changed = calculate_progress_readiness(changed_payload)

        with self.assertRaises(DerivedViewDriftError):
            validate_readme(
                committed,
                contract,
                metadata,
                {},
                changed,
            )

    def test_readme_progress_readiness_generation_is_deterministic_and_strict(self):
        contract, template, metadata = self.readme_inputs()
        snapshot = calculate_progress_readiness(self.payload())

        first = generate_readme(template, contract, metadata, {}, snapshot)
        second = generate_readme(template, contract, metadata, {}, snapshot)
        self.assertEqual(first, second)

        missing = generate_readme(template, contract, metadata, {}, None)
        self.assertIn("| Progress | UNKNOWN |", missing)
        self.assertIn("| Readiness | UNKNOWN |", missing)

        invalid = copy.deepcopy(snapshot)
        invalid["token"] = "should-never-render"
        with self.assertRaises(ReadmeEngineError):
            generate_readme(template, contract, metadata, {}, invalid)


if __name__ == "__main__":
    unittest.main()
