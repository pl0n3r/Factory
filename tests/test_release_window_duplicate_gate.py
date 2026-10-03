#!/usr/bin/env python3
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import release_window as rw


ROOT = Path(__file__).resolve().parents[1]
OLD_SHA = "4" * 40
NEW_SHA = "5" * 40
NOW = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)


def gate_row(*, number: int, body: str, state: str = "open",
             comments: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "issue": {
            "number": number,
            "state": state,
            "title": f"gate {number}",
            "body": body,
            "updated_at": "2026-10-03T09:55:00Z",
        },
        "comments": comments or [],
    }


def bot_comment(body: str) -> dict[str, object]:
    return {"user": {"login": "github-actions[bot]"}, "body": body}


class ReleaseWindowDuplicateGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical = rw._render_gate(
            "1.0.23", OLD_SHA, NOW, source_issue=936
        )

    def duplicate_row(self, body: str = (
        "<!-- factory-human-gate-duplicate canonical=939 -->"
    )) -> dict[str, object]:
        return gate_row(
            number=940,
            body=self.canonical["body"],
            state="closed",
            comments=[bot_comment(body)],
        )

    def test_closed_duplicate_does_not_shadow_open_canonical_gate(self) -> None:
        records = rw.gate_records([
            gate_row(number=939, body=self.canonical["body"]),
            self.duplicate_row(),
        ])
        latest = rw._latest_by_version(records, "1.0.23")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["number"], 939)
        duplicate = next(item for item in records if item["number"] == 940)
        self.assertEqual(duplicate["duplicate_of"], 939)

        workflow = (
            ROOT / ".github" / "workflows" / "release-window.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(workflow.count("factory-human-gate-duplicate"), 2)

    def test_main_move_rearms_from_canonical_gate_when_newer_issue_is_duplicate(self) -> None:
        planned = rw.plan_rearm({
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [
                gate_row(number=939, body=self.canonical["body"]),
                self.duplicate_row(),
            ],
        })
        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(planned["source_issue"], 939)
        self.assertEqual(planned["source_sha"], OLD_SHA)
        self.assertEqual(planned["sha"], NEW_SHA)

    def test_real_closed_unapproved_gate_still_blocks_rearm(self) -> None:
        planned = rw.plan_rearm({
            "now": "2026-10-03T10:20:00Z",
            "main_sha": NEW_SHA,
            "version": "1.0.23",
            "gates": [
                gate_row(number=939, body=self.canonical["body"]),
                gate_row(number=941, body=self.canonical["body"], state="closed"),
            ],
        })
        self.assertEqual(
            planned,
            {"action": "none", "reason": "latest_gate_not_approved"},
        )

    def test_ambiguous_duplicate_marker_fails_closed(self) -> None:
        ambiguous = (
            "<!-- factory-human-gate-duplicate canonical=939 -->\n"
            "<!-- factory-human-gate-duplicate canonical=938 -->"
        )
        with self.assertRaises(rw.ReleaseWindowError):
            rw.gate_records([
                gate_row(number=939, body=self.canonical["body"]),
                self.duplicate_row(ambiguous),
            ])


    def test_duplicate_reference_validation_fails_closed(self) -> None:
        with self.subTest("self_reference"):
            with self.assertRaises(rw.ReleaseWindowError):
                rw.gate_records([
                    gate_row(number=939, body=self.canonical["body"]),
                    gate_row(
                        number=940,
                        body=self.canonical["body"],
                        state="closed",
                        comments=[bot_comment(
                            "<!-- factory-human-gate-duplicate canonical=940 -->"
                        )],
                    ),
                ])

        with self.subTest("missing_canonical"):
            with self.assertRaises(rw.ReleaseWindowError):
                rw.gate_records([
                    gate_row(number=939, body=self.canonical["body"]),
                    self.duplicate_row(
                        "<!-- factory-human-gate-duplicate canonical=938 -->"
                    ),
                ])

        with self.subTest("different_version"):
            other = rw._render_gate(
                "1.0.22", OLD_SHA, NOW, source_issue=900
            )
            with self.assertRaises(rw.ReleaseWindowError):
                rw.gate_records([
                    gate_row(number=938, body=other["body"]),
                    self.duplicate_row(
                        "<!-- factory-human-gate-duplicate canonical=938 -->"
                    ),
                ])

        with self.subTest("duplicate_chain"):
            with self.assertRaises(rw.ReleaseWindowError):
                rw.gate_records([
                    gate_row(number=938, body=self.canonical["body"]),
                    gate_row(
                        number=939,
                        body=self.canonical["body"],
                        state="closed",
                        comments=[bot_comment(
                            "<!-- factory-human-gate-duplicate canonical=938 -->"
                        )],
                    ),
                    self.duplicate_row(),
                ])

    def test_duplicate_gate_cannot_freeze_as_active(self) -> None:
        records = rw.gate_records([
            gate_row(
                number=939,
                body=self.canonical["body"],
                state="closed",
            ),
            gate_row(
                number=940,
                body=self.canonical["body"],
                state="open",
                comments=[bot_comment(
                    "<!-- factory-human-gate-duplicate canonical=939 -->"
                )],
            ),
        ])
        self.assertIsNone(rw.freeze_gate(records, NOW))



if __name__ == "__main__":
    unittest.main()
