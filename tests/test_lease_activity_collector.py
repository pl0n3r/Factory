"""Regresiones offline del recolector REST de reservas V3."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone, tzinfo

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
        self.issue_reads = 0
        self.change_assignees_on_recheck = False
        self.remaining = 80
        self.repo_id = 123
        self.issue = {
            "number": 21, "state": "open", "comments": 2,
            "updated_at": "2026-10-11T09:45:00Z",
            "labels": [{"name": "estado: reservado"}],
            "assignees": [{"login": "pl0n3r"}],
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
        # An authenticated push-triggered Actions run is a bounded,
        # positive witness of branch activity, not a complete push audit.
        self.push_event = "push"
        self.push_created_at = "2026-10-11T09:40:00Z"
        self.push_head_sha = SHA
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
            self.issue_reads += 1
            observed = copy.deepcopy(self.issue)
            if self.change_assignees_on_recheck and self.issue_reads == 2:
                observed["assignees"] = [{"login": "other"}]
            return observed
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
                "id": 8, "head_sha": self.push_head_sha,
                "head_branch": "trabajo/issue-21",
                "head_repository": {"id": 123, "full_name": REPO},
                "event": self.push_event,
                "created_at": self.push_created_at,
                "status": self.checks[0]["status"],
            }
            runs = [current] + self.extra_runs
            total = (self.runs_count_override if self.runs_count_override is not None
                     else len(runs))
            return {"total_count": total,
                    "workflow_runs": copy.deepcopy(runs) if page == 1 else []}
        raise AssertionError("unexpected GET")


class LeaseActivityCollectorTests(unittest.TestCase):
    def test_activity_source_is_attributed_to_marker_or_exact_sha_push(self):
        """Sólo dos fuentes autenticadas, con empate temporal fail-closed."""
        via_push = API()
        reported = collect_activity(via_push, 21, now=NOW)
        self.assertTrue(reported["evidence_complete"])
        self.assertEqual(reported["activity_source"], "workflow_push")
        self.assertEqual(reported["last_activity_at"], "2026-10-11T09:40:00Z")

        via_marker = API()
        via_marker.comments[0]["updated_at"] = "2026-10-11T09:55:00Z"
        reported = collect_activity(via_marker, 21, now=NOW)
        self.assertTrue(reported["evidence_complete"])
        self.assertEqual(reported["activity_source"], "reservation_marker")
        self.assertEqual(reported["last_activity_at"], "2026-10-11T09:55:00Z")

        collision = API()
        collision.comments[0]["updated_at"] = "2026-10-11T09:40:00Z"
        self.assertEqual(
            collect_activity(collision, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        unverified = API()
        unverified.push_event = "pull_request"
        self.assertEqual(
            collect_activity(unverified, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )

    def test_old_marker_with_authenticated_running_ci_is_veto_only(self):
        """Un CI vivo puede impedir release sin demostrar inactividad."""
        api = API()
        api.push_event = "pull_request"  # no push-run reciente verificable
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        observed = collect_activity(
            api, 21, now=NOW, allow_ci_veto_only=True)
        self.assertTrue(observed["evidence_complete"])
        self.assertTrue(observed["ci_running"])
        self.assertTrue(observed["ci_veto_only"])
        self.assertEqual(observed["activity_source"], "reservation_marker")
        self.assertEqual(observed["last_activity_at"], "2026-10-11T08:00:00Z")
        self.assertTrue(all(path.startswith("/repos/") or path == "/rate_limit"
                            for path in api.calls))
        api.checks[0]["status"] = "completed"
        self.assertEqual(
            collect_activity(api, 21, now=NOW, allow_ci_veto_only=True),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        tampered = API()
        tampered.push_event = "pull_request"
        tampered.change_assignees_on_recheck = True
        self.assertEqual(
            collect_activity(tampered, 21, now=NOW, allow_ci_veto_only=True),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        race = API()
        race.push_event = "pull_request"
        race.restart_check_during_recheck = True
        # La carrera no puede certificar un veto estable ni inactividad.
        race.checks[0]["status"] = "completed"
        self.assertEqual(
            collect_activity(race, 21, now=NOW, allow_ci_veto_only=True),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        self.assertEqual(
            collect_activity(API(), 21, now=NOW,
                             allow_ci_veto_only="yes"),
            {"status": "UNKNOWN", "evidence_complete": False},
        )

    def test_old_authored_commit_recent_push_is_unknown_without_provenance(self):
        # A commit authored before the lease can be pushed moments ago.
        api = API()
        api.commits[0]["commit"]["author"]["date"] = "2026-10-11T07:00:00Z"
        api.push_event = "pull_request"
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        # A current-SHA push run proves recent activity, not the author date.
        api.push_event = "push"
        observed = collect_activity(api, 21, now=NOW)
        self.assertTrue(observed["evidence_complete"])
        self.assertEqual(observed["last_activity_at"], "2026-10-11T09:40:00Z")
        self.assertTrue(all("secret" not in str(v).lower()
                            for v in observed.values()))

    def test_branch_push_provenance_missing_or_racy_fails_closed(self):
        # No push-run evidence means we cannot prove the *absence* of a push.
        for event, stamp, head in (
            ("pull_request", "2026-10-11T09:40:00Z", SHA),
            ("workflow_dispatch", "2026-10-11T09:40:00Z", SHA),
            (None, "2026-10-11T09:40:00Z", SHA),
            ("push", None, SHA),
            ("push", "2026-10-11T09:30:00Z", SHA),
            ("push", "2026-10-11T09:29:59Z", SHA),
            ("push", "2026-10-11T10:00:01Z", SHA),
            ("push", "not-an-utc-clock", SHA),
            ("push", "2026-10-11T09:40:00Z", "b" * 40),
        ):
            with self.subTest(event=event, stamp=stamp, head=head):
                api = API()
                api.push_event = event
                api.push_created_at = stamp
                api.push_head_sha = head
                self.assertEqual(
                    collect_activity(api, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )
        api = API()
        api.commits = []  # /commits?since can hide late-pushed old commits.
        api.push_event = "pull_request"
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        api = API()
        api.race = True
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )

    def test_proven_owner_activity_and_existing_guards_preserved(self):
        api = API()
        observed = collect_activity(api, 21, now=NOW)
        self.assertTrue(observed["evidence_complete"])
        self.assertEqual(observed["repository_id"], 123)
        self.assertEqual(observed["owner"], "pl0n3r")
        self.assertEqual(observed["last_activity_at"], "2026-10-11T09:40:00Z")
        self.assertTrue(observed["ci_running"])
        self.assertTrue(all("/repos/" in p or p == "/rate_limit"
                            for p in api.calls))
        # A recently revalidated bot lease also cannot expire; it is not
        # evidence of an owner push and must not be attributed to one.
        api = API()
        api.push_event = "pull_request"
        api.comments[0]["updated_at"] = "2026-10-11T09:50:00Z"
        api.issue["updated_at"] = "2026-10-11T09:50:00Z"
        result = collect_activity(api, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(result["last_activity_at"], "2026-10-11T09:50:00Z")
        # Fresh fake: the first two reads above already consumed the
        # recheck counter; reuse would not trigger a deterministic race.
        race = API()
        race.change_assignees_on_recheck = True
        self.assertEqual(
            collect_activity(race, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )

    def test_external_changes_requested_fail_closed(self):
        # An authenticated third-party review is a veto, not owner activity.
        # The Fake API raises if a non-GET operation is attempted.
        for reviewer in ("other", "pl0n3r"):
            with self.subTest(reviewer=reviewer):
                api = API()
                api.reviews = [{
                    "id": 12, "user": {"login": reviewer},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2026-10-11T09:25:00Z",
                }]
                self.assertEqual(
                    collect_activity(api, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )
                self.assertTrue(any("/pulls/35/reviews?" in p for p in api.calls))

    def test_dismissed_and_approved_reviews_are_not_change_requests(self):
        # Recognized non-blocking external review states remain compatible.
        for state in ("APPROVED", "DISMISSED", "COMMENTED", "PENDING"):
            with self.subTest(state=state):
                api = API()
                api.reviews = [{
                    "id": 12, "user": {"login": "other"},
                    "state": state, "submitted_at": "2026-10-11T09:25:00Z",
                }]
                self.assertTrue(collect_activity(api, 21, now=NOW)["evidence_complete"])
        for state in ("INVALID", None, "", 7):
            with self.subTest(invalid_state=state):
                api = API()
                api.reviews = [{
                    "id": 12, "user": {"login": "other"},
                    "state": state, "submitted_at": "2026-10-11T09:25:00Z",
                }]
                self.assertEqual(
                    collect_activity(api, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )

    def test_unverifiable_now_timezone_fails_closed(self):
        """No inferir la zona local del runner para decidir inactividad V3."""
        class UndefinedOffset(tzinfo):
            def utcoffset(self, dt):
                return None

            def dst(self, dt):
                return None

        class ExplodingOffset(UndefinedOffset):
            def utcoffset(self, dt):
                raise RuntimeError("unverifiable UTC offset")

        for invalid_clock in (
            NOW.replace(tzinfo=None),
            NOW.replace(tzinfo=UndefinedOffset()),
            NOW.replace(tzinfo=ExplodingOffset()),
        ):
            with self.subTest(clock=type(invalid_clock.tzinfo).__name__):
                api = API()
                self.assertEqual(
                    collect_activity(api, 21, now=invalid_clock),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )
                self.assertEqual(api.calls, [])

    def test_valid_timezone_now_preserves_snapshot(self):
        """Offsets auténticos representan el mismo instante UTC."""
        baseline = collect_activity(API(), 21, now=NOW)
        self.assertTrue(baseline["evidence_complete"])
        for offset in (timedelta(hours=-5), timedelta(hours=5, minutes=30)):
            with self.subTest(offset=offset):
                api = API()
                observed = collect_activity(
                    api, 21, now=NOW.astimezone(timezone(offset)))
                self.assertEqual(observed, baseline)
                self.assertGreater(len(api.calls), 0)

    def test_assignee_authority_requires_exactly_one_owner(self):
        good = collect_activity(API(), 21, now=NOW)
        self.assertTrue(good["evidence_complete"])
        cases = (
            [],
            [{"login": "other"}],
            [{"login": "pl0n3r"}, {"login": "other"}],
            [{"login": 123}],
            [{"user": "pl0n3r"}],
            [None],
            "pl0n3r",
        )
        for assignees in cases:
            with self.subTest(assignees=assignees):
                api = API()
                api.issue["assignees"] = assignees
                self.assertEqual(
                    collect_activity(api, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )
        missing = API()
        missing.issue.pop("assignees")
        self.assertEqual(
            collect_activity(missing, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )

    def test_assignee_authority_race_fails_closed(self):
        api = API()
        api.change_assignees_on_recheck = True
        self.assertEqual(
            collect_activity(api, 21, now=NOW),
            {"status": "UNKNOWN", "evidence_complete": False},
        )
        self.assertEqual(api.issue_reads, 2)

    def test_complete_authenticated_snapshots_track_owner_activity(self):
        api = API()
        result = collect_activity(api, 21, now=NOW)
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(result["status"], "estado: reservado")
        self.assertEqual(result["last_activity_at"], "2026-10-11T09:40:00Z")
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

    def test_check_run_statuses_match_github_rest_contract(self):
        for status in ("queued", "in_progress", "requested", "waiting", "pending", "completed"):
            with self.subTest(status=status):
                api = API()
                api.checks[0]["status"] = status
                observed = collect_activity(api, 21, now=NOW)
                self.assertTrue(observed["evidence_complete"])
                self.assertEqual(observed["ci_running"], status != "completed")
        invalid = API()
        invalid.checks[0]["status"] = "broken"
        self.assertEqual(
            collect_activity(invalid, 21, now=NOW),
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

    def test_prelease_owner_comment_edit_is_not_silent_inactivity(self):
        """Una edición nueva de comentario viejo no acredita ausencia de trabajo."""
        api = API()
        old_owner_comment = {
            "id": 0, "user": {"login": "pl0n3r", "type": "User"},
            "body": "Comentario anterior a esta reserva",
            "created_at": "2026-10-11T07:00:00Z",
            "updated_at": "2026-10-11T07:30:00Z",
        }
        # Preserve API cursor ordering: IDs must be positive and increasing.
        api.comments[0]["id"] = 2  # reserva de bot
        api.comments[1]["id"] = 3  # comentario ajeno
        old_owner_comment["id"] = 1
        api.comments.insert(0, old_owner_comment)
        api.issue["comments"] = len(api.comments)
        # Sin edición posterior al marker, un comentario antiguo no basta
        # por sí mismo para vetar una observación positiva de push reciente.
        baseline = collect_activity(api, 21, now=NOW)
        self.assertTrue(baseline["evidence_complete"])
        self.assertEqual(baseline["activity_source"], "workflow_push")

        for edited in ("2026-10-11T09:59:00Z", None,
                       "invalid-date", "2026-10-11T06:00:00Z",
                       "2026-10-11T10:01:00Z"):
            with self.subTest(updated_at=edited):
                trial = copy.deepcopy(api)
                if edited is None:
                    trial.comments[0].pop("updated_at")
                else:
                    trial.comments[0]["updated_at"] = edited
                trial.issue["updated_at"] = "2026-10-11T09:59:00Z"
                self.assertEqual(
                    collect_activity(trial, 21, now=NOW),
                    {"status": "UNKNOWN", "evidence_complete": False},
                )
                self.assertTrue(all(path == "/rate_limit" or path.startswith("/repos/")
                                    for path in trial.calls))

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
        self.assertEqual(out["last_activity_at"], "2026-10-11T09:40:00Z")
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
