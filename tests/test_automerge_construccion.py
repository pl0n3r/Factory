"""AC ejecutables de Factory#1142: datos fakes y ningún efecto de merge."""
import copy
import unittest
from unittest.mock import patch

from scripts.automerge_construccion import evaluate

HEAD = "a" * 40
BASE = "b" * 40


def evidence():
    return {
        "phase": "construccion", "kill_switch": "RUNNING",
        "head_sha": HEAD, "observed_head_sha": HEAD,
        "base_sha": BASE, "main_sha": BASE,
        "draft": False, "mergeable": True, "behind_by": 0,
        "required_checks": [{"name": "Validar", "conclusion": "success", "head_sha": HEAD}],
        "gates": {name: {"conclusion": "success", "head_sha": HEAD}
                  for name in ("acceptance", "coordination", "security")},
        "reviews": [{"author": "qa-reviewer", "state": "APPROVED", "trusted": True,
                     "head_sha": HEAD}],
        "author": "implementation-owner", "blocking_threads": 0,
        "paths": ["scripts/feature.py", "tests/test_feature.py"],
        "freeze_active": False, "human_gate_required": False,
        "inventory_complete": True, "api_remaining": 55, "api_minimum": 20,
        "observed_at": "2026-10-11T07:50:00Z",
        "expires_at": "2026-10-11T07:55:00Z", "now": "2026-10-11T07:52:00Z",
    }


class AutoMergeConstruccionTests(unittest.TestCase):
    def deny(self, key, value):
        item = evidence()
        item[key] = value
        decision = evaluate(item)
        self.assertFalse(decision.eligible, (key, decision))
        self.assertNotEqual(decision.reason, "eligible_diagnostic_only")

    def test_valid_construction_candidate_is_diagnostic_only(self):
        candidate = evidence()
        before = copy.deepcopy(candidate)
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            outcome = evaluate(candidate)
        self.assertEqual(outcome.public(), {"eligible": True,
                                            "reason": "eligible_diagnostic_only"})
        self.assertEqual(candidate, before)
        self.assertEqual(set(outcome.public()), {"eligible", "reason"})

    def test_draft_checks_reviews_threads_and_sha_drift_fail_closed(self):
        for key, value in (("draft", True), ("mergeable", False), ("behind_by", 1),
                           ("observed_head_sha", "c" * 40), ("main_sha", "d" * 40),
                           ("blocking_threads", 1)):
            with self.subTest(key=key):
                self.deny(key, value)
        for check in ([], [{"name": "Validar", "conclusion": "pending", "head_sha": HEAD}],
                      [{"name": "Validar", "conclusion": "failure", "head_sha": HEAD}],
                      [{"name": "Validar", "conclusion": "success", "head_sha": BASE}]):
            with self.subTest(check=check):
                self.deny("required_checks", check)
        for state, trusted, reviewer in (("CHANGES_REQUESTED", True, "other"),
                                         ("APPROVED", False, "other"),
                                         ("APPROVED", True, "implementation-owner")):
            self.deny("reviews", [{"author": reviewer, "state": state,
                                   "trusted": trusted, "head_sha": HEAD}])
        gate = evidence()["gates"]
        gate["security"]["conclusion"] = "pending"
        self.deny("gates", gate)

    def test_live_sensitive_paths_and_freeze_require_human_gate(self):
        self.deny("phase", "live")
        self.deny("freeze_active", True)
        self.deny("human_gate_required", True)
        for path in (".github/workflows/release-main.yml", "scripts/politica_ci.py",
                     ".github/rulesets/protection.json", "security/audit.py",
                     "PLAN-AGENTES.md", "../escape.py",
                     "secrets/token.env", "docs/puertas-humanas.md",
                     "config/production.yml", "deploy/prod.py",
                     ".github/workflows/ci.yml",
                     "scripts/coordinar_trabajo.py",
                     "scripts/automerge_construccion.py",
                     "scripts/unattended_kill_switch.py",
                     ".github/dependabot.yml", "config/credentials.yml",
                     "CODEOWNERS", "docs/CODEOWNERS"):
            with self.subTest(path=path):
                self.deny("paths", [path])

    def test_kill_switch_budget_and_incomplete_evidence_deny(self):
        for key, value in (("kill_switch", "PAUSED"), ("kill_switch", "UNKNOWN"),
                           ("api_remaining", 19), ("inventory_complete", False),
                           ("now", "2026-10-11T07:56:00Z"),
                           ("observed_at", None), ("expires_at", "invalid")):
            with self.subTest(key=key):
                self.deny(key, value)
        self.deny("gates", {})

    def test_malformed_inputs_are_safe_and_no_external_effects(self):
        for malformed in (None, [], {}, "secret", {**evidence(), "token": "SENSITIVE"}):
            with self.subTest(malformed=type(malformed).__name__):
                self.assertEqual(evaluate(malformed).public(),
                                 {"eligible": False, "reason": "invalid_snapshot"})
        for key, value in (("draft", 0), ("behind_by", True), ("api_remaining", 20.0),
                           ("required_checks", [{"name": "Validar", "conclusion": "success",
                                                 "head_sha": HEAD}] * 2),
                           ("reviews", [{"author": "x", "state": "APPROVED", "trusted": 1,
                                         "head_sha": HEAD}]),
                           ("reviews", [{"author": "x", "state": [], "trusted": True,
                                         "head_sha": HEAD}])):
            self.deny(key, value)
        for key, value in (
            ("paths", ["scripts/feature.py", "SCRIPTS/FEATURE.PY"]),
            ("paths", ["scripts/feature.py"] * 129),
            ("paths", ["a" * 241]),
            ("required_checks", evidence()["required_checks"] * 129),
            ("reviews", evidence()["reviews"] * 129),
        ):
            with self.subTest(oversized_or_duplicate=key):
                self.deny(key, value)
        secret = evidence()
        secret["phase"] = "SECRET=do-not-expose"
        self.assertNotIn("do-not-expose", repr(evaluate(secret).public()))


if __name__ == "__main__":
    unittest.main()

