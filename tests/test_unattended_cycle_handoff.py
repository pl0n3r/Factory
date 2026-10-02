#!/usr/bin/env python3
"""Regresiones del handoff read-only del ciclo Factory#774."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from scripts.unattended_cycle import compose_unattended_cycle
from scripts.unattended_cycle_handoff import project_unattended_cycle_handoff
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import DailySummary, WatchdogDecision, WatchdogIncident


def dispatch(action: str) -> dict[str, object]:
    suppressed = action != "ALLOW"
    return {
        "selected": None if suppressed else "Factory#774",
        "selected_class": None if suppressed else "high",
        "next_action": {"step": "normal"},
        "ready_not_selected": [],
        "excluded": {},
        "candidates": {},
        "aging_threshold": 3,
        "active_tranche": None,
        "unattended": {
            "enabled": True,
            "action": action,
            "authority": "unchanged",
            "reasons": () if action == "ALLOW" else (f"unattended_watchdog_{action.lower()}",),
        },
    }


def guard(action: str) -> GuardDecision:
    return GuardDecision(
        action=action,
        authority="unchanged",
        pause_allowed=action == "PAUSE",
        reasons=("guards_satisfied",),
        evidence_fingerprint="a" * 64,
    )


def watchdog(action: str, *, freshness: str = "fresh") -> WatchdogDecision:
    incidents = ()
    summary_incidents = ()
    interrupt_owner = False
    if action == "BLOCKED":
        incident = WatchdogIncident(
            code="state_stale",
            severity="S2",
            fingerprint="d" * 64,
            repeated=False,
            reasons=("state_stale",),
        )
        incidents = (incident,)
        summary_incidents = ("state_stale",)
        interrupt_owner = True

    return WatchdogDecision(
        action=action,
        authority="unchanged",
        incidents=incidents,
        new_alert_fingerprints=(("d" * 64,) if action == "BLOCKED" else ()),
        interrupt_owner=interrupt_owner,
        daily_summary=DailySummary(
            active_fronts=("Factory#774",),
            state_freshness=freshness,
            incidents=summary_incidents,
            blockers=(),
            human_gates=(),
            integrated=(),
            reverted=(),
            next_actions=("handoff",),
        ),
        evidence_fingerprint="b" * 64,
    )


def provenance(freshness: str = "fresh") -> dict[str, object]:
    return {
        "head_sha": "c" * 40,
        "dispatch_ref": "dispatcher:exact-snapshot",
        "guard_ref": "a" * 64,
        "watchdog_ref": "b" * 64,
        "freshness": freshness,
    }


def cycle(action: str, *, freshness: str = "fresh") -> dict[str, object]:
    return compose_unattended_cycle(
        dispatch(action),
        guard(action),
        watchdog(action, freshness=freshness),
        provenance=provenance(freshness),
    )


class UnattendedCycleHandoffTests(TestCase):
    def test_handoff_preserves_identity_provenance_freshness_reasons_and_interrupt_state(self):
        allow = project_unattended_cycle_handoff(cycle("ALLOW"))
        self.assertEqual(allow["action"], "ALLOW")
        self.assertEqual(allow["next_transition"], "ALLOW")
        self.assertEqual(allow["work_identity"], "Factory#774")
        self.assertEqual(allow["work_class"], "high")
        self.assertEqual(allow["freshness"], "fresh")
        self.assertEqual(allow["reasons"], ())
        self.assertEqual(allow["provenance"], provenance())
        self.assertEqual(allow["incidents"], ())
        self.assertFalse(allow["interrupt_owner"])

        blocked = project_unattended_cycle_handoff(cycle("BLOCKED"))
        self.assertEqual(blocked["action"], "BLOCKED")
        self.assertEqual(blocked["next_transition"], "BLOCKED")
        self.assertEqual(blocked["work_identity"], None)
        self.assertEqual(blocked["incidents"], ("state_stale",))
        self.assertTrue(blocked["interrupt_owner"])
        self.assertEqual(
            blocked["reasons"],
            ("unattended_watchdog_blocked",),
        )

    def test_handoff_never_grants_reservation_merge_deploy_spend_or_live_authority(self):
        expected = {
            "reserve": False,
            "merge": False,
            "deploy": False,
            "spend": False,
            "live": False,
        }
        for action in ("ALLOW", "PAUSE", "BLOCKED"):
            with self.subTest(action=action):
                result = project_unattended_cycle_handoff(cycle(action))
                self.assertEqual(result["authority"], "unchanged")
                self.assertEqual(result["permissions"], expected)
                self.assertFalse(any(result["permissions"].values()))

    def test_e2e_allow_pause_blocked_and_drift_are_external_io_free(self):
        with (
            patch("builtins.open", side_effect=AssertionError("handoff must not read files")),
            patch("subprocess.run", side_effect=AssertionError("handoff must not run commands")),
            patch("urllib.request.urlopen", side_effect=AssertionError("handoff must not use network")),
        ):
            allow = project_unattended_cycle_handoff(cycle("ALLOW"))
            pause = project_unattended_cycle_handoff(cycle("PAUSE"))
            blocked = project_unattended_cycle_handoff(cycle("BLOCKED"))

            stale_cycle = cycle("ALLOW", freshness="stale")
            drift = project_unattended_cycle_handoff(stale_cycle)

            malformed = cycle("ALLOW")
            malformed["unexpected"] = True
            malformed_result = project_unattended_cycle_handoff(malformed)

        self.assertEqual(allow["action"], "ALLOW")
        self.assertEqual(pause["action"], "PAUSE")
        self.assertEqual(blocked["action"], "BLOCKED")
        self.assertEqual(drift["action"], "BLOCKED")
        self.assertIn("cycle_evidence_not_fresh", drift["reasons"])
        self.assertEqual(
            malformed_result["reasons"],
            ("handoff_cycle_invalid",),
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
