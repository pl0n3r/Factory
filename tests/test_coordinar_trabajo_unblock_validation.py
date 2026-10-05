#!/usr/bin/env python3
"""Pruebas adicionales del contrato factory-unblock."""

from __future__ import annotations

import json
import unittest

import scripts.coordinar_trabajo as coordinator


def marker(**payload: object) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return f"<!-- factory-unblock {data} -->"


class UnblockValidationTests(unittest.TestCase):
    def test_issue_closed_rejects_bad_issue_and_extra_field(self) -> None:
        bad_issue = marker(version=1, kind="issue_closed", issue=0)
        extra_issue = marker(version=1, kind="issue_closed", issue=9, extra=True)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(bad_issue)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(extra_issue)

    def test_workflow_rejects_bad_run_and_sha(self) -> None:
        bad_run = marker(
            version=1, kind="workflow_success", run_id=0, sha="a" * 40
        )
        bad_sha = marker(
            version=1, kind="workflow_success", run_id=7, sha="deadbeef"
        )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(bad_run)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(bad_sha)

    def test_branch_rejects_noncanonical_name(self) -> None:
        bad_branch = marker(
            version=1, kind="branch_sha", branch="../main", sha="b" * 40
        )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(bad_branch)

    def test_duplicate_and_malformed_markers_fail_closed(self) -> None:
        valid = marker(version=1, kind="issue_closed", issue=9)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(valid + "\n" + valid)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker("<!-- factory-unblock {not-json} -->")

    def test_missing_targets_fail_closed_without_stopping_sweep(self) -> None:
        missing = {
            "number": 1,
            "state": "open",
            "labels": [{"name": coordinator.STATUS_BLOCKED}],
            "body": marker(version=1, kind="issue_closed", issue=999),
        }
        valid = {
            "number": 2,
            "state": "open",
            "labels": [{"name": coordinator.STATUS_BLOCKED}],
            "body": marker(
                version=1,
                kind="branch_sha",
                branch="main",
                sha="a" * 40,
            ),
        }

        class FakeGitHub:
            def __init__(self) -> None:
                self.issues = {1: missing, 2: valid}
                self.comments: list[tuple[int, str]] = []

            def open_issues(self) -> list[dict]:
                return [missing, valid]

            def issue(self, number: int) -> dict:
                if number == 999:
                    raise coordinator.GitHubError(404, "Not Found")
                return self.issues[number]

            def workflow_run(self, run_id: int) -> dict:
                raise coordinator.GitHubError(404, "Not Found")

            def branch_sha(self, branch: str) -> str | None:
                return "a" * 40 if branch == "main" else None

            def issue_comments(self, issue_number: int) -> list[dict]:
                return []

            def comment(self, issue_number: int, body: str) -> None:
                self.comments.append((issue_number, body))

            def set_status(self, issue_number: int, status: str | None) -> None:
                self.issues[issue_number]["labels"] = (
                    [] if status is None else [{"name": status}]
                )

        api = FakeGitHub()
        changed = coordinator.sweep_satisfied_blocks(api)  # type: ignore[arg-type]

        self.assertEqual(changed, 1)
        self.assertIn(
            coordinator.STATUS_BLOCKED,
            coordinator.label_names(missing),
        )
        self.assertIn(
            coordinator.STATUS_AVAILABLE,
            coordinator.label_names(valid),
        )
        self.assertEqual([number for number, _ in api.comments], [2])

        workflow = {
            "version": 1,
            "kind": "workflow_success",
            "run_id": 404,
            "sha": "b" * 40,
        }
        self.assertEqual(
            coordinator.verify_unblock_condition(api, workflow),  # type: ignore[arg-type]
            (False, None),
        )

    def test_public_workflow_run_read_can_verify_exact_evidence_without_actions_token_scope(self) -> None:
        """AC-03: workflow_success usa GET público real sin Authorization."""
        sha = "c" * 40
        payload = {
            "status": "completed",
            "conclusion": "success",
            "head_sha": sha,
            "repository": {"full_name": "pl0n3r/Factory", "private": False},
        }
        captured = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        original = coordinator.urlopen

        def fake_urlopen(request, timeout=30):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

        try:
            coordinator.urlopen = fake_urlopen
            api = coordinator.GitHub("pl0n3r/Factory", token="token-without-actions")
            condition = {
                "version": 1,
                "kind": "workflow_success",
                "run_id": 123,
                "sha": sha,
            }
            self.assertEqual(
                coordinator.verify_unblock_condition(api, condition),
                (True, f"workflow_run:123@{sha}"),
            )
        finally:
            coordinator.urlopen = original

        request = captured["request"]
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://api.github.com/repos/pl0n3r/Factory/actions/runs/123",
        )
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(
            request.get_header("User-agent"),
            "condor-coordinacion-public-evidence",
        )

    def test_public_request_keeps_allowed_404_fail_closed_without_token(self) -> None:
        """La ruta pública conserva allow=(404,) sin Authorization."""
        class Missing:
            code = 404

            def read(self):
                return b'{"message":"Not Found"}'

        original = coordinator.urlopen

        def fake_urlopen(request, timeout=30):
            self.assertIsNone(request.get_header("Authorization"))
            raise coordinator.HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=Missing(),
            )

        try:
            coordinator.urlopen = fake_urlopen
            api = coordinator.GitHub("pl0n3r/Factory", token="token-without-actions")
            self.assertIsNone(
                api.public_request(
                    "/repos/pl0n3r/Factory/actions/runs/999",
                    allow=(404,),
                )
            )
        finally:
            coordinator.urlopen = original

    def test_unreadable_or_private_workflow_run_evidence_remains_fail_closed(self) -> None:
        """AC-04: 404, repos no gobernados y payload privado nunca desbloquean."""
        sha = "d" * 40
        condition = {
            "version": 1,
            "kind": "workflow_success",
            "run_id": 404,
            "sha": sha,
        }

        class MissingGitHub(coordinator.GitHub):
            def __init__(self) -> None:
                super().__init__("pl0n3r/Factory", token="scoped-token")

            def public_request(self, path: str, allow: tuple[int, ...] = ()) -> object:
                return None

        self.assertEqual(
            coordinator.verify_unblock_condition(MissingGitHub(), condition),
            (False, None),
        )

        class PrivateGitHub(coordinator.GitHub):
            def __init__(self) -> None:
                super().__init__("pl0n3r/Factory", token="scoped-token")

            def public_request(self, path: str, allow: tuple[int, ...] = ()) -> object:
                return {
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": sha,
                    "repository": {"full_name": "pl0n3r/Factory", "private": True},
                }

        with self.assertRaises(coordinator.CoordinationError):
            coordinator.verify_unblock_condition(PrivateGitHub(), condition)

        outside = coordinator.GitHub("example/private", token="scoped-token")
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.verify_unblock_condition(outside, condition)

    def test_non_404_evidence_errors_propagate(self) -> None:
        class ForbiddenGitHub:
            def issue(self, number: int) -> dict:
                raise coordinator.GitHubError(403, "Forbidden")

        condition = {"version": 1, "kind": "issue_closed", "issue": 9}
        with self.assertRaisesRegex(coordinator.GitHubError, "403"):
            coordinator.verify_unblock_condition(
                ForbiddenGitHub(),  # type: ignore[arg-type]
                condition,
            )


    def _reblock_fake_api(
        self,
        *,
        comments: list[dict] | None = None,
    ):
        condition = {"version": 1, "kind": "issue_closed", "issue": 9}
        blocked = {
            "number": 10,
            "state": "open",
            "labels": [{"name": coordinator.STATUS_BLOCKED}],
            "body": marker(**condition),
        }
        target = {
            "number": 9,
            "state": "closed",
            "labels": [],
            "body": "",
        }

        class FakeGitHub:
            def __init__(self) -> None:
                self.issues = {9: target, 10: blocked}
                self._comments = list(comments or [])
                self.comments: list[tuple[int, str]] = []

            def open_issues(self) -> list[dict]:
                return [blocked]

            def issue(self, number: int) -> dict:
                return self.issues[number]

            def issue_comments(self, issue_number: int) -> list[dict]:
                return list(self._comments) if issue_number == 10 else []

            def comment(self, issue_number: int, body: str) -> None:
                self.comments.append((issue_number, body))
                self._comments.append(
                    {
                        "user": {"login": coordinator.TRUSTED_MARKER_LOGIN},
                        "body": body,
                    }
                )

            def set_status(self, issue_number: int, status: str | None) -> None:
                self.issues[issue_number]["labels"] = (
                    [] if status is None else [{"name": status}]
                )

        fingerprint = coordinator.unblock_fingerprint(condition)
        return FakeGitHub(), blocked, fingerprint

    def test_manual_reblock_after_auto_unblock_is_not_overridden(self) -> None:
        api, blocked, fingerprint = self._reblock_fake_api()
        api._comments.append(
            {
                "user": {"login": coordinator.TRUSTED_MARKER_LOGIN},
                "body": coordinator._unblock_evidence_comment(
                    fingerprint,
                    "issue:9:closed",
                ),
            }
        )

        changed = coordinator.sweep_satisfied_blocks(api)

        self.assertEqual(changed, 0)
        self.assertIn(coordinator.STATUS_BLOCKED, coordinator.label_names(blocked))
        self.assertEqual(api.comments, [])

    def test_automatic_reblock_allows_future_auto_unblock(self) -> None:
        api, blocked, fingerprint = self._reblock_fake_api()
        api._comments.extend(
            [
                {
                    "user": {"login": coordinator.TRUSTED_MARKER_LOGIN},
                    "body": coordinator._unblock_evidence_comment(
                        fingerprint,
                        "issue:9:closed",
                    ),
                },
                {
                    "user": {"login": coordinator.TRUSTED_MARKER_LOGIN},
                    "body": coordinator._reblock_evidence_comment(fingerprint),
                },
            ]
        )

        changed = coordinator.sweep_satisfied_blocks(api)

        self.assertEqual(changed, 1)
        self.assertIn(
            coordinator.STATUS_AVAILABLE,
            coordinator.label_names(blocked),
        )
        self.assertEqual(len(api.comments), 1)
        self.assertIn("factory-unblock-evidence", api.comments[0][1])

    def test_first_auto_unblock_remains_idempotent(self) -> None:
        api, blocked, _fingerprint = self._reblock_fake_api()

        first = coordinator.sweep_satisfied_blocks(api)
        second = coordinator.sweep_satisfied_blocks(api)

        self.assertEqual((first, second), (1, 0))
        self.assertIn(
            coordinator.STATUS_AVAILABLE,
            coordinator.label_names(blocked),
        )
        self.assertEqual(len(api.comments), 1)
        self.assertIn("factory-unblock-evidence", api.comments[0][1])


if __name__ == "__main__":
    unittest.main()
