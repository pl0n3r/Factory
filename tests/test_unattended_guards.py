#!/usr/bin/env python3
"""Regresiones del contrato 4B de guardas desatendidas."""
from pathlib import Path
import unittest

from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_guards import evaluate_unattended_guards

ROOT = Path(__file__).resolve().parents[1]


def fence(action="replan", pause=True):
    return FencingDecision(action, pause, 4, 2, "a" * 64, "b" * 64, 1, ("test",))


def cfg(**changes):
    value = {
        "global_pause": False,
        "breakers": {"health": {"state": "closed"}},
        "ceilings": {"usage": 100, "cost": 50.0, "parallelism": 2},
    }
    value.update(changes)
    return value


def ev(**changes):
    value = {
        "breakers": {"health": {"condition": False, "fresh": True, "consistent": True}},
        "risk": "low",
        "second_pass": False,
        "sensitive": {key: False for key in ("go_live", "spend", "irreversible", "real_data")},
        "production_change": False,
        "backup_required": False,
        "backup_verified": None,
    }
    value.update(changes)
    return value


def metrics(**changes):
    value = {"usage": 10, "cost": 5.0, "parallelism": 1}
    value.update(changes)
    return value


class UnattendedGuardsTests(unittest.TestCase):
    def test_global_pause_and_missing_configuration_fail_closed(self):
        paused = evaluate_unattended_guards(fence(), cfg(global_pause=True), ev(), metrics())
        self.assertEqual((paused.action, paused.pause_allowed, paused.authority), ("PAUSE", True, "unchanged"))
        self.assertIn("global_pause_active", paused.reasons)
        missing = cfg(); del missing["global_pause"]
        blocked = evaluate_unattended_guards(fence(), missing, ev(), metrics())
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertIn("invalid_config_shape", blocked.reasons)

    def test_circuit_breaker_requires_explicit_current_consistent_evidence(self):
        allowed = evaluate_unattended_guards(fence("keep", False), cfg(), ev(), metrics())
        self.assertEqual(allowed.action, "ALLOW")
        cases = (
            ({"condition": False, "fresh": False, "consistent": True}, "breaker_evidence_not_fresh"),
            ({"condition": False, "fresh": True, "consistent": False}, "breaker_evidence_not_consistent"),
            ({"condition": None, "fresh": True, "consistent": True}, "breaker_condition_unknown"),
            ({"condition": True, "fresh": True, "consistent": True}, "breaker_state_contradictory"),
        )
        for observed, reason in cases:
            with self.subTest(reason=reason):
                result = evaluate_unattended_guards(fence(), cfg(), ev(breakers={"health": observed}), metrics())
                self.assertEqual(result.action, "BLOCKED")
                self.assertIn(reason, result.reasons)
        opened = evaluate_unattended_guards(
            fence(), cfg(breakers={"health": {"state": "open"}}),
            ev(breakers={"health": {"condition": True, "fresh": True, "consistent": True}}), metrics()
        )
        self.assertEqual(opened.action, "PAUSE")

    def test_usage_cost_and_parallelism_ceilings_never_infer_limits(self):
        for field, value in (("usage", 101), ("cost", 50.1), ("parallelism", 3)):
            with self.subTest(field=field):
                result = evaluate_unattended_guards(fence(), cfg(), ev(), metrics(**{field: value}))
                self.assertEqual(result.action, "PAUSE")
                self.assertIn(f"{field}_ceiling_exceeded", result.reasons)
        missing = cfg(ceilings={"usage": 100, "parallelism": 2})
        blocked = evaluate_unattended_guards(fence(), missing, ev(), metrics())
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertIn("invalid_ceilings_shape", blocked.reasons)

    def test_guards_never_expand_adaptive_fencing_pause_or_authority(self):
        failed = evaluate_unattended_guards(fence("fail_closed", False), cfg(), ev(), metrics())
        self.assertEqual((failed.action, failed.pause_allowed, failed.authority), ("BLOCKED", False, "unchanged"))
        unsafe_replan = evaluate_unattended_guards(fence("replan", False), cfg(), ev(), metrics())
        self.assertEqual((unsafe_replan.action, unsafe_replan.pause_allowed), ("BLOCKED", False))
        self.assertIn("adaptive_pause_not_allowed", unsafe_replan.reasons)

    def test_high_risk_requires_second_pass_and_sensitive_authority_stays_closed(self):
        blocked = evaluate_unattended_guards(fence("keep", False), cfg(), ev(risk="high"), metrics())
        self.assertIn("high_risk_second_pass_required", blocked.reasons)
        reviewed = evaluate_unattended_guards(fence("keep", False), cfg(), ev(risk="high", second_pass=True), metrics())
        self.assertEqual(reviewed.action, "ALLOW")
        for key in ("go_live", "spend", "irreversible", "real_data"):
            flags = ev()["sensitive"].copy(); flags[key] = True
            with self.subTest(key=key):
                result = evaluate_unattended_guards(fence("keep", False), cfg(), ev(sensitive=flags), metrics())
                self.assertIn("sensitive_authority_not_granted", result.reasons)
        backup = evaluate_unattended_guards(
            fence("keep", False), cfg(),
            ev(production_change=True, backup_required=True, backup_verified=None), metrics()
        )
        self.assertIn("required_backup_not_verified", backup.reasons)

    def test_decision_is_deterministic_sanitized_and_external_io_free(self):
        first = evaluate_unattended_guards(fence("keep", False), cfg(), ev(), metrics())
        second = evaluate_unattended_guards(fence("keep", False), cfg(), ev(), metrics())
        self.assertEqual(first, second)
        self.assertEqual((first.action, first.authority, len(first.evidence_fingerprint)), ("ALLOW", "unchanged", 64))
        secret = "TOP-SECRET-TOKEN"; unsafe = ev(); unsafe["token"] = secret
        blocked = evaluate_unattended_guards(fence(), cfg(), unsafe, metrics())
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertNotIn(secret, repr(blocked))
        source = (ROOT / "scripts" / "unattended_guards.py").read_text(encoding="utf-8")
        for forbidden in ("import requests", "import subprocess", "import socket", "import urllib", "import httpx"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
