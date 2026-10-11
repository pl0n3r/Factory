"""Regresiones offline del contrato Factory #1158."""
import unittest

from scripts.retro_diaria import evaluate_retro_daily


NOW = "2026-10-11T09:00:00Z"
SOURCE = {"id": "snapshot-1", "repo": "pl0n3r/Factory", "sha": "a" * 40,
          "authenticated": True, "complete": True}


def event(ident, when, kind="pr_merged"):
    return {"id": ident, "source_id": "snapshot-1", "repo": "pl0n3r/Factory",
            "kind": kind, "occurred_at": when}


class RetroDailyTests(unittest.TestCase):
    def test_rolling_24h_event_window_utc_and_determinism(self):
        input_rows = [event("new", "2026-10-11T08:00:00Z"),
                      event("old", "2026-10-10T08:59:59Z"),
                      event("edge", "2026-10-10T09:00:00Z", "incident_closed"),
                      event("new", "2026-10-11T10:00:00+02:00")]
        first = evaluate_retro_daily(events=input_rows, sources=[SOURCE], now=NOW)
        second = evaluate_retro_daily(events=list(reversed(input_rows)),
                                      sources=[SOURCE], now="2026-10-11T04:00:00-05:00")
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "READY")
        self.assertFalse(first["publication_allowed"])
        self.assertEqual([x["kind"] for x in first["events"]], ["incident_closed", "pr_merged"])
        self.assertEqual(first["counts_by_repo"]["pl0n3r/Factory"]["pr_merged"], 1)
        self.assertEqual(first["counts_by_repo"]["pl0n3r/Factory"]["incident_closed"], 1)

    def test_missing_authenticated_evidence_fails_closed(self):
        good = [event("new", "2026-10-11T08:00:00Z")]
        scenarios = [
            (good, [], NOW),
            (good, [{**SOURCE, "authenticated": False}], NOW),
            (good, [{**SOURCE, "authenticated": 1}], NOW),
            (good, [{**SOURCE, "complete": False}], NOW),
            (good, [{**SOURCE, "sha": "bad"}], NOW),
            (good, [SOURCE], "2026-10-11T09:00:00"),
            ([], [SOURCE], "0001-01-01T00:00:00Z"),
            ([], [SOURCE], "0001-01-01T00:00:00+23:00"),
            (good + [event("new", "2026-10-11T07:00:00Z")], [SOURCE], NOW),
            ([{**good[0], "source_id": "unknown"}], [SOURCE], NOW),
            ([{**good[0], "occurred_at": "2026-10-11T10:00:00Z"}], [SOURCE], NOW),
            ([{**good[0], "occurred_at": None}], [SOURCE], NOW),
        ]
        for events, sources, now in scenarios:
            with self.subTest(events=events, sources=sources, now=now):
                result = evaluate_retro_daily(events=events, sources=sources, now=now)
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertNotIn("counts_by_repo", result)
                self.assertNotIn("events", result)
        self.assertNotIn("secret-token", str(evaluate_retro_daily(
            events=good, sources=[{**SOURCE, "sha": "secret-token"}], now=NOW)))


if __name__ == "__main__":
    unittest.main()
