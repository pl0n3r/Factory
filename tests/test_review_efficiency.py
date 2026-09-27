import json
import unittest
from pathlib import Path
from evolution.constitution import PROTECTED_INVARIANTS
from metricas.review_efficiency import FINDING_CLASSES, ReviewEfficiencyError, STABLE_REVIEW_ROUND_LIMIT, build_report, build_shadow_candidate, is_substantive_review, validate_observation
from scripts.politica_kit import load_policy
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "metricas/datos/review-efficiency-baseline.jsonl"
def finding(fid="f1", classification="valid_fixed", severity="medium", material=True, change_ref="commit:abc"):
    return {"id": fid, "classification": classification, "severity": severity, "material": material, "change_ref": change_ref}
def observation(**overrides):
    row = {"repo": "pl0n3r/factory", "pr": 900, "issue": 901, "sha": "a" * 40, "task_type": "quality", "surface": "ci", "risk": "low", "provider": "coderabbit", "review_state": "COMMENTED", "round": 1, "findings": [finding()], "rework_commits": 1, "added_minutes": 10, "tokens": 100, "ci_minutes": 5, "escaped_defect": False, "incident_after": False, "rollback_after": False, "result_ref": "result:green"}
    row.update(overrides)
    return row
def protected(value=1.0):
    return {name: value for name in PROTECTED_INVARIANTS}
def sample():
    rows = []
    for pr in (1, 2, 3):
        for number, cost in ((1, 8), (2, 5), (3, 3)):
            rows.append(observation(pr=pr, issue=100 + pr, sha=hex(pr * 100 + number)[2:].zfill(40), round=number, rework_commits=cost, added_minutes=cost * 2, tokens=cost * 100, ci_minutes=cost, findings=[finding(fid=f"f{pr}{number}", classification="valid_fixed" if number < 3 else "valid_no_change", severity="low", material=number < 3, change_ref=f"commit:{pr}{number}")], result_ref=f"result:factory-{pr}"))
    rows.append(observation(repo="pl0n3r/GrindFlow", pr=10, issue=11, sha="f" * 40, task_type="security", surface="auth", risk="high", result_ref="result:consumer"))
    return rows
def fixture():
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
class ReviewEfficiencyTests(unittest.TestCase):
    def test_administrative_reviews_do_not_count_as_substantive_rounds(self):
        self.assertFalse(is_substantive_review(observation(findings=[])))
        self.assertTrue(is_substantive_review(observation()))
        self.assertTrue(is_substantive_review(observation(findings=[], review_state="APPROVED")))
    def test_finding_taxonomy_is_closed_and_unknown_stays_explicit(self):
        row = validate_observation(observation(findings=[finding(classification="unknown", severity="none", material=False, change_ref=None)]))
        self.assertEqual(row["findings"][0]["classification"], "unknown")
        self.assertIn("unknown", FINDING_CLASSES)
        with self.assertRaisesRegex(ReviewEfficiencyError, "classification"):
            validate_observation(observation(findings=[finding(classification="maybe")]))
    def test_report_keeps_value_and_cost_dimensions_separate(self):
        report = build_report([observation()], min_samples=1)
        self.assertEqual(set(report["cohorts"][0]["rounds"]["1"]), {"quality", "cost", "risk", "noise"})
        self.assertNotIn("score", json.dumps(report).lower())
    def test_incompatible_cohorts_are_not_merged(self):
        report = build_report([observation(pr=1, risk="low", provider="coderabbit"), observation(pr=2, risk="high", provider="codeql")], min_samples=1)
        self.assertEqual({(c["key"]["risk"], c["key"]["provider"]) for c in report["cohorts"]}, {("low", "coderabbit"), ("high", "codeql")})
    def test_insufficient_sample_yields_no_policy_recommendation(self):
        report = build_report(fixture(), min_samples=3)
        self.assertTrue(report["baseline_reproducible"])
        self.assertTrue(all(c["sample_status"] == "insufficient_data" and c["policy_recommendation"] is None for c in report["cohorts"]))
    def test_protected_regression_blocks_round_reduction_candidate(self):
        report = build_report(sample(), min_samples=3)
        key = next(c["key"] for c in report["cohorts"] if c["key"]["repo"] == "pl0n3r/factory")
        degraded = protected(); degraded["security"] = 0.5
        result = build_shadow_candidate(report=report, cohort_key=key, stable_sha="1" * 40, candidate_sha="2" * 40, protected_stable=protected(), protected_candidate=degraded)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("security", result["lab"]["fitness"]["protected_regressions"])
    def test_baseline_requires_factory_and_consumer_evidence(self):
        rows = fixture()
        self.assertTrue(build_report(rows)["baseline_reproducible"])
        self.assertFalse(build_report([r for r in rows if r["repo"].lower() == "pl0n3r/factory"])["baseline_reproducible"])
        self.assertFalse(build_report([r for r in rows if r["repo"].lower() != "pl0n3r/factory"])["baseline_reproducible"])
    def test_shadow_candidate_never_changes_stable_policy(self):
        report = build_report(sample(), min_samples=3)
        key = next(c["key"] for c in report["cohorts"] if c["key"]["repo"] == "pl0n3r/factory")
        result = build_shadow_candidate(report=report, cohort_key=key, stable_sha="3" * 40, candidate_sha="4" * 40, protected_stable=protected(), protected_candidate=protected())
        self.assertEqual(result["status"], "shadow_candidate")
        self.assertFalse(result["mutation_allowed"])
        self.assertEqual(result["external_writes"], [])
        self.assertEqual(result["lab"]["promotion"]["execution"], "not-performed")
    def test_lineage_preserves_pr_round_finding_change_result(self):
        report = build_report([observation(repo="pl0n3r/factory", pr=253, issue=252, round=2, findings=[finding(fid="security-fix", change_ref="commit:265ca2cb")], result_ref="main:34409905")], min_samples=1)
        link = report["cohorts"][0]["lineage"][0]
        self.assertEqual((link["pr"], link["round"], link["finding"], link["change"], link["result"]), ("pl0n3r/factory#253", 2, "security-fix", "commit:265ca2cb", "main:34409905"))
    def test_stable_review_round_limit_remains_three(self):
        self.assertEqual(load_policy(root=ROOT)["review_round_limit"], 3)
        self.assertEqual(STABLE_REVIEW_ROUND_LIMIT, 3)
if __name__ == "__main__":
    unittest.main()
