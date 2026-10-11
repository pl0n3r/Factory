"""Offline acceptance for Factory #1156: pure, deterministic capture."""
import copy
import unittest
from unittest.mock import patch

from scripts.captura_leccion import CaptureError, capture_lessons

SHA = "a" * 40


def event(event_id="evt-1", **overrides):
    payload = {"event_id": event_id, "repo": "pl0n3r/Factory", "issue": 1156,
               "sha": SHA, "occurred_at": "2026-10-11T09:00:00Z",
               "event": "issue_closed", "summary": "Regresión de paginación cubierta",
               "issuer": "github-actions[bot]", "verified": True}
    return {**payload, **overrides}


class CaptureLessonTests(unittest.TestCase):
    def test_validated_event_pure_and_deterministic(self):
        rows = [event("evt-2", occurred_at="2026-10-11T10:00:00Z"), event()]
        baseline = copy.deepcopy(rows)
        with patch("socket.create_connection", side_effect=AssertionError("no network")):
            observed = capture_lessons(rows)
            self.assertEqual(observed, capture_lessons(list(reversed(rows))))
        self.assertEqual([r["event_id"] for r in observed], ["evt-1", "evt-2"])
        self.assertEqual(rows, baseline)
        self.assertEqual(len(capture_lessons([rows[0], rows[0]])), 1)
        self.assertRegex(observed[0]["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertNotIn("verified", observed[0])
        self.assertNotIn("issuer", observed[0])

    def test_untrusted_source_secrets_and_duplicate_fail_closed(self):
        bad = [event(verified=False), event(issuer="unknown"),
               event(summary="Token=secret-do-not-log"),
               event(summary="Correo alice@example.com"),
               event(sha="f" * 39), event(issue=True),
               event(occurred_at="2026-02-30T09:00:00Z"),
               event(repo="evil/repo"), event(extra="payload")]
        for payload in bad:
            with self.subTest(payload=repr(payload)[:80]):
                with self.assertRaises(CaptureError):
                    capture_lessons([payload])
        with self.assertRaisesRegex(CaptureError, "conflicting_event_id"):
            capture_lessons([event(), event(summary="El resultado fue diferente")])
        for payload in (None, [], {}, [None], [event()] * 129):
            with self.subTest(type=type(payload).__name__):
                with self.assertRaises(CaptureError):
                    capture_lessons(payload)


if __name__ == "__main__":
    unittest.main()
