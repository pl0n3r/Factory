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
        """AC-03: workflow_success usa la ruta pública y nunca el request autenticado."""
        sha = "c" * 40
        payload = {
            "status": "completed",
            "conclusion": "success",
            "head_sha": sha,
            "repository": {"full_name": "pl0n3r/Factory", "private": False},
        }

        class PublicOnlyGitHub(coordinator.GitHub):
            def __init__(self) -> None:
                super().__init__("pl0n3r/Factory", token="token-without-actions")
                self.public_path = ""

            def request(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("workflow_success no debe usar el token autenticado")

            def public_request(self, path: str, allow: tuple[int, ...] = ()) -> object:
                self.public_path = path
                self.assert_allow = allow
                return payload

        api = PublicOnlyGitHub()
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
        self.assertEqual(api.public_path, "/repos/pl0n3r/Factory/actions/runs/123")
        self.assertEqual(api.assert_allow, (404,))

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


if __name__ == "__main__":
    unittest.main()
