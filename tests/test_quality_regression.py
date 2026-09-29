import copy
import unittest

from lecciones.memoria import validate_lesson
from quality.regression import (
    QualityRegressionError,
    analyze_regression,
    compile_regression_guardrail_candidates,
)

EVALUATED_AT = "2026-09-28T23:00:00Z"


def observation(
    regression_id="quality-flaky-001",
    source="pl0n3r/Factory#346",
    *,
    before_failures=3,
    after_failures=0,
    regression_test_ref="tests/test_quality_regression.py::QualityRegressionTests::test_regression",
):
    return {
        "version": 1,
        "regression_id": regression_id,
        "project": "pl0n3r/Factory",
        "surface": "quality-regression",
        "signature": "quality gate oscillates",
        "occurred_at": "2026-09-28T20:00:00Z",
        "source": source,
        "root_cause": "The same unstable signal was treated as conclusive evidence.",
        "prevention": "Require reproducible before evidence and a clean after sample.",
        "before": {
            "runs": 3,
            "failures": before_failures,
            "evidence_ref": "ci://quality/before",
            "observed_at": "2026-09-28T20:10:00Z",
        },
        "after": {
            "runs": 3,
            "failures": after_failures,
            "evidence_ref": "ci://quality/after",
            "observed_at": "2026-09-28T20:20:00Z",
        },
        "regression_test_ref": regression_test_ref,
    }


class QualityRegressionTests(unittest.TestCase):
    def test_observation_distinguishes_reproducible_and_flaky_without_turning_flaky_green(self):
        reproduced = analyze_regression(
            observation(), evaluated_at=EVALUATED_AT
        )
        self.assertEqual(reproduced["classification"], "VERIFIED")
        self.assertTrue(reproduced["reproduced"])
        self.assertTrue(reproduced["pass_evidence_eligible"])
        self.assertIn("pl0n3r/Factory#346", reproduced["provenance"])
        self.assertIn("ci://quality/before", reproduced["provenance"])
        self.assertIn("ci://quality/after", reproduced["provenance"])

        flaky_before = analyze_regression(
            observation(before_failures=1), evaluated_at=EVALUATED_AT
        )
        self.assertEqual(flaky_before["classification"], "FLAKY")
        self.assertTrue(flaky_before["flaky"])
        self.assertFalse(flaky_before["pass_evidence_eligible"])
        self.assertIsNone(flaky_before["guardrail_material"])

        flaky_after = analyze_regression(
            observation(after_failures=1), evaluated_at=EVALUATED_AT
        )
        self.assertEqual(flaky_after["classification"], "FLAKY")
        self.assertTrue(flaky_after["flaky"])
        self.assertFalse(flaky_after["pass_evidence_eligible"])
        self.assertIsNone(flaky_after["guardrail_material"])

    def test_verified_regression_emits_valid_lesson_and_reuses_experience_guardrail_compiler(self):
        first = analyze_regression(
            observation(), evaluated_at=EVALUATED_AT
        )
        lesson = first["guardrail_material"]
        validated = validate_lesson(lesson, "test")
        self.assertEqual(validated["project"], "pl0n3r/Factory")
        self.assertEqual(validated["source"], "pl0n3r/Factory#346")

        second = observation(
            regression_id="quality-flaky-002",
            source="pl0n3r/Factory#349",
        )
        candidates = compile_regression_guardrail_candidates(
            [observation(), second],
            evaluated_at=EVALUATED_AT,
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["occurrences"], 2)
        self.assertEqual(
            candidates[0]["sources"],
            ["pl0n3r/Factory#346", "pl0n3r/Factory#349"],
        )
        self.assertEqual(
            candidates[0]["candidate"]["changes"][0]["value"]["status"],
            "candidate",
        )

    def test_unverified_fix_or_missing_regression_test_never_emits_guardrail_material(self):
        dirty_after = observation(after_failures=3)
        missing_test = observation(
            regression_id="quality-flaky-003",
            source="pl0n3r/Factory#350",
            regression_test_ref=None,
        )

        for item in (dirty_after, missing_test):
            result = analyze_regression(item, evaluated_at=EVALUATED_AT)
            self.assertFalse(result["pass_evidence_eligible"])
            self.assertIsNone(result["guardrail_material"])

        self.assertEqual(
            compile_regression_guardrail_candidates(
                [dirty_after, missing_test],
                evaluated_at=EVALUATED_AT,
            ),
            [],
        )

    def test_invalid_future_sensitive_or_incoherent_evidence_fails_closed_without_echo(self):
        future = observation()
        future["after"]["observed_at"] = "2999-01-01T00:00:00Z"

        incoherent = observation()
        incoherent["before"]["failures"] = 4

        invalid_ref = observation()
        invalid_ref["source"] = "not a github ref"

        sensitive = observation()
        sensitive["root_cause"] = "token=supersecretvalue"

        for item in (future, incoherent, invalid_ref, sensitive):
            with self.subTest(item=item):
                with self.assertRaises(QualityRegressionError) as caught:
                    analyze_regression(item, evaluated_at=EVALUATED_AT)
                self.assertNotIn("supersecretvalue", str(caught.exception))

    def test_docs_define_regression_boundary_without_parallel_engine_or_queue(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "quality-regression.md"
        ).read_text(encoding="utf-8")
        for marker in (
            "FLAKY",
            "PASS",
            "Experience Guardrail Compiler",
            "no promueve",
            "Immune/Guardrail Engine",
            "scheduler",
            "backlog",
            "Queue #269",
            "Readiness #293",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
