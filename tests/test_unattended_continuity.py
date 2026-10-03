#!/usr/bin/env python3
"""Regresiones de continuidad pre-live: UNKNOWN local no equivale a pausa global."""
from __future__ import annotations

import unittest

from scripts.adaptive_fencing import FencingDecision
from scripts.dispatcher_v2 import (
    CANONICAL_DISPATCH_REPOS,
    Candidate,
    adaptive_dispatch_record,
    no_work_proof,
    work_ladder,
)
from scripts.presence_contract import classify_presence
from scripts.unattended_guards import GuardDecision
from scripts.unattended_kill_switch import (
    CANONICAL_OWNER,
    CANONICAL_REPOSITORY_URL,
    CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)
from scripts.unattended_watchdog import DailySummary, WatchdogDecision, WatchdogIncident


def guard(action: str = "ALLOW", reason: str = "guards_satisfied") -> GuardDecision:
    return GuardDecision(
        action=action,
        authority="unchanged",
        pause_allowed=action == "PAUSE",
        reasons=(reason,),
        evidence_fingerprint="c" * 64,
    )


def unknown_watchdog() -> WatchdogDecision:
    incident = WatchdogIncident(
        code="presence_insufficient",
        severity="UNKNOWN",
        fingerprint="a" * 64,
        repeated=False,
        reasons=("capacity:unknown",),
    )
    return WatchdogDecision(
        action="BLOCKED",
        authority="unchanged",
        incidents=(incident,),
        new_alert_fingerprints=("a" * 64,),
        interrupt_owner=False,
        daily_summary=DailySummary(
            active_fronts=(),
            state_freshness="fresh",
            incidents=("UNKNOWN:presence_insufficient",),
            blockers=("presence_insufficient",),
            human_gates=(),
            integrated=(),
            reverted=(),
            next_actions=(),
        ),
        evidence_fingerprint="b" * 64,
    )


def presence_unknown():
    return classify_presence(
        {
            "version": 1,
            "source": "controlbot-runtime",
            "observed_at": "2026-10-03T08:00:00Z",
            "sessions": [
                {
                    "session_id": "factory-watchdog",
                    "agent_id": "watchdog",
                    "project": "factory",
                    "repo": "pl0n3r/Factory",
                    "work_item": "Factory#818",
                    "issue_ref": "#818",
                    "pr_ref": None,
                    "state": "working",
                    "assignment": "watchdog",
                    "claims": ["scripts/unattended_watchdog_runtime.py"],
                    "capabilities": ["python"],
                    "heartbeat_at": "2026-10-03T07:59:30Z",
                    "freshness": "unknown",
                    "generation": 7,
                    "attempt": 1,
                    "safe_point": True,
                    "preemptibility": "preemptible",
                }
            ],
            "capacity": {
                "known_slots": 1,
                "eligible_free_slots": 0,
                "degraded_slots": 0,
                "freshness": "unknown",
            },
        }
    )


def stable_fencing() -> FencingDecision:
    return FencingDecision(
        action="keep",
        pause_allowed=False,
        generation=7,
        attempt=1,
        snapshot_fingerprint="d" * 64,
        event_fingerprint="e" * 64,
        coalesced_events=1,
        reasons=("continuity",),
    )


def kill_switch_issue(body: str) -> dict[str, object]:
    return {
        "number": 767,
        "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL,
        "user": {"login": CANONICAL_OWNER},
        "body": body,
    }


class UnattendedContinuityTests(unittest.TestCase):
    def test_unknown_does_not_globally_block_safe_cross_repo_work(self) -> None:
        factory = Candidate(
            key="pl0n3r/Factory#818",
            priority="critical",
            metadata={"repository_ref": "pl0n3r/Factory"},
        )
        condor = Candidate(
            key="pl0n3r/Condor#safe",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )

        record = adaptive_dispatch_record(
            [factory, condor],
            presence=presence_unknown(),
            fencing=stable_fencing(),
            replan_action="keep",
            unattended_mode=True,
            unattended_guard=guard(),
            unattended_watchdog=unknown_watchdog(),
        )

        self.assertEqual("pl0n3r/Condor#safe", record["selected"])
        self.assertEqual("ALLOW", record["unattended"]["action"])
        self.assertIn("watchdog_unknown_local_scope", record["unattended"]["reasons"])
        self.assertIn(
            "adaptive_presence_unknown",
            record["excluded"]["pl0n3r/Factory#818"],
        )
        self.assertNotIn("pl0n3r/Condor#safe", record["excluded"])

    def test_unknown_action_remains_fail_closed(self) -> None:
        factory = Candidate(
            key="pl0n3r/Factory#818",
            priority="critical",
            metadata={"repository_ref": "pl0n3r/Factory"},
        )
        record = adaptive_dispatch_record(
            [factory],
            presence=presence_unknown(),
            fencing=stable_fencing(),
            replan_action="keep",
            unattended_mode=True,
            unattended_guard=guard(),
            unattended_watchdog=unknown_watchdog(),
        )

        self.assertIsNone(record["selected"])
        self.assertEqual("unattended_gate", record["next_action"]["step"])
        self.assertEqual("BLOCKED", record["unattended"]["action"])
        self.assertIn("watchdog:presence_insufficient", record["unattended"]["reasons"])

    def test_paused_kill_switch_still_stops_all_dispatch(self) -> None:
        paused = kill_switch_issue(
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","owner":"pl0n3r"} -->'
        )
        running = kill_switch_issue(
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
        )

        self.assertTrue(evaluate_unattended_kill_switch(paused).global_pause)
        self.assertTrue(evaluate_unattended_kill_switch(None).global_pause)
        self.assertFalse(evaluate_unattended_kill_switch(running).global_pause)

    def test_human_only_boundaries_remain_closed(self) -> None:
        condor = Candidate(
            key="pl0n3r/Condor#safe",
            priority="high",
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        blocked = work_ladder(
            [condor],
            unattended_mode=True,
            unattended_guard=guard("BLOCKED", "sensitive_authority_not_granted"),
            unattended_watchdog=unknown_watchdog(),
        )
        self.assertEqual("unattended_gate", blocked["step"])
        self.assertEqual("BLOCKED", blocked["action"])
        self.assertIn(
            "guard:sensitive_authority_not_granted",
            blocked["reasons"],
        )

        human_gate = Candidate(
            key="pl0n3r/Condor#human",
            priority="high",
            pending_human_gate=True,
            metadata={"repository_ref": "pl0n3r/Condor"},
        )
        still_blocked = work_ladder(
            [human_gate],
            unattended_mode=True,
            unattended_guard=guard(),
            unattended_watchdog=unknown_watchdog(),
        )
        self.assertEqual("unattended_gate", still_blocked["step"])

    def test_no_work_only_when_no_safe_candidate_exists(self) -> None:
        empty = {repo: () for repo in CANONICAL_DISPATCH_REPOS}
        reasons = {repo: "no safe candidate" for repo in CANONICAL_DISPATCH_REPOS}
        verified = no_work_proof(
            initial_inventory=empty,
            reasons=reasons,
            final_inventory=empty,
        )
        self.assertTrue(verified["valid"])
        self.assertEqual("no_work_verified", verified["reason"])

        with_work = dict(empty)
        with_work["pl0n3r/Condor"] = ("Condor#safe",)
        rejected = no_work_proof(
            initial_inventory=with_work,
            reasons=reasons,
            final_inventory=with_work,
        )
        self.assertFalse(rejected["valid"])
        self.assertEqual("available_work_present", rejected["reason"])


if __name__ == "__main__":
    unittest.main()
