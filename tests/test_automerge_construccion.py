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
        "required_checks": [
            {"name": name, "conclusion": "success", "head_sha": HEAD}
            for name in ("CI factory", "Sonar CI-based", "Evidencia CodeQL",
                         "CodeRabbit", "Criterios de aceptación",
                         "Validar coordinación", "Seguridad")
        ],
        "gates": {name: {"conclusion": "success", "head_sha": HEAD}
                  for name in ("acceptance", "coordination", "security")},
        "reviews": [{"author": "qa-reviewer", "state": "APPROVED", "trusted": True,
                     "head_sha": HEAD}],
        "author": "implementation-owner", "blocking_threads": 0,
        "owner_waiver": None,
        "reservation": {
            "version": 3, "active": True,
            "source": "verified_github_issue_comment",
            "reservation_id": "e94142c2-af88-4a43-b5db-ee9d28abe611",
            "owner": "pl0n3r", "issue_number": 1162,
            "branch": "trabajo/issue-1162",
            "task_paths": ["scripts/feature.py", "tests/test_feature.py"],
            "head_sha": HEAD,
            "verified_at": "2026-10-11T07:51:00Z",
            "expires_at": "2026-10-11T07:55:00Z",
        },
        "review_bot": {
            "provider": "coderabbitai[bot]", "result": "success",
            "head_sha": HEAD, "final_review": "complete",
            "blocking_findings": 0, "trusted": True,
        },
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
        self.assertFalse(evaluate(only_dismissed).eligible)
        valid_other = evidence()
        valid_other["reviews"] = [revoked,
            {"author": "security-reviewer", "state": "APPROVED",
             "trusted": True, "head_sha": HEAD}]
        self.assertEqual(evaluate(valid_other).reason, "reviews_blocked")

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

    @staticmethod
    def _owner_waiver():
        return {
            "source": "github_issue_comment", "repo": "pl0n3r/Factory",
            "issue": 1139, "comment_id": 6107503429, "author": "pl0n3r",
            "scope": "construccion", "head_sha": HEAD, "mvp_declared": False,
            "verification": "authenticated_github_rest",
            "verified_at": "2026-10-11T07:51:00Z",
            "expires_at": "2026-10-11T07:55:00Z",
        }

    def _waived(self):
        candidate = evidence()
        candidate["reviews"] = []
        candidate["owner_waiver"] = self._owner_waiver()
        return candidate

    def test_owner_build_waiver_is_explicit_and_not_a_self_approval(self):
        candidate = self._waived()
        outcome = evaluate(candidate)
        self.assertEqual(outcome.public(),
                         {"eligible": True, "reason": "eligible_diagnostic_only"})
        missing = copy.deepcopy(candidate)
        missing["owner_waiver"] = None
        self.assertEqual(evaluate(missing).reason, "independent_approval_missing")
        for key, bad in (
            ("repo", "attacker/Factory"), ("issue", 1138),
            ("comment_id", 6107503430), ("author", "qa-impostor"),
            ("scope", "live"), ("head_sha", BASE),
            ("verification", "self_attested"), ("mvp_declared", True),
            ("verified_at", "2026-10-11T07:56:00Z"),
            ("expires_at", "2026-10-11T07:51:00Z"),
        ):
            with self.subTest(key=key):
                corrupted = copy.deepcopy(candidate)
                corrupted["owner_waiver"][key] = bad
                self.assertFalse(evaluate(corrupted).eligible)
        selfreview = copy.deepcopy(candidate)
        selfreview["owner_waiver"] = None
        selfreview["reviews"] = [
            {"author": selfreview["author"], "state": "APPROVED",
             "trusted": True, "head_sha": HEAD}
        ]
        self.assertFalse(evaluate(selfreview).eligible)

    def test_waiver_requires_terminal_exact_head_quality_gates(self):
        original = self._waived()
        required = {c["name"] for c in original["required_checks"]}
        self.assertEqual(required, {"CI factory", "Sonar CI-based",
                                    "Evidencia CodeQL", "CodeRabbit",
                                    "Criterios de aceptación",
                                    "Validar coordinación", "Seguridad"})
        for name in required:
            for failure in ("skipped", "pending", "failure", "neutral"):
                with self.subTest(name=name, conclusion=failure):
                    candidate = copy.deepcopy(original)
                    for check in candidate["required_checks"]:
                        if check["name"] == name:
                            check["conclusion"] = failure
                    self.assertFalse(evaluate(candidate).eligible)
            with self.subTest(name=name, case="missing"):
                candidate = copy.deepcopy(original)
                candidate["required_checks"] = [
                    check for check in candidate["required_checks"]
                    if check["name"] != name
                ]
                self.assertFalse(evaluate(candidate).eligible)
            with self.subTest(name=name, case="wrong_head"):
                candidate = copy.deepcopy(original)
                for check in candidate["required_checks"]:
                    if check["name"] == name:
                        check["head_sha"] = BASE
                self.assertFalse(evaluate(candidate).eligible)
        for key, bad in (
            ("final_review", "rate_limited"), ("result", "skipped"),
            ("head_sha", BASE), ("trusted", False),
            ("blocking_findings", 1),
        ):
            with self.subTest(review_bot=key):
                candidate = copy.deepcopy(original)
                candidate["review_bot"][key] = bad
                self.assertFalse(evaluate(candidate).eligible)
        for gate_name in ("acceptance", "coordination", "security"):
            with self.subTest(gate=gate_name):
                candidate = copy.deepcopy(original)
                candidate["gates"][gate_name]["conclusion"] = "pending"
                self.assertFalse(evaluate(candidate).eligible)
        for key, bad in (
            ("active", False), ("version", 2),
            ("source", "self_attested"), ("reservation_id", "not-uuid"),
            ("head_sha", BASE), ("issue_number", 1000),
            ("branch", "trabajo/issue-8888"),
            ("task_paths", ["tests/other.py"]),
            ("expires_at", "2026-10-11T07:49:00Z"),
        ):
            with self.subTest(reservation=key):
                candidate = copy.deepcopy(original)
                candidate["reservation"][key] = bad
                self.assertFalse(evaluate(candidate).eligible)

    def test_waiver_fails_closed_for_live_sensitive_paused_and_review_blocks(self):
        candidate = self._waived()
        for key, bad in (
            ("phase", "live"), ("phase", "UNKNOWN"),
            ("kill_switch", "PAUSED"), ("freeze_active", True),
            ("human_gate_required", True), ("blocking_threads", 1),
            ("base_sha", HEAD), ("observed_head_sha", BASE),
        ):
            with self.subTest(key=key):
                mutant = copy.deepcopy(candidate)
                mutant[key] = bad
                self.assertFalse(evaluate(mutant).eligible)
        for path in ("scripts/automerge_construccion.py",
                     ".github/workflows/release.yml",
                     "template/AGENTES.md", "docs/principios-construccion.md"):
            with self.subTest(path=path):
                mutant = copy.deepcopy(candidate)
                mutant["paths"] = [path]
                mutant["reservation"]["task_paths"] = [path]
                self.assertFalse(evaluate(mutant).eligible)
        for state in ("CHANGES_REQUESTED", "DISMISSED"):
            with self.subTest(review=state):
                mutant = copy.deepcopy(candidate)
                mutant["reviews"] = [
                    {"author": "security", "state": state,
                     "trusted": True, "head_sha": HEAD}
                ]
                self.assertFalse(evaluate(mutant).eligible)
        duplicate = copy.deepcopy(candidate)
        duplicate["reviews"] = [
            {"author": "security", "state": "COMMENTED",
             "trusted": True, "head_sha": HEAD},
            {"author": "SECURITY", "state": "COMMENTED",
             "trusted": True, "head_sha": HEAD},
        ]
        self.assertFalse(evaluate(duplicate).eligible)

    def test_waiver_is_pure_sanitized_and_never_enables_merge(self):
        candidate = self._waived()
        snapshot = copy.deepcopy(candidate)
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            decision = evaluate(candidate)
        self.assertEqual(candidate, snapshot)
        self.assertEqual(decision.public(),
                         {"eligible": True, "reason": "eligible_diagnostic_only"})
        self.assertEqual(set(decision.public()), {"eligible", "reason"})
        for secret in ("token-super-secret", "password", "raw_issue_json"):
            changed = copy.deepcopy(candidate)
            changed[secret] = "SENSITIVE"
            output = repr(evaluate(changed).public())
            self.assertNotIn("SENSITIVE", output)
            self.assertFalse(evaluate(changed).eligible)

    def test_legacy_unknown_phase_remains_human_gated(self):
        """The older #1143 dry-run omits new waiver fields by design."""
        snapshot = evidence()
        for field in ("owner_waiver", "reservation", "review_bot"):
            del snapshot[field]
        snapshot["phase"] = "UNKNOWN"
        self.assertEqual(evaluate(snapshot).public(),
                         {"eligible": False, "reason": "human_gate_required"})
        snapshot["phase"] = "construccion"
        self.assertEqual(evaluate(snapshot).public(),
                         {"eligible": False, "reason": "invalid_snapshot"})

    def test_waiver_issue_and_comment_ids_require_exact_integers(self):
        baseline = self._waived()
        self.assertTrue(evaluate(baseline).eligible)
        for key, aliases in (
            ("issue", (1139.0, "1139", None, True)),
            ("comment_id", (6107503429.0, "6107503429", None, False)),
        ):
            for alias in aliases:
                with self.subTest(key=key, value=repr(alias)):
                    candidate = copy.deepcopy(baseline)
                    candidate["owner_waiver"][key] = alias
                    self.assertEqual(evaluate(candidate).public(),
                                     {"eligible": False,
                                      "reason": "independent_approval_missing"})

    def test_nfc_equivalent_paths_and_control_modules_are_sensitive(self):
        candidate = evidence()
        duplicate = ["src/café.py", "src/cafe\u0301.py"]
        candidate["paths"] = duplicate
        candidate["reservation"]["task_paths"] = duplicate.copy()
        self.assertEqual(evaluate(candidate).reason, "invalid_snapshot")
        for path in (
            "docs/poli\u0301tica.md", "docs/política.md",
            "scripts/orquestador_kit.py", "scripts/unattended_guards.py",
            "scripts/lease_authority_snapshot.py",
        ):
            with self.subTest(path=path):
                negative = evidence()
                negative["paths"] = [path]
                negative["reservation"]["task_paths"] = [path]
                self.assertEqual(evaluate(negative).public(),
                                 {"eligible": False, "reason": "sensitive_paths"})

    def test_independent_approval_does_not_override_dismissed_review(self):
        approved = {"author": "qa-a", "state": "APPROVED",
                    "trusted": True, "head_sha": HEAD}
        dismissed = {"author": "qa-b", "state": "DISMISSED",
                     "trusted": True, "head_sha": HEAD}
        for reviews in ((approved, dismissed), (dismissed, approved)):
            with self.subTest(order=reviews[0]["state"]):
                candidate = evidence()
                candidate["reviews"] = [copy.deepcopy(review) for review in reviews]
                self.assertEqual(evaluate(candidate).public(),
                                 {"eligible": False, "reason": "reviews_blocked"})
        positive = evidence()
        self.assertEqual(evaluate(positive).reason, "eligible_diagnostic_only")

    def test_reservation_uuid_matches_coordinator_version_and_variant(self):
        base = evidence()
        self.assertEqual(evaluate(base).reason, "eligible_diagnostic_only")
        canonical = copy.deepcopy(base)
        canonical["reservation"]["reservation_id"] = (
            "11111111-1111-4111-8111-111111111111"
        )
        self.assertEqual(evaluate(canonical).reason, "eligible_diagnostic_only")
        for invalid_uuid in (
            "00000000-0000-0000-0000-000000000000",
            "11111111-1111-7111-8111-111111111111",
            "11111111-1111-4111-0111-111111111111",
            "11111111-1111-4111-c111-111111111111",
            "00000000-0000-4000-8000-00000000000z",
        ):
            with self.subTest(uuid=invalid_uuid):
                candidate = copy.deepcopy(base)
                candidate["reservation"]["reservation_id"] = invalid_uuid
                self.assertEqual(evaluate(candidate).public(),
                                 {"eligible": False, "reason": "incomplete_evidence"})


if __name__ == "__main__":
    unittest.main()

