import unittest

from intelligence.dod_compiler import (
    FACTORY_INVARIANTS,
    SAFE_FALLBACK,
    compile_done_contract,
)
from intelligence.project_dna import discover_project_dna


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
        capabilities=["api", "web"],
    )


class DodCompilerTests(unittest.TestCase):
    def test_different_changes_compile_different_done_contracts(self):
        code = compile_done_contract(
            project_dna=complete_dna(),
            task={
                "id": "factory#148-code",
                "title": "API change",
                "change_type": "code",
                "surfaces": ["api"],
                "risk": "low",
            },
        )
        database = compile_done_contract(
            project_dna=complete_dna(),
            task={
                "id": "factory#148-db",
                "title": "Database change",
                "change_type": "database",
                "surfaces": ["database"],
                "risk": "high",
            },
        )

        self.assertNotEqual(code["evidence"], database["evidence"])
        self.assertIn(
            {"kind": "test", "target": "api:contract"},
            code["evidence"],
        )
        self.assertIn(
            {"kind": "check", "target": "backup:evidence"},
            database["evidence"],
        )

    def test_every_contract_keeps_factory_invariants(self):
        contract = compile_done_contract(
            project_dna=complete_dna(),
            task={
                "id": "factory#148-docs",
                "title": "Docs change",
                "change_type": "docs",
                "surfaces": ["web"],
                "risk": "medium",
            },
        )

        self.assertEqual(
            contract["invariants"],
            [dict(item) for item in FACTORY_INVARIANTS],
        )
        for invariant in FACTORY_INVARIANTS:
            self.assertIn(dict(invariant), contract["evidence"])

    def test_evidence_targets_are_machine_verifiable(self):
        contract = compile_done_contract(
            project_dna=complete_dna(),
            task={
                "id": "factory#148-ci",
                "title": "CI change",
                "change_type": "ci",
                "surfaces": ["ci", "release"],
                "risk": "high",
            },
        )

        for item in contract["evidence"]:
            self.assertIn(item["kind"], {"test", "check"})
            self.assertIn(":", item["target"])
            self.assertFalse(item["target"].endswith(":"))
        self.assertRegex(contract["fingerprint"], r"^[0-9a-f]{64}$")

    def test_unknown_context_fails_safe_instead_of_weakening_done(self):
        unknown_dna = discover_project_dna(paths=["README.md"])
        contract = compile_done_contract(
            project_dna=unknown_dna,
            task={
                "id": "factory#148-unknown",
                "title": "Unknown change",
                "change_type": "unknown",
                "surfaces": [],
                "risk": "unknown",
            },
        )

        self.assertEqual(contract["profile"], "safe-fallback")
        self.assertFalse(contract["context_complete"])
        for requirement in SAFE_FALLBACK:
            self.assertIn(dict(requirement), contract["evidence"])
        for invariant in FACTORY_INVARIANTS:
            self.assertIn(dict(invariant), contract["evidence"])


if __name__ == "__main__":
    unittest.main()
