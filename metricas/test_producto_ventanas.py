"""Regresión offline: las ventanas diarias UTC usan (inicio, fin]."""
from __future__ import annotations

import json
import socket
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from metricas.evaluar_agentes import summarize_product_day

REPO = "pl0n3r/Factory"
UTC = timezone.utc


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def event(number: int, at: datetime) -> dict:
    return {
        "number": number,
        "merge_commit_sha": f"{number:040x}",
        "merged_at": iso(at),
        "merged": True,
    }


def snapshot(at: datetime, events: list[dict]) -> dict:
    return {
        "repo": REPO,
        "repository_sha": "a" * 40,
        "observed_at": iso(at),
        "source": "github-api",
        "authenticated": True,
        "complete": True,
        "run_id": 17,
        "run_status": "completed",
        "run_conclusion": "success",
        "pages": 1,
        "verified_pages": 1,
        "events": events,
    }


def evaluate(at: datetime, events: list[dict]) -> dict:
    return summarize_product_day(
        [snapshot(at, events)],
        as_of=iso(at),
        repos=(REPO,),
    )


class WindowBoundsTests(unittest.TestCase):
    def test_adjacent_24h_windows_exclude_lower_bound(self) -> None:
        first_end = datetime(2026, 10, 10, 12, tzinfo=UTC)
        second_end = first_end + timedelta(hours=24)
        first = evaluate(first_end, [
            event(1, first_end - timedelta(hours=24)),
            event(2, first_end),
        ])
        second = evaluate(second_end, [
            event(2, first_end),
            event(3, second_end),
        ])
        self.assertEqual("MEASURED", first["status"])
        self.assertEqual("MEASURED", second["status"])
        self.assertEqual(1, first["repositories"][REPO]["merged_prs"])
        self.assertEqual(1, second["repositories"][REPO]["merged_prs"])
        self.assertEqual(
            first["repositories"][REPO]["window_end"],
            second["repositories"][REPO]["window_start"],
        )
        self.assertEqual(
            (iso(first_end - timedelta(hours=24)), iso(first_end)),
            (first["repositories"][REPO]["window_start"],
             first["repositories"][REPO]["window_end"]),
        )

    def test_end_boundary_is_inclusive_and_idempotent(self) -> None:
        end = datetime(2026, 10, 11, 12, tzinfo=UTC)
        begin = end - timedelta(hours=24)
        final = event(4, end)
        result = evaluate(end, [
            event(6, begin), event(5, end - timedelta(seconds=1)),
            final, dict(final),
        ])
        self.assertEqual("MEASURED", result["status"])
        self.assertEqual(2, result["repositories"][REPO]["merged_prs"])
        self.assertEqual(3, result["repositories"][REPO]["observations"])
        self.assertFalse(result["publication_allowed"])

    def test_offline_evidence_remains_non_authoritative(self) -> None:
        end = datetime(2026, 10, 11, 12, tzinfo=UTC)
        evidence = snapshot(end, [event(1, end)])
        evidence["hidden_private_context"] = "synthetic-secret-should-not-leak"
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            measured = summarize_product_day(
                [evidence], as_of=iso(end), repos=(REPO,),
            )
            untrusted = dict(evidence, source="not-an-authenticated-api")
            denied = summarize_product_day(
                [untrusted], as_of=iso(end), repos=(REPO,),
            )
        self.assertEqual("MEASURED", measured["status"])
        self.assertFalse(measured["publication_allowed"])
        self.assertEqual(1, measured["repositories"][REPO]["merged_prs"])
        self.assertNotIn("synthetic-secret-should-not-leak", json.dumps(measured))
        self.assertEqual("UNKNOWN", denied["status"])
        self.assertFalse(denied["publication_allowed"])
        self.assertNotIn("merged_prs", denied)


if __name__ == "__main__":
    unittest.main()
