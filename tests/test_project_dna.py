import copy
import json
import unittest
from pathlib import Path

from intelligence.project_dna import (
    ProjectDnaError,
    _fingerprint_payload,
    discover_project_dna,
    validate_project_dna,
)


ROOT = Path(__file__).resolve().parents[1]


class ProjectDnaTests(unittest.TestCase):
    def test_discovers_stack_and_surfaces_from_repository_signals(self):
        dna = discover_project_dna(
            paths=[
                "package.json",
                "composer.json",
                "pyproject.toml",
                ".github/workflows/ci.yml",
                "database/migration_001.sql",
                "src/sentry_integration.php",
            ],
            manifests={
                "package.json": {
                    "dependencies": {
                        "fastify": "^5",
                        "react": "^19",
                        "@sentry/node": "^9",
                    }
                },
                "composer.json": {
                    "require": {"symfony/framework-bundle": "^7"}
                },
                "pyproject.toml": {
                    "project": {"dependencies": ["Django>=5.0"]}
                },
            },
            capabilities=["web", "api"],
        )

        self.assertEqual(dna["stack"], ["node", "php", "python"])
        self.assertEqual(
            dna["frameworks"],
            ["django", "fastify", "react", "symfony"],
        )
        self.assertEqual(dna["data"], ["sql"])
        self.assertEqual(dna["ci"], ["github-actions"])
        self.assertEqual(dna["integrations"], ["sentry"])
        self.assertEqual(dna["capabilities"], ["api", "web"])

    def test_unknown_capabilities_are_explicit_not_invented(self):
        dna = discover_project_dna(paths=["README.md"])

        self.assertEqual(dna["stack"], "unknown")
        self.assertEqual(dna["frameworks"], "unknown")
        self.assertEqual(dna["data"], "unknown")
        self.assertEqual(dna["ci"], "unknown")
        self.assertEqual(dna["hosting"], "unknown")
        self.assertEqual(dna["integrations"], "unknown")
        self.assertEqual(dna["capabilities"], "unknown")

    def test_fingerprint_is_deterministic_and_versioned(self):
        first = discover_project_dna(
            paths=["composer.json", ".github/workflows/ci.yml"],
            manifests={
                "composer.json": {
                    "require": {"symfony/framework-bundle": "^7"}
                }
            },
        )
        second = discover_project_dna(
            paths=[
                ".github/workflows/ci.yml",
                "composer.json",
                "composer.json",
            ],
            manifests={
                "composer.json": {
                    "require": {"symfony/framework-bundle": "^7"}
                }
            },
        )

        self.assertEqual(first["version"], 1)
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(validate_project_dna(first), first)

        tampered = copy.deepcopy(first)
        tampered["stack"] = ["python"]
        with self.assertRaisesRegex(ProjectDnaError, "fingerprint no coincide"):
            validate_project_dna(tampered)

    def test_schema_is_extensible_without_breaking_base_fields(self):
        schema = json.loads(
            (ROOT / "intelligence" / "project_dna.schema.json").read_text(
                encoding="utf-8"
            )
        )
        dna = discover_project_dna(paths=["package.json"])
        extended = copy.deepcopy(dna)
        extended["extensions"]["future.runtime_profile"] = {
            "version": 2,
            "signal": "explicit",
        }
        extended["fingerprint"] = _fingerprint_payload(extended)

        self.assertEqual(validate_project_dna(extended), extended)
        self.assertTrue(
            schema["properties"]["extensions"]["additionalProperties"]
        )
        self.assertFalse(schema["additionalProperties"])

        extra_top_level = copy.deepcopy(extended)
        extra_top_level["future"] = {"invented": False}
        extra_top_level["fingerprint"] = _fingerprint_payload(extra_top_level)
        with self.assertRaisesRegex(ProjectDnaError, "campos base"):
            validate_project_dna(extra_top_level)

        invalid_extension = copy.deepcopy(extended)
        invalid_extension["extensions"]["bad"] = {"not-json"}
        invalid_extension["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ProjectDnaError, "valores no JSON"):
            validate_project_dna(invalid_extension)

        non_finite_extension = copy.deepcopy(extended)
        non_finite_extension["extensions"]["bad"] = float("nan")
        non_finite_extension["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ProjectDnaError, "valores no JSON"):
            validate_project_dna(non_finite_extension)

        non_string_key = copy.deepcopy(extended)
        non_string_key["extensions"]["nested"] = {"ok": {1: "bad"}}
        non_string_key["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ProjectDnaError, "claves no string"):
            validate_project_dna(non_string_key)

    def test_integration_detection_requires_explicit_signal(self):
        inferred = discover_project_dna(
            paths=[
                ".github/workflows/ci.yml",
                "src/sentry_integration.php",
                "docs/stripe-notes.md",
            ]
        )
        self.assertEqual(inferred["integrations"], "unknown")

        explicit = discover_project_dna(
            paths=["package.json", ".sentryclirc"],
            manifests={
                "package.json": {
                    "dependencies": {
                        "@sentry/node": "^9",
                        "stripe": "^18",
                    }
                }
            },
        )
        self.assertEqual(explicit["integrations"], ["sentry", "stripe"])


if __name__ == "__main__":
    unittest.main()
