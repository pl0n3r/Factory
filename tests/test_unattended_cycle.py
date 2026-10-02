#!/usr/bin/env python3
"""Regresiones del contrato de ciclo desatendido Factory#772."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from scripts.unattended_cycle import compose_unattended_cycle
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import DailySummary, WatchdogDecision


def dispatch(action: str = "ALLOW") -> dict[str, object]:
    suppressed = action != "ALLOW"
    return {
        "selected": None if suppressed else "Factory#772",
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


def guard(action: str = "ALLOW") -> GuardDecision:
    return GuardDecision(
        action=action,
        authority="unchanged",
        pause_allowed=action == "PAUSE",
        reasons=("guards_satisfied",),
        evidence_fingerprint="a" * 64,
    )


def watchdog(action: str = "ALLOW", *, freshness: str = "fresh") -> WatchdogDecision:
    return WatchdogDecision(
        action=action,
        authority="unchanged",
        incidents=(),
        new_alert_fingerprints=(),
        interrupt_owner=False,
        daily_summary=DailySummary(
            active_fronts=("Factory#772",),
            state_freshness=freshness,
            incidents=(),
            blockers=(),
            human_gates=(),
            integrated=(),
            reverted=(),
            next_actions=("compose",),
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


class UnattendedCycleTests(TestCase):
    def test_cycle_consumes_canonical_dispatch_guard_and_watchdog_without_recalculation(self):
        with (
            patch(
                "scripts.dispatcher_v2.select_next",
                side_effect=AssertionError("cycle must not recalculate dispatcher ranking"),
            ),
            patch(
                "scripts.unattended_guards.evaluate_unattended_guards",
                side_effect=AssertionError("cycle must not recalculate 4B"),
            ),
            patch(
                "scripts.unattended_watchdog.evaluate_unattended_watchdog",
                side_effect=AssertionError("cycle must not recalculate 4C"),
            ),
        ):
            result = compose_unattended_cycle(
                dispatch(),
                guard(),
                watchdog(),
                provenance=provenance(),
            )

        self.assertEqual(result["action"], "ALLOW")
        self.assertEqual(result["authority"], "unchanged")
        self.assertEqual(result["selected"], "Factory#772")
        self.assertEqual(result["freshness"], "fresh")
        self.assertEqual(result["provenance"], provenance())
        self.assertEqual(result["components"]["guard"]["action"], "ALLOW")
        self.assertEqual(result["components"]["watchdog"]["action"], "ALLOW")
        self.assertEqual(result["components"]["dispatch"]["action"], "ALLOW")

    def test_invalid_stale_unknown_or_contradictory_inputs_fail_closed(self):
        cases: list[tuple[str, object, object, object, object, str]] = [
            (
                "invalid dispatch",
                {"selected": "Factory#772"},
                guard(),
                watchdog(),
                provenance(),
                "cycle_dispatch_shape_invalid",
            ),
            (
                "stale evidence",
                dispatch(),
                guard(),
                watchdog(),
                provenance("stale"),
                "cycle_evidence_not_fresh",
            ),
            (
                "unknown evidence",
                dispatch(),
                guard(),
                watchdog(),
                provenance("unknown"),
                "cycle_evidence_not_fresh",
            ),
            (
                "watchdog stale",
                dispatch(),
                guard(),
                watchdog(freshness="stale"),
                provenance(),
                "cycle_watchdog_state_not_fresh",
            ),
            (
                "contradictory actions",
                dispatch("ALLOW"),
                guard("ALLOW"),
                watchdog("BLOCKED"),
                provenance(),
                "cycle_component_action_mismatch",
            ),
        ]

        for name, dispatch_input, guard_input, watchdog_input, refs, reason in cases:
            with self.subTest(name=name):
                result = compose_unattended_cycle(
                    dispatch_input,
                    guard_input,
                    watchdog_input,
                    provenance=refs,
                )
                self.assertEqual(result["action"], "BLOCKED")
                self.assertEqual(result["authority"], "unchanged")
                self.assertIsNone(result["selected"])
                self.assertEqual(result["reasons"], (reason,))


if __name__ == "__main__":
    import unittest

    unittest.main()
