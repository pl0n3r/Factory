"""Regresiones offline del recolector REST de reservas V3."""
import copy
import json
import unittest
from datetime import datetime, timezone

from scripts.lease_activity_collector import collect_activity

REPO = "pl0n3r/Factory"
SHA = "a" * 40
NOW = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)


def marker():
    payload = {
        "version": 3, "active": True, "owner": "pl0n3r",
        "branch": "trabajo/issue-21", "reason": "tomar",
        "reservation_id": "e33f1859-0304-4fa8-8ce3-776de22c9707",
        "acceptance_sha256": "c" * 64, "task_marker_sha256": "d" * 64,
        "task_paths": ["scripts/example.py"], "task_depends_on": [],
    }
    return "<!-- condor-reserva " + json.dumps(payload) + " -->"


class API:
    repo = REPO

    def __init__(self):
        self.calls = []
        self.block = ""
        self.race = False
        self.ref_reads = 0
        self.issue = {
            "number": 21, "state": "open", "comments": 2,
            "updated_at": "2026-10-11T09:45:00Z",
            "labels": [{"name": "estado: reservado"}],
        }
        self.comments = [
            {"id": 1, "user": {"login": "github-actions[bot]"},
             "body": marker(), "created_at": "2026-10-11T08:00:00Z"},
            {"id": 2, "user": {"login": "other"},
             "body": "noise", "created_at": "2026-10-11T09:59:00Z"},
        ]
        self.commits = [
            {"sha": "b" * 40, "author": {"login": "pl0n3r"},
             "commit": {"author": {"date": "2026-10-11T09:10:00Z"}}},
        ]
        self.pulls = [
            {"id": 4, "number": 35, "head": {
                "ref": "trabajo/issue-21", "sha": SHA,
            }},
        ]
        self.reviews = [
            {"id": 5, "user": {"login": "pl0n3r"},
             "state": "COMMENTED", "submitted_at": "2026-10-11T09:25:00Z"},
        ]
        self.checks = [
            {"id": 6, "head_sha": SHA, "status": "in_progress"},
        ]

    def request(self, method, path):
        assert method == "GET", "read-only collector"
        self.calls.append(path)
        if self.block and self.block in path:
            raise RuntimeError("private-token-should-not-leak")
        if path == "/rate_limit":
            return {"resources": {"core": {"limit": 100, "remaining": 80}}}
        if path == f"/repos/{REPO}/issues/21":
            return copy.deepcopy(self.issue)
        if path.endswith("/git/ref/heads/trabajo/issue-21"):
            self.ref_reads += 1
            return {"object": {"sha": "b" * 40 if self.race and self.ref_reads > 1 else SHA}}
        page = int(path.rsplit("page=", 1)[-1])
        if "/issues/21/comments?" in path:
            return copy.deepcopy(self.comments) if page == 1 else []
        if "/commits?sha=" in path:
            return copy.deepcopy(self.commits) if page == 1 else []
        if "/pulls?state=open" in path:
            return copy.deepcopy(self.pulls) if page == 1 else []
        if "/pulls/35/reviews?" in path:
            return copy.deepcopy(self.reviews) if page == 1 else []
        if "/check-runs?" in path:
            return {"total_count": len(self.checks),
                    "check_runs": copy.deepcopy(self.checks) if page == 1 else []}
        raise AssertionError("unexpected GET")


class LeaseActivityCollectorTests(unittest.TestCase):
    def test_complete_authenticated_snapshots_track_owner_activity(self):
        api = API()
        result = collect_activity(api, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(result["status"], "estado: reservado")
        self.assertEqual(result["last_activity_at"], "2026-10-11T09:25:00Z")
        self.assertEqual(result["branch_sha"], SHA)
        self.assertTrue(result["ci_running"])
        self.assertEqual(result["rate_remaining"], 80)
        self.assertTrue(all("secret" not in str(x).lower() for x in result.values()))
        self.assertTrue(all(isinstance(p, str) for p in api.calls))

    def test_api_403_truncated_pages_and_untrusted_identity_fail_closed(self):
        cases = []
        a = API(); a.block = "/issues/21/comments"; cases.append(a)
        a = API(); a.issue["comments"] = 3; cases.append(a)
        a = API(); a.pulls[0]["head"]["sha"] = "b" * 40; cases.append(a)
        a = API(); a.race = True; cases.append(a)
        a = API(); a.checks.append(copy.deepcopy(a.checks[0])); cases.append(a)
        a = API(); a.comments[0]["body"] = "<!-- condor-reserva SECRET -->"; cases.append(a)
        a = API(); a.issue["labels"].append({"name": "estado: en revisión"}); cases.append(a)
        for case in cases:
            with self.subTest(case=cases.index(case)):
                self.assertEqual(
                    collect_activity(case, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )

    def test_only_verified_owner_activity_and_active_checks_extend_window(self):
        api = API()
        api.commits[0]["author"]["login"] = "other"
        api.reviews[0]["user"]["login"] = "other"
        out = collect_activity(api, 21, now=NOW)
        self.assertEqual(out["last_activity_at"], "2026-10-11T08:00:00Z")
        self.assertTrue(out["ci_running"])  # protege, sin atribuirlo al titular
        api.comments[1]["user"]["login"] = "pl0n3r"
        out = collect_activity(api, 21, now=NOW)
        self.assertEqual(out["last_activity_at"], "2026-10-11T09:59:00Z")
        api.checks[0]["status"] = "completed"
        out = collect_activity(api, 21, now=NOW)
        self.assertFalse(out["ci_running"])


if __name__ == "__main__":
    unittest.main()
