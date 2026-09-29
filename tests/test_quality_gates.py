import copy
import json
import unittest
from pathlib import Path

from intelligence.dod_compiler import (
    FACTORY_INVARIANTS,
    compile_done_contract,
)
from intelligence.project_dna import (
    attach_quality_contract,
    discover_project_dna,
)
from intelligence.risk_compiler import (
    RiskCompilerError,
    compile_risk,
)
from intelligence.dod_compiler import DodCompilerError


ROOT = Path(__file__).resolve().parents[1]


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
        capabilities=["api", "auth", "web"],
    )


def quality_contract():
    return {
        "version": 1,
        "project": "factory",
        "surfaces": [
            {
                "id": "api",
                "criticality": "high",
                "required_gates": ["contract", "e2e", "security"],
            },
            {
                "id": "auth",
                "criticality": "low",
                "required_gates": ["security", "tenancy"],
            },
            {
                "id": "docs",
                "criticality": "critical",
                "required_gates": ["accessibility", "unit"],
            },
        ],
        "invariants": ["authorization", "no-secret-logging"],
        "compatibility": {
            "runtimes": ["python-3"],
            "browsers": [],
            "devices": [],
        },
        "accessibility": {"target": "WCAG_AA"},
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


def governed_dna(contract=None):
    contract = contract or quality_contract()
    return attach_quality_contract(
        complete_dna(),
        source_ref="pl0n3r/Factory#343",
        contract=contract,
    )


class QualityGateCompilerTests(unittest.TestCase):
    def test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk(self):
        contract = quality_contract()
        dna = governed_dna(contract)

        quality_raised = compile_risk(
            project_dna=dna,
            quality_contract=contract,
            task={
                "id": "factory#345-docs",
                "title": "Critical docs surface",
                "change_type": "docs",
                "surfaces": ["docs"],
                "signals": signals(),
            },
        )
        self.assertEqual(quality_raised["risk"], "high")
        self.assertEqual(quality_raised["dimensions"]["quality"], "high")
        self.assertTrue(
            any(
                row["source"]
                == "quality_contract.surfaces.docs.criticality"
                for row in quality_raised["trace"]
            )
        )

        base_high = compile_risk(
            project_dna=dna,
            quality_contract=contract,
            task={
                "id": "factory#345-auth",
                "title": "Security change",
                "change_type": "security",
                "surfaces": ["auth"],
                "signals": signals(touches_auth=True),
            },
        )
        self.assertEqual(base_high["risk"], "high")
        self.assertEqual(base_high["dimensions"]["quality"], "low")

    def test_dod_adds_required_quality_gates_without_removing_existing_evidence(self):
        contract = quality_contract()
        dna = governed_dna(contract)
        done = compile_done_contract(
            project_dna=dna,
            quality_contract=contract,
            task={
                "id": "factory#345-api",
                "title": "API change",
                "change_type": "code",
                "surfaces": ["api"],
                "risk": "low",
            },
        )

        for invariant in FACTORY_INVARIANTS:
            self.assertIn(dict(invariant), done["evidence"])
        for gate in (
            {"kind": "test", "target": "quality:contract"},
            {"kind": "test", "target": "quality:e2e"},
            {"kind": "check", "target": "quality:security"},
        ):
            self.assertIn(gate, done["evidence"])
        self.assertIn(
            {"kind": "test", "target": "api:contract"},
            done["evidence"],
        )
        self.assertRegex(
            done["quality_contract_fingerprint"],
            r"^[0-9a-f]{64}$",
        )

    def test_dna_without_quality_extension_preserves_existing_risk_and_dod_behavior(self):
        dna = complete_dna()
        risk = compile_risk(
            project_dna=dna,
            task={
                "id": "factory#345-legacy-risk",
                "title": "Legacy API",
                "change_type": "code",
                "surfaces": ["api"],
                "signals": signals(),
            },
        )
        done = compile_done_contract(
            project_dna=dna,
            task={
                "id": "factory#345-legacy-dod",
                "title": "Legacy API",
                "change_type": "code",
                "surfaces": ["api"],
                "risk": "medium",
            },
        )

        self.assertEqual(risk["risk"], "medium")
        self.assertNotIn("quality", risk["dimensions"])
        self.assertNotIn("quality_contract_fingerprint", risk)
        self.assertEqual(done["profile"], "derived")
        self.assertNotIn("quality_contract_fingerprint", done)
        self.assertIn(
            {"kind": "test", "target": "api:contract"},
            done["evidence"],
        )

    def test_missing_mismatched_or_undeclared_quality_context_fails_closed(self):
        contract = quality_contract()
        dna = governed_dna(contract)
        risk_task = {
            "id": "factory#345-fail",
            "title": "API",
            "change_type": "code",
            "surfaces": ["api"],
            "signals": signals(),
        }

        with self.assertRaisesRegex(
            RiskCompilerError,
            "falta evidencia fuente",
        ):
            compile_risk(project_dna=dna, task=risk_task)

        mismatch = copy.deepcopy(contract)
        mismatch["evidence_freshness_seconds"] = 7200
        with self.assertRaisesRegex(RiskCompilerError, "fingerprint"):
            compile_risk(
                project_dna=dna,
                quality_contract=mismatch,
                task=risk_task,
            )

        undeclared = copy.deepcopy(risk_task)
        undeclared["surfaces"] = ["billing"]
        with self.assertRaisesRegex(RiskCompilerError, "no declarada"):
            compile_risk(
                project_dna=dna,
                quality_contract=contract,
                task=undeclared,
            )

        invalid_gate = copy.deepcopy(contract)
        invalid_gate["surfaces"][0]["required_gates"].append("magic-score")
        with self.assertRaisesRegex(DodCompilerError, "Quality Contract"):
            compile_done_contract(
                project_dna=dna,
                quality_contract=invalid_gate,
                task={
                    "id": "factory#345-invalid-gate",
                    "title": "API",
                    "change_type": "code",
                    "surfaces": ["api"],
                    "risk": "low",
                },
            )

    def test_docs_keep_performance_recovery_external_and_no_parallel_score(self):
        text = (
            ROOT / "docs" / "quality-gates.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "Performance",
            "Recovery",
            "no recalcula",
            "No hay score único",
            "scheduler",
            "backlog",
        ):
            self.assertIn(marker, text)
        self.assertNotIn('"score"', json.dumps(quality_contract()).lower())


if __name__ == "__main__":
    unittest.main()
