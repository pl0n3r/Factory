import copy
import unittest

from intelligence.project_dna import discover_project_dna
from intelligence.risk_compiler import compile_risk


def signals(**overrides):
    base = {
        "production": False,
        "destructive": False,
        "migration": False,
        "touches_auth": False,
        "external_integration": False,
    }
    base.update(overrides)
    return base


def complete_dna():
    return discover_project_dna(
        paths=[
            "package.json",
            ".github/workflows/ci.yml",
            "vercel.json",
            "database/schema.sql",
            ".sentryclirc",
        ],
        manifests={
            "package.json": {
                "dependencies": {
                    "fastify": "^5",
                    "@sentry/node": "^9",
                }
            }
        },
        capabilities=["api", "auth"],
    )


class RiskCompilerTests(unittest.TestCase):
    def test_risk_uses_task_and_project_dna(self):
        low = compile_risk(
            project_dna=complete_dna(),
            task={
                "id": "factory#150-docs",
                "title": "Docs only",
                "change_type": "docs",
                "surfaces": ["docs"],
                "signals": signals(),
            },
        )
        sparse_dna = discover_project_dna(
            paths=["package.json"],
            manifests={"package.json": {"dependencies": {"fastify": "^5"}}},
            capabilities=["api"],
        )
        high = compile_risk(
            project_dna=sparse_dna,
            task={
                "id": "factory#150-release",
                "title": "Release API",
                "change_type": "release",
                "surfaces": ["api", "release"],
                "signals": signals(production=True),
            },
        )

        self.assertEqual(low["risk"], "low")
        self.assertEqual(high["risk"], "high")
        self.assertNotEqual(low["project_dna_fingerprint"], high["project_dna_fingerprint"])
        self.assertNotEqual(low["dimensions"], high["dimensions"])

    def test_blast_radius_and_controls_are_traceable(self):
        result = compile_risk(
            project_dna=complete_dna(),
            task={
                "id": "factory#150-db",
                "title": "Migration",
                "change_type": "database",
                "surfaces": ["database"],
                "signals": signals(migration=True),
            },
        )

        self.assertEqual(result["risk"], "high")
        self.assertTrue(result["blast_radius"])
        sources = {row["source"] for row in result["trace"]}
        self.assertIn("task.change_type", sources)
        self.assertIn("task.signals.migration", sources)
        for control in result["controls"]:
            self.assertTrue(control["sources"])
            self.assertTrue(set(control["sources"]).issubset(sources))
            self.assertIn(":", control["target"])

    def test_high_risk_never_compiles_weaker_controls(self):
        low = compile_risk(
            project_dna=complete_dna(),
            task={
                "id": "low",
                "title": "Docs",
                "change_type": "docs",
                "surfaces": ["docs"],
                "signals": signals(),
            },
        )
        medium = compile_risk(
            project_dna=complete_dna(),
            task={
                "id": "medium",
                "title": "API",
                "change_type": "code",
                "surfaces": ["api"],
                "signals": signals(),
            },
        )
        high = compile_risk(
            project_dna=complete_dna(),
            task={
                "id": "high",
                "title": "Auth",
                "change_type": "security",
                "surfaces": ["auth"],
                "signals": signals(touches_auth=True),
            },
        )

        low_controls = {item["target"] for item in low["controls"]}
        medium_controls = {item["target"] for item in medium["controls"]}
        high_controls = {item["target"] for item in high["controls"]}
        self.assertTrue(low_controls < medium_controls)
        self.assertTrue(medium_controls < high_controls)

    def test_unknown_critical_signal_fails_safe(self):
        result = compile_risk(
            project_dna=complete_dna(),
            task={
                "id": "factory#150-unknown",
                "title": "Unknown production impact",
                "change_type": "code",
                "surfaces": ["api"],
                "signals": signals(production="unknown"),
            },
        )

        self.assertEqual(result["risk"], "high")
        self.assertFalse(result["context_complete"])
        self.assertIn("task.signals.production", result["unknown_critical_signals"])
        targets = {item["target"] for item in result["controls"]}
        self.assertIn("tests:full-suite", targets)
        self.assertIn("security:scan", targets)
        self.assertIn("smoke:exact-sha", targets)
        self.assertIn("context:complete-before-promotion", targets)

    def test_result_is_deterministic(self):
        task = {
            "id": "factory#150-deterministic",
            "title": "API",
            "change_type": "code",
            "surfaces": ["release", "api"],
            "signals": signals(external_integration=True),
        }
        first = compile_risk(project_dna=complete_dna(), task=task)
        reordered = copy.deepcopy(task)
        reordered["surfaces"] = list(reversed(reordered["surfaces"]))
        second = compile_risk(project_dna=complete_dna(), task=reordered)
        self.assertEqual(first, second)
        self.assertRegex(first["fingerprint"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
