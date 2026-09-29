import copy
import unittest
from pathlib import Path

from intelligence.dod_compiler import (
    FACTORY_INVARIANTS,
    DodCompilerError,
    compile_done_contract,
)
from intelligence.project_dna import attach_quality_contract, discover_project_dna
from intelligence.risk_compiler import RiskCompilerError, compile_risk


ROOT = Path(__file__).resolve().parents[1]


def dna():
    return discover_project_dna(
        paths=[
            "package.json", ".github/workflows/ci.yml", "vercel.json",
            "database/schema.sql", ".sentryclirc",
        ],
        manifests={
            "package.json": {
                "dependencies": {"fastify": "^5", "@sentry/node": "^9"}
            }
        },
        capabilities=["api", "auth", "web"],
    )


def quality():
    return {
        "version": 1,
        "project": "factory",
        "surfaces": [
            {"id": "api", "criticality": "high",
             "required_gates": ["contract", "e2e", "security"]},
            {"id": "auth", "criticality": "low",
             "required_gates": ["security", "tenancy"]},
            {"id": "docs", "criticality": "critical",
             "required_gates": ["accessibility", "unit"]},
        ],
        "invariants": ["authorization"],
        "compatibility": {
            "runtimes": ["python-3"], "browsers": [], "devices": []
        },
        "accessibility": {"target": "WCAG_AA"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": True, "source_ref": "pl0n3r/Factory#306"},
        "evidence_freshness_seconds": 3600,
        "dimensions": {
            "performance": {
                "required": True, "source_ref": "pl0n3r/Factory#304"
            },
            "recovery": {
                "required": True, "source_ref": "pl0n3r/Factory#305"
            },
        },
    }


def governed(contract):
    return attach_quality_contract(
        dna(), source_ref="pl0n3r/Factory#343", contract=contract
    )


def risk_task(surface, *, change_type="code", touches_auth=False):
    return {
        "id": f"factory#345-{surface}",
        "title": surface,
        "change_type": change_type,
        "surfaces": [surface],
        "signals": {
            "production": False,
            "destructive": False,
            "migration": False,
            "touches_auth": touches_auth,
            "external_integration": False,
        },
    }


class QualityGateCompilerTests(unittest.TestCase):
    def test_risk_uses_authenticated_quality_surface_criticality_without_lowering_base_risk(self):
        contract = quality()
        project = governed(contract)
        raised = compile_risk(
            project_dna=project,
            quality_contract=contract,
            task=risk_task("docs", change_type="docs"),
        )
        self.assertEqual((raised["risk"], raised["dimensions"]["quality"]),
                         ("high", "high"))
        self.assertIn(
            "quality_contract.surfaces.docs.criticality",
            {row["source"] for row in raised["trace"]},
        )

        high = compile_risk(
            project_dna=project,
            quality_contract=contract,
            task=risk_task("auth", change_type="security", touches_auth=True),
        )
        self.assertEqual(high["risk"], "high")
        self.assertEqual(high["dimensions"]["quality"], "low")

    def test_dod_adds_required_quality_gates_without_removing_existing_evidence(self):
        contract = quality()
        done = compile_done_contract(
            project_dna=governed(contract),
            quality_contract=contract,
            task={
                "id": "factory#345-api", "title": "API",
                "change_type": "code", "surfaces": ["api"], "risk": "low",
            },
        )
        for item in FACTORY_INVARIANTS:
            self.assertIn(dict(item), done["evidence"])
        for item in (
            {"kind": "test", "target": "quality:contract"},
            {"kind": "test", "target": "quality:e2e"},
            {"kind": "check", "target": "quality:security"},
            {"kind": "test", "target": "api:contract"},
        ):
            self.assertIn(item, done["evidence"])

    def test_dna_without_quality_extension_preserves_existing_risk_and_dod_behavior(self):
        project = dna()
        risk = compile_risk(project_dna=project, task=risk_task("api"))
        done = compile_done_contract(
            project_dna=project,
            task={
                "id": "legacy", "title": "API", "change_type": "code",
                "surfaces": ["api"], "risk": "medium",
            },
        )
        self.assertEqual(risk["risk"], "medium")
        self.assertNotIn("quality", risk["dimensions"])
        self.assertNotIn("quality_contract_fingerprint", done)
        self.assertIn({"kind": "test", "target": "api:contract"}, done["evidence"])

    def test_missing_mismatched_or_undeclared_quality_context_fails_closed(self):
        contract = quality()
        project = governed(contract)
        with self.assertRaisesRegex(RiskCompilerError, "falta evidencia fuente"):
            compile_risk(project_dna=project, task=risk_task("api"))

        mismatch = copy.deepcopy(contract)
        mismatch["evidence_freshness_seconds"] = 7200
        with self.assertRaisesRegex(RiskCompilerError, "fingerprint"):
            compile_risk(
                project_dna=project,
                quality_contract=mismatch,
                task=risk_task("api"),
            )

        with self.assertRaisesRegex(RiskCompilerError, "no declarada"):
            compile_risk(
                project_dna=project,
                quality_contract=contract,
                task=risk_task("billing"),
            )

        invalid = copy.deepcopy(contract)
        invalid["surfaces"][0]["required_gates"].append("magic-score")
        with self.assertRaisesRegex(DodCompilerError, "Quality Contract"):
            compile_done_contract(
                project_dna=project,
                quality_contract=invalid,
                task={
                    "id": "bad", "title": "API", "change_type": "code",
                    "surfaces": ["api"], "risk": "low",
                },
            )

    def test_docs_keep_performance_recovery_external_and_no_parallel_score(self):
        text = (ROOT / "docs" / "quality-gates.md").read_text(encoding="utf-8")
        for marker in (
            "Performance", "Recovery", "no recalcula",
            "No hay score único", "scheduler", "backlog",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
