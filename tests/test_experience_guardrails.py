import copy
import unittest

from evolution.constitution import validate_candidate
from evolution.experience_guardrails import compile_guardrail_candidates


def lesson(
    lesson_id,
    source,
    *,
    why="CI drift repeated after local workflow forks.",
    prevention="Consume the central Factory workflow instead of forking it.",
    what="A repository workflow drifted from the central contract.",
    occurred_at="2026-09-20T12:00:00Z",
):
    return {
        "id": lesson_id,
        "project": "pl0n3r/factory",
        "kind": "incident",
        "occurred_at": occurred_at,
        "what": what,
        "why": why,
        "prevention": prevention,
        "source": source,
    }


class ExperienceGuardrailTests(unittest.TestCase):
    def test_repeated_evidence_can_generate_guardrail_candidate(self):
        candidates = compile_guardrail_candidates(
            [
                lesson("drift-001", "pl0n3r/factory#101"),
                lesson(
                    "drift-002",
                    "pl0n3r/factory#102",
                    occurred_at="2026-09-21T12:00:00Z",
                ),
            ]
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["occurrences"], 2)
        self.assertEqual(candidate["lesson_ids"], ["drift-001", "drift-002"])
        self.assertRegex(candidate["candidate_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            validate_candidate(candidate["candidate"]),
            candidate["candidate_fingerprint"],
        )

    def test_single_anecdote_does_not_become_policy(self):
        candidates = compile_guardrail_candidates(
            [lesson("only-001", "pl0n3r/factory#103")]
        )
        self.assertEqual(candidates, [])

    def test_equivalent_lessons_are_consolidated(self):
        base = lesson("eq-001", "pl0n3r/factory#110")
        equivalent = lesson(
            "eq-002",
            "pl0n3r/factory#111",
            why="  CI DRIFT repeated after local workflow forks! ",
            prevention="Consume the CENTRAL Factory workflow instead of forking it.",
            occurred_at="2026-09-22T12:00:00Z",
        )
        duplicate_shape = copy.deepcopy(equivalent)
        duplicate_shape["id"] = "eq-003"
        duplicate_shape["source"] = "pl0n3r/factory#112"
        duplicate_shape["occurred_at"] = "2026-09-23T12:00:00Z"

        candidates = compile_guardrail_candidates(
            [duplicate_shape, base, equivalent]
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["occurrences"], 3)
        self.assertEqual(
            candidates[0]["sources"],
            [
                "pl0n3r/factory#110",
                "pl0n3r/factory#111",
                "pl0n3r/factory#112",
            ],
        )

    def test_candidate_keeps_origin_and_expected_prevention(self):
        first = lesson("origin-001", "pl0n3r/factory#120")
        second = lesson(
            "origin-002",
            "pl0n3r/factory#121",
            occurred_at="2026-09-24T12:00:00Z",
        )
        candidate = compile_guardrail_candidates([second, first])[0]

        value = candidate["candidate"]["changes"][0]["value"]
        self.assertEqual(
            candidate["expected_prevention"],
            "Consume the central Factory workflow instead of forking it.",
        )
        self.assertEqual(value["expected_prevention"], candidate["expected_prevention"])
        self.assertEqual(
            [(item["lesson_id"], item["source"]) for item in value["origins"]],
            [
                ("origin-001", "pl0n3r/factory#120"),
                ("origin-002", "pl0n3r/factory#121"),
            ],
        )
        self.assertEqual(value["status"], "candidate")
        self.assertTrue(candidate["candidate"]["rollback"]["reversible"])


if __name__ == "__main__":
    unittest.main()
