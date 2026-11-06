"""Factory #2065: prueba offline de la allowlist CAS V3 owner-only de FactoryRunner.

Usa API y recibos sintéticos. Ninguna prueba accede a GitHub, elimina refs,
toca secretos, autoriza infraestructura ni realiza una llamada CAS real.
El caller FactoryRunner y Factory@v1 requieren despliegue/puerta separados.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch

from scripts import coordinar_trabajo as coord


OWNER = "pl0n3r"
ISSUE = 608
PR = 632
LOCK_SHA = "a" * 40
HEAD_SHA = "b" * 40
BASE_SHA = "c" * 40
TREE_SHA = "d" * 40
SESSION = "d9f4d5a0-1fc7-46be-a278-18c34d35ab90"
ENV = {
    "GITHUB_REPOSITORY": "pl0n3r/FactoryRunner",
    "GITHUB_WORKFLOW_REF":
        "pl0n3r/FactoryRunner/.github/workflows/coordinacion.yml@refs/heads/main",
    "GITHUB_EVENT_NAME": "issue_comment",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ID": "654321",
}
FIXED_NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


class GateReached(Exception):
    """Sentinela: prueba el acceso a guarda global, no a IO de GitHub."""


class CasWouldBeCalled(Exception):
    """Sentinela que intercepta el CAS ANTES de que se produzca escritura."""


class MemoryOnlyApi:
    def __init__(self, repo="pl0n3r/FactoryRunner"):
        self.repo = repo
        self.locks = LOCK_SHA
        self.lease = {
            "version": 3, "active": True, "owner": OWNER,
            "reservation_id": SESSION, "branch": "trabajo/issue-608",
            "task_marker_sha256": "task-pin",
            "acceptance_sha256": "acceptance-pin",
            "task_paths": [
                "docs/hostinger-ops-readiness.md",
                "tests/test_hostinger_ops_readiness.py",
            ],
            "task_depends_on": [],
        }
        self.task = {
            "owner": OWNER,
            "paths": list(self.lease["task_paths"]),
            "depends_on": [],
        }
        self.issue_data = {
            "number": ISSUE, "state": "open",
            "labels": [{"name": "estado: en revisión"}],
            "body": "### Contrato de aceptación\n",
        }
        self.pr = {
            "number": PR, "state": "open",
            "head": {"sha": HEAD_SHA, "ref": "trabajo/issue-608"},
            "base": {"sha": BASE_SHA, "ref": "main"},
            "body": f"Closes #{ISSUE}\n<!-- condor-reserva-id: {SESSION} -->",
        }
        self.files = ["docs/hostinger-ops-readiness.md",
                      "tests/test_hostinger_ops_readiness.py"]
        self.lock_commit = {
            "sha": LOCK_SHA,
            "message": "lock coordinacion Issue #608 425103be-1f46-4dce-814a-7bb01ea9cb6d",
            "author": {
                "name": "github-actions[bot]",
                "email": "41898282+github-actions[bot]@users.noreply.github.com",
                "date": "2026-11-05T16:11:36Z",
            },
            "committer": {
                "name": "GitHub", "email": "noreply@github.com",
                "date": "2026-11-05T16:11:36Z",
            },
            "verification": {"verified": True, "reason": "valid"},
            "tree": {"sha": TREE_SHA},
            "parents": [{"sha": HEAD_SHA}],
        }
        self.parent_tree = TREE_SHA
        self.release_attempts = 0
        self.issue_reads = 0
        self.lock_reads = 0
        self.change_issue_on_second_read = False
        self.move_lock_on_second_read = False

    def branch_sha(self, branch):
        if branch == "coordinacion/lock-issue-608":
            self.lock_reads += 1
            if self.move_lock_on_second_read and self.lock_reads > 1:
                return "f" * 40
            return self.locks
        if branch == "trabajo/issue-608":
            return HEAD_SHA
        raise AssertionError("Rama inesperada: " + branch)

    def issue(self, number):
        assert number == ISSUE
        self.issue_reads += 1
        data = deepcopy(self.issue_data)
        if self.change_issue_on_second_read and self.issue_reads > 1:
            data["body"] = "CONTRACT_CHANGED"
        return data

    def pull_files_exact_head(self, number):
        assert number == PR
        return {
            "complete": True, "head_sha": HEAD_SHA,
            "base_sha": BASE_SHA, "files": list(self.files),
        }

    def request(self, method, path, payload=None, allow=()):
        assert method == "GET", "Solo lecturas simuladas"
        if path.endswith("/git/commits/" + LOCK_SHA):
            return deepcopy(self.lock_commit)
        if path.endswith("/git/commits/" + HEAD_SHA):
            return {"tree": {"sha": self.parent_tree}}
        if "/compare/" in path:
            return {"status": "ahead", "behind_by": 0}
        raise AssertionError("Consulta inesperada: " + path)

    def release_issue_lock(self, *_args):
        self.release_attempts += 1
        raise CasWouldBeCalled("CAS interceptado, cero mutaciones")


@contextmanager
def simulated_run(api: MemoryOnlyApi):
    """El resto del algoritmo conserva sus guardas reales; sólo se simulan fuentes."""
    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, ENV, clear=True))
        stack.enter_context(patch.object(coord, "require_global_running"))
        stack.enter_context(patch.object(coord, "active_reservation",
                                         side_effect=lambda _api, _n: api.lease))
        stack.enter_context(patch.object(coord, "valid_reservation_payload",
                                         return_value=True))
        stack.enter_context(patch.object(coord, "parse_contract", return_value=True))
        stack.enter_context(patch.object(coord, "parse_task_marker",
                                         side_effect=lambda _body: api.task))
        stack.enter_context(patch.object(coord, "task_marker_fingerprint",
                                         return_value="task-pin"))
        stack.enter_context(patch.object(coord, "contract_fingerprint",
                                         return_value="acceptance-pin"))
        stack.enter_context(patch.object(coord, "open_pull_records_for_branch",
                                         side_effect=lambda _api, _br: [api.pr]))
        stack.enter_context(patch.object(
            coord, "orphan_adoption_pull_snapshot",
            side_effect=lambda prs: tuple(
                (p["number"], p["head"]["sha"], p["base"]["sha"],
                 p["body"]) for p in prs)))
        stack.enter_context(patch.object(
            coord, "reservation_from_pr_body",
            side_effect=lambda body: SESSION if
            f"condor-reserva-id: {SESSION}" in body else None))
        stack.enter_context(patch.object(
            coord, "closing_issues",
            side_effect=lambda body: [ISSUE] if "Closes #608" in body else []))
        yield


class FactoryRunnerLiveV3LockRecoveryTests(unittest.TestCase):
    def recover(self, api):
        return coord.recover_live_owner_v3_orphaned_issue_lock(
            api, ISSUE, OWNER, "OWNER", LOCK_SHA, SESSION, now=FIXED_NOW)

    def assert_rejected(self, api):
        with simulated_run(api):
            with self.assertRaises(coord.CoordinationError):
                self.recover(api)
        self.assertEqual(api.release_attempts, 0)

    def test_owner_workflow_exact_and_existing_consumers_are_unchanged(self):
        cases = (
            (ENV, "pl0n3r/FactoryRunner"),
            (ENV, "pl0n3r/factoryrunner"),
            ({
                **ENV, "GITHUB_REPOSITORY": "pl0n3r/Factory",
                "GITHUB_WORKFLOW_REF":
                "pl0n3r/Factory/.github/workflows/coordinacion-trabajo.yml@refs/heads/main"
            }, "pl0n3r/Factory"),
            ({
                **ENV, "GITHUB_REPOSITORY": "pl0n3r/GrindFlow",
                "GITHUB_WORKFLOW_REF":
                "pl0n3r/GrindFlow/.github/workflows/work-coordination.yml@refs/heads/main"
            }, "pl0n3r/GrindFlow"),
            ({
                **ENV, "GITHUB_REPOSITORY": "pl0n3r/ControlBot",
                "GITHUB_WORKFLOW_REF":
                "pl0n3r/ControlBot/.github/workflows/coordinacion.yml@refs/heads/main"
            }, "pl0n3r/ControlBot"),
            ({
                **ENV, "GITHUB_REPOSITORY": "pl0n3r/AutoFactory",
                "GITHUB_WORKFLOW_REF":
                "pl0n3r/AutoFactory/.github/workflows/coordinacion.yml@refs/heads/main"
            }, "pl0n3r/AutoFactory"),
        )
        for env, repo in cases:
            with self.subTest(repo=repo):
                api = MemoryOnlyApi(repo)
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=GateReached) as guard:
                        with self.assertRaises(GateReached):
                            self.recover(api)
                        guard.assert_called_once_with(api)
                self.assertEqual(api.release_attempts, 0)

    def test_identity_sha_session_and_workflow_fail_closed(self):
        invalid = [
            ("attacker", "OWNER", LOCK_SHA, SESSION),
            (OWNER, "MEMBER", LOCK_SHA, SESSION),
            (OWNER, "COLLABORATOR", LOCK_SHA, SESSION),
            (OWNER, "OWNER", LOCK_SHA[:-1], SESSION),
            (OWNER, "OWNER", LOCK_SHA.upper(), SESSION),
            (OWNER, "OWNER", LOCK_SHA, "not-a-uuid"),
        ]
        for actor, role, sha, sid in invalid:
            with self.subTest(actor=actor, role=role, sha=sha):
                api = MemoryOnlyApi()
                with patch.dict(os.environ, ENV, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=AssertionError("guarda omitida")):
                        with self.assertRaises(coord.CoordinationError):
                            coord.recover_live_owner_v3_orphaned_issue_lock(
                                api, ISSUE, actor, role, sha, sid,
                                now=FIXED_NOW)
                self.assertEqual(api.release_attempts, 0)

        env_changes = [
            {"GITHUB_REPOSITORY": "attacker/FactoryRunner"},
            {"GITHUB_REPOSITORY": "pl0n3r/FactoryRunner-fork"},
            {"GITHUB_WORKFLOW_REF":
             "pl0n3r/FactoryRunner/.github/workflows/other.yml@refs/heads/main"},
            {"GITHUB_WORKFLOW_REF":
             "pl0n3r/FactoryRunner/.github/workflows/coordinacion.yml@refs/heads/dev"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch"},
            {"GITHUB_REF": "refs/heads/dev"},
            {"GITHUB_RUN_ID": "0"}, {"GITHUB_RUN_ID": "invalid"},
        ]
        for change in env_changes:
            with self.subTest(change=change):
                api = MemoryOnlyApi()
                with patch.dict(os.environ, {**ENV, **change}, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=AssertionError("guarda omitida")):
                        with self.assertRaises(coord.CoordinationError):
                            self.recover(api)
                self.assertEqual(api.release_attempts, 0)
        with patch.dict(os.environ, ENV, clear=True):
            with self.assertRaises(coord.CoordinationError):
                self.recover(MemoryOnlyApi("pl0n3r/unknown"))

    def test_authentic_synthetic_snapshot_reaches_only_intercepted_cas(self):
        api = MemoryOnlyApi()
        with simulated_run(api):
            with self.assertRaises(CasWouldBeCalled):
                self.recover(api)
        self.assertEqual(api.release_attempts, 1)

    def test_absent_moved_or_replaced_lock_cannot_trigger_cas(self):
        for lock in (None, "e" * 40):
            with self.subTest(lock=lock):
                api = MemoryOnlyApi()
                api.locks = lock
                self.assert_rejected(api)
        api = MemoryOnlyApi()
        api.move_lock_on_second_read = True
        self.assert_rejected(api)

    def test_invalid_reservation_issue_and_pr_never_trigger_cas(self):
        changes = (
            lambda a: a.lease.update(active=False),
            lambda a: a.lease.update(owner="outsider"),
            lambda a: a.lease.update(reservation_id="bad-uuid"),
            lambda a: a.lease.update(branch="trabajo/issue-609"),
            lambda a: a.lease.update(task_paths=["src/secret.py"]),
            lambda a: a.lease.update(acceptance_sha256="wrong"),
            lambda a: a.lease.update(task_marker_sha256="wrong"),
            lambda a: a.issue_data.update(state="closed"),
            lambda a: a.issue_data.update(labels=[{"name": "estado: bloqueado"}]),
            lambda a: a.pr["head"].update(sha="f" * 40),
            lambda a: a.pr["base"].update(ref="feature"),
            lambda a: a.pr.update(body="Closes #608"),
            lambda a: a.pr.update(body=f"<!-- condor-reserva-id: {SESSION} -->"),
            lambda a: a.files.append("src/secrets.py"),
        )
        for change in changes:
            with self.subTest(change=change):
                api = MemoryOnlyApi()
                change(api)
                self.assert_rejected(api)

    def test_invalid_signed_commit_nonce_age_parent_and_tree_fail_closed(self):
        changes = (
            lambda a: a.lock_commit["author"].update(name="other"),
            lambda a: a.lock_commit["author"].update(email="other@invalid"),
            lambda a: a.lock_commit["committer"].update(name="other"),
            lambda a: a.lock_commit["verification"].update(verified=False),
            lambda a: a.lock_commit["verification"].update(reason="unsigned"),
            lambda a: a.lock_commit.update(message="lock coordinacion Issue #608 forged"),
            lambda a: a.lock_commit["parents"].clear(),
            lambda a: a.lock_commit["tree"].update(sha="bad"),
            lambda a: a.lock_commit["author"].update(date="2026-11-06T11:59:00Z"),
            lambda a: a.lock_commit["committer"].update(date="invalid"),
            lambda a: setattr(a, "parent_tree", "e" * 40),
        )
        for change in changes:
            with self.subTest(change=change):
                api = MemoryOnlyApi()
                change(api)
                self.assert_rejected(api)

    def test_snapshot_race_never_reaches_cas(self):
        api = MemoryOnlyApi()
        api.change_issue_on_second_read = True
        self.assert_rejected(api)

    def test_legacy_recovery_does_not_bypass_active_v3(self):
        api = MemoryOnlyApi()
        with simulated_run(api):
            with self.assertRaises(coord.CoordinationError):
                coord.recover_orphaned_issue_lock(
                    api, ISSUE, OWNER, "OWNER", LOCK_SHA)
        self.assertEqual(api.release_attempts, 0)


if __name__ == "__main__":
    unittest.main()
