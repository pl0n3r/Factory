import copy
import json
import unittest
from pathlib import Path

from quality.contract import (
    QualityContractError,
    canonical_quality_contract,
    quality_contract_fingerprint,
    validate_quality_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def sample(project="factory"):
    return {
        "version": 1,
        "project": project,
        "surfaces": [
            {
                "id": "admin",
                "criticality": "high",
                "required_gates": ["security", "unit", "contract"],
            },
            {
                "id": "public-web",
                "criticality": "medium",
                "required_gates": ["browser", "accessibility", "e2e"],
            },
        ],
        "invariants": ["authorization", "no-secret-logging"],
        "compatibility": {
            "runtimes": ["python-3"],
            "browsers": ["chromium"],
            "devices": [],
        },
        "accessibility": {"target": "WCAG_AA"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": True, "source_ref": "pl0n3r/Factory#306"},
        "evidence_freshness_seconds": 3600,
        "dimensions": {
            "performance": {
                "required": True,
                "source_ref": "pl0n3r/Factory#304",
            },
            "recovery": {
                "required": True,
                "source_ref": "pl0n3r/Factory#305",
            },
        },
    }


class QualityContractTests(unittest.TestCase):
    def test_contract_v1_schema_is_closed_and_deterministic(self):
        left = sample()
        right = sample()
        right["surfaces"].reverse()
        right["surfaces"][1]["required_gates"].reverse()
        right["invariants"].reverse()

        self.assertEqual(
            canonical_quality_contract(left),
            canonical_quality_contract(right),
        )
        self.assertEqual(
            quality_contract_fingerprint(left),
            quality_contract_fingerprint(right),
        )
        schema = json.loads(
            (ROOT / "quality" / "contract.schema.json").read_text()
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["version"], {"const": 1})

    def test_contract_supports_project_specific_surfaces_and_required_gates(self):
        factory = validate_quality_contract(sample("factory"))
        grindflow_raw = sample("grindflow")
        grindflow_raw["surfaces"] = [
            {
                "id": "upload",
                "criticality": "critical",
                "required_gates": [
                    "integration",
                    "performance",
                    "resilience",
                ],
            }
        ]
        grindflow_raw["evidence_freshness_seconds"] = 900
        grindflow = validate_quality_contract(grindflow_raw)

        self.assertNotEqual(factory["surfaces"], grindflow["surfaces"])
        self.assertNotEqual(
            factory["evidence_freshness_seconds"],
            grindflow["evidence_freshness_seconds"],
        )
        self.assertNotIn("score", json.dumps(grindflow).lower())

    def test_performance_and_recovery_are_external_dimensions_not_parallel_pipelines(self):
        normalized = validate_quality_contract(sample())
        self.assertEqual(
            normalized["dimensions"],
            {
                "performance": {
                    "required": True,
                    "source_ref": "pl0n3r/Factory#304",
                },
                "recovery": {
                    "required": True,
                    "source_ref": "pl0n3r/Factory#305",
                },
            },
        )
        self.assertEqual(
            set(normalized["dimensions"]["performance"]),
            {"required", "source_ref"},
        )

    def test_invalid_unknown_or_duplicate_contract_fails_closed(self):
        cases = []

        unknown = sample()
        unknown["extra"] = True
        cases.append(unknown)

        duplicate_surface = sample()
        duplicate_surface["surfaces"].append(
            copy.deepcopy(duplicate_surface["surfaces"][0])
        )
        cases.append(duplicate_surface)

        duplicate_gate = sample()
        duplicate_gate["surfaces"][0]["required_gates"].append("unit")
        cases.append(duplicate_gate)

        bad_ref = sample()
        bad_ref["dimensions"]["performance"]["source_ref"] = "not a ref"
        cases.append(bad_ref)

        inconsistent = sample()
        inconsistent["smoke"] = {
            "required": False,
            "source_ref": "pl0n3r/Factory#306",
        }
        cases.append(inconsistent)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(QualityContractError):
                    validate_quality_contract(payload)

    def test_docs_define_quality_contract_boundary_and_unknown_not_pass(self):
        text = (
            ROOT / "docs" / "quality-contract.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "UNKNOWN",
            "no equivale a PASS",
            "Performance",
            "Recovery",
            "scheduler/backlog",
            "#344–#348",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
