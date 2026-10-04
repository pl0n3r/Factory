#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import release_bootstrap as rb
from scripts import release_window as rw


ROOT = Path(__file__).resolve().parents[1]
OLD_SHA = "4" * 40
NEW_SHA = "5" * 40
OPENED = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)
AFTER_EXPIRY = "2026-10-03T12:00:00Z"
VERSION = "1.0.23"
SOURCE_ISSUE = 946


def owner_gate_body(sha: str = OLD_SHA) -> str:
    rendered = rw._render_gate(VERSION, sha, OPENED, source_issue=900)
    return "\n".join(
        line
        for line in rendered["body"].splitlines()
        if "factory-release-window" not in line
        and "factory-release-rearm" not in line
    )


def approved_comment(body: str) -> dict[str, object]:
    parsed = rw._gate_from_body(body)
    assert parsed is not None
    gate, _, _ = parsed
    marker = json.dumps(
        {
            "gate_sha256": rw._gate_fingerprint(gate),
            "option": "A",
            "version": 2,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return {
        "user": {"login": "github-actions[bot]"},
        "body": f"<!-- factory-human-decision {marker} -->",
    }


def gate_row(
    *,
    number: int,
    body: str,
    state: str = "closed",
) -> dict[str, object]:
    return {
        "issue": {
            "number": number,
            "state": state,
            "title": f"gate {number}",
            "body": body,
            "updated_at": "2026-10-03T10:10:00Z",
        },
        "comments": [approved_comment(body)],
    }


def bootstrap_payload(
    *,
    expected_sha: str = OLD_SHA,
    gate_sha: str = OLD_SHA,
) -> dict[str, object]:
    rendered = rw._render_gate(
        VERSION,
        gate_sha,
        OPENED,
        source_issue=SOURCE_ISSUE,
    )
    gate_body = rendered["body"]
    source_body = owner_gate_body(gate_sha)
    return {
        "repository": "pl0n3r/factory",
        "repository_owner": "pl0n3r",
        "actor": "pl0n3r",
        "event_name": "workflow_dispatch",
        "ref": "refs/heads/main",
        "default_branch": "main",
        "expected_sha": expected_sha,
        "current_sha": expected_sha,
        "default_branch_sha": expected_sha,
        "v1_sha": "9" * 40,
        "v1_0_0_exists": True,
        "now": AFTER_EXPIRY,
        "rearm_sources": [
            {
                "number": SOURCE_ISSUE,
                "state": "closed",
                "author_association": "OWNER",
                "created_at": "2026-10-03T09:50:00Z",
                "user": {"login": "pl0n3r"},
                "body": source_body,
            }
        ],
        "issues": {
            number: {"state": "closed"}
            for number in rb.REQUIRED_ISSUES
        },
        "gate": {
            "state": "closed",
            "author_association": "NONE",
            "created_at": "2026-10-03T10:05:00Z",
            "user": {"login": "github-actions[bot]"},
            "closed_by": "github-actions[bot]",
            "body": gate_body,
            "comments": [
                {
                    "author_association": "OWNER",
                    "user": {"login": "pl0n3r"},
                    "body": "/decidir A",
                },
                {
                    "author_association": "NONE",
                    **approved_comment(gate_body),
                },
            ],
        },
    }


class ReleaseWindowExpiredDecisionTests(unittest.TestCase):
    def test_valid_owner_decision_on_unchanged_head_survives_expired_window(self) -> None:
        self.assertEqual(
            rb.validate_payload(bootstrap_payload()),
            {"status": "ready", "sha": OLD_SHA},
        )

    def test_expired_decision_with_head_drift_requires_new_gate(self) -> None:
        rendered = rw._render_gate(
            VERSION,
            OLD_SHA,
            OPENED,
            source_issue=900,
        )
        planned = rw.plan_rearm(
            {
                "now": AFTER_EXPIRY,
                "main_sha": NEW_SHA,
                "version": VERSION,
                "gates": [
                    gate_row(number=949, body=rendered["body"])
                ],
            }
        )
        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(planned["source_issue"], 949)
        self.assertEqual(planned["source_sha"], OLD_SHA)
        self.assertEqual(planned["sha"], NEW_SHA)
        self.assertNotIn("factory-human-decision", planned["body"])

    def test_rearm_opens_new_gate_when_previous_is_closed_expired_and_unexecuted(self) -> None:
        rendered = rw._render_gate(
            VERSION,
            OLD_SHA,
            OPENED,
            source_issue=900,
        )
        planned = rw.plan_rearm(
            {
                "now": AFTER_EXPIRY,
                "main_sha": OLD_SHA,
                "version": VERSION,
                "force_rearm": True,
                "gates": [
                    gate_row(number=949, body=rendered["body"])
                ],
            }
        )
        self.assertEqual(planned["action"], "create_gate")
        self.assertEqual(
            planned["reason"],
            "forced_rearm_expired_approved_gate",
        )
        self.assertEqual(planned["sha"], OLD_SHA)
        self.assertNotIn("factory-human-decision", planned["body"])

        workflow = (
            ROOT / ".github" / "workflows" / "release-window.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('EVENT_NAME: ${{ github.event_name }}', workflow)
        self.assertIn('force_rearm=true', workflow)
        self.assertIn('force_rearm:$force_rearm', workflow)

    def test_expired_window_error_message_names_expiry_and_next_step(self) -> None:
        with self.assertRaises(rb.ReleaseBootstrapError) as raised:
            rb.validate_payload(
                bootstrap_payload(
                    expected_sha=NEW_SHA,
                    gate_sha=OLD_SHA,
                )
            )
        message = str(raised.exception)
        self.assertIn("Ventana de release venció en", message)
        self.assertIn("HEAD derivó", message)
        self.assertIn("Rearma una puerta nueva exact-SHA", message)

        guide = (
            ROOT / "docs" / "release-bootstrap.md"
        ).read_text(encoding="utf-8")
        self.assertIn("solo termina el freeze de merges", guide)
        self.assertIn("workflow_dispatch", guide)
        self.assertIn("hora de expiración", guide)

    def test_same_head_expired_without_manual_force_preserves_gate(self) -> None:
        rendered = rw._render_gate(
            VERSION,
            OLD_SHA,
            OPENED,
            source_issue=900,
        )
        result = rw.plan_rearm(
            {
                "now": AFTER_EXPIRY,
                "main_sha": OLD_SHA,
                "version": VERSION,
                "gates": [
                    gate_row(number=949, body=rendered["body"])
                ],
            }
        )
        self.assertEqual(
            result,
            {"action": "none", "reason": "current_head_already_has_gate"},
        )

    def test_force_rearm_input_must_be_boolean(self) -> None:
        with self.assertRaisesRegex(
            rw.ReleaseWindowError,
            "force_rearm debe ser booleano",
        ):
            rw.plan_rearm(
                {
                    "now": AFTER_EXPIRY,
                    "main_sha": OLD_SHA,
                    "version": VERSION,
                    "force_rearm": "true",
                    "gates": [],
                }
            )

    def test_release_window_helper_keeps_actionable_time_errors(self) -> None:
        rendered = rw._render_gate(
            VERSION,
            OLD_SHA,
            OPENED,
            source_issue=900,
        )
        current = rb._release_window(
            rendered["body"],
            OLD_SHA,
            created_at="2026-10-03T10:05:00Z",
            current_at="2026-10-03T10:30:00Z",
        )
        self.assertEqual(
            current["expires_at"].isoformat(timespec="seconds"),
            "2026-10-03T11:00:00+00:00",
        )

        with self.assertRaisesRegex(
            rb.ReleaseBootstrapError,
            "todavía no está vigente",
        ):
            rb._release_window(
                rendered["body"],
                OLD_SHA,
                current_at="2026-10-03T09:59:00Z",
            )

        with self.assertRaisesRegex(
            rb.ReleaseBootstrapError,
            "Ventana de release venció en .*rearma una puerta nueva",
        ):
            rb._release_window(
                rendered["body"],
                OLD_SHA,
                current_at=AFTER_EXPIRY,
            )

    def test_nonexpired_exact_sha_drift_fails_closed_too(self) -> None:
        payload = bootstrap_payload(
            expected_sha=NEW_SHA,
            gate_sha=OLD_SHA,
        )
        payload["now"] = "2026-10-03T10:30:00Z"
        with self.assertRaises(rb.ReleaseBootstrapError) as raised:
            rb.validate_payload(payload)
        message = str(raised.exception)
        self.assertIn("corresponde a otro SHA", message)
        self.assertIn("HEAD derivó", message)
        self.assertIn("puerta nueva exact-SHA", message)


if __name__ == "__main__":
    unittest.main()
