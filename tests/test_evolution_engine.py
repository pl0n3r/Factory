import unittest

from evolution.constitution import EXPECTED_LIFECYCLE
from evolution.engine import EvolutionEngine
from evolution.models import EvolutionError


def valid_candidate():
    return {
        "version": 1,
        "changes": [
            {
                "path": "evolution_state.heuristics.review_threshold",
                "operation": "replace",
                "value": 3,
            }
        ],
        "evidence": ["factory#145:test"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


class EvolutionEngineTests(unittest.TestCase):
    def make_engine(self):
        return EvolutionEngine(
            valid_candidate(),
            reason="observación inicial",
            evidence=["signal:initial"],
        )

    def advance_to_prune(self, engine):
        for stage in EXPECTED_LIFECYCLE[1:-1]:
            kwargs = {}
            if stage == "promote_or_reject":
                kwargs["decision"] = "adopt"
            engine.transition(
                stage,
                reason=f"advance:{stage}",
                evidence=[f"evidence:{stage}"],
                **kwargs,
            )

    def test_candidate_follows_closed_lifecycle(self):
        engine = self.make_engine()
        self.assertEqual(engine.lifecycle, EXPECTED_LIFECYCLE)
        self.advance_to_prune(engine)
        engine.rollback(
            0,
            reason="restore baseline",
            evidence=["incident:regression"],
        )

        self.assertEqual(
            tuple(record.stage for record in engine.history),
            EXPECTED_LIFECYCLE,
        )
        self.assertEqual(engine.current.stage, "rollback")
        self.assertEqual(engine.active_generation, 0)

    def test_invalid_transition_fails_closed(self):
        engine = self.make_engine()

        with self.assertRaisesRegex(EvolutionError, "transición inválida"):
            engine.transition(
                "experiment",
                reason="skip",
                evidence=["invalid:skip"],
            )

        with self.assertRaisesRegex(EvolutionError, "decision"):
            engine.transition(
                "remember",
                reason="bad decision placement",
                evidence=["invalid:decision"],
                decision="adopt",
            )

        engine.transition(
            "remember",
            reason="remember",
            evidence=["signal:remember"],
        )
        engine.transition(
            "learn",
            reason="learn",
            evidence=["signal:learn"],
        )
        engine.transition(
            "propose",
            reason="propose",
            evidence=["signal:propose"],
        )
        engine.transition(
            "shadow",
            reason="shadow",
            evidence=["signal:shadow"],
        )
        engine.transition(
            "experiment",
            reason="experiment",
            evidence=["signal:experiment"],
        )
        engine.transition(
            "validate",
            reason="validate",
            evidence=["signal:validate"],
        )
        with self.assertRaisesRegex(EvolutionError, "adopt o reject"):
            engine.transition(
                "promote_or_reject",
                reason="missing decision",
                evidence=["invalid:missing-decision"],
            )

    def test_lineage_preserves_parent_reason_and_evidence(self):
        engine = self.make_engine()
        record = engine.transition(
            "remember",
            reason="remember signal",
            evidence=["issue:145", "test:lineage"],
        )

        self.assertEqual(record.generation, 1)
        self.assertEqual(record.parent_generation, 0)
        self.assertEqual(record.reason, "remember signal")
        self.assertEqual(record.evidence, ("issue:145", "test:lineage"))
        self.assertEqual(
            record.candidate_fingerprint,
            engine.history[0].candidate_fingerprint,
        )

    def test_rollback_restores_prior_generation_without_erasing_history(self):
        engine = self.make_engine()
        self.advance_to_prune(engine)
        before = engine.history

        rollback = engine.rollback(
            2,
            reason="fitness regression",
            evidence=["metric:regressed"],
        )

        self.assertEqual(len(engine.history), len(before) + 1)
        self.assertEqual(engine.history[:-1], before)
        self.assertEqual(rollback.parent_generation, before[-1].generation)
        self.assertEqual(rollback.restores_generation, 2)
        self.assertEqual(engine.active_generation, 2)

        with self.assertRaisesRegex(EvolutionError, "etapa actual"):
            engine.rollback(
                1,
                reason="second rollback",
                evidence=["invalid:second"],
            )


if __name__ == "__main__":
    unittest.main()
