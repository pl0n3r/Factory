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


    def consumer(self, api=None, runner=None, token=LOCK,
                 repo_name="pl0n3r/GrindFlow"):
        consumer = api if api is not None else FakeApi()
        consumer.repo = repo_name
        env = {**RUNNER,
               "GITHUB_REPOSITORY": "pl0n3r/GrindFlow",
               "GITHUB_WORKFLOW_REF":
                   "pl0n3r/GrindFlow/.github/workflows/work-coordination.yml@refs/heads/main",
               "GITHUB_REF": "refs/heads/main"}
        if runner:
            env.update(runner)
        with patch.dict(os.environ, env, clear=True):
            with patch.object(coordinator, "require_global_running") as guard:
                result = coordinator.recover_orphaned_issue_lock(
                    consumer, ISSUE, "pl0n3r", "OWNER", token, now=DATE,
                )
                self.assertGreaterEqual(guard.call_count, 2)
                return result

    def test_consumidor_liberacion_cas_segura(self):
        consumer = FakeApi()
        self.assertTrue(self.consumer(consumer))
        self.assertEqual([(ISSUE, LOCK)], consumer.releases)
        self.assertEqual(PARENT, consumer.refs["main"])
        self.assertEqual({"main": PARENT}, consumer.refs)
        self.assertEqual(LOCK, consumer.record["sha"])
        self.assertEqual("open", consumer.issue_data["state"])

    def test_consumidor_rechaza_origen_no_autorizado(self):
        for repo in ("pl0n3r/other", "evil/GrindFlow", "pl0n3r/GrindFlow-fork"):
            with self.subTest(repo=repo):
                consumer = FakeApi()
                consumer.repo = repo
                with self.assertRaises(coordinator.CoordinationError):
                    self.consumer(consumer, runner={"GITHUB_REPOSITORY": repo},
                                  repo_name=repo)
                self.assertEqual([], consumer.releases)
        for key, value in (
            ("GITHUB_REPOSITORY", "pl0n3r/Factory"),
            ("GITHUB_EVENT_NAME", "pull_request"),
            ("GITHUB_REF", "refs/heads/topic"),
            ("GITHUB_RUN_ID", "bad-id"),
        ):
            with self.subTest(key=key):
                consumer = FakeApi()
                with self.assertRaises(coordinator.CoordinationError):
                    self.consumer(consumer, runner={key: value})
                self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        consumer.record["verification"]["verified"] = False
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer)
        self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        consumer.record["tree"]["sha"] = "d" * 40
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer)
        self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        consumer.issue_data["labels"].clear()
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer)
        self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer, token="f" * 40)
        self.assertEqual([], consumer.releases)

    def test_consumidor_requiere_workflow_serializado(self):
        consumer = FakeApi()
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer, runner={
                "GITHUB_WORKFLOW_REF":
                    "pl0n3r/GrindFlow/.github/workflows/parallel.yml@refs/heads/main",
            })
        self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer, runner={
                "GITHUB_WORKFLOW_REF":
                    "pl0n3r/GrindFlow/.github/workflows/work-coordination.yml@refs/heads/unsafe",
            })
        self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        consumer.refs["trabajo/issue-1946"] = "d" * 40
        with self.assertRaises(coordinator.CoordinationError):
            self.consumer(consumer)
        self.assertEqual([], consumer.releases)
        consumer = FakeApi()
        with patch.object(consumer, "release_issue_lock",
                          side_effect=coordinator.CoordinationError("CAS race")):
            with self.assertRaises(coordinator.CoordinationError):
                self.consumer(consumer)
        self.assertEqual([], consumer.releases)


# Nueva primitiva offline: no debe asociarse a parse_comment_command.
class LiveOwnerV3RecoveryTests(unittest.TestCase):
    SESSION = "cbb53f02-a68b-4d1d-b118-4dfc4efea06d"

    class LiveApi(FakeApi):
        def __init__(self):
            super().__init__()
            self.refs["trabajo/issue-1946"] = PARENT
            self.issue_data["labels"] = [{"name": coordinator.STATUS_REVIEW}]
            task = {
                "version": 1, "epic": 1296,
                "task_key": "FACTORY_TEST_OWNER_LOCK", "order": 1,
                "owner": "pl0n3r",
                "roles": ["ingenieria-software", "seguridad", "qa"],
                "depends_on": [], "paths": ["scripts/coordinar_trabajo.py"],
            }
            accept = {"version": 1, "criteria": [{
                "id": "AC-01", "kind": "test",
                "target": "tests/test_coordinar_lock_huerfano.py::RecoveryLockTests::test_comando_owner_y_snapshot",
            }]}
            self.issue_data["body"] = (
                "### Contexto\nprueba offline\n"
                "### Alcance\nrecuperación CAS\n"
                "### Fuera de alcance\nsin consumidor\n"
                "### Criterios de aceptación\n"
                "- [ ] [AC-01] lock preservado\n"
                "### Contrato ejecutable\n"
                "<!-- factory-acceptance " +
                __import__("json").dumps(accept) + " -->\n"
                "### Rutas reclamadas\n- " + chr(96) +
                "scripts/coordinar_trabajo.py" + chr(96) + "\n"
                "<!-- factory-plan-task " +
                __import__("json").dumps(task) + " -->\n"
            )
            self.reservation = {
                "version": 3, "owner": "pl0n3r",
                "reservation_id": LiveOwnerV3RecoveryTests.SESSION,
                "branch": "trabajo/issue-1946", "active": True,
                "reason": "tomar",
                "acceptance_sha256": coordinator.contract_fingerprint(
                    self.issue_data["body"]),
                "task_marker_sha256": coordinator.task_marker_fingerprint(
                    coordinator.parse_task_marker(self.issue_data["body"])),
                "task_paths": ["scripts/coordinar_trabajo.py"],
                "task_depends_on": [],
            }
            self.comments = [{
                "user": {"login": "github-actions[bot]"},
                "body": coordinator.reservation_marker(
                    "pl0n3r", LiveOwnerV3RecoveryTests.SESSION,
                    "trabajo/issue-1946", True, "tomar",
                    self.reservation["acceptance_sha256"],
                    task_snapshot={
                        "task_marker_sha256":
                            self.reservation["task_marker_sha256"],
                        "task_paths": self.reservation["task_paths"],
                        "task_depends_on": [],
                    }),
            }]
            self.pull_record = {
                "number": 1947, "state": "open", "draft": False,
                "head": {"ref": "trabajo/issue-1946", "sha": PARENT,
                         "repo": {"full_name": "pl0n3r/Factory",
                                  "name": "Factory",
                                  "owner": {"login": "pl0n3r"}}},
                "base": {"ref": "main", "sha": PARENT},
                "body": "Closes #1946\n<!-- condor-reserva-id: " +
                        LiveOwnerV3RecoveryTests.SESSION + " -->",
            }
            self.proof = {
                "complete": True, "head_sha": PARENT, "base_sha": PARENT,
                "files": ["scripts/coordinar_trabajo.py"],
            }

        def open_pulls(self):
            return [deepcopy(self.pull_record)]

        def pull_files_exact_head(self, number):
            if number != 1947:
                raise AssertionError("PR ajeno")
            return deepcopy(self.proof)

        def set_trusted_lease(self):
            self.comments = [{
                "user": {"login": "github-actions[bot]"},
                "body": "<!-- condor-reserva " +
                        __import__("json").dumps(self.reservation) + " -->",
            }]

    def call(self, api, *, actor="pl0n3r", association="OWNER",
             session=None, token=LOCK, env=None):
        runner = {**RUNNER, "GITHUB_REF": "refs/heads/main"}
        runner.update(env or {})
        with patch.dict(os.environ, runner, clear=True):
            with patch.object(coordinator, "require_global_running") as guard:
                result = coordinator.recover_live_owner_v3_orphaned_issue_lock(
                    api, ISSUE, actor, association, token,
                    session or self.SESSION, now=DATE,
                )
                self.assertGreaterEqual(guard.call_count, 2)
                return result

    def test_live_v3_cas_preserva_lease_pr_y_rama(self):
        api = self.LiveApi()
        before = deepcopy((api.issue_data, api.comments, api.pull_record))
        evidence = self.call(api)
        self.assertEqual("cas_only", evidence["result"])
        self.assertEqual(1947, evidence["pr"])
        self.assertEqual([(ISSUE, LOCK)], api.releases)
        self.assertEqual(PARENT, api.refs["trabajo/issue-1946"])
        self.assertEqual(before, (api.issue_data, api.comments, api.pull_record))
        self.assertEqual(self.SESSION,
                         coordinator.active_reservation(api, ISSUE)["reservation_id"])
        self.assertNotIn("coordinacion/lock-issue-1946", api.refs)
        with self.assertRaises(coordinator.CoordinationError):
            self.call(api)

    def test_live_v3_rechaza_replay_roles_y_falsificaciones(self):
        for actor, association in (("attacker", "OWNER"),
                                   ("pl0n3r", "COLLABORATOR")):
            api = self.LiveApi()
            with self.assertRaises(coordinator.CoordinationError):
                self.call(api, actor=actor, association=association)
            self.assertEqual([], api.releases)
        for change in (
            {"GITHUB_REPOSITORY": "evil/Factory"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_WORKFLOW_REF": "evil/workflow.yml@refs/heads/main"},
            {"GITHUB_REF": "refs/heads/other"},
            {"GITHUB_RUN_ID": "bad"},
        ):
            api = self.LiveApi()
            with self.assertRaises(coordinator.CoordinationError):
                self.call(api, env=change)
            self.assertEqual([], api.releases)
        api = self.LiveApi()
        with self.assertRaises(coordinator.CoordinationError):
            self.call(api, session="85773c47-d586-4860-a921-7053d23f9f4b")
        self.assertEqual([], api.releases)

    def test_live_v3_rechaza_derivas_de_sesion_claims_pr_nonce(self):
        cases = [
            ("owner", lambda a: a.reservation.update(owner="other"), True),
            ("sesion", lambda a: a.reservation.update(
                reservation_id="85773c47-d586-4860-a921-7053d23f9f4b"), True),
            ("lease inactiva", lambda a: a.reservation.update(active=False), True),
            ("lease antigua", lambda a: a.reservation.update(version=2), True),
            ("claims", lambda a: a.reservation.update(
                task_paths=["other/path.py"]), True),
            ("fingerprint acceptance", lambda a: a.reservation.update(
                acceptance_sha256="1"*64), True),
            ("fingerprint plan", lambda a: a.reservation.update(
                task_marker_sha256="2"*64), True),
            ("body alterado", lambda a: a.issue_data.update(
                body=a.issue_data["body"].replace(
                    "test_comando_owner_y_snapshot", "test_ataque")), False),
            ("estado", lambda a: a.issue_data["labels"].clear(), False),
            ("rama", lambda a: a.refs.update({
                "trabajo/issue-1946": "d"*40}), False),
            ("PR HEAD", lambda a: a.pull_record["head"].update(
                sha="d"*40), False),
            ("PR fork", lambda a: a.pull_record["head"]["repo"].update(
                full_name="evil/Factory"), False),
            ("PR ajeno", lambda a: a.pull_record.update(
                body="Closes #999"), False),
            ("PR closed", lambda a: a.pull_record.update(state="closed"), False),
            ("diff vacío", lambda a: a.proof.update(files=[]), False),
            ("diff fuera", lambda a: a.proof.update(
                files=["other/path.py"]), False),
            ("diff HEAD", lambda a: a.proof.update(head_sha="d"*40), False),
            ("nonce", lambda a: a.record.update(message="forged"), False),
            ("firma", lambda a: a.record["verification"].update(
                verified=False), False),
            ("árbol", lambda a: a.record["tree"].update(sha="d"*40), False),
            ("lock reciente", lambda a: a.record["author"].update(
                date="2026-10-30T15:45:00Z"), False),
        ]
        for name, mutate, trusted in cases:
            with self.subTest(name=name):
                api = self.LiveApi()
                mutate(api)
                if trusted:
                    api.set_trusted_lease()
                with self.assertRaises(coordinator.CoordinationError):
                    self.call(api)
                self.assertEqual([], api.releases)

    def test_live_v3_carreras_cas_killswitch_y_comando_legacy(self):
        api = self.LiveApi()
        with patch.object(api, "release_issue_lock",
                          side_effect=coordinator.CoordinationError("CAS race")):
            with self.assertRaises(coordinator.CoordinationError):
                self.call(api)
        self.assertEqual([], api.releases)

        api = self.LiveApi()
        original = api.open_pulls
        times = [0]
        def concurrent_pull():
            times[0] += 1
            if times[0] >= 2:
                api.pull_record["head"]["sha"] = "d"*40
            return original()
        with patch.object(api, "open_pulls", side_effect=concurrent_pull):
            with self.assertRaises(coordinator.CoordinationError):
                self.call(api)
        self.assertEqual([], api.releases)

        api = self.LiveApi()
        runner = {**RUNNER, "GITHUB_REF": "refs/heads/main"}
        with patch.dict(os.environ, runner, clear=True):
            with patch.object(coordinator, "require_global_running",
                              side_effect=[
                                  None, coordinator.CoordinationError("PAUSED")]):
                with self.assertRaises(coordinator.CoordinationError):
                    coordinator.recover_live_owner_v3_orphaned_issue_lock(
                        api, ISSUE, "pl0n3r", "OWNER",
                        LOCK, self.SESSION, now=DATE)
        self.assertEqual([], api.releases)
        with self.assertRaises(coordinator.CoordinationError):
            coordinator.parse_comment_command(
                "/recuperar-lock-v3-activa " + self.SESSION)

if __name__ == "__main__":
    unittest.main()
