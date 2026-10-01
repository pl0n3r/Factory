import inspect
import unittest
from datetime import datetime, timezone

import intelligence.account_capacity_learning as learning
from intelligence.account_capacity_learning import (
    AccountCapacityLearningError,
    compile_limit_learning,
)
from lecciones.memoria import validate_lesson


NOW = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
FP_A = "a" * 64
FP_B = "b" * 64


def event(
    *,
    occurred_at="2026-10-01T12:00:00Z",
    accepted=4,
    window=600,
    reset=900,
    fingerprint=FP_A,
    source="pl0n3r/Factory#584",
):
    return {
        "occurred_at": occurred_at,
        "accepted_before_limit": accepted,
        "window_seconds": window,
        "reset_after_seconds": reset,
        "capacity_fingerprint": fingerprint,
        "source": source,
    }


def request(events):
    return {
        "version": 1,
        "project": "pl0n3r/Factory",
        "accountAlias": "primary",
        "events": events,
    }


class AccountCapacityLearningTests(unittest.TestCase):
    def test_limit_event_emits_one_canonical_lesson(self):
        output = compile_limit_learning(request([event()]), now=NOW)

        self.assertEqual(output["version"], 1)
        self.assertEqual(output["project"], "pl0n3r/Factory")
        self.assertEqual(output["accountAlias"], "primary")
        self.assertEqual(len(output["lessons"]), 1)
        lesson = output["lessons"][0]
        validated = validate_lesson(lesson, "test")
        self.assertEqual(validated["kind"], "incident")
        self.assertEqual(validated["source"], "pl0n3r/Factory#584")
        self.assertRegex(lesson["id"], r"^account-cap-limit-[0-9a-f]{24}$")

        repeated = compile_limit_learning(request([event()]), now=NOW)
        self.assertEqual(output, repeated)

    def test_recurrence_is_deterministic_deduplicated_and_evidence_bound(self):
        first = event(
            occurred_at="2026-10-01T12:00:00Z",
            fingerprint=FP_A,
            source="pl0n3r/Factory#584",
        )
        second = event(
            occurred_at="2026-10-01T13:00:00+00:00",
            accepted=3,
            fingerprint=FP_B,
            source="https://github.com/pl0n3r/AutoFactory/issues/62",
        )
        output = compile_limit_learning(
            request([second, first, first]),
            now=NOW,
        )
        permuted = compile_limit_learning(
            request([first, second, first]),
            now=NOW,
        )

        self.assertEqual(output, permuted)
        self.assertEqual(len(output["lessons"]), 2)
        self.assertEqual(
            output["recurrence"],
            {
                "limitEvents": 2,
                "firstOccurredAt": "2026-10-01T12:00:00Z",
                "lastOccurredAt": "2026-10-01T13:00:00Z",
                "repeated": True,
                "sourceFingerprints": [FP_A, FP_B],
            },
        )
        self.assertRegex(output["fingerprint"], r"^[0-9a-f]{64}$")

    def test_closed_schema_rejects_sensitive_and_incoherent_evidence(self):
        cases = []

        extra_request = request([])
        extra_request["extra"] = True
        cases.append(extra_request)

        identifying_alias = request([])
        identifying_alias["accountAlias"] = "person@example.com"
        cases.append(identifying_alias)

        extra_event = event()
        extra_event["message"] = "not accepted"
        cases.append(request([extra_event]))

        cases.extend([
            request([{**event(), "occurred_at": "2026-10-01T12:00:00"}]),
            request([{**event(), "occurred_at": "2026-10-01T15:00:00Z"}]),
            request([{**event(), "accepted_before_limit": -1}]),
            request([{**event(), "window_seconds": 0}]),
            request([{**event(), "reset_after_seconds": 0}]),
            request([{**event(), "capacity_fingerprint": "bad"}]),
            request([{**event(), "source": "not-a-github-source"}]),
        ])

        for bad in cases:
            with self.subTest(bad=bad):
                with self.assertRaises(AccountCapacityLearningError):
                    compile_limit_learning(bad, now=NOW)

    def test_module_is_pure_and_secret_free(self):
        source = inspect.getsource(learning).lower()
        for forbidden in (
            "requests.",
            "urllib.",
            "socket.",
            "subprocess.",
            "pathlib",
            "open(",
            "write_text",
            "read_text",
        ):
            self.assertNotIn(forbidden, source)

        output = compile_limit_learning(request([event()]), now=NOW)
        encoded = str(output).lower()
        for forbidden in ("@", "cookie", "token", "conversation"):
            self.assertNotIn(forbidden, encoded)

    def test_empty_events_are_valid_zero_recurrence(self):
        output = compile_limit_learning(request([]), now=NOW)

        self.assertEqual(output["lessons"], [])
        self.assertEqual(
            output["recurrence"],
            {
                "limitEvents": 0,
                "firstOccurredAt": None,
                "lastOccurredAt": None,
                "repeated": False,
                "sourceFingerprints": [],
            },
        )
        self.assertRegex(output["fingerprint"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
