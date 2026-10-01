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
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(
                marker(version=1, kind="issue_closed", issue=0)
            )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(
                marker(version=1, kind="issue_closed", issue=9, extra=True)
            )

    def test_workflow_rejects_bad_run_and_sha(self) -> None:
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(
                marker(version=1, kind="workflow_success", run_id=0, sha="a" * 40)
            )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(
                marker(version=1, kind="workflow_success", run_id=7, sha="deadbeef")
            )

    def test_branch_rejects_noncanonical_name(self) -> None:
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(
                marker(version=1, kind="branch_sha", branch="../main", sha="b" * 40)
            )

    def test_duplicate_and_malformed_markers_fail_closed(self) -> None:
        valid = marker(version=1, kind="issue_closed", issue=9)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker(valid + "\n" + valid)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_unblock_marker("<!-- factory-unblock {not-json} -->")


if __name__ == "__main__":
    unittest.main()
