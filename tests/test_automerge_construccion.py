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
        "quality_evidence": [
            {"source": source, "head_sha": HEAD, "complete": True}
            for source in ("sonarcloud", "codeql", "coderabbit")
        ],
        "quality_findings": [],
        "hard_gates": {
            "spend": False, "real_data": False, "deploy": False,
            "release": False, "move_v1": False, "go_live": False,
            "destructive": False, "reservation_v3": True,
            "branch_protection": True,
        },
        "commit_count": 14, "review_rounds": 6,
        "quality_debt_cleared_for_live": False,
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
                           ("observed_head_sha", "c" * 40), ("main_sha", "d" * 40)):
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
            candidate = evidence()
            candidate["reviews"] = [{"author": reviewer, "state": state,
                                     "trusted": trusted, "head_sha": HEAD}]
            self.assertTrue(evaluate(candidate).eligible)
        candidate = evidence()
        candidate["blocking_threads"] = 1
        self.assertTrue(evaluate(candidate).eligible)
        gate = evidence()["gates"]
        gate["security"]["conclusion"] = "pending"
        self.deny("gates", gate)

    def test_dismissed_or_duplicated_reviewer_does_not_count_as_approval(self):
        approval = evidence()["reviews"][0]
        revoked = {"author": "qa-reviewer", "state": "DISMISSED",
                   "trusted": True, "head_sha": HEAD}
        repeated = {"author": "QA-REVIEWER", "state": "COMMENTED",
                    "trusted": True, "head_sha": HEAD}
        for reviews in ([approval, revoked], [revoked, approval],
                        [approval, repeated], [approval, approval]):
            with self.subTest(reviews=reviews):
                candidate = evidence()
                candidate["reviews"] = reviews
                self.assertEqual(evaluate(candidate).public(),
                                 {"eligible": False, "reason": "invalid_snapshot"})
        only_dismissed = evidence()
        only_dismissed["reviews"] = [revoked]
        self.assertTrue(evaluate(only_dismissed).eligible)
        valid_other = evidence()
        valid_other["reviews"] = [revoked,
            {"author": "security-reviewer", "state": "APPROVED",
             "trusted": True, "head_sha": HEAD}]
        self.assertTrue(evaluate(valid_other).eligible)

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
                     "CODEOWNERS", "docs/CODEOWNERS",
                     "template/AGENTES.md", "template/AGENTS.md",
                     "template/PLAN-AGENTES.md",
                     "docs/principios-construccion.md",
                     "agentes/roles/ingenieria-software.md",
                     "docs/unattended-safe-mode.md",
                     "decisiones.yml", "agentes/NUCLEO.md",
                     "template/decisiones.yml", "template/agentes/NUCLEO.md",
                     "template/.github/workflows/ci.yml",
                     "template/.github/workflows/coordinacion.yml",
                     "template/.github/CODEOWNERS",
                     "template/config/credentials.yml"):
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
        self.deny("quality_evidence", [])
        self.deny("hard_gates", {})

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

