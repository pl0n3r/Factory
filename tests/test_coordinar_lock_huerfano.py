"""CAS-only recovery for a terminal orphaned Factory coordination lock."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import os
import unittest

from scripts import coordinar_trabajo as coordinator


ISSUE = 1946
LOCK = "a" * 40
PARENT = "b" * 40
DATE = datetime(2026, 10, 30, 16, 0, tzinfo=timezone.utc)
RUNNER = {
    "GITHUB_REPOSITORY": "pl0n3r/Factory",
    "GITHUB_EVENT_NAME": "issue_comment",
    "GITHUB_WORKFLOW_REF":
        "pl0n3r/Factory/.github/workflows/coordinacion-trabajo.yml@refs/heads/main",
    "GITHUB_RUN_ID": "12345",
}


class FakeApi:
    repo = "pl0n3r/Factory"

    def __init__(self):
        self.refs = {"coordinacion/lock-issue-1946": LOCK, "main": PARENT}
        self.record = {
            "sha": LOCK,
            "message": "lock coordinacion Issue #1946 "
                       "85773c47-d586-4860-a921-7053d23f9f4b",
            "author": {
                "name": "github-actions[bot]",
                "email": "41898282+github-actions[bot]@users.noreply.github.com",
                "date": "2026-10-30T14:27:10Z",
            },
            "committer": {
                "name": "GitHub",
                "email": "noreply@github.com",
                "date": "2026-10-30T14:27:10Z",
            },
            "verification": {"verified": True, "reason": "valid"},
            "tree": {"sha": "c" * 40},
            "parents": [{"sha": PARENT}],
        }
        self.issue_data = {
            "number": ISSUE, "state": "open", "body": "offline",
            "labels": [{"name": coordinator.STATUS_BLOCKED}],
        }
        self.comments = []
        self.releases = []
        self.parent_tree = "c" * 40

    def branch_sha(self, branch):
        return self.refs.get(branch)

    def issue(self, number):
        if number != ISSUE:
            raise AssertionError("unexpected Issue")
        return deepcopy(self.issue_data)

    def issue_comments(self, number):
        return deepcopy(self.comments)

    def request(self, method, path, payload=None, allow=()):
        if method != "GET":
            raise AssertionError("No direct mutation allowed")
        if path.endswith("/git/commits/" + LOCK):
            return deepcopy(self.record)
        if "/git/commits/" in path:
            return {"sha": path.rsplit("/", 1)[-1],
                    "tree": {"sha": self.parent_tree}}
        if "/compare/" in path:
            matched = (path.endswith("/compare/" + PARENT + "...main")
                       and self.refs["main"] == PARENT)
            return {"behind_by": 0 if matched else 1,
                    "status": "identical" if matched else "diverged"}
        raise AssertionError(f"unexpected REST path: {path}")

    def release_issue_lock(self, number, token):
        if number != ISSUE or token != self.refs.get(
            "coordinacion/lock-issue-1946"
        ):
            raise coordinator.CoordinationError("CAS race")
        self.releases.append((number, token))
        del self.refs["coordinacion/lock-issue-1946"]


class RecoveryLockTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()

    def check(self, api=None, token=LOCK, actor="pl0n3r",
              association="OWNER"):
        with patch.dict(os.environ, RUNNER, clear=True):
            with patch.object(coordinator, "require_global_running") as guard:
                result = coordinator.recover_orphaned_issue_lock(
                    api or self.api, ISSUE, actor, association, token, now=DATE,
                )
                self.assertGreaterEqual(guard.call_count, 2)
                return result

    def test_rechaza_lock_vigente_o_no_autorizado(self):
        cases = [
            ("actor", lambda a: setattr(a, "repo", "evil/fork")),
            ("bloqueo", lambda a: a.issue_data["labels"].clear()),
            ("estado", lambda a: a.issue_data.update(state="closed")),
            ("nonce", lambda a: a.record.update(message="another lock")),
            ("autor", lambda a: a.record["author"].update(name="other")),
            ("committer", lambda a: a.record["committer"].update(name="fake")),
            ("correo committer", lambda a: a.record["committer"].update(
                email="fake@example.test")),
            ("sin firma", lambda a: a.record.update(verification=None)),
            ("firma no válida", lambda a: a.record["verification"].update(
                verified=False)),
            ("razón firma", lambda a: a.record["verification"].update(
                reason="unsigned")),
            ("árbol alterado", lambda a: a.record["tree"].update(sha="d" * 40)),
            ("árbol de parent distinto", lambda a: setattr(
                a, "parent_tree", "d" * 40)),
            ("árbol ausente", lambda a: a.record.update(tree=None)),
            ("fecha", lambda a: a.record["author"].update(
                date="2026-10-30T15:30:00Z")),
            ("parent", lambda a: a.record["parents"][0].update(sha="0"*40)),
            ("origen", lambda a: a.record.update(sha="0"*40)),
            ("comparacion", lambda a: a.refs.update(main="0"*40)),
        ]
        for title, mutate in cases:
            with self.subTest(case=title):
                api = FakeApi()
                mutate(api)
                if title == "comparacion":
                    with patch.dict(os.environ, RUNNER, clear=True):
                        with patch.object(coordinator, "require_global_running"):
                            self.assertRaises(
                                coordinator.CoordinationError,
                                coordinator.recover_orphaned_issue_lock,
                                api, ISSUE, "pl0n3r", "OWNER", LOCK, now=DATE,
                            )
                else:
                    with self.assertRaises(coordinator.CoordinationError):
                        self.check(api)
                self.assertEqual([], api.releases)
        for actor, association in (
            ("other", "OWNER"), ("pl0n3r", "COLLABORATOR"),
        ):
            with self.assertRaises(coordinator.CoordinationError):
                self.check(FakeApi(), actor=actor, association=association)
        with self.assertRaises(coordinator.CoordinationError):
            self.check(FakeApi(), token="0"*40)

    def test_acepta_solo_token_huerfano_cas(self):
        self.assertTrue(self.check())
        self.assertEqual([(ISSUE, LOCK)], self.api.releases)
        self.assertEqual(PARENT, self.api.refs["main"])
        self.assertNotIn("trabajo/issue-1946", self.api.refs)
        contender = FakeApi()
        with patch.object(contender, "release_issue_lock",
                          side_effect=coordinator.CoordinationError("CAS denied")):
            with self.assertRaises(coordinator.CoordinationError):
                self.check(contender)
        self.assertEqual(
            LOCK, contender.refs["coordinacion/lock-issue-1946"],
        )
        with self.assertRaises(coordinator.CoordinationError):
            self.check()

    def test_comando_owner_y_snapshot(self):
        self.assertEqual(
            ("recuperar-lock-huerfano", LOCK),
            coordinator.parse_comment_command(
                "/recuperar-lock-huerfano " + LOCK,
            ),
        )
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command(
                "/recuperar-lock-huerfano " + "z"*40,
            )
        with self.assertRaises(coordinator.CoordinationError):
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(coordinator, "require_global_running"):
                    coordinator.recover_orphaned_issue_lock(
                        FakeApi(), ISSUE, "pl0n3r", "OWNER", LOCK, now=DATE,
                    )
        with patch.dict(os.environ, RUNNER, clear=True):
            with patch.object(coordinator, "require_global_running"):
                with patch.object(coordinator, "active_reservation",
                                  return_value={"active": True}):
                    with self.assertRaises(coordinator.CoordinationError):
                        coordinator.recover_orphaned_issue_lock(
                            FakeApi(), ISSUE, "pl0n3r", "OWNER", LOCK, now=DATE,
                        )
        self.assertEqual([], self.api.releases)


    def test_negativos_de_fecha_origen_y_relectura(self):
        cases = [
            ("sin committer", lambda a: a.record.update(committer=None)),
            ("sin fecha", lambda a: a.record["committer"].update(date=None)),
            ("fecha inválida", lambda a: a.record["author"].update(date="bad")),
            ("fecha sin zona", lambda a: a.record["author"].update(
                date="2026-10-30T14:27:10")),
            ("fecha futura", lambda a: a.record["committer"].update(
                date="2026-10-30T17:27:10Z")),
            ("sin parent", lambda a: a.record.update(parents=[])),
            ("issue PR", lambda a: a.issue_data.update(pull_request={})),
            ("ref sustituida", lambda a: a.refs.update({
                "coordinacion/lock-issue-1946": "c"*40})),
            ("rama ajena", lambda a: a.refs.update({
                "trabajo/issue-1946": "c"*40})),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                api = FakeApi()
                mutate(api)
                with self.assertRaises(coordinator.CoordinationError):
                    self.check(api)
                self.assertEqual([], api.releases)
        api = FakeApi()
        api.refs["trabajo/issue-1946"] = PARENT
        self.assertTrue(self.check(api))
        self.assertEqual(PARENT, api.refs["trabajo/issue-1946"])

    def test_entorno_ci_y_races_fallan_cerrado(self):
        for key, replacement in (
            ("GITHUB_REPOSITORY", "evil/fork"),
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_WORKFLOW_REF", RUNNER["GITHUB_WORKFLOW_REF"] + "-fake"),
            ("GITHUB_RUN_ID", "not-an-id"),
        ):
            with self.subTest(env=key):
                env = dict(RUNNER)
                env[key] = replacement
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(coordinator, "require_global_running"):
                        with self.assertRaises(coordinator.CoordinationError):
                            coordinator.recover_orphaned_issue_lock(
                                FakeApi(), ISSUE, "pl0n3r", "OWNER",
                                LOCK, now=DATE,
                            )
        api = FakeApi()
        before = deepcopy(api.issue_data)
        after = deepcopy(before)
        after["body"] = "cambio concurrente"
        with patch.object(api, "issue", side_effect=[before, after]):
            with self.assertRaises(coordinator.CoordinationError):
                self.check(api)
        self.assertEqual([], api.releases)


if __name__ == "__main__":
    unittest.main()
