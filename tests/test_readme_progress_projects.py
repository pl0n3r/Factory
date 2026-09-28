import copy
import json
import unittest
from pathlib import Path

from readme.progress_readiness import (
    calculate_progress_readiness,
    canonical_payload,
    compare_progress_readiness,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "readme" / "projects" / "progress-readiness"
DOCS = ROOT / "docs" / "readme-progress-readiness.md"

EXPECTED = {
    "autofactory": ("autofactory-local-automation-v1", "Local Automation Readiness", "pl0n3r/AutoFactory"),
    "brvtal": ("brvtal-platform-event-operations-v1", "Platform / Event Operations Readiness", "pl0n3r/brvtal"),
    "condor": ("condor-colombia-v1", "Colombia V1 Readiness", "pl0n3r/Condor"),
    "controlbot": ("controlbot-business-os-v1", "Business OS Readiness", "pl0n3r/ControlBot"),
    "factory": ("factory-autonomous-v1", "Autonomous Factory Readiness", "pl0n3r/factory"),
    "factoryrunner": ("factoryrunner-execution-plane-v1", "Execution Plane Readiness", "pl0n3r/FactoryRunner"),
    "grindflow": ("grindflow-commercial-v1", "Commercial V1 Readiness", "pl0n3r/GrindFlow"),
}


class ReadmeProgressProjectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(PROJECTS.glob("*.json"))
        }

    def test_seven_projects_have_explicit_unique_versioned_targets(self):
        self.assertEqual(set(EXPECTED), set(self.fixtures))
        ids = set()
        scopes = set()
        for slug, expected in EXPECTED.items():
            target = self.fixtures[slug]["target"]
            self.assertEqual(expected, (target["id"], target["label"], target["scope"]))
            self.assertEqual("1", target["version"])
            self.assertNotIn(target["id"], ids)
            self.assertNotIn(target["scope"], scopes)
            ids.add(target["id"])
            scopes.add(target["scope"])

    def test_project_dimensions_and_not_applicable_evidence_are_valid(self):
        dimension_sets = set()
        saw_not_applicable = False
        for payload in self.fixtures.values():
            ids = tuple(row["id"] for row in payload["dimensions"])
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(ids)
            dimension_sets.add(ids)
            for dimension in payload["dimensions"]:
                self.assertGreater(dimension["weight"], 0)
                self.assertTrue(dimension["milestones"])
                for milestone in dimension["milestones"]:
                    states = {
                        milestone["progress_state"],
                        milestone["readiness_state"],
                    }
                    if "NOT_APPLICABLE" in states:
                        saw_not_applicable = True
                        self.assertEqual({"NOT_APPLICABLE"}, states)
                        self.assertTrue(milestone["evidence_refs"])
                        self.assertTrue(
                            all(
                                ref.startswith("policy:not-applicable:")
                                for ref in milestone["evidence_refs"]
                            )
                        )
        self.assertGreater(len(dimension_sets), 1)
        self.assertTrue(saw_not_applicable)

    def test_all_project_targets_compile_with_canonical_engine(self):
        for slug, payload in self.fixtures.items():
            with self.subTest(project=slug):
                snapshot = calculate_progress_readiness(payload)
                self.assertEqual(payload["target"], snapshot["target"])
                self.assertEqual("DEGRADED", snapshot["evidence_freshness"])
                self.assertEqual("BUILDING", snapshot["readiness"]["status"])
                decoded = json.loads(canonical_payload(snapshot))
                self.assertEqual(snapshot, decoded)

    def test_target_scope_weight_or_applicability_change_rebaselines(self):
        base = copy.deepcopy(self.fixtures["factory"])
        previous = calculate_progress_readiness(base)

        mutations = []

        changed = copy.deepcopy(base)
        changed["target"]["version"] = "2"
        mutations.append(changed)

        changed = copy.deepcopy(base)
        changed["target"]["scope"] = "pl0n3r/factory-v2"
        mutations.append(changed)

        changed = copy.deepcopy(base)
        changed["dimensions"][0]["weight"] += 1
        mutations.append(changed)

        changed = copy.deepcopy(base)
        milestone = changed["dimensions"][0]["milestones"][0]
        milestone["progress_state"] = "NOT_APPLICABLE"
        milestone["readiness_state"] = "NOT_APPLICABLE"
        milestone["evidence_refs"] = ["policy:not-applicable:governance"]
        mutations.append(changed)

        for payload in mutations:
            current = calculate_progress_readiness(payload)
            comparison = compare_progress_readiness(previous, current)
            self.assertEqual("REBASELINE", comparison["kind"])
            self.assertFalse(comparison["comparable"])
            self.assertIsNone(comparison["progress_delta_basis_points"])
            self.assertIsNone(comparison["readiness_delta_basis_points"])

    def test_project_fixtures_are_deterministic_without_manual_percentages(self):
        forbidden = {
            "percent",
            "percentage",
            "progress_percent",
            "readiness_percent",
            "basis_points",
            "progress_basis_points",
            "readiness_basis_points",
        }

        def assert_no_manual_scores(value):
            if isinstance(value, dict):
                self.assertTrue(forbidden.isdisjoint(value))
                for nested in value.values():
                    assert_no_manual_scores(nested)
            elif isinstance(value, list):
                for nested in value:
                    assert_no_manual_scores(nested)

        for slug, payload in self.fixtures.items():
            with self.subTest(project=slug):
                assert_no_manual_scores(payload)
                first = calculate_progress_readiness(payload)
                second = calculate_progress_readiness(copy.deepcopy(payload))
                self.assertEqual(first, second)
                self.assertEqual(canonical_payload(first), canonical_payload(second))

    def test_documentation_explains_targets_sources_and_rebaseline(self):
        docs = DOCS.read_text(encoding="utf-8")
        for _, label, scope in EXPECTED.values():
            self.assertIn(label, docs)
            self.assertIn(scope, docs)
        self.assertIn("roadmap", docs.lower())
        self.assertIn("fuentes de verdad", docs.lower())
        self.assertIn("REBASELINE", docs)
        self.assertIn("readme/projects/progress-readiness/", docs)
        self.assertIn("no contienen porcentajes manuales", docs.lower())


if __name__ == "__main__":
    unittest.main()
