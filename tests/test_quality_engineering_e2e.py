import copy
import unittest
from pathlib import Path

from intelligence.dod_compiler import compile_done_contract
from intelligence.project_dna import attach_quality_contract, discover_project_dna
from intelligence.risk_compiler import compile_risk
from quality.regression import analyze_regression
from quality.status import derive_quality_health, readiness_projection
from scripts.dispatcher_v2 import (
    WorkItemReadinessContext,
    candidate_from_work_item,
    classify_readiness,
    select_next,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T03:00:00Z"


def quality_contract():
    return {
        "version": 1,
        "project": "factory",
        "surfaces": [{
            "id": "api",
            "criticality": "critical",
            "required_gates": ["contract", "e2e", "security"],
        }],
        "invariants": ["authorization", "no-secret-logging"],
        "compatibility": {
            "runtimes": ["python-3"],
            "browsers": [],
            "devices": [],
        },
        "accessibility": {"target": "NOT_APPLICABLE"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": False, "source_ref": None},
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


def governed_dna(contract):
    dna = discover_project_dna(
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
    return attach_quality_contract(
        dna,
        source_ref="pl0n3r/Factory#343",
        contract=contract,
    )


def risk_task():
    return {
        "id": "factory#348-api",
        "title": "Quality E2E API",
        "change_type": "code",
        "surfaces": ["api"],
        "signals": {
            "production": False,
            "destructive": False,
            "migration": False,
            "touches_auth": False,
            "external_integration": False,
        },
    }


def gate_evidence(status="PASS", *, observed_at="2026-09-29T02:30:00Z"):
    return [
        {
            "surface": "api",
            "gate": gate,
            "status": status,
            "observed_at": observed_at,
            "evidence_ref": f"ci:api:{gate}",
        }
        for gate in ("contract", "e2e", "security")
    ]


def regression(*, before_failures=3, after_failures=0):
    return analyze_regression(
        {
            "version": 1,
            "regression_id": "quality-e2e-001",
            "project": "pl0n3r/Factory",
            "surface": "api",
            "signature": "quality contract regression",
            "occurred_at": "2026-09-29T02:00:00Z",
            "source": "pl0n3r/Factory#348",
            "root_cause": "The regression bypassed a required quality gate.",
            "prevention": "Keep the gate in the compiled Definition of Done.",
            "before": {
                "runs": 3,
                "failures": before_failures,
                "evidence_ref": "ci:quality:before",
                "observed_at": "2026-09-29T02:10:00Z",
            },
            "after": {
                "runs": 3,
                "failures": after_failures,
                "evidence_ref": "ci:quality:after",
                "observed_at": "2026-09-29T02:20:00Z",
            },
            "regression_test_ref": (
                "tests/test_quality_engineering_e2e.py::"
                "QualityEngineeringE2ETests"
            ),
        },
        evaluated_at="2026-09-29T02:40:00Z",
    )


def performance_health():
    return {
        "status": "HEALTHY",
        "reasons": [],
        "evidence_refs": ["run:performance:348"],
        "evidence_state": "CURRENT",
        "project": "factory",
        "surface": "api",
        "metric": "latency",
        "authority": "unchanged",
        "execute_actions": False,
    }


def recovery_health():
    return {
        "version": 1,
        "project": "factory",
        "state": "HEALTHY",
        "reasons": ["RECOVERY_EVIDENCE_CURRENT"],
        "work_item_classes": [],
        "authority": "unchanged",
        "execute": False,
    }


def derive(gates, regressions):
    return derive_quality_health(
        quality_contract(),
        gates,
        regressions,
        observed_at=NOW,
        project_ref="pl0n3r/Factory",
        performance_status=performance_health(),
        recovery_health=recovery_health(),
    )


class QualityEngineeringE2ETests(unittest.TestCase):
    def test_quality_happy_path_contract_to_readiness_uses_real_contracts(self):
        contract = quality_contract()
        dna = governed_dna(contract)

        risk = compile_risk(
            project_dna=dna,
            task=risk_task(),
            quality_contract=contract,
        )
        self.assertEqual(risk["risk"], "high")
        self.assertEqual(risk["dimensions"]["quality"], "high")

        done = compile_done_contract(
            project_dna=dna,
            quality_contract=contract,
            task={
                "id": "factory#348-api",
                "title": "Quality E2E API",
                "change_type": "code",
                "surfaces": ["api"],
                "risk": risk["risk"],
            },
        )
        required = {
            (row["kind"], row["target"])
            for row in done["evidence"]
        }
        self.assertIn(("test", "quality:contract"), required)
        self.assertIn(("test", "quality:e2e"), required)
        self.assertIn(("check", "quality:security"), required)
        self.assertEqual(
            done["quality_contract_fingerprint"],
            dna["extensions"]["quality_contract"]["fingerprint"],
        )

        health = derive(gate_evidence(), [regression()])
        readiness = readiness_projection(health)
        self.assertEqual(health["state"], "PASS")
        self.assertEqual(health["authority"], "unchanged")
        self.assertFalse(health["execute_actions"])
        self.assertFalse(health["parallel_queue"])
        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["recalculated"])
        self.assertEqual(readiness["quality_health"], health["state"])

    def test_critical_quality_failure_materializes_corrective_work_through_existing_dispatcher(self):
        gates = gate_evidence()
        gates[2]["status"] = "FAIL"
        health = derive(gates, [])
        readiness = readiness_projection(health)

        self.assertEqual(health["state"], "BLOCKED")
        self.assertFalse(readiness["ready"])
        self.assertTrue(readiness["critical_blocker"])
        self.assertIn("quality_gate_failed", health["work_item_classes"])

        work_item = {
            "work_id": "quality-fix-348",
            "origin_mode": "automatic",
            "origin_system": "factory",
            "group_id": "pl0n3r",
            "project_id": "factory",
            "repository_ref": "pl0n3r/Factory",
            "work_type": "engineering",
            "requested_capabilities": ["python"],
            "required_roles": ["qa"],
            "authority_level": "standard",
            "producer_ref": "quality-health-v1",
            "priority_class": "high",
            "depends_on": [],
            "claims": ["quality/status.py"],
            "policy_ref": "factory:quality",
            "evidence_refs": health["evidence_refs"],
            "idempotency_key": "quality_gate_failed",
        }
        context = WorkItemReadinessContext(
            authority_valid=True,
            policy_valid=True,
            freshness_valid=True,
            evidence_valid=True,
        )
        candidate = candidate_from_work_item(work_item, context)
        self.assertTrue(classify_readiness(candidate).ready)
        self.assertEqual(select_next([candidate]).key, "quality-fix-348")
        self.assertEqual(candidate.metadata["origin_system"], "factory")

    def test_stale_flaky_or_unknown_evidence_fails_closed_without_expanding_authority(self):
        stale = derive(
            gate_evidence(observed_at="2026-09-29T00:00:00Z"),
            [],
        )
        self.assertEqual(stale["state"], "UNKNOWN")
        self.assertFalse(readiness_projection(stale)["ready"])

        flaky = derive(
            gate_evidence(),
            [regression(before_failures=1)],
        )
        self.assertEqual(flaky["state"], "DEGRADED")
        self.assertNotEqual(flaky["state"], "PASS")

        unknown_gates = gate_evidence()
        unknown_gates[0]["status"] = "UNKNOWN"
        unknown = derive(unknown_gates, [])
        self.assertEqual(unknown["state"], "UNKNOWN")
        self.assertFalse(readiness_projection(unknown)["ready"])

        for artifact in (stale, flaky, unknown):
            self.assertEqual(artifact["authority"], "unchanged")
            self.assertFalse(artifact["execute_actions"])
            self.assertFalse(artifact["parallel_queue"])

    def test_docs_define_single_quality_pipeline_and_external_dimension_boundaries(self):
        text = (
            ROOT / "docs" / "quality-engineering.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "Quality Contract",
            "Project DNA",
            "Risk/DoD",
            "Regression Intelligence",
            "Quality Health",
            "Readiness #293",
            "Factory Queue #269",
            "Performance #304",
            "Recovery #305",
            "sin recalcular",
            "sin scheduler",
            "sin backlog",
            "authority=unchanged",
            "execute_actions=false",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
