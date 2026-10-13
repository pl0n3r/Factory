"""Contratos ejecutables de #1295: diagnóstico de gates esenciales pre-live."""
import copy
import unittest
from pathlib import Path
from scripts.automerge_construccion import evaluate

HEAD = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def candidate():
    return {
        "phase": "construccion", "kill_switch": "RUNNING",
        "head_sha": HEAD, "observed_head_sha": HEAD,
        "base_sha": "b" * 40, "main_sha": "b" * 40,
        "draft": False, "mergeable": True, "behind_by": 0,
        "required_checks": [
            {"name": "Validar", "conclusion": "success", "head_sha": HEAD},
            {"name": "CodeQL", "conclusion": "failure", "head_sha": HEAD},
        ],
        "gates": {
            x: {"conclusion": "success", "head_sha": HEAD}
            for x in ("acceptance", "coordination", "security")
        },
        "reviews": [], "author": "owner", "blocking_threads": 0,
        "paths": ["src/feature.py", "tests/test_feature.py"],
        "freeze_active": False, "human_gate_required": False,
        "inventory_complete": True, "api_remaining": 80, "api_minimum": 20,
        "observed_at": "2026-10-12T19:00:00Z",
        "expires_at": "2026-10-12T19:04:00Z",
        "now": "2026-10-12T19:02:00Z",
        "quality_evidence": [
            {"source": x, "head_sha": HEAD, "complete": True}
            for x in ("sonarcloud", "codeql", "coderabbit")
        ],
        "quality_findings": [],
        "hard_gates": {
            "spend": False, "real_data": False, "deploy": False,
            "release": False, "move_v1": False, "go_live": False,
            "destructive": False, "reservation_v3": True,
            "branch_protection": True,
        },
        "commit_count": 15, "review_rounds": 9,
        "quality_debt_cleared_for_live": False,
    }


def finding(source="codeql", severity="high", category="security",
            on_new_code=True, open=True):
    return dict(source=source, severity=severity, category=category,
                on_new_code=on_new_code, open=open)


class EssentialGatesTests(unittest.TestCase):
    def test_construction_merge_requires_only_essential_checks_plus_severe_findings(self):
        s = candidate()
        self.assertEqual(evaluate(s).public(),
                         {"eligible": True, "reason": "eligible_diagnostic_only"})
        for key, value in (("draft", True), ("mergeable", False),
                           ("behind_by", 1), ("main_sha", "c" * 40),
                           ("observed_head_sha", "c" * 40)):
            with self.subTest(key=key):
                bad = candidate()
                bad[key] = value
                self.assertFalse(evaluate(bad).eligible)
        for state in ("failure", "pending", "cancelled"):
            bad = candidate()
            bad["required_checks"][0]["conclusion"] = state
            self.assertEqual(evaluate(bad).reason, "checks_not_green")
        missing = candidate()
        missing["required_checks"] = missing["required_checks"][1:]
        self.assertEqual(evaluate(missing).reason, "incomplete_evidence")

    def test_explicit_lint_and_build_failures_veto_even_when_validar_is_green(self):
        # Un agregado de CI inconsistente no convierte en informativo un
        # fallo de lint/build declarado para el mismo HEAD.
        for check_name in ("Lint de workflows", "lint", "Build", "build del producto"):
            for status in ("failure", "pending", "cancelled", "skipped"):
                with self.subTest(check_name=check_name, status=status):
                    bad = candidate()
                    bad["required_checks"].append({
                        "name": check_name, "head_sha": HEAD, "conclusion": status,
                    })
                    self.assertEqual(evaluate(bad).reason, "checks_not_green")
            good = candidate()
            good["required_checks"].append({
                "name": check_name, "head_sha": HEAD, "conclusion": "success",
            })
            self.assertTrue(evaluate(good).eligible)
        advisory = candidate()
        advisory["quality_findings"] = [finding("coderabbit", "low", "code_smell")]
        self.assertTrue(evaluate(advisory).eligible)

    def test_minor_findings_are_advisory_and_severe_findings_still_block(self):
        for source in ("sonarcloud", "codeql", "coderabbit"):
            for severity in ("high", "critical"):
                with self.subTest(source=source, severity=severity):
                    bad = candidate()
                    bad["quality_findings"] = [finding(source, severity)]
                    self.assertEqual(evaluate(bad).reason, "severe_quality_finding")
        for severity in ("medium", "low", "info"):
            advisory = candidate()
            advisory["quality_findings"] = [finding("sonarcloud", severity)]
            self.assertTrue(evaluate(advisory).eligible)
        for change in ({"on_new_code": False}, {"open": False},
                       {"category": "code_smell"}):
            advisory = candidate()
            advisory["quality_findings"] = [dict(finding(), **change)]
            self.assertTrue(evaluate(advisory).eligible)
        for mutation in (
            lambda s: s["quality_evidence"][0].update(complete=False),
            lambda s: s["quality_evidence"][0].update(head_sha="c" * 40),
            lambda s: s.update(quality_evidence=[]),
        ):
            bad = candidate()
            mutation(bad)
            self.assertFalse(evaluate(bad).eligible)
        invalid = candidate()
        invalid["quality_findings"] = [finding(severity=["high"])]
        self.assertFalse(evaluate(invalid).eligible)

    def test_open_review_threads_and_changes_requested_do_not_block_construction(self):
        advisory = candidate()
        advisory["blocking_threads"] = 4
        advisory["reviews"] = [
            {"author": "reviewer", "state": "CHANGES_REQUESTED",
             "trusted": True, "head_sha": HEAD},
        ]
        advisory["gates"]["coordination"]["conclusion"] = "failure"
        advisory["gates"]["acceptance"]["conclusion"] = "pending"
        self.assertTrue(evaluate(advisory).eligible)
        advisory["quality_findings"] = [finding("coderabbit", "critical")]
        self.assertEqual(evaluate(advisory).reason, "severe_quality_finding")

    def test_commit_cap_and_review_rounds_are_not_blocking(self):
        s = candidate()
        s["commit_count"] = 42
        s["review_rounds"] = 100
        self.assertTrue(evaluate(s).eligible)
        for key in ("commit_count", "review_rounds"):
            bad = candidate()
            bad[key] = -1
            self.assertEqual(evaluate(bad).reason, "invalid_snapshot")

    def test_hard_gates_remain_blocking(self):
        for key in ("freeze_active", "human_gate_required"):
            bad = candidate()
            bad[key] = True
            self.assertEqual(evaluate(bad).reason, "human_gate_required")
        for key in ("spend", "real_data", "deploy", "release", "move_v1",
                    "go_live", "destructive"):
            bad = candidate()
            bad["hard_gates"][key] = True
            self.assertEqual(evaluate(bad).reason, "human_gate_required")
        for key in ("reservation_v3", "branch_protection"):
            bad = candidate()
            bad["hard_gates"][key] = False
            self.assertEqual(evaluate(bad).reason, "human_gate_required")
        bad = candidate()
        bad["kill_switch"] = "PAUSED"
        self.assertEqual(evaluate(bad).reason, "kill_switch_inactive")
        bad = candidate()
        bad["hard_gates"]["deploy"] = "false"
        self.assertEqual(evaluate(bad).reason, "invalid_snapshot")

    def test_legacy_observer_is_denied_and_malformed_evidence_is_fail_closed(self):
        """El observador sin evidencia nueva nunca obtiene autorización."""
        legacy = candidate()
        for field in (
            "quality_evidence", "quality_findings", "hard_gates",
            "commit_count", "review_rounds", "quality_debt_cleared_for_live",
        ):
            legacy.pop(field)
        legacy["phase"] = "UNKNOWN"
        legacy["freeze_active"] = True
        legacy["human_gate_required"] = True
        self.assertEqual(evaluate(legacy).reason, "human_gate_required")
        legacy["phase"] = "construccion"
        self.assertEqual(evaluate(legacy).reason, "invalid_snapshot")

        for field, index, attribute, payload in (
            ("required_checks", 0, "conclusion", ["failure"]),
            ("quality_evidence", 0, "source", ["sonarcloud"]),
            ("quality_findings", 0, "severity", ["critical"]),
            ("quality_findings", 0, "category", {"unexpected": "security"}),
        ):
            with self.subTest(field=field, attribute=attribute):
                bad = candidate()
                bad["quality_findings"] = [finding()]
                bad[field][index][attribute] = payload
                self.assertEqual(evaluate(bad).reason, "invalid_snapshot")

        for status in ("failure", "pending", "cancelled", "skipped"):
            with self.subTest(tests_status=status):
                bad = candidate()
                bad["required_checks"].append({
                    "name": "Tests de scripts",
                    "head_sha": HEAD,
                    "conclusion": status,
                })
                self.assertEqual(evaluate(bad).reason, "checks_not_green")

    def test_live_phase_restores_full_gates_and_no_auto_merge(self):
        bad = candidate()
        bad["phase"] = "live"
        bad["quality_debt_cleared_for_live"] = True
        self.assertFalse(evaluate(bad).eligible)
        bad["phase"] = "UNKNOWN"
        self.assertFalse(evaluate(bad).eligible)

    def test_quality_debt_must_be_cleared_before_go_live(self):
        s = candidate()
        self.assertFalse(s["quality_debt_cleared_for_live"])
        self.assertTrue(evaluate(s).eligible)
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        doc = (ROOT / "docs" / "automerge-construccion.md").read_text(encoding="utf-8")
        for text in (plan, doc):
            self.assertIn("deuda", text.lower())
            self.assertIn("go-live", text.lower())
        bad = copy.deepcopy(s)
        bad["quality_debt_cleared_for_live"] = None
        self.assertEqual(evaluate(bad).reason, "invalid_snapshot")


if __name__ == "__main__":
    unittest.main()
