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
    def test_case_variant_repositories_are_one_identity(self):
        # GitHub resolves Factory/factory and PL0N3R/pl0n3r to one repository.
        for variant in ("pl0n3r/factory", "PL0N3R/Factory"):
            with self.subTest(variant=variant):
                alias = {**SOURCE, "id": "alias", "repo": variant}
                result = evaluate_retro_daily(
                    events=[event("e1", "2026-10-11T08:00:00Z")],
                    sources=[SOURCE, alias], now=NOW,
                )
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertEqual(result["reason"], "ambiguous_source_identity")
                self.assertNotIn("counts_by_repo", result)

        other = {**SOURCE, "id": "other", "repo": "pl0n3r/Condor"}
        positive = evaluate_retro_daily(
            events=[event("e1", "2026-10-11T08:00:00Z")],
            sources=[SOURCE, other], now=NOW,
        )
        self.assertEqual(positive["status"], "READY")
        self.assertEqual(positive["counts_by_repo"]["pl0n3r/Factory"]["pr_merged"], 1)
        self.assertEqual(positive["counts_by_repo"]["pl0n3r/Condor"]["pr_merged"], 0)
        self.assertFalse(positive["publication_allowed"])

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


    def test_duplicate_ids_across_repos_are_independent_but_conflicts_fail_closed(self):
        other = {"id": "snapshot-2", "repo": "pl0n3r/Condor",
                 "sha": "b" * 40, "authenticated": True, "complete": True}
        first = event("123", "2026-10-11T08:00:00Z")
        second = {"id": "123", "source_id": "snapshot-2",
                  "repo": "pl0n3r/Condor", "kind": "incident_opened",
                  "occurred_at": "2026-10-11T08:15:00Z"}
        rows = [first, second, dict(first)]
        a = evaluate_retro_daily(events=rows, sources=[SOURCE, other], now=NOW)
        b = evaluate_retro_daily(events=list(reversed(rows)),
                                 sources=[other, SOURCE], now=NOW)
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "READY")
        self.assertEqual(len(a["events"]), 2)
        self.assertEqual(a["counts_by_repo"]["pl0n3r/Factory"]["pr_merged"], 1)
        self.assertEqual(a["counts_by_repo"]["pl0n3r/Condor"]["incident_opened"], 1)
        self.assertFalse(a["publication_allowed"])
        conflict = evaluate_retro_daily(
            events=rows + [{**first, "kind": "incident_closed"}],
            sources=[SOURCE, other], now=NOW)
        self.assertEqual(conflict["status"], "UNKNOWN")
        self.assertEqual(conflict["reason"], "conflicting_duplicate_event")
        self.assertNotIn("counts_by_repo", conflict)

    def test_refactor_preserves_source_and_event_failure_reasons(self):
        original = event("e1", "2026-10-11T08:00:00Z")
        cases = [
            ([SOURCE, False], [original], "invalid_source"),
            ([{**SOURCE, "complete": 1}], [original], "unauthenticated_or_incomplete_source"),
            ([SOURCE, dict(SOURCE)], [original], "ambiguous_source_identity"),
            ([SOURCE], [False], "invalid_event"),
            ([SOURCE], [{**original, "source_id": "unknown"}], "invalid_event_identity"),
            ([SOURCE], [{**original, "occurred_at": "invalid"}], "invalid_event_time"),
            ([SOURCE], [original, {**original, "kind": "incident_closed"}],
             "conflicting_duplicate_event"),
        ]
        for sources, events, reason in cases:
            with self.subTest(reason=reason):
                result = evaluate_retro_daily(sources=sources, events=events, now=NOW)
                self.assertEqual(result, {"status": "UNKNOWN", "reason": reason})

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
