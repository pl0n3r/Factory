"""Factory #2063: AutoFactory live-V3 recovery allowlist remains fail closed.

No real GitHub writes, releases, CAS, or consumer modifications are performed.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts import coordinar_trabajo as coord


SHA = "a" * 40
SESSION = "327c4295-b5a8-4f88-8304-08f20c43ff3b"
OWNER = "pl0n3r"
ENV = {
    "GITHUB_REPOSITORY": "pl0n3r/AutoFactory",
    "GITHUB_WORKFLOW_REF":
        "pl0n3r/AutoFactory/.github/workflows/coordinacion.yml@refs/heads/main",
    "GITHUB_EVENT_NAME": "issue_comment",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ID": "654321",
}


class AuthorizedGate(Exception):
    """Raised by the mock before any repository read or remote CAS."""


class NoWriteApi:
    def __init__(self, repo="pl0n3r/AutoFactory", lock=None):
        self.repo = repo
        self.lock = lock
        self.releases = 0

    def branch_sha(self, branch):
        if branch == "coordinacion/lock-issue-454":
            return self.lock
        raise AssertionError("Unexpected repository read")

    def release_issue_lock(self, *_args):
        self.releases += 1
        raise AssertionError("No test may attempt a real lock release")


class AutoFactoryLiveV3RecoveryTests(unittest.TestCase):
    def assert_reaches_global_guard(self, api, environment):
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(coord, "require_global_running",
                              side_effect=AuthorizedGate) as gate:
                with self.assertRaises(AuthorizedGate):
                    coord.recover_live_owner_v3_orphaned_issue_lock(
                        api, 454, OWNER, "OWNER", SHA, SESSION,
                    )
                gate.assert_called_once_with(api)
        self.assertEqual(api.releases, 0)

    def test_owner_workflow_exact_and_existing_consumers_unchanged(self):
        self.assert_reaches_global_guard(NoWriteApi(), ENV)
        self.assert_reaches_global_guard(NoWriteApi("pl0n3r/autofactory"), ENV)
        for repo, ref in (
            ("pl0n3r/Factory",
             "pl0n3r/Factory/.github/workflows/coordinacion-trabajo.yml@refs/heads/main"),
            ("pl0n3r/GrindFlow",
             "pl0n3r/GrindFlow/.github/workflows/work-coordination.yml@refs/heads/main"),
            ("pl0n3r/ControlBot",
             "pl0n3r/ControlBot/.github/workflows/coordinacion.yml@refs/heads/main"),
        ):
            with self.subTest(repo=repo):
                self.assert_reaches_global_guard(NoWriteApi(repo), {
                    **ENV, "GITHUB_REPOSITORY": repo,
                    "GITHUB_WORKFLOW_REF": ref,
                })

    def test_foreign_identity_or_invalid_session_rejected_before_reads(self):
        attempts = (
            ("attacker", "OWNER", SHA, SESSION),
            (OWNER, "MEMBER", SHA, SESSION),
            (OWNER, "COLLABORATOR", SHA, SESSION),
            (OWNER, "OWNER", SHA[:-1], SESSION),
            (OWNER, "OWNER", SHA.upper(), SESSION),
            (OWNER, "OWNER", SHA, "not-a-uuid"),
        )
        for actor, association, sha, session in attempts:
            with self.subTest(actor=actor, association=association, sha=sha):
                api = NoWriteApi()
                with patch.dict(os.environ, ENV, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=AssertionError("security bypass")):
                        with self.assertRaises(coord.CoordinationError):
                            coord.recover_live_owner_v3_orphaned_issue_lock(
                                api, 454, actor, association, sha, session,
                            )
                self.assertEqual(api.releases, 0)

    def test_fork_workflow_event_ref_and_runid_rejected(self):
        variants = (
            {"GITHUB_REPOSITORY": "attacker/AutoFactory"},
            {"GITHUB_REPOSITORY": "pl0n3r/AutoFactory-fork"},
            {"GITHUB_WORKFLOW_REF":
             "pl0n3r/AutoFactory/.github/workflows/other.yml@refs/heads/main"},
            {"GITHUB_WORKFLOW_REF":
             "pl0n3r/AutoFactory/.github/workflows/coordinacion.yml@refs/heads/dev"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch"},
            {"GITHUB_REF": "refs/heads/dev"},
            {"GITHUB_RUN_ID": "0"},
            {"GITHUB_RUN_ID": "invalid"},
        )
        for variation in variants:
            with self.subTest(variation=variation):
                api = NoWriteApi()
                with patch.dict(os.environ, {**ENV, **variation}, clear=True):
                    with patch.object(coord, "require_global_running",
                                      side_effect=AssertionError("security bypass")):
                        with self.assertRaises(coord.CoordinationError):
                            coord.recover_live_owner_v3_orphaned_issue_lock(
                                api, 454, OWNER, "OWNER", SHA, SESSION,
                            )
                self.assertEqual(api.releases, 0)
        with patch.dict(os.environ, ENV, clear=True):
            with self.assertRaises(coord.CoordinationError):
                coord.recover_live_owner_v3_orphaned_issue_lock(
                    NoWriteApi("pl0n3r/untrusted"), 454,
                    OWNER, "OWNER", SHA, SESSION,
                )

    def test_lock_absent_or_moved_does_not_trigger_cas(self):
        for observed in (None, "b" * 40):
            with self.subTest(observed=observed):
                api = NoWriteApi(lock=observed)
                with patch.dict(os.environ, ENV, clear=True):
                    with patch.object(coord, "require_global_running"):
                        with self.assertRaises(coord.CoordinationError):
                            coord.recover_live_owner_v3_orphaned_issue_lock(
                                api, 454, OWNER, "OWNER", SHA, SESSION,
                            )
                self.assertEqual(api.releases, 0)

    def test_legacy_recovery_does_not_enable_active_v3_consumer(self):
        api = NoWriteApi()
        with patch.dict(os.environ, ENV, clear=True):
            with self.assertRaises(coord.CoordinationError):
                coord.recover_orphaned_issue_lock(
                    api, 454, OWNER, "OWNER", SHA,
                )
        self.assertEqual(api.releases, 0)


if __name__ == "__main__":
    unittest.main()
