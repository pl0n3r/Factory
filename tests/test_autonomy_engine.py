import copy
import unittest

from evolution.autonomy import (
    AUTHORITY_FINGERPRINT,
    AUTONOMY_LEVELS,
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


def risk(level="low"):
    change_type = {
        "low": "docs",
        "medium": "code",
        "high": "security",
    }[level]
    surface = {
        "low": "docs",
        "medium": "api",
        "high": "auth",
    }[level]
    signals = {
        "production": False,
        "destructive": False,
        "migration": False,
        "touches_auth": level == "high",
        "external_integration": False,
    }
    return compile_risk(
        project_dna=complete_dna(),
        task={
            "id": f"risk-{level}",
            "title": f"{level} risk",
            "change_type": change_type,
            "surfaces": [surface],
            "signals": signals,
        },
    )


def fitness():
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
    return compare_fitness(baseline=baseline, candidate=candidate)


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
                fitness=fitness(),
                risk=risk("low"),
                reason="evidence supports next level",
                evidence=["ci:green", "fitness:stable"],
            )
            observed.append(engine.current.level)

        self.assertEqual(tuple(observed), AUTONOMY_LEVELS)
        with self.assertRaisesRegex(AutonomyError, "ya está en autonomous"):
            engine.promote(
                fitness=fitness(),
                risk=risk("low"),
                reason="cannot skip terminal",
                evidence=["terminal"],
            )

    def test_failures_reduce_or_revoke_autonomy(self):
        engine = AutonomyEngine(
            "delivery",
            reason="observe",
            evidence=["baseline"],
        )
        for _ in range(4):
            engine.promote(
                fitness=fitness(),
                risk=risk("low"),
                reason="earned",
                evidence=["evidence"],
            )
        self.assertEqual(engine.current.level, "autonomous")

        engine.record_failure(
            "minor",
            reason="small regression",
            evidence=["incident#1"],
        )
        self.assertEqual(engine.current.level, "supervised")

        engine.record_failure(
            "major",
            reason="repeated regression",
            evidence=["incident#2"],
        )
        self.assertEqual(engine.current.level, "propose")

        engine.record_failure(
            "critical",
            reason="unsafe behavior",
            evidence=["incident#3"],
        )
        self.assertEqual(engine.current.level, "observe")

    def test_autonomy_never_expands_constitutional_authority(self):
        engine = AutonomyEngine(
            "analysis",
            reason="observe",
            evidence=["baseline"],
        )
        initial = engine.authority
        for _ in range(4):
            engine.promote(
                fitness=fitness(),
                risk=risk("low"),
                reason="earned",
                evidence=["evidence"],
            )
            self.assertEqual(engine.authority, initial)
            self.assertEqual(engine.current.authority_fingerprint, AUTHORITY_FINGERPRINT)
            self.assertEqual(engine.authority["external_permissions_added"], [])

        with self.assertRaisesRegex(AutonomyError, "risk high"):
            limited = AutonomyEngine(
                "security-change",
                reason="observe",
                evidence=["baseline"],
            )
            for _ in range(3):
                limited.promote(
                    fitness=fitness(),
                    risk=risk("medium"),
                    reason="earned",
                    evidence=["evidence"],
                )
            limited.promote(
                fitness=fitness(),
                risk=risk("high"),
                reason="attempt autonomous",
                evidence=["evidence"],
            )

    def test_promotion_and_downgrade_are_auditable(self):
        engine = AutonomyEngine(
            "context-compilation",
            reason="observe",
            evidence=["issue#151"],
        )
        promotion = engine.promote(
            fitness=fitness(),
            risk=risk("low"),
            reason="validated history",
            evidence=["run#1", "run#2"],
        )
        downgrade = engine.record_failure(
            "minor",
            reason="new regression",
            evidence=["incident#42"],
        )

        self.assertEqual(promotion.action, "promote")
        self.assertEqual(promotion.previous_level, "observe")
        self.assertIsNotNone(promotion.fitness_fingerprint)
        self.assertIsNotNone(promotion.risk_fingerprint)
        self.assertEqual(downgrade.action, "downgrade:minor")
        self.assertEqual(downgrade.previous_level, "propose")
        self.assertEqual(downgrade.evidence, ("incident#42",))
        self.assertEqual(len(engine.history), 3)
        self.assertRegex(engine.snapshot()["fingerprint"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
