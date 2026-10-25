"""Factory #1501: benchmark GET-only sin fake ADOPT ni exposición de logs."""
import unittest

from performance.ci_suite_benchmark import (
    SuiteBenchmarkError,
    compare_unittest_summaries,
    parse_unittest_summary,
)


def summary(count: int, seconds: str) -> str:
    return (
        "2026-10-24T18:15:58.0838084Z ...\n"
        f"2026-10-24T18:16:01.3389022Z Ran {count} tests in {seconds}s\n"
        "2026-10-24T18:16:01.3389359Z \n"
        "2026-10-24T18:16:01.3389613Z OK\n"
    )


def identity(run: int, sha: str, job: int) -> dict:
    return {
        "repository": "pl0n3r/FactoryRunner",
        "event": "push",
        "branch": "main",
        "suite": "python.unittest",
        "run_id": run,
        "head_sha": sha,
        "job_id": job,
    }


class CiSuiteBenchmarkTests(unittest.TestCase):
    def test_parse_real_python_summary_without_exposing_logs(self):
        observed = parse_unittest_summary(
            "2026-10-24T18:14:16.664Z opaque_sensitive_synthetic_marker\n"
            + summary(616, "104.376")
        )
        self.assertEqual(
            observed,
            {
                "suite": "python.unittest", "tests": 616,
                "duration_ms": 104376, "status": "DIAGNOSTIC_ONLY",
            },
        )
        self.assertNotIn("opaque_sensitive", str(observed))

    def test_invalid_or_ambiguous_logs_fail_closed(self):
        valid = summary(616, "104.376")
        invalid = [
            "", "not a test log", valid + valid,
            summary(0, "104.376"),
            summary(616, "0"), summary(616, "99999"),
            summary(616, "104.376").replace("OK", "FAILED (errors=1)"),
            valid.replace("OK", ""),
            valid.replace("104.376", "nan"),
            valid + "\x00",
            valid + " " * 256001,
            "Ran 616 tests in 104.376s\nOK\nRan 616 tests in 104.376s\nOK",
            valid + "Ran 999 tests in 1.000s \nOK\n",
            "Ran 616 tests in 104.376s \nOK\n",
            "\ud800",
        ]
        for raw in invalid:
            with self.subTest(case=str(raw[:30]).encode("ascii", errors="backslashreplace")):
                with self.assertRaises(SuiteBenchmarkError):
                    parse_unittest_summary(raw)

    def test_real_runs_differ_in_test_count_and_are_not_comparable(self):
        old = parse_unittest_summary(summary(615, "152.868"))
        current = parse_unittest_summary(summary(616, "104.376"))
        old_run = identity(
            40029930158, "789a312d7520e9813835f99d8c4e5de5ee22cb2a",
            120675383335,
        )
        new_run = identity(
            40119747013, "33277d549a82e9cba5371982d1d80e43e06bd0d5",
            120948484385,
        )
        result = compare_unittest_summaries(old, current, old_run, new_run)
        self.assertEqual(result["status"], "NO_COMPARABLE")
        self.assertEqual(result["reason"], "different_test_count")
        self.assertIsNone(result["duration_delta_ms"])
        self.assertFalse(result["adopt"])
        self.assertFalse(result["create_work_item"])
        self.assertFalse(result["execute_actions"])

    def test_comparable_synthetic_runs_only_produce_advisory_delta(self):
        old = parse_unittest_summary(summary(616, "100.000"))
        current = parse_unittest_summary(summary(616, "90.500"))
        old_run = identity(100, "a" * 40, 111)
        new_run = identity(101, "b" * 40, 112)
        result = compare_unittest_summaries(old, current, old_run, new_run)
        self.assertEqual(result["status"], "COMPARABLE_DIAGNOSTIC")
        self.assertEqual(result["duration_delta_ms"], -9500)
        self.assertEqual(result["sample_pairs"], 1)
        self.assertEqual(result["causality"], "unproven")
        self.assertEqual(result["authority"], "unchanged")
        self.assertFalse(result["adopt"])
        self.assertFalse(result["execute_actions"])
        for corrupt_before, corrupt_after in [
            ({**old, "tests": True}, current),
            (old, {**current, "status": "HEALTHY"}),
            ({**old, "test_payload": "secret"}, current),
        ]:
            with self.assertRaises(SuiteBenchmarkError):
                compare_unittest_summaries(
                    corrupt_before, corrupt_after, old_run, new_run
                )
        for changed in [
            {**new_run, "run_id": 100},
            {**new_run, "head_sha": "a" * 40},
            {**new_run, "repository": "other/repo"},
            {**new_run, "event": "workflow_run"},
            {**new_run, "head_sha": "invalid"},
        ]:
            with self.assertRaises(SuiteBenchmarkError):
                compare_unittest_summaries(old, current, old_run, changed)


if __name__ == "__main__":
    unittest.main()
