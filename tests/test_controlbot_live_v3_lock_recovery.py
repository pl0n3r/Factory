"""Factory #2050: owner CAS ControlBot allowlist, exclusivamente offline."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts import coordinar_trabajo as coord


SHA = "a" * 40
SESSION = "cafe1234-aaaa-4bbb-8ccc-000000000012"
OWNER = "pl0n3r"
RUNNER = {
    "GITHUB_REPOSITORY": "pl0n3r/ControlBot",
    "GITHUB_WORKFLOW_REF":
        "pl0n3r/ControlBot/.github/workflows/coordinacion.yml@refs/heads/main",
    "GITHUB_EVENT_NAME": "issue_comment",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ID": "123456",
}


class GateReached(Exception):
    """Proves we passed provenance, never performs actual CAS."""


class NoWriteApi:
    def __init__(self, repo: str = "pl0n3r/ControlBot"):
        self.repo = repo

    def request(self, *_args, **_kw):
        raise AssertionError("Auth gate must precede GitHub reads")

    def release_issue_lock(self, *_args):
        raise AssertionError("No real lock release permitted")


class ControlBotLiveV3Tests(unittest.TestCase):
    def assert_permitted(self, api, environment):
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(coord, "require_global_running",
                              side_effect=GateReached) as guarded:
                with self.assertRaises(GateReached):
                    coord.recover_live_owner_v3_orphaned_issue_lock(
                        api, 1445, OWNER, "OWNER", SHA, SESSION)
                guarded.assert_called_once()

    def test_workflow_controlbot_exacto_y_consumidores_existentes(self):
        self.assert_permitted(NoWriteApi(), RUNNER)
        self.assert_permitted(NoWriteApi("pl0n3r/controlbot"), RUNNER)
        for repo, workflow in (
            ("pl0n3r/Factory",
             "pl0n3r/Factory/.github/workflows/coordinacion-trabajo.yml@refs/heads/main"),
            ("pl0n3r/GrindFlow",
             "pl0n3r/GrindFlow/.github/workflows/work-coordination.yml@refs/heads/main"),
        ):
            with self.subTest(repo=repo):
                self.assert_permitted(NoWriteApi(repo), {
                    **RUNNER, "GITHUB_REPOSITORY": repo,
                    "GITHUB_WORKFLOW_REF": workflow,
                })

    def test_identidad_sha_y_sesion_no_se_suplantan(self):
        cases = (
            ("otro", "OWNER", SHA, SESSION),
            (OWNER, "MEMBER", SHA, SESSION),
            (OWNER, "COLLABORATOR", SHA, SESSION),
            (OWNER, "OWNER", "a" * 39, SESSION),
            (OWNER, "OWNER", SHA, "bad"),
        )
        for actor, association, sha, session in cases:
            with self.subTest(actor=actor, association=association):
                with patch.dict(os.environ, RUNNER, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=AssertionError("unexpected authority")):
                        with self.assertRaises(coord.CoordinationError):
                            coord.recover_live_owner_v3_orphaned_issue_lock(
                                NoWriteApi(), 1445, actor, association,
                                sha, session)

    def test_fork_evento_rama_y_workflow_incorrectos_rechazados(self):
        mutations = (
            {"GITHUB_REPOSITORY": "attacker/ControlBot"},
            {"GITHUB_REPOSITORY": "pl0n3r/ControlBot-fork"},
            {"GITHUB_WORKFLOW_REF": "pl0n3r/ControlBot/.github/workflows/other.yml@refs/heads/main"},
            {"GITHUB_WORKFLOW_REF": "pl0n3r/ControlBot/.github/workflows/coordinacion.yml@refs/heads/feature"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch"},
            {"GITHUB_REF": "refs/heads/feature"},
            {"GITHUB_RUN_ID": "0"},
            {"GITHUB_RUN_ID": "invalid"},
        )
        for change in mutations:
            with self.subTest(change=change):
                with patch.dict(os.environ, {**RUNNER, **change}, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=AssertionError("unexpected authority")):
                        with self.assertRaises(coord.CoordinationError):
                            coord.recover_live_owner_v3_orphaned_issue_lock(
                                NoWriteApi(), 1445, OWNER, "OWNER", SHA, SESSION)
        with patch.dict(os.environ, RUNNER, clear=True):
            with self.assertRaises(coord.CoordinationError):
                coord.recover_live_owner_v3_orphaned_issue_lock(
                    NoWriteApi("pl0n3r/Other"), 1445,
                    OWNER, "OWNER", SHA, SESSION)

    def test_legacy_no_acepta_v3_activa_controlbot(self):
        with patch.dict(os.environ, RUNNER, clear=True):
            with self.assertRaises(coord.CoordinationError):
                coord.recover_orphaned_issue_lock(
                    NoWriteApi(), 1445, OWNER, "OWNER", SHA)


if __name__ == "__main__":
    unittest.main()
