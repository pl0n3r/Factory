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


def base_dna():
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


def governed_dna(contract):
    return attach_quality_contract(
        base_dna(),
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


def dod_task(risk):
    return {
        "id": "factory#348-api",
        "title": "Quality E2E API",
        "change_type": "code",
        "surfaces": ["api"],
        "risk": risk,
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


def derive(gates, regressions, *, perf=None, recovery=None):
    return derive_quality_health(
        quality_contract(),
        gates,
        regressions,
        observed_at=NOW,
        project_ref="pl0n3r/Factory",
        performance_status=performance_health() if perf is None else perf,
        recovery_health=recovery_health() if recovery is None else recovery,
    )


class QualityEngineeringE2ETests(unittest.TestCase):
    def test_contract_to_project_dna_to_risk_and_dod_preserves_fingerprint_and_authority(self):
        contract = quality_contract()
        dna = governed_dna(contract)
        extension = dna["extensions"]["quality_contract"]
        self.assertEqual(
            set(extension),
            {"version", "source_ref", "fingerprint"},
        )
        self.assertEqual(extension["source_ref"], "pl0n3r/Factory#343")

        risk = compile_risk(
            project_dna=dna,
            task=risk_task(),
            quality_contract=contract,
        )
        done = compile_done_contract(
            project_dna=dna,
            quality_contract=contract,
            task=dod_task(risk["risk"]),
        )

        self.assertEqual(risk["risk"], "high")
        self.assertEqual(risk["dimensions"]["quality"], "high")
        self.assertEqual(
            risk["quality_contract_fingerprint"],
            extension["fingerprint"],
        )
        self.assertEqual(
            done["quality_contract_fingerprint"],
            extension["fingerprint"],
        )
        targets = {(row["kind"], row["target"]) for row in done["evidence"]}
        self.assertIn(("test", "quality:contract"), targets)
        self.assertIn(("test", "quality:e2e"), targets)
        self.assertIn(("check", "quality:security"), targets)
        self.assertNotIn("authority", risk)
        self.assertNotIn("authority", done)

    def test_current_verified_healthy_flow_reaches_quality_pass_and_ready(self):
        health = derive(gate_evidence(), [regression()])
        projected = readiness_projection(health)

        self.assertEqual(health["state"], "PASS")
        self.assertEqual(health["authority"], "unchanged")
        self.assertFalse(health["execute_actions"])
        self.assertFalse(health["parallel_queue"])
        self.assertTrue(projected["ready"])
        self.assertFalse(projected["critical_blocker"])
        self.assertFalse(projected["recalculated"])
        self.assertEqual(projected["quality_health"], "PASS")

    def test_missing_stale_flaky_or_reproduced_evidence_fails_closed(self):
        missing = derive(gate_evidence()[:-1], [])
        self.assertEqual(missing["state"], "UNKNOWN")
        self.assertFalse(readiness_projection(missing)["ready"])

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

        reproduced = derive(
            gate_evidence(),
            [regression(after_failures=3)],
        )
        self.assertEqual(reproduced["state"], "BLOCKED")
        self.assertFalse(readiness_projection(reproduced)["ready"])

        for artifact in (missing, stale, flaky, reproduced):
            self.assertEqual(artifact["authority"], "unchanged")
            self.assertFalse(artifact["execute_actions"])
            self.assertFalse(artifact["parallel_queue"])

    def test_performance_and_recovery_remain_external_without_recalculation(self):
        health = derive(gate_evidence(), [regression()])
        perf = health["external_dimensions"]["performance"]
        recovery = health["external_dimensions"]["recovery"]

        self.assertEqual(perf["status"], "HEALTHY")
        self.assertEqual(recovery["status"], "HEALTHY")
        self.assertFalse(perf["recalculated"])
        self.assertFalse(recovery["recalculated"])
        self.assertIn("run:performance:348", perf["evidence_refs"])
        self.assertIn("RECOVERY_EVIDENCE_CURRENT", recovery["reasons"])
        self.assertIn("run:performance:348", health["evidence_refs"])

    def test_corrective_quality_class_materializes_via_existing_workitem_dispatcher(self):
        gates = gate_evidence()
        gates[2]["status"] = "FAIL"
        health = derive(gates, [])
        projected = readiness_projection(health)

        self.assertEqual(health["state"], "BLOCKED")
        self.assertFalse(projected["ready"])
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

    def test_project_without_quality_extension_keeps_legacy_risk_and_dod_behavior(self):
        dna = base_dna()
        risk = compile_risk(
            project_dna=dna,
            task=risk_task(),
        )
        done = compile_done_contract(
            project_dna=dna,
            task=dod_task(risk["risk"]),
        )

        self.assertEqual(risk["risk"], "medium")
        self.assertNotIn("quality", risk["dimensions"])
        self.assertNotIn("quality_contract_fingerprint", risk)
        self.assertNotIn("quality_contract_fingerprint", done)
        self.assertIn(
            {"kind": "test", "target": "api:contract"},
            done["evidence"],
        )

    def test_docs_close_quality_dag_without_parallel_engine(self):
        text = (
            ROOT / "docs" / "quality-engineering.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "#343–#347",
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
            "Quality Engine",
            "authority=unchanged",
            "execute_actions=false",
            "rollout",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
