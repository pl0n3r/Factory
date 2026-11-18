"""Pruebas sintéticas y reversibles de auditoría fail-closed."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from scripts.audit_integral_checkpoint import build, main
from scripts.work_inventory import CANONICAL_REPOSITORIES
NOW = "2026-11-18T01:00:00Z"
SHA = "a" * 40
REF = "https://github.com/pl0n3r/Factory/issues/2157"
def leaf(issue=2157):
    return {
        "issue": issue, "state": "completed", "required_ac": ["AC-01"],
        "acceptance": [{"id": "AC-01", "status": "passed", "ref": REF}],
        "depends_on": [], "claims": ["scripts/audit_integral_checkpoint.py"], "ref": REF,
        "pr": {"number": 2200, "state": "merged", "sha": SHA,
               "ref": "https://github.com/pl0n3r/Factory/pull/2200"},
        "qa": {"status": "success", "sha": SHA, "observed_at": NOW,
               "ref": "https://github.com/pl0n3r/Factory/actions/runs/1"},
        "production": {"state": "VALIDATED_IN_PRODUCTION", "sha": SHA, "observed_at": NOW,
                       "ref": REF, "pending": []},
    }
def fixture():
    repos = [{"repo": name, "sha": SHA, "observed_at": NOW,
              "ref": f"https://github.com/{name}/commit/{SHA}",
              "leaves": [], "incidents": []} for name in CANONICAL_REPOSITORIES]
    repos[0]["leaves"] = [leaf()]
    return {"version": 1, "as_of": NOW, "kill_switch": "RUNNING", "repositories": repos}
def issues(source):
    return build(source)["repositories"][0]["issues"]
class IntegralCheckpointTests(unittest.TestCase):
    def test_seven_repos_deterministic_positive(self):
        source = fixture()
        report = build(source)
        self.assertEqual([r["repo"] for r in report["repositories"]], list(CANONICAL_REPOSITORIES))
        self.assertEqual(issues(source)[0]["status"], "auditable")
        source["repositories"].reverse()
        self.assertEqual(report, build(source))
    def test_missing_duplicate_stale_sha_ref_all_fail_closed(self):
        cases = [
            (lambda f: f["repositories"][0]["leaves"][0].update(acceptance=[]), "acceptance_missing"),
            (lambda f: f["repositories"][0]["leaves"][0]["qa"].update(sha="b" * 40), "sha_mismatch"),
            (lambda f: f["repositories"][0]["leaves"][0].update(ref="https://bad/secret?token=PII"), "invalid_leaf"),
            (lambda f: f["repositories"][0]["leaves"][0]["qa"].update(observed_at="2026-11-10T01:00:00Z"), "evidence_stale"),
        ]
        for mutate, reason in cases:
            with self.subTest(reason=reason):
                source = fixture()
                mutate(source)
                self.assertEqual(issues(source)[0]["status"], "unknown")
                self.assertIn(reason, issues(source)[0]["reasons"])
                self.assertNotIn("PII", json.dumps(build(source)))
        source = fixture()
        source["repositories"][0]["leaves"].append(copy.deepcopy(source["repositories"][0]["leaves"][0]))
        self.assertEqual([x["status"] for x in issues(source)], ["unknown", "unknown"])
        source = fixture()
        source["repositories"][0]["observed_at"] = "2026-11-10T01:00:00Z"
        self.assertEqual(build(source)["repositories"][0]["status"], "unknown")
    def test_dependencies_cycles_and_claims_block(self):
        source = fixture()
        second = leaf(111)
        second["state"], second["pr"], second["claims"] = "available", None, ["docs/other.md"]
        source["repositories"][0]["leaves"].append(second)
        source["repositories"][0]["leaves"][0]["depends_on"] = ["pl0n3r/Factory#111"]
        self.assertIn("dependency_open", next(x for x in issues(source) if x["issue"] == 2157)["reasons"])
        second["state"], second["pr"] = "completed", leaf()["pr"]
        second["depends_on"] = ["pl0n3r/Factory#2157"]
        self.assertTrue(all("dependency_cycle" in x["reasons"] for x in issues(source)))
        second["depends_on"] = []
        second["state"], second["pr"], second["claims"] = "reserved", None, ["scripts/"]
        first = source["repositories"][0]["leaves"][0]
        first["depends_on"], first["state"], first["pr"] = [], "reserved", None
        self.assertTrue(all("claim_conflict" in x["reasons"] for x in issues(source)))
    def test_pending_production_incident_and_unknown_kill(self):
        source = fixture()
        prod = source["repositories"][0]["leaves"][0]["production"]
        prod.update(state="PENDING", pending=["smoke", "backup"])
        self.assertEqual(issues(source)[0]["status"], "blocked")
        self.assertEqual(issues(source)[0]["production"], "pending")
        source = fixture()
        source["repositories"][1]["incidents"].append({
            "issue": 903, "state": "open", "ref": "https://github.com/pl0n3r/GrindFlow/issues/903"})
        self.assertEqual(build(source)["repositories"][1]["status"], "blocked")
        source["kill_switch"] = "UNKNOWN"
        self.assertTrue(all(r["status"] == "unknown" for r in build(source)["repositories"]))
    def test_cli_is_read_only_and_redacts_bad_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fiction.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue())["repositories"][0]["status"], "auditable")
            self.assertEqual([x.name for x in Path(tmp).iterdir()], ["fiction.json"])
            path.write_text('{"token":"secret","user":"test@example.net"}', encoding="utf-8")
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([str(path)]), 2)
            self.assertNotIn("secret", output.getvalue())
            self.assertNotIn("example.net", output.getvalue())
if __name__ == "__main__":
    unittest.main()
