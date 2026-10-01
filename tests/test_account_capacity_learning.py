import copy
import hashlib
import inspect
import json
import unittest

import intelligence.account_capacity_learning as learning_module
from intelligence.account_capacity_learning import (
    AccountCapacityLearningError,
    learn_limit_events,
)
from lecciones.memoria import validate_lesson


NOW = "2026-10-01T10:00:00Z"


def event(
    *,
    alias="primary",
    occurred_at="2026-10-01T09:00:00Z",
    fingerprint="a" * 64,
    source="pl0n3r/factory#584",
):
    return {
        "account_alias": alias,
        "occurred_at": occurred_at,
        "capacity_fingerprint": fingerprint,
        "source": source,
    }


def request(events):
    return {
        "version": 1,
        "project": "pl0n3r/factory",
        "events": events,
    }


class AccountCapacityLearningTests(unittest.TestCase):
    def test_valid_limit_event_produces_canonical_deterministic_lesson(self):
        payload = request([event()])
        first = learn_limit_events(payload, now=NOW)
        second = learn_limit_events(copy.deepcopy(payload), now=NOW)

        self.assertEqual(first, second)
        self.assertEqual(len(first["lessons"]), 1)
        lesson = first["lessons"][0]
        validated = validate_lesson(lesson, "test")
        self.assertEqual(validated["source"], "pl0n3r/factory#584")
        self.assertEqual(lesson["kind"], "process")
        self.assertRegex(lesson["id"], r"^capacity-limit-[0-9a-f]{20}$")
        self.assertEqual(lesson["occurred_at"], "2026-10-01T09:00:00Z")

    def test_recurrence_is_account_scoped_exact_and_stably_ordered(self):
        payload = request([
            event(alias="beta", occurred_at="2026-10-01T08:00:00Z", fingerprint="b" * 64),
            event(alias="alpha", occurred_at="2026-10-01T07:00:00Z", fingerprint="c" * 64),
            event(alias="alpha", occurred_at="2026-10-01T09:30:00Z", fingerprint="d" * 64),
        ])
        result = learn_limit_events(payload, now=NOW)

        self.assertEqual(
            result["recurrence"],
            [
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
            ],
        )
        reversed_result = learn_limit_events(
            request(list(reversed(payload["events"]))),
            now=NOW,
        )
        self.assertEqual(result, reversed_result)

    def test_duplicate_delivery_is_idempotent_and_material_change_is_distinct(self):
        original = event()
        duplicate = copy.deepcopy(original)
        changed = event(fingerprint="b" * 64)

        deduplicated = learn_limit_events(
            request([original, duplicate]),
            now=NOW,
        )
        distinct = learn_limit_events(
            request([original, duplicate, changed]),
            now=NOW,
        )

        self.assertEqual(len(deduplicated["lessons"]), 1)
        self.assertEqual(deduplicated["recurrence"][0]["limitEvents"], 1)
        self.assertEqual(len(distinct["lessons"]), 2)
        self.assertEqual(distinct["recurrence"][0]["limitEvents"], 2)
        self.assertNotEqual(
            deduplicated["fingerprint"],
            distinct["fingerprint"],
        )

    def test_closed_contract_rejects_identifying_unknown_future_and_invalid_evidence(self):
        cases = []

        extra_request = request([event()])
        extra_request["chat_content"] = "secret"
        cases.append(extra_request)

        extra_event = request([event()])
        extra_event["events"][0]["model"] = "hidden"
        cases.append(extra_event)

        cases.append(request([event(alias="person@example.com")]))
        cases.append(request([event(occurred_at="2026-10-01T10:00:01Z")]))
        cases.append(request([event(fingerprint="BAD")]))
        cases.append(request([event(source="https://example.com/not-github")]))

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(AccountCapacityLearningError) as caught:
                    learn_limit_events(payload, now=NOW)
                self.assertNotIn("secret", str(caught.exception))
                self.assertNotIn("person@example.com", str(caught.exception))

    def test_output_fingerprint_is_deterministic_pure_and_provider_limit_free(self):
        payload = request([
            event(alias="primary", fingerprint="a" * 64),
            event(alias="secondary", fingerprint="b" * 64),
        ])
        first = learn_limit_events(payload, now=NOW)
        second = learn_limit_events(copy.deepcopy(payload), now=NOW)
        self.assertEqual(first, second)

        material = {
            key: value
            for key, value in first.items()
            if key != "fingerprint"
        }
        encoded = json.dumps(
            material,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(
            first["fingerprint"],
            hashlib.sha256(encoded).hexdigest(),
        )

        source = inspect.getsource(learning_module)
        for forbidden in (
            "requests",
            "urllib",
            "subprocess",
            "socket.",
            "open(",
            "gpt-",
            "messages_per_hour",
            "chat_content",
            "conversation_id",
            "email",
            "token",
            "cookie",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source.lower())

    def test_empty_events_are_valid_zero_recurrence(self):
        result = learn_limit_events(request([]), now=NOW)
        self.assertEqual(result["lessons"], [])
        self.assertEqual(result["recurrence"], [])
        self.assertRegex(result["fingerprint"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
