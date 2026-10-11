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
        self.remaining = 80
        self.repo_id = 123
        self.issue = {
            "number": 21, "state": "open", "comments": 2,
            "updated_at": "2026-10-11T09:45:00Z",
            "labels": [{"name": "estado: reservado"}],
        }
        self.comments = [
            {"id": 1, "user": {"login": "github-actions[bot]", "type": "Bot"},
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
                "repo": {"full_name": REPO, "id": 123},
            }},
        ]
        self.reviews = [
            {"id": 5, "user": {"login": "other"},
             "state": "COMMENTED", "submitted_at": "2026-10-11T09:25:00Z"},
        ]
        self.checks = [
            {"id": 6, "head_sha": SHA, "status": "in_progress"},
        ]
        self.extra_runs = []
        self.runs_count_override = None
        self.extra_pull_page = []
        self.check_reads = 0
        self.run_reads = 0
        self.restart_check_during_recheck = False
        self.start_run_during_recheck = False

    def request(self, method, path):
        assert method == "GET", "read-only collector"
        self.calls.append(path)
        if self.block and self.block in path:
            raise RuntimeError("private-token-should-not-leak")
        if path == "/rate_limit":
            return {"resources": {"core": {"limit": 100, "remaining": self.remaining}}}
        if path == f"/repos/{REPO}":
            return {"id": self.repo_id, "full_name": REPO}
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
            return (copy.deepcopy(self.pulls) if page == 1
                    else copy.deepcopy(self.extra_pull_page) if page == 2 else [])
        if "/pulls/35/reviews?" in path:
            return copy.deepcopy(self.reviews) if page == 1 else []
        if "/check-runs?" in path:
            self.check_reads += 1
            if self.restart_check_during_recheck and self.check_reads == 2:
                self.checks[0]["status"] = "in_progress"
            return {"total_count": len(self.checks),
                    "check_runs": copy.deepcopy(self.checks) if page == 1 else []}
        if "/actions/runs?branch=" in path:
            self.run_reads += 1
            if self.start_run_during_recheck and self.run_reads == 2:
                self.extra_runs.append({
                    "id": 45, "head_sha": SHA,
                    "head_branch": "trabajo/issue-21",
                    "head_repository": {"id": 123, "full_name": REPO},
                    "status": "in_progress",
                })
            current = {
                "id": 8, "head_sha": SHA,
                "head_branch": "trabajo/issue-21",
                "head_repository": {"id": 123, "full_name": REPO},
                "status": self.checks[0]["status"],
            }
            runs = [current] + self.extra_runs
            total = (self.runs_count_override if self.runs_count_override is not None
                     else len(runs))
            return {"total_count": total,
                    "workflow_runs": copy.deepcopy(runs) if page == 1 else []}
        raise AssertionError("unexpected GET")


class LeaseActivityCollectorTests(unittest.TestCase):
    def test_complete_authenticated_snapshots_track_owner_activity(self):
        api = API()
        result = collect_activity(api, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(result["status"], "estado: reservado")
        self.assertEqual(result["last_activity_at"], "2026-10-11T09:10:00Z")
        self.assertEqual(result["branch_sha"], SHA)
        self.assertEqual(result["branch"], "trabajo/issue-21")
        self.assertEqual(result["repository_id"], 123)
        self.assertEqual(result["pagination"], {
            "comments": {"pages": 1, "items": 2},
            "commits": {"pages": 2, "items": 1},
            "pulls": {"pages": 2, "items": 1},
            "reviews": {"pages": 2, "items": 1},
            "checks": {"pages": 1, "items": 1},
            "runs": {"pages": 1, "items": 1},
            "checks_recheck": {"pages": 1, "items": 1},
            "runs_recheck": {"pages": 1, "items": 1},
        })
        api.issue["labels"].append({"name": "prioridad: crítica"})
        self.assertTrue(collect_activity(api, 21, now=NOW)["evidence_complete"])
        self.assertTrue(result["ci_running"])
        self.assertEqual(result["rate_remaining"], 63)
        self.assertEqual(result["api_requests"], 17)
        self.assertTrue(all("secret" not in str(x).lower() for x in result.values()))
        self.assertTrue(all(isinstance(p, str) for p in api.calls))

    def test_api_403_truncated_pages_and_untrusted_identity_fail_closed(self):
        cases = []
        a = API(); a.block = "/issues/21/comments"; cases.append(a)
        a = API(); a.remaining = 29; cases.append(a)
        a = API(); a.issue["comments"] = 3; cases.append(a)
        a = API(); a.pulls[0]["head"]["sha"] = "b" * 40; cases.append(a)
        a = API(); a.pulls[0]["head"]["repo"] = None; cases.append(a)
        a = API(); a.pulls[0]["head"]["repo"]["id"] = 999; cases.append(a)
        a = API(); a.pulls[0]["head"]["repo"]["full_name"] = "other/fork"; cases.append(a)
        a = API(); a.repo_id = None; cases.append(a)
        a = API(); a.runs_count_override = 2; cases.append(a)
        a = API(); a.extra_runs = [{"id": 9, "head_sha": "c" * 40,
            "head_branch": "trabajo/issue-21", "head_repository": None,
            "status": "in_progress"}]; cases.append(a)
        a = API(); a.extra_pull_page = [{"id": 99}]; cases.append(a)
        a = API(); a.race = True; cases.append(a)
        a = API(); a.checks.append(copy.deepcopy(a.checks[0])); cases.append(a)
        a = API(); a.comments[0]["body"] = "<!-- condor-reserva SECRET -->"; cases.append(a)
        a = API(); a.comments[0]["user"]["type"] = "User"; cases.append(a)
        a = API(); a.comments[0]["user"].pop("type"); cases.append(a)
        a = API(); a.comments[0]["user"]["type"] = "Organization"; cases.append(a)
        a = API(); a.comments[0]["user"]["type"] = None; cases.append(a)
        a = API(); a.comments[0]["updated_at"] = "2026-10-11T07:00:00Z"; cases.append(a)
        a = API(); a.comments[0]["updated_at"] = "2026-10-11T10:01:00Z"; cases.append(a)
        a = API(); a.comments[0]["updated_at"] = "not-a-date"; cases.append(a)
        a = API(); a.issue["labels"].append({"name": "estado: en revisión"}); cases.append(a)
        a = API(); a.comments[1]["user"] = None; cases.append(a)
        a = API(); a.commits[0]["author"] = None; cases.append(a)
        a = API(); a.reviews[0]["user"] = None; cases.append(a)
        for state in ("estado: bloqueado", "estado: disponible", "estado: completado",
                      "ESTADO: bloqueado"):
            a = API(); a.issue["labels"].append({"name": state}); cases.append(a)
        for case in cases:
            with self.subTest(case=cases.index(case)):
                self.assertEqual(
                    collect_activity(case, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )

    def test_restarted_ci_on_same_sha_during_recheck_fails_closed(self):
        for kind in ("check", "run"):
            with self.subTest(kind=kind):
                api = API()
                api.checks[0]["status"] = "completed"
                if kind == "check":
                    api.restart_check_during_recheck = True
                else:
                    api.start_run_during_recheck = True
                self.assertEqual(
                    collect_activity(api, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )
        stable = API()
        stable.checks[0]["status"] = "completed"
        result = collect_activity(stable, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertFalse(result["ci_running"])

    def test_ci_in_progress_on_previous_sha_remains_protected(self):
        api = API()
        api.checks[0]["status"] = "completed"
        earlier = {"id": 9, "head_sha": "b" * 40,
                   "head_branch": "trabajo/issue-21",
                   "head_repository": {"id": 123, "full_name": REPO},
                   "status": "in_progress"}
        api.extra_runs = [earlier]
        observed = collect_activity(api, 21, now=NOW)
        self.assertTrue(observed["evidence_complete"])
        self.assertTrue(observed["ci_running"])
        self.assertEqual(observed["pagination"]["runs"]["items"], 2)
        api.extra_runs[0]["status"] = "completed"
        terminal = collect_activity(api, 21, now=NOW)
        self.assertTrue(terminal["evidence_complete"])
        self.assertFalse(terminal["ci_running"])

    def test_shared_login_qa_comment_is_not_verified_session_activity(self):
        api = API()
        api.comments[1]["user"]["login"] = "pl0n3r"
        api.comments[1]["body"] = "QA de otra hoja; no soy titular V3"
        api.commits[0]["author"]["login"] = "other"
        api.checks[0]["status"] = "completed"
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )

    def test_same_branch_name_from_foreign_fork_is_ignored(self):
        api = API()
        foreign = copy.deepcopy(api.pulls[0])
        foreign["id"], foreign["number"] = 7, 37
        foreign["head"]["repo"] = {"full_name": "other/fork", "id": 999}
        foreign["head"]["sha"] = "c" * 40
        api.pulls.append(foreign)
        result = collect_activity(api, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(result["branch_sha"], SHA)
        self.assertEqual(result["pagination"]["pulls"]["items"], 2)

    def test_edited_reservation_marker_updates_activity_clock(self):
        api = API()
        api.comments[0]["updated_at"] = "2026-10-11T09:50:00Z"
        api.issue["updated_at"] = "2026-10-11T09:50:00Z"
        api.checks[0]["status"] = "completed"
        result = collect_activity(api, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(result["last_activity_at"], "2026-10-11T09:50:00Z")

    def test_only_verified_owner_activity_and_active_checks_extend_window(self):
        api = API()
        api.commits[0]["author"]["login"] = "other"
        api.reviews[0]["user"]["login"] = "other"
        out = collect_activity(api, 21, now=NOW)
        self.assertEqual(out["last_activity_at"], "2026-10-11T08:00:00Z")
        self.assertTrue(out["ci_running"])  # protege, sin atribuirlo al titular
        api.comments[1]["user"]["login"] = "pl0n3r"
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        api.comments[1]["user"]["login"] = "other"
        api.reviews[0]["user"]["login"] = "pl0n3r"
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        api.reviews[0]["user"]["login"] = "other"
        api.checks[0]["status"] = "completed"
        out = collect_activity(api, 21, now=NOW)
        self.assertFalse(out["ci_running"])


if __name__ == "__main__":
    unittest.main()
