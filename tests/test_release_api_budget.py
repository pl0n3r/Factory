"""Regresiones sin red para Factory #1135 y el incidente raíz #1132."""

from __future__ import annotations

import copy
import json
import unittest

from scripts.release_api_budget import (
    ReleaseBudgetError, classify_transport_failure, estimate_api_budget,
)


def issue(n: int, gate: bool = False) -> dict:
    return {
        "number": n, "state": "closed", "title": f"Puerta {n}",
        "body": "factory-human-gate factory-release" if gate else "factory-human-gate",
        "updated_at": "2026-10-10T20:00:00Z",
    }


def search_pages(*, rows: int = 120, gates: int = 98) -> list[dict]:
    items = [issue(i + 1, i < gates) for i in range(rows)]
    return [
        {"incomplete_results": False, "total_count": rows,
         "items": items[start:start + 100]}
        for start in range(0, max(1, rows), 100)
    ]


class ReleaseApiBudgetTests(unittest.TestCase):
    def test_120_results_and_98_gates_require_at_least_104_calls(self):
        pages = search_pages()
        report = estimate_api_budget(pages, copy.deepcopy(pages))
        self.assertEqual(report.search_rows, 120)
        self.assertEqual(report.release_gates, 98)
        self.assertEqual(report.search_calls, 4)
        self.assertEqual(report.comments_calls_min, 98)
        self.assertEqual(report.metadata_calls, 2)
        self.assertEqual(report.total_calls_min, 104)
        self.assertFalse(report.comments_fully_paginated)
        self.assertEqual(estimate_api_budget(search_pages(rows=0, gates=0),
                                              search_pages(rows=0, gates=0)).total_calls_min, 4)

    def test_incomplete_ambiguous_or_drifting_search_fails_closed(self):
        good = search_pages()
        bad_cases = []
        missing = copy.deepcopy(good[:1]); bad_cases.append(missing)
        partial = copy.deepcopy(good); partial[1]["incomplete_results"] = True; bad_cases.append(partial)
        altered = copy.deepcopy(good); altered[1]["total_count"] = 121; bad_cases.append(altered)
        duplicated = copy.deepcopy(good); duplicated[1]["items"][0]["number"] = 1; bad_cases.append(duplicated)
        bool_count = copy.deepcopy(good); bool_count[0]["total_count"] = True; bad_cases.append(bool_count)
        wrong_body = copy.deepcopy(good); del wrong_body[1]["items"][0]["body"]; bad_cases.append(wrong_body)
        oversized = search_pages(rows=201, gates=0); bad_cases.append(oversized)
        for bad in bad_cases:
            with self.subTest(bad=str(bad)[:70]), self.assertRaises(ReleaseBudgetError):
                estimate_api_budget(bad, good)
        for change in ("body", "updated_at", "title"):
            drift = copy.deepcopy(good)
            drift[1]["items"][0][change] += " cambiado"
            with self.subTest(change=change), self.assertRaises(ReleaseBudgetError):
                estimate_api_budget(good, drift)

    def test_rate_limit_retries_bounded_and_always_fail_closed(self):
        primary = classify_transport_failure(403, remaining=0, reset_after_seconds=25)
        self.assertEqual(primary.kind, "limite_primario")
        self.assertEqual(primary.suggested_retry_seconds, 25)
        failures = (
            classify_transport_failure(403),
            classify_transport_failure(403, remaining=25),
            classify_transport_failure(429, retry_after_seconds=31),
            classify_transport_failure(429, retry_after_seconds=5, attempts_used=2),
            classify_transport_failure(401),
            classify_transport_failure(500),
        )
        for failure in (primary, *failures):
            self.assertTrue(failure.must_fail_closed)
            self.assertFalse(failure.execution_authorized)
        self.assertTrue(all(f.suggested_retry_seconds is None for f in failures))
        for option in ({"remaining": False}, {"retry_after_seconds": "15"},
                       {"reset_after_seconds": -1}, {"max_attempts": True},
                       {"attempts_used": 4}):
            with self.subTest(option=option), self.assertRaises(ReleaseBudgetError):
                classify_transport_failure(403, **option)

    def test_report_excludes_comment_bodies_and_tokens(self):
        pages = search_pages()
        secret = "ghp_SUPER_SECRET_TOKEN_NOT_A_REAL_CREDENTIAL"
        pages[0]["items"][0]["body"] += secret
        report = estimate_api_budget(pages, copy.deepcopy(pages))
        public = json.dumps(report.public_report(), sort_keys=True)
        self.assertEqual(set(report.public_report()), {
            "search_rows", "release_gates", "search_calls", "comments_calls_min",
            "metadata_calls", "total_calls_min", "comments_fully_paginated",
        })
        self.assertNotIn(secret, public)
        self.assertNotIn("factory-release", public)
        self.assertNotIn("ghp_", repr(report))
        with self.assertRaises(ReleaseBudgetError) as caught:
            altered = copy.deepcopy(pages)
            altered[0]["items"][0]["body"] += "another private string"
            estimate_api_budget(pages, altered)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn("private string", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
