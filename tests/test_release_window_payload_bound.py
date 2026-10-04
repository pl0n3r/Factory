#!/usr/bin/env python3
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import release_window as rw


ROOT = Path(__file__).resolve().parents[1]


class ReleaseWindowPayloadBoundTests(unittest.TestCase):
    def test_factory_ci_compacts_release_snapshot_before_pr_check(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "factory-ci.yml"
        ).read_text(encoding="utf-8")
        release_job = workflow.split("  release_window:", 1)[1].split(
            "  coordinacion:", 1
        )[0]

        self.assertIn(
            "| {number, state, title, body, updated_at}",
            release_job,
        )
        self.assertIn(
            'select(.user.login == "github-actions[bot]")',
            release_job,
        )
        for marker in (
            "factory-human-decision",
            "factory-release-executed",
            "factory-human-gate-duplicate",
        ):
            self.assertIn(f'contains("{marker}")', release_job)

        self.assertIn(
            '| {user: {login: .user.login}, body: (.body // "")}',
            release_job,
        )
        self.assertIn(
            """gh api "repos/$REPOSITORY/pulls/$PR" | jq '{number, body: (.body // "")}'""",
            release_job,
        )
        self.assertIn(
            """gh api "repos/$REPOSITORY/issues/$work_issue" | jq '{number, state, labels: [.labels[]? | {name}]}'""",
            release_job,
        )
        self.assertNotIn(
            "--slurp | jq 'add // []' > /tmp/release-comments.json",
            release_job,
        )

    def test_release_window_parser_keeps_two_megabyte_fail_closed_bound(self) -> None:
        oversized = "{" + (" " * 2_000_000) + "}"
        with patch.object(sys, "stdin", io.StringIO(oversized)):
            with self.assertRaisesRegex(
                rw.ReleaseWindowError,
                "Payload demasiado grande",
            ):
                rw._read_payload()

        near_limit = '{"gates":[]}'
        with patch.object(sys, "stdin", io.StringIO(near_limit)):
            self.assertEqual(rw._read_payload(), {"gates": []})


if __name__ == "__main__":
    unittest.main()
