#!/usr/bin/env python3
import unittest

from scripts.dispatcher_v2 import (
    Candidate,
    DirectionLeaf,
    DirectionProposal,
    direction_gate_trigger,
)


class DirectionGateThresholdBoundaryTests(unittest.TestCase):
    def proposal(self):
        return DirectionProposal(
            repository_ref="pl0n3r/Condor",
            objective="Preparar el siguiente tramo antes de vaciar la cola.",
            leaves=(
                DirectionLeaf(
                    key="CONDOR_NEXT",
                    title="Siguiente leaf funcional",
                    acceptance_targets=(
                        "tests/test_next_slice.py::NextSliceTests::test_first_leaf",
                    ),
                ),
            ),
        )

    def test_rejects_invalid_threshold_values(self):
        for value in (-1, True, 1.5, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "threshold"
            ):
                direction_gate_trigger(
                    self.proposal(),
                    [],
                    eligible_leaf_threshold=value,
                )

    def test_zero_threshold_requires_empty_eligible_queue(self):
        candidate = Candidate(
            key="condor-current",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        result = direction_gate_trigger(
            self.proposal(),
            [candidate],
            eligible_leaf_threshold=0,
        )
        self.assertEqual(result["action"], "noop")
        self.assertEqual(result["reason"], "sufficient_eligible_work")
        self.assertEqual(result["eligible_leaf_count"], 1)
        self.assertEqual(result["eligible_leaf_threshold"], 0)

    def test_count_ignores_other_repositories_and_epics(self):
        target = Candidate(
            key="condor-current",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        other_repo = Candidate(
            key="grindflow-current",
            priority="high",
            metadata={"repository_ref": "pl0n3r/GrindFlow"},
        )
        epic = Candidate(
            key="condor-epic",
            priority="high",
            is_epic=True,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        result = direction_gate_trigger(
            self.proposal(),
            [target, other_repo, epic],
            eligible_leaf_threshold=1,
        )
        self.assertEqual(result["action"], "open_gate")
        self.assertEqual(result["eligible_leaf_count"], 1)


if __name__ == "__main__":
    unittest.main()
