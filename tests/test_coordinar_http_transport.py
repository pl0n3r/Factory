#!/usr/bin/env python3
"""Regresiones de transporte REST fail-closed de Coordinación (#1361)."""

from __future__ import annotations

import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import scripts.coordinar_trabajo as coordinator
from scripts.coordinar_trabajo import (
    GitHub, GitHubError, latest_reservation, reservation_marker,
)


class CoordinarHttpTransportTests(unittest.TestCase):
    """Ningún fallo del transporte concede autoridad ni filtra identificadores."""

    @staticmethod
    def denied(request, code: int, content: bytes = b""):
        return HTTPError(
            request.full_url, code, "hidden http reason",
            {}, BytesIO(content),
        )

    def test_empty_http500_is_typed_and_sanitized(self) -> None:
        api = GitHub("pl0n3r/Factory", "private-test-token")
        api._transport_stage = "tomar-issue"
        private = "/repos/pl0n3r/Factory/issues/1361?auth=private-query"
        def fail(request, timeout):
            raise self.denied(request, 500)
        with patch.object(coordinator, "urlopen", side_effect=fail):
            with self.assertRaises(GitHubError) as caught:
                api.request("GET", private)
        error = caught.exception
        self.assertEqual(error.status, 500)
        self.assertEqual(error.method, "GET")
        self.assertEqual(error.endpoint_class, "issue")
        self.assertEqual(error.stage, "tomar-issue")
        self.assertEqual(error.failure_class, "http")
        rendered = str(error)
        for forbidden in (
            "private-test-token", "private-query", "1361",
            "pl0n3r/Factory", "hidden http reason",
        ):
            self.assertNotIn(forbidden, rendered)
        self.assertIn("method=GET", rendered)
        self.assertIn("endpoint=issue", rendered)

    def test_403_429_and_timeout_are_fail_closed_without_writes(self) -> None:
        private = "hidden-body-with-auth-token"
        for status in (403, 429):
            api = GitHub("pl0n3r/Factory", "private-token")
            requests = []
            def denied(request, timeout):
                requests.append(request.get_method())
                raise self.denied(request, status, private.encode())
            with self.subTest(status=status):
                with patch.object(coordinator, "urlopen", side_effect=denied):
                    with self.assertRaises(GitHubError) as caught:
                        api.request("GET", "/repos/pl0n3r/Factory/issues")
                self.assertEqual(caught.exception.status, status)
                self.assertEqual(caught.exception.endpoint_class, "open-issues")
                self.assertEqual(requests, ["GET"])
                self.assertNotIn(private, str(caught.exception))
        for failure in (URLError("private.host.local"), TimeoutError("secret")):
            api = GitHub("pl0n3r/Factory", "private-token")
            requests = []
            def broken(request, timeout):
                requests.append(request.get_method())
                raise failure
            with self.subTest(type=type(failure).__name__):
                with patch.object(coordinator, "urlopen", side_effect=broken):
                    with self.assertRaises(GitHubError) as caught:
                        api.request("GET", "/repos/pl0n3r/Factory/issues/1361/comments")
                self.assertEqual(caught.exception.status, 0)
                self.assertEqual(caught.exception.failure_class, "network-timeout")
                self.assertEqual(caught.exception.endpoint_class, "issue-comments")
                self.assertEqual(requests, ["GET"])
                self.assertNotIn("private.host.local", str(caught.exception))
        api = GitHub("pl0n3r/Factory", "private-token")
        with patch.object(coordinator, "urlopen", return_value=BytesIO(b"{bad-json-private")):
            with self.assertRaises(GitHubError) as caught:
                api.request("GET", "/repos/pl0n3r/Factory/pulls/123/files")
        self.assertEqual(caught.exception.failure_class, "invalid-json")
        self.assertEqual(caught.exception.endpoint_class, "pr-files")
        self.assertNotIn("bad-json-private", str(caught.exception))

    def test_partial_write_and_idempotent_reconciliation(self) -> None:
        """Error ambiguo de POST: ninguna repetición ni cleanup/lock ficticio."""
        api = GitHub("pl0n3r/Factory", "private-token")
        marker = reservation_marker(
            "pl0n3r", "11111111-1111-4111-8111-111111111111",
            "trabajo/issue-1361", True, "tomar", "a" * 64,
            task_snapshot={
                "task_marker_sha256": "b" * 64,
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [1243],
            },
        )
        persisted = []
        calls = []
        def ambiguous(request, timeout):
            method = request.get_method()
            calls.append(method)
            if method == "POST":
                # Servidor persistió antes de devolver un HTTP 500 ambiguo.
                persisted.append({
                    "user": {"login": "github-actions[bot]"}, "body": marker,
                })
                raise self.denied(request, 500, b"private response")
            if method == "GET":
                return BytesIO(json.dumps(persisted).encode("utf-8"))
            raise AssertionError("No se permite cleanup, CAS ni retry implícito")
        with patch.object(coordinator, "urlopen", side_effect=ambiguous):
            with self.assertRaises(GitHubError) as caught:
                api.comment(1361, marker)
            observed = api.issue_comments(1361)
        self.assertEqual(caught.exception.status, 500)
        self.assertEqual(calls, ["POST", "GET"])
        self.assertEqual(len(persisted), 1)
        winner = latest_reservation(observed)
        self.assertIsNotNone(winner)
        self.assertEqual(
            winner["reservation_id"],
            "11111111-1111-4111-8111-111111111111",
        )
        self.assertTrue(winner["active"])


if __name__ == "__main__":
    unittest.main()
