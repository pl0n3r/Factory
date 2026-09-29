import copy
import json
import unittest
from pathlib import Path

from intelligence.project_dna import (
    ProjectDnaError,
    _fingerprint_payload,
    attach_quality_contract,
    discover_project_dna,
    validate_project_dna,
)
from quality.contract import quality_contract_fingerprint


ROOT = Path(__file__).resolve().parents[1]


def quality_contract():
    return {
        "version": 1,
        "project": "factory",
        "surfaces": [
            {
                "id": "admin",
                "criticality": "high",
                "required_gates": ["contract", "security", "unit"],
            }
        ],
        "invariants": ["authorization", "no-secret-logging"],
        "compatibility": {
            "runtimes": ["python-3"],
            "browsers": [],
            "devices": [],
        },
        "accessibility": {"target": "NOT_APPLICABLE"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {
            "required": True,
            "source_ref": "pl0n3r/Factory#306",
        },
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


class QualityProjectDnaTests(unittest.TestCase):
    def test_valid_quality_contract_is_attached_by_reference_and_fingerprint(self):
        dna = discover_project_dna(
            paths=["package.json", ".github/workflows/ci.yml"]
        )
        contract = quality_contract()

        attached = attach_quality_contract(
            dna,
            source_ref="pl0n3r/Factory#343",
            contract=contract,
        )

        self.assertEqual(
            attached["extensions"]["quality_contract"],
            {
                "version": 1,
                "source_ref": "pl0n3r/Factory#343",
                "fingerprint": quality_contract_fingerprint(contract),
            },
        )
        self.assertEqual(validate_project_dna(attached), attached)
        self.assertNotEqual(attached["fingerprint"], dna["fingerprint"])

    def test_invalid_contract_reference_or_tampered_dna_fails_closed_without_inference(self):
        dna = discover_project_dna(
            paths=["quality/contract.schema.json", "README.md"]
        )
        self.assertNotIn("quality_contract", dna["extensions"])

        invalid_contract = quality_contract()
        invalid_contract["unexpected"] = True
        with self.assertRaisesRegex(ProjectDnaError, "Quality Contract inválido"):
            attach_quality_contract(
                dna,
                source_ref="pl0n3r/Factory#343",
                contract=invalid_contract,
            )

        with self.assertRaisesRegex(ProjectDnaError, "source_ref"):
            attach_quality_contract(
                dna,
                source_ref="not a ref",
                contract=quality_contract(),
            )

        attached = attach_quality_contract(
            dna,
            source_ref="pl0n3r/Factory#343",
            contract=quality_contract(),
        )
        tampered = copy.deepcopy(attached)
        tampered["extensions"]["quality_contract"]["source_ref"] = "not a ref"
        tampered["fingerprint"] = _fingerprint_payload(tampered)
        with self.assertRaisesRegex(ProjectDnaError, "source_ref"):
            validate_project_dna(tampered)

    def test_existing_project_dna_discovery_remains_backward_compatible(self):
        dna = discover_project_dna(
            paths=["composer.json", ".github/workflows/ci.yml"],
            manifests={
                "composer.json": {
                    "require": {"symfony/framework-bundle": "^7"}
                }
            },
        )

        self.assertEqual(dna["extensions"], {})
        self.assertEqual(validate_project_dna(dna), dna)
        self.assertEqual(dna["stack"], ["php"])
        self.assertEqual(dna["ci"], ["github-actions"])

    def test_schema_documents_quality_extension_without_closing_extensions_namespace(self):
        schema = json.loads(
            (ROOT / "intelligence" / "project_dna.schema.json").read_text(
                encoding="utf-8"
            )
        )
        extensions = schema["properties"]["extensions"]
        quality = schema["$defs"]["qualityContractRef"]

        self.assertTrue(extensions["additionalProperties"])
        self.assertEqual(
            extensions["properties"]["quality_contract"],
            {"$ref": "#/$defs/qualityContractRef"},
        )
        self.assertFalse(quality["additionalProperties"])
        self.assertEqual(
            quality["required"],
            ["version", "source_ref", "fingerprint"],
        )

    def test_docs_define_reference_only_boundary(self):
        text = (
            ROOT / "docs" / "quality-project-dna.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "no se copia",
            "no infiere",
            "source_ref",
            "fingerprint",
            "extensions",
            "#345",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
