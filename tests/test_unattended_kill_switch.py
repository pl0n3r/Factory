#!/usr/bin/env python3
"""Regresiones del kill switch global Factory#767."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_guards import evaluate_unattended_guards
from scripts.unattended_kill_switch import (
    CANONICAL_OWNER,
    CANONICAL_REPOSITORY_URL,
    CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)

ROOT = Path(__file__).resolve().parents[1]
MARKER_RUNNING = '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
MARKER_PAUSED = '<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","owner":"pl0n3r"} -->'


def issue(body: str = MARKER_RUNNING) -> dict[str, object]:
    return {
        "number": 767,
        "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL,
        "user": {"login": CANONICAL_OWNER},
        "body": body,
    }


def guard_config(global_pause: bool) -> dict[str, object]:
    return {
        "global_pause": global_pause,
        "breakers": {
            "health": {
                "scope": "repo",
                "subject": "pl0n3r/Factory",
                "threshold": 3,
            }
        },
        "ceilings": {"usage": 100, "cost": 50.0, "parallelism": 2},
    }


def guard_evidence() -> dict[str, object]:
    return {
        "breakers": {
            "health": {
                "consecutive_failures": 0,
                "fresh": True,
                "consistent": True,
            }
        },
        "risk": "low",
        "second_pass": False,
        "sensitive": {
            "go_live": False,
            "spend": False,
            "irreversible": False,
            "real_data": False,
        },
        "production_change": False,
        "backup_required": False,
        "backup_verified": None,
    }


def fencing(action: str = "keep", pause: bool = False) -> FencingDecision:
    return FencingDecision(
        action, pause, 7, 1, "a" * 64, "b" * 64, 1, ("kill-switch",)
    )


class UnattendedKillSwitchTests(unittest.TestCase):
    def test_source_is_canonical_public_and_owner_controlled(self):
        running = evaluate_unattended_kill_switch(issue())
        self.assertEqual(
            CANONICAL_SOURCE_URL,
            "https://api.github.com/repos/pl0n3r/Factory/issues/767",
        )
        self.assertEqual((running.state, running.global_pause), ("RUNNING", False))

        wrong_issue = issue()
        wrong_issue["number"] = 768
        self.assertTrue(evaluate_unattended_kill_switch(wrong_issue).global_pause)

        wrong_url = issue()
        wrong_url["url"] = "https://api.github.com/repos/pl0n3r/Factory/issues/768"
        self.assertTrue(evaluate_unattended_kill_switch(wrong_url).global_pause)

        wrong_repo = issue()
        wrong_repo["repository_url"] = "https://api.github.com/repos/pl0n3r/Other"
        self.assertTrue(evaluate_unattended_kill_switch(wrong_repo).global_pause)

        wrong_owner = issue()
        wrong_owner["user"] = {"login": "other"}
        decision = evaluate_unattended_kill_switch(wrong_owner)
        self.assertEqual(
            (decision.state, decision.global_pause, decision.reason),
            ("UNKNOWN", True, "unexpected_issue_author"),
        )

    def test_plan_and_startup_card_check_switch_before_dispatch_or_write(self):
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        startup = (ROOT / "agentes" / "NUCLEO.md").read_text(encoding="utf-8")

        for content in (plan, startup):
            self.assertIn(CANONICAL_SOURCE_URL, content)
            self.assertIn("factory-unattended-kill-switch", content)
            self.assertIn("RUNNING", content)
            self.assertIn("cero mutaciones", content)

        switch_section = plan.index("### Interruptor global antes de cualquier mutación")
        preflight = plan.index("### Preflight de capacidades")
        self.assertLess(switch_section, preflight)
        self.assertIn("antes del primer comentario de despacho", plan.lower())

    def test_missing_or_invalid_switch_fails_closed(self):
        cases: list[tuple[object, str]] = [
            (None, "source_unreadable"),
            ({}, "unexpected_issue"),
            (issue("sin marker"), "kill_switch_marker_count_invalid"),
            (
                issue(MARKER_RUNNING + "\n" + MARKER_PAUSED),
                "kill_switch_marker_count_invalid",
            ),
            (
                issue('<!-- factory-unattended-kill-switch {not-json} -->'),
                "kill_switch_marker_invalid_json",
            ),
            (
                issue('<!-- factory-unattended-kill-switch {"version":2,"state":"RUNNING","owner":"pl0n3r"} -->'),
                "kill_switch_marker_invalid_version",
            ),
            (
                issue('<!-- factory-unattended-kill-switch {"version":true,"state":"RUNNING","owner":"pl0n3r"} -->'),
                "kill_switch_marker_invalid_version",
            ),
            (
                issue('<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","state":"RUNNING","owner":"pl0n3r"} -->'),
                "kill_switch_marker_duplicate_key",
            ),
            (
                issue('<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"other"} -->'),
                "kill_switch_marker_invalid_owner",
            ),
            (
                issue('<!-- factory-unattended-kill-switch {"version":1,"state":"UNKNOWN","owner":"pl0n3r"} -->'),
                "kill_switch_marker_invalid_state",
            ),
        ]

        for payload, expected_reason in cases:
            with self.subTest(reason=expected_reason):
                decision = evaluate_unattended_kill_switch(payload)
                self.assertEqual(decision.state, "UNKNOWN")
                self.assertTrue(decision.global_pause)
                self.assertEqual(decision.reason, expected_reason)

    def test_running_paused_missing_and_resume_feed_global_pause(self):
        metrics = {"usage": 10, "cost": 5.0, "parallelism": 1}

        running = evaluate_unattended_kill_switch(issue(MARKER_RUNNING))
        allowed = evaluate_unattended_guards(
            fencing(),
            guard_config(running.global_pause),
            guard_evidence(),
            metrics,
        )
        self.assertEqual((running.global_pause, allowed.action), (False, "ALLOW"))

        for payload in (issue(MARKER_PAUSED), None):
            paused = evaluate_unattended_kill_switch(payload)
            guarded = evaluate_unattended_guards(
                fencing("replan", True),
                guard_config(paused.global_pause),
                guard_evidence(),
                metrics,
            )
            self.assertTrue(paused.global_pause)
            self.assertEqual(guarded.action, "PAUSE")
            self.assertIn("global_pause_active", guarded.reasons)

        resumed = evaluate_unattended_kill_switch(issue(MARKER_RUNNING))
        resumed_guard = evaluate_unattended_guards(
            FencingDecision(
                "keep", False, 8, 1, "c" * 64, "d" * 64, 1, ("resume",)
            ),
            guard_config(resumed.global_pause),
            guard_evidence(),
            metrics,
        )
        self.assertEqual(
            (resumed.state, resumed.global_pause, resumed_guard.action),
            ("RUNNING", False, "ALLOW"),
        )

    def test_owner_runbook_is_short_and_explicit(self):
        guide = (ROOT / "docs" / "unattended-kill-switch.md").read_text(encoding="utf-8")
        self.assertIn(CANONICAL_SOURCE_URL, guide)
        self.assertIn("PAUSED", guide)
        self.assertIn("RUNNING", guide)
        self.assertIn("UNKNOWN", guide)
        self.assertIn("no mata procesos", guide.lower())
        self.assertIn("solo el dueño", guide.lower())
        self.assertIn("no demuestra quién hizo la última edición", guide)
        self.assertIn("creador", guide.lower())
        self.assertLessEqual(len(guide.splitlines()), 90)


if __name__ == "__main__":
    unittest.main()
