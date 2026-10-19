"""Offline regressions for #1198: shared windows and event provenance."""
from datetime import datetime, timedelta, timezone
import unittest

from metricas.evaluar_agentes import (
    MAX_METRIC_INTEGER, ValidationError, _integer, summarize_product_day,
)

A = "pl0n3r/Factory"
B = "pl0n3r/GrindFlow"
AS_OF = "2026-10-19T12:00:00Z"


def snapshot(repo, *, observed=AS_OF, events=None):
    return {
        "repo": repo, "repository_sha": "a" * 40,
        "observed_at": observed, "source": "github-api",
        "authenticated": True, "complete": True,
        "run_id": 22, "run_status": "completed",
        "run_conclusion": "success", "pages": 1,
        "verified_pages": 1, "events": [] if events is None else events,
    }


def event(repo, number=3, when="2026-10-19T11:00:00Z"):
    return {
        "repo": repo, "number": number, "merge_commit_sha": "b" * 40,
        "merged_at": when, "merged": True,
    }


class ProductMetricsIntegrityTests(unittest.TestCase):
    def test_multi_repo_requires_shared_utc_anchor(self):
        correct = snapshot(A, events=[event(A)])
        also_correct = snapshot(B)
        observed = summarize_product_day(
            [correct, also_correct], as_of=AS_OF, repos=(A, B),
        )
        self.assertEqual("MEASURED", observed["status"])
        self.assertFalse(observed["publication_allowed"])
        self.assertEqual(1, observed["repositories"][A]["merged_prs"])
        self.assertEqual(0, observed["repositories"][B]["merged_prs"])
        for row in observed["repositories"].values():
            self.assertEqual("2026-10-18T12:00:00Z", row["window_start"])
            self.assertEqual(AS_OF, row["window_end"])

        older = snapshot(B, observed="2026-10-19T11:30:00Z")
        unknown = summarize_product_day(
            [correct, older], as_of=AS_OF, repos=(A, B),
        )
        self.assertEqual("UNKNOWN", unknown["status"])
        self.assertEqual("incomparable_repository_windows", unknown["reason"])
        self.assertFalse(unknown["publication_allowed"])
        self.assertNotIn("repositories", unknown)

    def test_huge_integer_is_rejected(self):
        self.assertEqual(
            MAX_METRIC_INTEGER,
            _integer({"commits": MAX_METRIC_INTEGER}, "commits", "fixture"),
        )
        for invalid in (10 ** 500, MAX_METRIC_INTEGER + 1, True):
            with self.subTest(value=type(invalid).__name__):
                with self.assertRaises(ValidationError):
                    _integer({"commits": invalid}, "commits", "fixture")

    def test_mixed_repository_events_fail_closed(self):
        for invalid_event in (
            event(B), {k: v for k, v in event(A).items() if k != "repo"},
            dict(event(A), repo=None), dict(event(A), repo=[]),
        ):
            with self.subTest(kind=str(invalid_event.get("repo"))):
                result = summarize_product_day([
                    snapshot(A, events=[invalid_event]), snapshot(B),
                ], as_of=AS_OF, repos=(A, B))
                self.assertEqual("UNKNOWN", result["status"])
                self.assertEqual("unverified_event_repository", result["reason"])
                self.assertFalse(result["publication_allowed"])
                self.assertNotIn("repositories", result)


if __name__ == "__main__":
    unittest.main()
