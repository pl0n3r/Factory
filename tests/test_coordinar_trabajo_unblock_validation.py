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
