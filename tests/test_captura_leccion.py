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

    def test_cross_run_sha_drift_preserves_business_identity(self):
        """Runner checkout SHA is not the merge commit's event identity."""
        merge_sha = "c" * 40
        stable = event("pr_merged-44-" + merge_sha, issue=44,
                       event="pr_merged", sha=merge_sha,
                       summary="Fusion de PR verificada en GitHub")
        run_a = {**stable, "run_sha": "a" * 40}
        run_b = {**stable, "run_sha": "b" * 40}
        self.assertEqual(capture_lessons([run_a, run_b]), capture_lessons([run_b, run_a]))
        self.assertEqual(len(capture_lessons([run_a, run_b])), 1)
        self.assertEqual(capture_lessons([run_a])[0]["sha"], merge_sha)
        self.assertNotIn("run_sha", capture_lessons([run_a])[0])
        with self.assertRaisesRegex(CaptureError, "invalid_run_provenance"):
            capture_lessons([{**stable, "run_sha": "bad"}])

    def test_pr_merge_id_is_bound_to_issue_and_sha(self):
        """A caller cannot split one merge with fabricated event IDs."""
        valid = event("pr_merged-44-" + "c" * 40, issue=44,
                      event="pr_merged", sha="c" * 40,
                      summary="Fusion de PR verificada en GitHub")
        self.assertEqual(len(capture_lessons([valid, valid])), 1)
        for candidate in (
                {**valid, "event_id": "pr_merged-44-" + "b" * 40},
                {**valid, "event_id": "pr_merged-45-" + "c" * 40},
                {**valid, "event_id": "evt-irrelevant"},
                {**valid, "issue": 45},
                {**valid, "sha": "d" * 40},
        ):
            with self.subTest(id=candidate["event_id"], issue=candidate["issue"]):
                with self.assertRaisesRegex(
                        CaptureError, "invalid_business_event_identity"):
                    capture_lessons([candidate])
        with self.assertRaisesRegex(CaptureError, "invalid_business_event_identity"):
            capture_lessons([valid, {**valid, "event_id": "pr_merged-44-" + "d" * 40}])

    def test_distinct_closure_identity_and_business_conflicts_fail_closed(self):
        first = event("pr_merged-44-" + "c" * 40, issue=44, event="pr_merged",
                      sha="c" * 40)
        other = event("pr_merged-45-" + "d" * 40, issue=45, event="pr_merged",
                      sha="d" * 40)
        self.assertEqual(len(capture_lessons([first, other, first])), 2)
        self.assertEqual(len(capture_lessons([first, first])), 1)
        for conflict in ({**first, "issue": 46},
                         {**first, "summary": "Otro cierre del mismo PR"}):
            with self.subTest(conflict=conflict):
                with self.assertRaisesRegex(CaptureError, "conflicting_event_id"):
                    capture_lessons([first, conflict])
        with self.assertRaisesRegex(CaptureError, "conflicting_event_id"):
            capture_lessons([first, {**first, "sha": "b" * 40}])

    def test_unicode_surrogates_are_rejected_with_typed_error(self):
        """JSON can decode lone surrogates; they cannot reach UTF-8 hashing."""
        for text in ("Fusion \ud800 verificada", "Fusion \udfff verificada",
                     "Fusion \udc00 verificada"):
            with self.subTest(text=repr(text)):
                with self.assertRaisesRegex(CaptureError, "unsafe_summary"):
                    capture_lessons([event(summary=text)])
        self.assertEqual(len(capture_lessons([
            event(summary="Fusion con emoji ✅ verificada")])), 1)

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
