import copy
import hashlib
import inspect
import json
import unittest

import intelligence.account_capacity_learning as module
from intelligence.account_capacity_learning import (
    AccountCapacityLearningError,
    learn_limit_events,
)
from lecciones.memoria import validate_lesson

NOW = "2026-10-01T10:00:00Z"


def event(alias="primary", at="2026-10-01T09:00:00Z", fp="a" * 64, **changes):
    row = {
        "account_alias": alias,
        "occurred_at": at,
        "capacity_fingerprint": fp,
        "source": "pl0n3r/factory#584",
    }
    row.update(changes)
    return row


def request(events):
    return {"version": 1, "project": "pl0n3r/factory", "events": events}


class AccountCapacityLearningTests(unittest.TestCase):
    def test_valid_limit_event_produces_canonical_deterministic_lesson(self):
        result = learn_limit_events(request([event()]), now=NOW)
        self.assertEqual(result, learn_limit_events(request([event()]), now=NOW))
        self.assertEqual(len(result["lessons"]), 1)
        lesson = result["lessons"][0]
        validate_lesson(lesson, "test")
        self.assertEqual(lesson["kind"], "incident")
        self.assertEqual(lesson["source"], "pl0n3r/factory#584")
        self.assertRegex(lesson["id"], r"^capacity-limit-[0-9a-f]{64}$")
        self.assertNotIn("primary", json.dumps(lesson))
        self.assertNotIn("a" * 64, json.dumps(lesson))

    def test_recurrence_is_account_scoped_exact_and_stably_ordered(self):
        rows = [
            event("beta", "2026-10-01T08:00:00Z", "b" * 64),
            event("alpha", "2026-10-01T07:00:00Z", "c" * 64),
            event("alpha", "2026-10-01T09:30:00Z", "d" * 64),
        ]
        result = learn_limit_events(request(rows), now=NOW)
        self.assertEqual(result["recurrence"], [
            {
                "accountAlias": "alpha",
                "limitEvents": 2,
                "lastOccurredAt": "2026-10-01T09:30:00Z",
            },
            {
                "accountAlias": "beta",
                "limitEvents": 1,
                "lastOccurredAt": "2026-10-01T08:00:00Z",
            },
        ])
        self.assertEqual(
            result,
            learn_limit_events(request(list(reversed(rows))), now=NOW),
        )

    def test_duplicate_delivery_is_idempotent_and_material_change_is_distinct(self):
        original = event()
        one = learn_limit_events(
            request([original, copy.deepcopy(original)]), now=NOW
        )
        two = learn_limit_events(
            request([original, event(fp="b" * 64)]), now=NOW
        )
        self.assertEqual(len(one["lessons"]), 1)
        self.assertEqual(one["recurrence"][0]["limitEvents"], 1)
        self.assertEqual(len(two["lessons"]), 2)
        self.assertEqual(two["recurrence"][0]["limitEvents"], 2)
        self.assertNotEqual(one["fingerprint"], two["fingerprint"])

    def test_closed_contract_rejects_identifying_unknown_future_and_invalid_evidence(self):
        bad_request = request([event()])
        bad_request["chat_content"] = "secret"
        bad_event = event()
        bad_event["model"] = "hidden"
        cases = [
            bad_request,
            request([bad_event]),
            request([event(alias="person@example.com")]),
            request([event(at="2026-10-01T10:00:01Z")]),
            request([event(fp="BAD")]),
            request([event(source="https://example.com/not-github")]),
        ]
        for payload in cases:
            with self.subTest(keys=set(payload)):
                with self.assertRaises(AccountCapacityLearningError) as caught:
                    learn_limit_events(payload, now=NOW)
                message = str(caught.exception)
                self.assertNotIn("secret", message)
                self.assertNotIn("person@example.com", message)

    def test_output_fingerprint_is_deterministic_pure_and_provider_limit_free(self):
        payload = request([event(), event("secondary", fp="b" * 64)])
        result = learn_limit_events(payload, now=NOW)
        self.assertEqual(
            result,
            learn_limit_events(copy.deepcopy(payload), now=NOW),
        )
        material = {key: value for key, value in result.items() if key != "fingerprint"}
        raw = json.dumps(
            material, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        ).encode()
        self.assertEqual(result["fingerprint"], hashlib.sha256(raw).hexdigest())

        source = inspect.getsource(module).lower()
        for forbidden in (
            "requests", "urllib", "subprocess", "socket.", "open(",
            "gpt-", "messages_per_hour", "chat_content",
            "conversation_id", "email", "cookie",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_empty_events_are_valid_zero_recurrence(self):
        result = learn_limit_events(request([]), now=NOW)
        self.assertEqual(result["lessons"], [])
        self.assertEqual(result["recurrence"], [])


if __name__ == "__main__":
    unittest.main()
