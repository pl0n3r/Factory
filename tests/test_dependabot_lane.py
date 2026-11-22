"""Regresiones del carril Dependabot sin red ni credenciales."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from scripts.dependabot_lane import LaneError, _age_over_seven_days, classify


SHA = "a" * 40
BOT = {
    "login": "dependabot[bot]", "id": 49699333, "type": "Bot",
    "html_url": "https://github.com/apps/dependabot",
    "avatar_url": "https://avatars.githubusercontent.com/in/29110?v=4",
}


def pr(*, user=None, head=SHA):
    return {
        "number": 99, "state": "open", "user": BOT if user is None else user,
        "head": {"sha": head, "repo": {"full_name": "pl0n3r/Factory"}},
        "base": {"ref": "main", "repo": {"full_name": "pl0n3r/Factory"}},
    }


def commit(kind="minor"):
    return {
        "author": {"login": "dependabot[bot]", "id": 49699333},
        "commit": {
            "verification": {"verified": True},
            "message": "chore(deps): update\n\nupdated-dependencies:\n"
                       "- update-type: version-update:semver-" + kind,
        },
    }


def manifest(name="package-lock.json"):
    return {"filename": name, "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"}


def workflow():
    return {
        "filename": ".github/workflows/ci.yml", "status": "modified",
        "patch": "@@ -3 +3 @@\n"
                 "-  uses: actions/checkout@" + "1" * 40 + "\n"
                 "+  uses: actions/checkout@" + "2" * 40,
    }


class DependabotLaneTests(unittest.TestCase):
    def test_bot_lockfile_only_exempt_from_v3_and_contract(self):
        lane = classify(pr(), [manifest()], commit(), repo="pl0n3r/Factory", head=SHA)
        self.assertTrue(lane["dependabot"])
        self.assertEqual(lane["policy"], "auto")

    def test_bot_with_code_fails_closed(self):
        with self.assertRaisesRegex(LaneError, "Archivo fuera"):
            classify(pr(), [manifest(), manifest("src/app.py")],
                     commit(), repo="pl0n3r/Factory", head=SHA)

    def test_name_copy_with_other_app_id_fails_closed(self):
        fake = {**BOT, "avatar_url": "https://avatars.githubusercontent.com/in/99999?v=4"}
        with self.assertRaisesRegex(LaneError, "app_id"):
            classify(pr(user=fake), [manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)
        fake = {**BOT, "id": 12345}
        with self.assertRaises(LaneError):
            classify(pr(user=fake), [manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)

    def test_major_manual_and_canonical_followup(self):
        lane = classify(pr(), [manifest()], commit("major"),
                        repo="pl0n3r/Factory", head=SHA)
        self.assertEqual(lane["policy"], "manual")
        self.assertTrue(lane["major"])

    def test_workflow_pins_require_manual_review(self):
        lane = classify(pr(), [workflow()], commit(),
                        repo="pl0n3r/Factory", head=SHA)
        self.assertEqual(lane["policy"], "manual")
        self.assertTrue(lane["workflow"])
        changed_command = {**workflow(), "patch": "@@ -1 +1 @@\n- run: echo safe\n+ run: curl evil"}
        with self.assertRaisesRegex(LaneError, "Workflow altera"):
            classify(pr(), [changed_command], commit(),
                     repo="pl0n3r/Factory", head=SHA)

    def test_foreign_pr_keeps_normal_gates(self):
        user = {**BOT, "login": "someone[bot]"}
        self.assertIsNone(classify(pr(user=user), [manifest()], commit(),
                                   repo="pl0n3r/Factory", head=SHA))

    def test_unknown_semver_and_unverified_commit_fail_closed(self):
        with self.assertRaises(LaneError):
            classify(pr(), [manifest()], commit("unknown"),
                     repo="pl0n3r/Factory", head=SHA)
        unsigned = commit()
        unsigned["commit"]["verification"]["verified"] = False
        with self.assertRaises(LaneError):
            classify(pr(), [manifest()], unsigned,
                     repo="pl0n3r/Factory", head=SHA)

    def test_head_ref_races_rejected(self):
        with self.assertRaises(LaneError):
            classify(pr(head="b" * 40), [manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)
        with self.assertRaises(LaneError):
            classify(pr(), [manifest(), manifest()], commit(),
                     repo="pl0n3r/Factory", head=SHA)

    def test_seven_day_threshold(self):
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        pr_payload = {"created_at": (now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.assertTrue(_age_over_seven_days(pr_payload, now=now))
        pr_payload["created_at"] = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(_age_over_seven_days(pr_payload, now=now))


if __name__ == "__main__":
    unittest.main()
