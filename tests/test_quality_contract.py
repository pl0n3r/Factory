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


def sonar_config():
    return {
        "expected_visibility": "public",
        "analysis_method": "ci",
        "max_analysis_age_seconds": 86400,
        "max_organization_line_usage_percent": 80,
        "max_open_vulnerabilities": 0,
        "max_open_bugs": 10,
        "max_open_hotspots": 0,
        "max_debt_age_days": 30,
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

    def test_legacy_contract_without_sonar_preserves_canonical_form_and_fingerprint(self):
        expected = (
            '{"accessibility":{"target":"WCAG_AA"},'
            '"compatibility":{"browsers":["chromium"],"devices":[],"runtimes":["python-3"]},'
            '"dimensions":{"performance":{"required":true,"source_ref":"pl0n3r/Factory#304"},'
            '"recovery":{"required":true,"source_ref":"pl0n3r/Factory#305"}},'
            '"evidence_freshness_seconds":3600,'
            '"invariants":["authorization","no-secret-logging"],'
            '"migration":{"strategy":"NOT_APPLICABLE"},'
            '"project":"factory",'
            '"smoke":{"required":true,"source_ref":"pl0n3r/Factory#306"},'
            '"surfaces":[{"criticality":"high","id":"admin","required_gates":["contract","security","unit"]},'
            '{"criticality":"medium","id":"public-web","required_gates":["accessibility","browser","e2e"]}],'
            '"version":1}'
        )
        self.assertEqual(canonical_quality_contract(sample()), expected)
        self.assertEqual(
            quality_contract_fingerprint(sample()),
            "6f98b2e3c47f7552df263a41bd20894c518cdfb276cad269c4e930f0f8ec5133",
        )
        self.assertNotIn("sonar", validate_quality_contract(sample()))

    def test_sonar_monitoring_thresholds_are_explicit_and_deterministic(self):
        payload = sample()
        payload["sonar"] = sonar_config()
        normalized = validate_quality_contract(payload)

        self.assertEqual(normalized["sonar"], sonar_config())
        self.assertEqual(
            canonical_quality_contract(payload),
            canonical_quality_contract(copy.deepcopy(payload)),
        )
        self.assertEqual(
            set(normalized["sonar"]),
            {
                "expected_visibility",
                "analysis_method",
                "max_analysis_age_seconds",
                "max_organization_line_usage_percent",
                "max_open_vulnerabilities",
                "max_open_bugs",
                "max_open_hotspots",
                "max_debt_age_days",
            },
        )

    def test_invalid_sonar_monitoring_contract_fails_closed(self):
        cases = []

        unknown = sonar_config()
        unknown["extra"] = True
        cases.append(unknown)

        for field, value in (
            ("expected_visibility", "internal"),
            ("analysis_method", "hybrid"),
            ("max_analysis_age_seconds", 0),
            ("max_organization_line_usage_percent", 0),
            ("max_organization_line_usage_percent", 101),
            ("max_open_vulnerabilities", -1),
            ("max_open_bugs", True),
            ("max_open_hotspots", -1),
            ("max_debt_age_days", -1),
        ):
            candidate = sonar_config()
            candidate[field] = value
            cases.append(candidate)

        for sonar in cases:
            payload = sample()
            payload["sonar"] = sonar
            with self.subTest(sonar=sonar):
                with self.assertRaises(QualityContractError):
                    validate_quality_contract(payload)

    def test_sonar_schema_extension_is_optional_and_closed(self):
        schema = json.loads(
            (ROOT / "quality" / "contract.schema.json").read_text()
        )
        self.assertIn("sonar", schema["properties"])
        self.assertNotIn("sonar", schema["required"])

        sonar = schema["$defs"]["sonar"]
        self.assertFalse(sonar["additionalProperties"])
        legacy_required = {
            "expected_visibility",
            "analysis_method",
            "max_analysis_age_seconds",
            "max_organization_line_usage_percent",
            "max_open_vulnerabilities",
            "max_open_bugs",
            "max_open_hotspots",
            "max_debt_age_days",
        }
        self.assertEqual(set(sonar["required"]), legacy_required)
        self.assertEqual(
            set(sonar["properties"]),
            legacy_required | {"applicability"},
        )
        self.assertNotIn("applicability", sonar["required"])
        self.assertEqual(
            sonar["properties"]["applicability"],
            {"$ref": "#/$defs/sonarApplicability"},
        )

        applicability = schema["$defs"]["sonarApplicability"]
        self.assertFalse(applicability["additionalProperties"])
        self.assertEqual(
            set(applicability["required"]),
            {"coverage", "organization_line_usage"},
        )
        self.assertEqual(
            set(applicability["properties"]),
            {"coverage", "organization_line_usage"},
        )

        entry = schema["$defs"]["sonarApplicabilityEntry"]
        self.assertFalse(entry["additionalProperties"])
        self.assertEqual(
            set(entry["required"]),
            {"state", "reason", "source_ref"},
        )
        self.assertEqual(
            set(entry["properties"]["state"]["enum"]),
            {"required", "not_applicable"},
        )
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
            "Sonar monitoring no configurado",
            "No existen defaults Sonar implícitos",
            "max_organization_line_usage_percent",
        ):
            self.assertIn(marker, text)

    def test_sonar_applicability_is_closed_and_consistent(self):
        payload = sample()
        payload["sonar"] = sonar_config()
        payload["sonar"]["applicability"] = {
            "coverage": {
                "state": "required",
                "reason": "coverage_required_ci_analysis",
                "source_ref": "pl0n3r/Factory#516",
            },
            "organization_line_usage": {
                "state": "not_applicable",
                "reason": "organization_line_usage_not_applicable_public",
                "source_ref": "pl0n3r/Factory#516",
            },
        }
        normalized = validate_quality_contract(payload)
        self.assertEqual(
            normalized["sonar"]["applicability"],
            payload["sonar"]["applicability"],
        )

        legacy = sample()
        legacy["sonar"] = sonar_config()
        self.assertNotIn(
            "applicability",
            validate_quality_contract(legacy)["sonar"],
        )

        inconsistent = copy.deepcopy(payload)
        inconsistent["sonar"]["applicability"]["coverage"]["state"] = "not_applicable"
        with self.assertRaises(QualityContractError):
            validate_quality_contract(inconsistent)

        automatic = copy.deepcopy(payload)
        automatic["sonar"]["analysis_method"] = "automatic"
        automatic["sonar"]["applicability"]["coverage"] = {
            "state": "not_applicable",
            "reason": "coverage_not_applicable_automatic_analysis",
            "source_ref": "pl0n3r/Factory#516",
        }
        self.assertEqual(
            validate_quality_contract(automatic)["sonar"]["applicability"]["coverage"]["state"],
            "not_applicable",
        )

        private = copy.deepcopy(payload)
        private["sonar"]["expected_visibility"] = "private"
        private["sonar"]["applicability"]["organization_line_usage"] = {
            "state": "required",
            "reason": "organization_line_usage_required_private",
            "source_ref": "pl0n3r/Factory#516",
        }
        self.assertEqual(
            validate_quality_contract(private)["sonar"]["applicability"]["organization_line_usage"]["state"],
            "required",
        )

        malformed = copy.deepcopy(payload)
        malformed["sonar"]["applicability"]["coverage"]["extra"] = True
        with self.assertRaises(QualityContractError):
            validate_quality_contract(malformed)


if __name__ == "__main__":
    unittest.main()
