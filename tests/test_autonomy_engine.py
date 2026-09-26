import copy
import unittest

from evolution.autonomy import (
    AUTHORITY_FINGERPRINT,
    AUTONOMY_LEVELS,
    CapabilityScope,
    AutonomyEngine,
    AutonomyError,
)
from evolution.fitness import compare_fitness
from intelligence.project_dna import discover_project_dna
from intelligence.risk_compiler import compile_risk


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


def risk_inputs(level="low"):
    change_type = {"low": "docs", "medium": "code", "high": "security"}[level]
    surface = {"low": "docs", "medium": "api", "high": "auth"}[level]
    task = {
        "id": f"risk-{level}",
        "title": f"{level} risk",
        "change_type": change_type,
        "surfaces": [surface],
        "signals": {
            "production": False,
            "destructive": False,
            "migration": False,
            "touches_auth": level == "high",
            "external_integration": False,
        },
    }
    dna = complete_dna()
    return dna, task


def risk_evidence(level="low"):
    dna, task = risk_inputs(level)
    return {
        "project_dna": dna,
        "task": task,
        "result": compile_risk(project_dna=dna, task=task),
    }


def fitness_inputs():
    protected = {
        "security": {"value": 1.0, "direction": "higher"},
        "privacy": {"value": 1.0, "direction": "higher"},
        "traceability": {"value": 1.0, "direction": "higher"},
        "reversibility": {"value": 1.0, "direction": "higher"},
        "authority": {"value": 1.0, "direction": "higher"},
    }
    baseline = {**protected, "reliability": {"value": 0.90, "direction": "higher"}}
    candidate = copy.deepcopy(baseline)
    candidate["reliability"]["value"] = 0.95
    return baseline, candidate


def fitness_evidence():
    baseline, candidate = fitness_inputs()
    return {
        "baseline": baseline,
        "candidate": candidate,
        "protected_dimensions": None,
        "result": compare_fitness(baseline=baseline, candidate=candidate),
    }


class AutonomyEngineTests(unittest.TestCase):
    def test_capability_progresses_through_evidence_ladder(self):
        engine = AutonomyEngine(
            "risk-compilation",
            reason="start observed",
            evidence=["issue#151"],
        )
        observed = [engine.current.level]
        for _ in AUTONOMY_LEVELS[1:]:
            engine.promote(
                fitness=fitness_evidence(),
                risk=risk_evidence("low"),
                reason="evidence supports next level",
                evidence=["ci:green", "fitness:stable"],
            )
            observed.append(engine.current.level)
        self.assertEqual(tuple(observed), AUTONOMY_LEVELS)

    def test_failures_reduce_or_revoke_autonomy(self):
        engine = AutonomyEngine("delivery", reason="observe", evidence=["baseline"])
        for _ in range(4):
            engine.promote(
                fitness=fitness_evidence(),
                risk=risk_evidence("low"),
                reason="earned",
                evidence=["evidence"],
            )
        engine.record_failure("minor", reason="small regression", evidence=["incident#1"])
        self.assertEqual(engine.current.level, "supervised")
        engine.record_failure("major", reason="repeated regression", evidence=["incident#2"])
        self.assertEqual(engine.current.level, "propose")
        engine.record_failure("critical", reason="unsafe behavior", evidence=["incident#3"])
        self.assertEqual(engine.current.level, "observe")

    def test_forbidden_authority_capabilities_cannot_gain_autonomy(self):
        for authority_class in (
            "money",
            "legal",
            "personal_data",
            "irreversible_delete",
        ):
            engine = AutonomyEngine(
                CapabilityScope("restricted", authority_class),
                reason="observe",
                evidence=["baseline"],
            )
            with self.assertRaisesRegex(AutonomyError, "authority class prohibida"):
                engine.promote(
                    fitness=fitness_evidence(),
                    risk=risk_evidence("low"),
                    reason="forbidden",
                    evidence=["evidence"],
                )
            self.assertEqual(engine.current.level, "observe")
            self.assertEqual(len(engine.history), 1)

    def test_forged_fitness_evidence_is_rejected(self):
        evidence = fitness_evidence()
        forged = copy.deepcopy(evidence)
        forged["result"]["claim"] = "equal"
        forged["result"]["can_claim_improvement"] = False
        forged["result"]["fingerprint"] = "a" * 64
        engine = AutonomyEngine("analysis", reason="observe", evidence=["baseline"])
        with self.assertRaisesRegex(AutonomyError, "fitness evidence no es canónica"):
            engine.promote(
                fitness=forged,
                risk=risk_evidence("low"),
                reason="forged",
                evidence=["evidence"],
            )

    def test_forged_risk_evidence_is_rejected(self):
        evidence = risk_evidence("low")
        forged = copy.deepcopy(evidence)
        forged["result"]["risk"] = "low"
        forged["result"]["context_complete"] = True
        forged["result"]["fingerprint"] = "b" * 64
        forged["task"]["change_type"] = "security"
        engine = AutonomyEngine("analysis", reason="observe", evidence=["baseline"])
        with self.assertRaisesRegex(AutonomyError, "risk evidence no es canónica"):
            engine.promote(
                fitness=fitness_evidence(),
                risk=forged,
                reason="forged",
                evidence=["evidence"],
            )

    def test_canonical_evidence_contracts_remain_promotable(self):
        engine = AutonomyEngine("analysis", reason="observe", evidence=["baseline"])
        record = engine.promote(
            fitness=fitness_evidence(),
            risk=risk_evidence("low"),
            reason="canonical",
            evidence=["run#1"],
        )
        self.assertEqual(record.level, "propose")
        self.assertRegex(record.fitness_fingerprint, r"^[0-9a-f]{64}$")
        self.assertRegex(record.risk_fingerprint, r"^[0-9a-f]{64}$")

    def test_hardening_preserves_authority_and_ladder(self):
        engine = AutonomyEngine(
            CapabilityScope("analysis", "operational"),
            reason="observe",
            evidence=["baseline"],
        )
        initial = engine.authority
        observed = [engine.current.level]
        for _ in AUTONOMY_LEVELS[1:]:
            record = engine.promote(
                fitness=fitness_evidence(),
                risk=risk_evidence("low"),
                reason="earned",
                evidence=["evidence"],
            )
            observed.append(record.level)
            self.assertEqual(engine.authority, initial)
            self.assertEqual(record.authority_fingerprint, AUTHORITY_FINGERPRINT)
            self.assertEqual(record.authority_class, "operational")
        self.assertEqual(tuple(observed), AUTONOMY_LEVELS)
        self.assertEqual(engine.authority["external_permissions_added"], [])


if __name__ == "__main__":
    unittest.main()
