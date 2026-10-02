#!/usr/bin/env python3
"""Regresiones del contrato de ciclo desatendido Factory#772."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from scripts.unattended_cycle import compose_unattended_cycle
from scripts.unattended_guards import GuardDecision
from scripts.unattended_watchdog import DailySummary, WatchdogDecision, WatchdogIncident


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
        bad_head = provenance()
        bad_head["head_sha"] = "not-a-sha"
        bad_dispatch_ref = provenance()
        bad_dispatch_ref["dispatch_ref"] = " has-space "
        bad_guard_ref = provenance()
        bad_guard_ref["guard_ref"] = "a" * 63
        bad_watchdog_ref = provenance()
        bad_watchdog_ref["watchdog_ref"] = "b" * 63
        bad_freshness = provenance()
        bad_freshness["freshness"] = "future"

        invalid_authority_guard = GuardDecision(
            action="ALLOW",
            authority="expanded",
            pause_allowed=False,
            reasons=("guards_satisfied",),
            evidence_fingerprint="a" * 64,
        )
        forged_pause_guard = GuardDecision(
            action="PAUSE",
            authority="unchanged",
            pause_allowed=False,
            reasons=("global_pause_active",),
            evidence_fingerprint="a" * 64,
        )
        incoherent_allow_watchdog = WatchdogDecision(
            action="ALLOW",
            authority="unchanged",
            incidents=(
                WatchdogIncident(
                    code="synthetic_incoherent",
                    severity="S3",
                    fingerprint="c" * 64,
                    repeated=False,
                    reasons=("synthetic",),
                ),
            ),
            new_alert_fingerprints=(),
            interrupt_owner=False,
            daily_summary=watchdog().daily_summary,
            evidence_fingerprint="b" * 64,
        )

        malformed_incident_watchdog = WatchdogDecision(
            action="BLOCKED",
            authority="unchanged",
            incidents=(object(),),
            new_alert_fingerprints=(),
            interrupt_owner=False,
            daily_summary=watchdog().daily_summary,
            evidence_fingerprint="b" * 64,
        )
        missing_summary_watchdog = WatchdogDecision(
            action="BLOCKED",
            authority="unchanged",
            incidents=(),
            new_alert_fingerprints=(),
            interrupt_owner=False,
            daily_summary=None,
            evidence_fingerprint="b" * 64,
        )

        missing_unattended_key = dispatch()
        missing_unattended_key["unattended"] = {
            "enabled": True,
            "action": "ALLOW",
            "authority": "unchanged",
        }
        invalid_unattended_value = dispatch()
        invalid_unattended_value["unattended"] = {
            "enabled": False,
            "action": "ALLOW",
            "authority": "unchanged",
            "reasons": (),
        }
        suppression_incoherent = dispatch("PAUSE")
        suppression_incoherent["selected"] = "Factory#772"

        evidence_ref_mismatch = provenance()
        evidence_ref_mismatch["guard_ref"] = "d" * 64

        cases: list[tuple[str, object, object, object, object, str]] = [
            (
                "invalid provenance shape",
                dispatch(),
                guard(),
                watchdog(),
                {},
                "cycle_provenance_invalid",
            ),
            (
                "invalid head sha",
                dispatch(),
                guard(),
                watchdog(),
                bad_head,
                "cycle_provenance_invalid",
            ),
            (
                "invalid dispatch ref",
                dispatch(),
                guard(),
                watchdog(),
                bad_dispatch_ref,
                "cycle_provenance_invalid",
            ),
            (
                "invalid guard ref",
                dispatch(),
                guard(),
                watchdog(),
                bad_guard_ref,
                "cycle_provenance_invalid",
            ),
            (
                "invalid watchdog ref",
                dispatch(),
                guard(),
                watchdog(),
                bad_watchdog_ref,
                "cycle_provenance_invalid",
            ),
            (
                "invalid freshness token",
                dispatch(),
                guard(),
                watchdog(),
                bad_freshness,
                "cycle_provenance_invalid",
            ),
            (
                "invalid guard type",
                dispatch(),
                object(),
                watchdog(),
                provenance(),
                "cycle_guard_invalid",
            ),
            (
                "invalid watchdog type",
                dispatch(),
                guard(),
                object(),
                provenance(),
                "cycle_watchdog_invalid",
            ),
            (
                "invalid component authority",
                dispatch(),
                invalid_authority_guard,
                watchdog(),
                provenance(),
                "cycle_component_contract_invalid",
            ),
            (
                "forged pause contract",
                dispatch("PAUSE"),
                forged_pause_guard,
                watchdog("PAUSE"),
                provenance(),
                "cycle_component_contract_invalid",
            ),
            (
                "incoherent allow watchdog",
                dispatch(),
                guard(),
                incoherent_allow_watchdog,
                provenance(),
                "cycle_component_contract_invalid",
            ),
            (
                "malformed watchdog incident",
                dispatch("BLOCKED"),
                guard("BLOCKED"),
                malformed_incident_watchdog,
                provenance(),
                "cycle_component_contract_invalid",
            ),
            (
                "missing watchdog summary",
                dispatch("BLOCKED"),
                guard("BLOCKED"),
                missing_summary_watchdog,
                provenance(),
                "cycle_component_contract_invalid",
            ),
            (
                "evidence ref mismatch",
                dispatch(),
                guard(),
                watchdog(),
                evidence_ref_mismatch,
                "cycle_evidence_ref_mismatch",
            ),
            (
                "invalid dispatch",
                {"selected": "Factory#772"},
                guard(),
                watchdog(),
                provenance(),
                "cycle_dispatch_shape_invalid",
            ),
            (
                "missing unattended key",
                missing_unattended_key,
                guard(),
                watchdog(),
                provenance(),
                "cycle_dispatch_unattended_invalid",
            ),
            (
                "invalid unattended value",
                invalid_unattended_value,
                guard(),
                watchdog(),
                provenance(),
                "cycle_dispatch_unattended_invalid",
            ),
            (
                "incoherent 4B/4C pair",
                dispatch("ALLOW"),
                guard("PAUSE"),
                watchdog("ALLOW"),
                provenance(),
                "cycle_component_pair_incoherent",
            ),
            (
                "contradictory actions",
                dispatch("ALLOW"),
                guard("ALLOW"),
                watchdog("BLOCKED"),
                provenance(),
                "cycle_component_action_mismatch",
            ),
            (
                "suppression incoherent",
                suppression_incoherent,
                guard("PAUSE"),
                watchdog("PAUSE"),
                provenance(),
                "cycle_suppression_incoherent",
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
