#!/usr/bin/env python3
"""Regresiones de las guardas runtime del modo desatendido seguro."""
from pathlib import Path
import unittest

from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_guards import evaluate_unattended_guards


ROOT = Path(__file__).resolve().parents[1]


def fencing(*, action="replan", pause_allowed=True):
    return FencingDecision(
        action=action,
        pause_allowed=pause_allowed,
        generation=4,
        attempt=2,
        snapshot_fingerprint="a" * 64,
        event_fingerprint="b" * 64,
        coalesced_events=1,
        reasons=("test",),
    )


def config(**overrides):
    payload = {
        "global_pause": False,
        "breakers": {"health": {"state": "closed"}},
        "ceilings": {"usage": 100, "cost": 50.0, "parallelism": 2},
    }
    payload.update(overrides)
    return payload


def evidence(**overrides):
    payload = {
        "breakers": {
            "health": {"condition": False, "fresh": True, "consistent": True}
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
    payload.update(overrides)
    return payload


def measurements(**overrides):
    payload = {"usage": 10, "cost": 5.0, "parallelism": 1}
    payload.update(overrides)
    return payload


class UnattendedGuardsTests(unittest.TestCase):
    def test_global_pause_and_missing_configuration_fail_closed(self):
        paused = evaluate_unattended_guards(
            fencing(),
            config(global_pause=True),
            evidence(),
            measurements(),
        )
        self.assertEqual(paused.action, "PAUSE")
        self.assertTrue(paused.pause_allowed)
        self.assertIn("global_pause_active", paused.reasons)
        self.assertEqual(paused.authority, "unchanged")

        missing = config()
        del missing["global_pause"]
        blocked = evaluate_unattended_guards(
            fencing(), missing, evidence(), measurements()
        )
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertFalse(blocked.pause_allowed)
        self.assertIn("invalid_config_shape", blocked.reasons)

    def test_circuit_breaker_requires_explicit_current_consistent_evidence(self):
        allowed = evaluate_unattended_guards(
            fencing(action="keep", pause_allowed=False),
            config(),
            evidence(),
            measurements(),
        )
        self.assertEqual(allowed.action, "ALLOW")

        stale_evidence = evidence(
            breakers={
                "health": {"condition": False, "fresh": False, "consistent": True}
            }
        )
        stale = evaluate_unattended_guards(
            fencing(), config(), stale_evidence, measurements()
        )
        self.assertEqual(stale.action, "BLOCKED")
        self.assertIn("breaker_evidence_not_fresh", stale.reasons)

        contradictory = evidence(
            breakers={
                "health": {"condition": True, "fresh": True, "consistent": True}
            }
        )
        conflict = evaluate_unattended_guards(
            fencing(), config(), contradictory, measurements()
        )
        self.assertEqual(conflict.action, "BLOCKED")
        self.assertIn("breaker_state_contradictory", conflict.reasons)

        opened = evaluate_unattended_guards(
            fencing(),
            config(breakers={"health": {"state": "open"}}),
            evidence(
                breakers={
                    "health": {
                        "condition": True,
                        "fresh": True,
                        "consistent": True,
                    }
                }
            ),
            measurements(),
        )
        self.assertEqual(opened.action, "PAUSE")
        self.assertIn("circuit_breaker_open", opened.reasons)

    def test_usage_cost_and_parallelism_ceilings_never_infer_limits(self):
        for field, value in (("usage", 101), ("cost", 50.1), ("parallelism", 3)):
            with self.subTest(field=field):
                decision = evaluate_unattended_guards(
                    fencing(), config(), measurements(**{field: value}) and evidence(), measurements(**{field: value})
                )
                self.assertEqual(decision.action, "PAUSE")
                self.assertIn(f"{field}_ceiling_exceeded", decision.reasons)

        missing_limit = config(
            ceilings={"usage": 100, "parallelism": 2}
        )
        blocked = evaluate_unattended_guards(
            fencing(), missing_limit, evidence(), measurements()
        )
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertIn("invalid_ceilings_shape", blocked.reasons)

    def test_guards_never_expand_adaptive_fencing_pause_or_authority(self):
        failed = evaluate_unattended_guards(
            fencing(action="fail_closed", pause_allowed=False),
            config(),
            evidence(),
            measurements(),
        )
        self.assertEqual(failed.action, "BLOCKED")
        self.assertFalse(failed.pause_allowed)
        self.assertEqual(failed.authority, "unchanged")

        cannot_pause = evaluate_unattended_guards(
            fencing(action="replan", pause_allowed=False),
            config(global_pause=True),
            evidence(),
            measurements(),
        )
        self.assertEqual(cannot_pause.action, "BLOCKED")
        self.assertFalse(cannot_pause.pause_allowed)
        self.assertIn("adaptive_pause_not_allowed", cannot_pause.reasons)
        self.assertEqual(cannot_pause.authority, "unchanged")

    def test_high_risk_requires_second_pass_and_sensitive_authority_stays_closed(self):
        high_without_review = evaluate_unattended_guards(
            fencing(action="keep", pause_allowed=False),
            config(),
            evidence(risk="high", second_pass=False),
            measurements(),
        )
        self.assertEqual(high_without_review.action, "BLOCKED")
        self.assertIn("high_risk_second_pass_required", high_without_review.reasons)

        high_reviewed = evaluate_unattended_guards(
            fencing(action="keep", pause_allowed=False),
            config(),
            evidence(risk="high", second_pass=True),
            measurements(),
        )
        self.assertEqual(high_reviewed.action, "ALLOW")

        for flag in ("go_live", "spend", "irreversible", "real_data"):
            sensitive = evidence()["sensitive"].copy()
            sensitive[flag] = True
            with self.subTest(flag=flag):
                blocked = evaluate_unattended_guards(
                    fencing(action="keep", pause_allowed=False),
                    config(),
                    evidence(sensitive=sensitive),
                    measurements(),
                )
                self.assertEqual(blocked.action, "BLOCKED")
                self.assertIn("sensitive_authority_not_granted", blocked.reasons)

        no_backup = evaluate_unattended_guards(
            fencing(action="keep", pause_allowed=False),
            config(),
            evidence(
                production_change=True,
                backup_required=True,
                backup_verified=None,
            ),
            measurements(),
        )
        self.assertEqual(no_backup.action, "BLOCKED")
        self.assertIn("required_backup_not_verified", no_backup.reasons)

    def test_decision_is_deterministic_sanitized_and_external_io_free(self):
        first = evaluate_unattended_guards(
            fencing(action="keep", pause_allowed=False),
            config(),
            evidence(),
            measurements(),
        )
        second = evaluate_unattended_guards(
            fencing(action="keep", pause_allowed=False),
            config(),
            evidence(),
            measurements(),
        )
        self.assertEqual(first, second)
        self.assertEqual(first.action, "ALLOW")
        self.assertEqual(first.authority, "unchanged")
        self.assertEqual(len(first.evidence_fingerprint), 64)
        self.assertEqual(first.reasons, tuple(sorted(first.reasons)))

        secret = "TOP-SECRET-TOKEN"
        unsafe_payload = evidence()
        unsafe_payload["token"] = secret
        blocked = evaluate_unattended_guards(
            fencing(), config(), unsafe_payload, measurements()
        )
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertNotIn(secret, repr(blocked))

        source = (ROOT / "scripts" / "unattended_guards.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "import requests",
            "import subprocess",
            "import socket",
            "import urllib",
            "import httpx",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
