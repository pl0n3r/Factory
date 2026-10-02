#!/usr/bin/env python3
"""Regresiones del contrato 4B de guardas desatendidas."""
from pathlib import Path
import unittest

from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_global_idle import CANONICAL_REPOSITORIES, evaluate_global_idle_snapshot
from scripts.unattended_guards import evaluate_global_idle_guard, evaluate_unattended_guards

ROOT = Path(__file__).resolve().parents[1]


def fence(action="replan", pause=True):
    return FencingDecision(action, pause, 4, 2, "a" * 64, "b" * 64, 1, ("test",))


def cfg(**changes):
    value = {
        "global_pause": False,
        "breakers": {"health": {"scope": "repo", "subject": "pl0n3r/Factory", "threshold": 3}},
        "ceilings": {"usage": 100, "cost": 50.0, "parallelism": 2},
    }
    value.update(changes)
    return value


def ev(**changes):
    value = {
        "breakers": {"health": {"consecutive_failures": 0, "fresh": True, "consistent": True}},
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


def global_idle_proof():
    return evaluate_global_idle_snapshot(
        {
            "version": 1,
            "repositories": [
                {
                    "repository": repository,
                    "freshness": "fresh",
                    "ready": False,
                    "reserved": False,
                    "reviewing": False,
                    "ambiguous": False,
                    "source_ref": f"github:{repository}#inventory",
                }
                for repository in CANONICAL_REPOSITORIES
            ],
        }
    )


class UnattendedGuardsTests(unittest.TestCase):
    def test_global_idle_guard_allows_only_valid_proven_idle(self):
        allowed = evaluate_global_idle_guard(global_idle_proof())
        self.assertEqual((allowed.action, allowed.authority), ("ALLOW", "unchanged"))
        self.assertFalse(allowed.pause_allowed)

        invalid = evaluate_global_idle_guard({"version": 1})
        self.assertEqual((invalid.action, invalid.authority), ("BLOCKED", "unchanged"))
        self.assertFalse(invalid.pause_allowed)

        non_idle = global_idle_proof()
        non_idle = {
            **non_idle,
            "idle_global": False,
            "reasons": ["repository_ready:pl0n3r/Factory"],
        }
        blocked = evaluate_global_idle_guard(non_idle)
        self.assertEqual((blocked.action, blocked.authority), ("BLOCKED", "unchanged"))

    def test_global_idle_guard_never_grants_sensitive_authority_or_pause(self):
        result = evaluate_global_idle_guard(global_idle_proof())
        self.assertEqual(result.authority, "unchanged")
        self.assertFalse(result.pause_allowed)
        self.assertNotIn("global_pause_active", result.reasons)
        self.assertNotIn("sensitive_authority_not_granted", result.reasons)
        self.assertEqual(result.action, "ALLOW")
        self.assertEqual(len(result.evidence_fingerprint), 64)

    def test_global_pause_and_missing_configuration_fail_closed(self):
        paused = evaluate_unattended_guards(fence(), cfg(global_pause=True), ev(), metrics())
        self.assertEqual((paused.action, paused.pause_allowed, paused.authority), ("PAUSE", True, "unchanged"))
        self.assertIn("global_pause_active", paused.reasons)
        missing = cfg(); del missing["global_pause"]
        blocked = evaluate_unattended_guards(fence(), missing, ev(), metrics())
        self.assertEqual(blocked.action, "BLOCKED")
        self.assertIn("invalid_config_shape", blocked.reasons)

    def test_circuit_breaker_uses_explicit_threshold_and_consecutive_failures_by_scope(self):
        for scope in ("agent", "repo"):
            subject = "worker-1" if scope == "agent" else "pl0n3r/Factory"
            with self.subTest(scope=scope, failures="N-1"):
                closed = evaluate_unattended_guards(
                    fence("keep", False),
                    cfg(breakers={"health": {"scope": scope, "subject": subject, "threshold": 3}}),
                    ev(breakers={"health": {"consecutive_failures": 2, "fresh": True, "consistent": True}}),
                    metrics(),
                )
                self.assertEqual(closed.action, "ALLOW")
            with self.subTest(scope=scope, failures="N"):
                opened = evaluate_unattended_guards(
                    fence(),
                    cfg(breakers={"health": {"scope": scope, "subject": subject, "threshold": 3}}),
                    ev(breakers={"health": {"consecutive_failures": 3, "fresh": True, "consistent": True}}),
                    metrics(),
                )
                self.assertEqual(opened.action, "PAUSE")
                self.assertIn("circuit_breaker_open", opened.reasons)

        invalid_configs = (
            {"health": {"scope": "repo", "threshold": 3}},
            {"health": {"scope": "repo", "subject": "pl0n3r/Factory"}},
            {"health": {"scope": "repo", "subject": "pl0n3r/Factory", "threshold": 0}},
            {"health": {"scope": "repo", "subject": "pl0n3r/Factory", "threshold": 1.5}},
            {"health": {"scope": "global", "subject": "pl0n3r/Factory", "threshold": 3}},
            {"health": {"scope": "repo", "subject": "../factory", "threshold": 3}},
        )
        for breakers in invalid_configs:
            with self.subTest(breakers=breakers):
                result = evaluate_unattended_guards(
                    fence(), cfg(breakers=breakers), ev(), metrics()
                )
                self.assertEqual(result.action, "BLOCKED")

        cases = (
            ({"consecutive_failures": 0, "fresh": False, "consistent": True}, "breaker_evidence_not_fresh"),
            ({"consecutive_failures": 0, "fresh": True, "consistent": False}, "breaker_evidence_not_consistent"),
        )
        for observed, reason in cases:
            with self.subTest(reason=reason):
                result = evaluate_unattended_guards(
                    fence(), cfg(), ev(breakers={"health": observed}), metrics()
                )
                self.assertEqual(result.action, "BLOCKED")
                self.assertIn(reason, result.reasons)

    def test_breaker_subject_is_scope_aware(self):
        for scope, subject in (("agent", "worker-1"), ("repo", "pl0n3r/Factory")):
            with self.subTest(valid_scope=scope):
                result = evaluate_unattended_guards(
                    fence("keep", False),
                    cfg(breakers={"health": {"scope": scope, "subject": subject, "threshold": 3}}),
                    ev(),
                    metrics(),
                )
                self.assertEqual(result.action, "ALLOW")

        for scope, subject in (
            ("agent", "pl0n3r/Factory"),
            ("repo", "Factory"),
            ("repo", "pl0n3r/Factory/extra"),
        ):
            with self.subTest(invalid_scope=scope, subject=subject):
                result = evaluate_unattended_guards(
                    fence("keep", False),
                    cfg(breakers={"health": {"scope": scope, "subject": subject, "threshold": 3}}),
                    ev(),
                    metrics(),
                )
                self.assertEqual(result.action, "BLOCKED")
                self.assertIn("invalid_breaker_subject", result.reasons)

    def test_replan_pending_never_becomes_allow(self):
        pending = evaluate_unattended_guards(fence("replan", True), cfg(), ev(), metrics())
        self.assertEqual(
            (pending.action, pending.pause_allowed, pending.authority),
            ("PAUSE", True, "unchanged"),
        )
        self.assertIn("adaptive_replan_pending", pending.reasons)

        stricter = evaluate_unattended_guards(
            fence("replan", True), cfg(), ev(risk="high"), metrics()
        )
        self.assertEqual((stricter.action, stricter.pause_allowed), ("BLOCKED", False))
        self.assertIn("high_risk_second_pass_required", stricter.reasons)

    def test_invalid_types_fail_closed_without_exceptions(self):
        bad_risk = evaluate_unattended_guards(
            fence("keep", False), cfg(), ev(risk=[]), metrics()
        )
        self.assertEqual(bad_risk.action, "BLOCKED")
        self.assertIn("invalid_risk", bad_risk.reasons)

        bad_scope = evaluate_unattended_guards(
            fence("keep", False),
            cfg(breakers={"health": {"scope": [], "subject": "pl0n3r/Factory", "threshold": 3}}),
            ev(),
            metrics(),
        )
        self.assertEqual(bad_scope.action, "BLOCKED")
        self.assertIn("invalid_breaker_scope", bad_scope.reasons)

        mixed_config = cfg(
            breakers={
                "health": {"scope": "repo", "subject": "pl0n3r/Factory", "threshold": 3},
                1: {"scope": "agent", "subject": "worker-1", "threshold": 3},
            }
        )
        mixed_evidence = ev(
            breakers={
                "health": {"consecutive_failures": 0, "fresh": True, "consistent": True},
                1: {"consecutive_failures": 0, "fresh": True, "consistent": True},
            }
        )
        mixed = evaluate_unattended_guards(
            fence("keep", False), mixed_config, mixed_evidence, metrics()
        )
        self.assertEqual(mixed.action, "BLOCKED")
        self.assertIn("invalid_breaker_identifier", mixed.reasons)

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
