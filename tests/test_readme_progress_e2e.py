import copy
import json
import unittest
from pathlib import Path

from readme.generate_readme import generate_readme
from readme.progress_readiness import (
    calculate_progress_readiness,
    canonical_payload,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "readme" / "projects" / "progress-readiness" / "condor.json"
CONTRACT = ROOT / "readme" / "contract.json"
TEMPLATE = ROOT / "readme" / "template.md"
DOCS = ROOT / "docs" / "readme-progress-readiness.md"


class ReadmeProgressE2ETests(unittest.TestCase):
    def fixture(self):
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def readme_inputs(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        template = TEMPLATE.read_text(encoding="utf-8")
        metadata = {
            "name": "Condor",
            "tagline": "SaaS B2B Colombia-first",
            "role": "product",
            "phase": "construction",
            "roadmap": "GitHub Issue #1",
            "stack": "PHP/Symfony",
        }
        return contract, template, metadata

    def progressed_payload(self):
        payload = self.fixture()
        milestone = payload["dimensions"][0]["milestones"][0]
        milestone["progress_state"] = "SATISFIED"
        milestone["readiness_state"] = "SATISFIED"
        milestone["evidence_refs"] = ["evidence:condor/product-baseline"]
        return payload

    def critical_blocker_payload(self):
        payload = self.progressed_payload()
        payload["blockers"] = [
            {
                "id": "launch-legal-gate",
                "label": "Launch legal gate",
                "severity": "critical",
                "state": "OPEN",
                "evidence_refs": ["lex:condor-colombia/pending"],
            }
        ]
        return payload

    @staticmethod
    def controlbot_consumer_payload(snapshot):
        canonical = json.loads(canonical_payload(snapshot))
        consumer = {
            "contract": "factory.progress-readiness.controlbot.v1",
            "target": canonical["target"],
            "progress": canonical["progress"],
            "readiness": canonical["readiness"],
            "evidence_freshness": canonical["evidence_freshness"],
            "critical_blockers": canonical["critical_blockers"],
            "trend": canonical["trend"],
        }
        return json.dumps(
            consumer,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def test_canonical_project_evidence_produces_deterministic_snapshot(self):
        payload = self.progressed_payload()

        first = calculate_progress_readiness(payload)
        second = calculate_progress_readiness(copy.deepcopy(payload))

        self.assertEqual("Colombia V1 Readiness", first["target"]["label"])
        self.assertEqual(first, second)
        self.assertEqual(canonical_payload(first), canonical_payload(second))
        self.assertGreater(first["progress"]["basis_points"], 0)
        self.assertGreater(first["readiness"]["basis_points"], 0)

    def test_same_snapshot_drives_readme_without_recalculation(self):
        snapshot = calculate_progress_readiness(self.progressed_payload())
        contract, template, metadata = self.readme_inputs()

        generated = generate_readme(
            template,
            contract,
            metadata,
            {},
            snapshot,
        )

        self.assertTrue(contract["derived_blocks"]["progress_readiness"][
            "consumers_must_not_recalculate"
        ])
        self.assertIn(
            f"| Progress | {snapshot['progress']['percent']}% |",
            generated,
        )
        self.assertIn(
            f"| Readiness | {snapshot['readiness']['percent']}% · "
            f"{snapshot['readiness']['status']} |",
            generated,
        )
        self.assertIn(snapshot["target"]["label"], generated)
        self.assertNotIn("issues cerrados", generated.lower())

    def test_controlbot_consumer_contract_uses_same_canonical_payload(self):
        snapshot = calculate_progress_readiness(self.progressed_payload())
        canonical = json.loads(canonical_payload(snapshot))
        consumer = json.loads(self.controlbot_consumer_payload(snapshot))

        self.assertEqual(canonical["target"], consumer["target"])
        self.assertEqual(canonical["progress"], consumer["progress"])
        self.assertEqual(canonical["readiness"], consumer["readiness"])
        self.assertEqual(
            canonical["evidence_freshness"],
            consumer["evidence_freshness"],
        )
        self.assertEqual(
            canonical["critical_blockers"],
            consumer["critical_blockers"],
        )
        self.assertEqual(canonical["trend"], consumer["trend"])

    def test_consumer_preserves_critical_blockers_without_formula(self):
        snapshot = calculate_progress_readiness(self.critical_blocker_payload())
        consumer = json.loads(self.controlbot_consumer_payload(snapshot))

        self.assertEqual("BLOCKED", consumer["readiness"]["status"])
        self.assertEqual(
            "launch-legal-gate",
            consumer["critical_blockers"][0]["id"],
        )
        self.assertNotIn("formula", consumer)
        self.assertNotIn("calculation", consumer)
        self.assertNotIn("dimensions", consumer)
        self.assertNotIn("milestones", consumer)

    def test_progress_trend_and_target_rebaseline_are_distinct(self):
        base_payload = self.fixture()
        base = calculate_progress_readiness(base_payload)

        progressed = calculate_progress_readiness(
            self.progressed_payload(),
            previous=base,
        )
        self.assertEqual("TREND", progressed["trend"]["kind"])
        self.assertTrue(progressed["trend"]["comparable"])
        self.assertGreater(
            progressed["trend"]["progress_delta_basis_points"],
            0,
        )
        self.assertTrue(
            any(
                cause["type"] == "milestone_change"
                for cause in progressed["trend"]["causes"]
            )
        )

        changed_target = self.progressed_payload()
        changed_target["target"]["scope"] = "pl0n3r/Condor:colombia-v2"
        changed_target["target"]["version"] = "2"
        rebased = calculate_progress_readiness(changed_target, previous=base)

        self.assertEqual("REBASELINE", rebased["trend"]["kind"])
        self.assertFalse(rebased["trend"]["comparable"])
        self.assertIsNone(rebased["trend"]["progress_delta_basis_points"])
        self.assertIsNone(rebased["trend"]["readiness_delta_basis_points"])

    def test_e2e_outputs_are_deterministic(self):
        payload = self.critical_blocker_payload()
        first = calculate_progress_readiness(payload)
        second = calculate_progress_readiness(copy.deepcopy(payload))
        contract, template, metadata = self.readme_inputs()

        first_canonical = canonical_payload(first)
        second_canonical = canonical_payload(second)
        first_readme = generate_readme(template, contract, metadata, {}, first)
        second_readme = generate_readme(template, contract, metadata, {}, second)
        first_consumer = self.controlbot_consumer_payload(first)
        second_consumer = self.controlbot_consumer_payload(second)

        self.assertEqual(first_canonical, second_canonical)
        self.assertEqual(first_readme, second_readme)
        self.assertEqual(first_consumer, second_consumer)

    def test_documentation_describes_evidence_readme_controlbot_flow(self):
        docs = DOCS.read_text(encoding="utf-8")

        self.assertIn("evidence → cálculo → README → ControlBot", docs)
        self.assertIn("consumer contract", docs)
        self.assertIn("no una segunda calculadora", docs)
        self.assertIn("REBASELINE", docs)
        self.assertIn("sin ampliar autoridad", docs)


if __name__ == "__main__":
    unittest.main()
