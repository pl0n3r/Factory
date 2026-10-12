"""Contratos offline del runner V3: ninguna credencial ni red real."""
import unittest
from dataclasses import replace
from pathlib import Path

from scripts.lease_auto_release_run import (
    decision_from_snapshot, run_cycle,
)
from test_lease_release_executor import FakePort, snapshot


class NoAccessPort:
    def __getattr__(self, name):
        raise AssertionError("La ejecución deshabilitada no debe consultar Port")


class LeaseAutoReleaseRunTests(unittest.TestCase):
    def test_scheduled_dry_run_defaults_off_and_never_writes(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/liberar-reservas.yml").read_text(
                        encoding="utf-8")
        self.assertIn("cron: '*/10 * * * *'", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("lease_auto_release_run.py", workflow)
        self.assertNotIn("lease_github_port.py", workflow)

        off = run_cycle([1191], NoAccessPort())
        self.assertEqual(off.state, "feature_disabled")
        self.assertEqual(off.results[0][1].reason, "feature_disabled")
        self.assertFalse(off.results[0][1].wrote)
        # An explicit feature flag without a separate mutation authority
        # may not read or mutate an authenticated GitHub Port.
        blocked = run_cycle(
            [1191], NoAccessPort(),
            feature_enabled=True, dry_run=False,
        )
        self.assertEqual(blocked.state, "mutation_gate_off")
        self.assertFalse(blocked.results[0][1].wrote)
        self.assertEqual(
            run_cycle([1191], NoAccessPort(),
                      mutations_authorized=True).state,
            "feature_disabled",
        )

        port = FakePort(snapshot())
        observed = run_cycle([1191], port, feature_enabled=True)
        self.assertEqual(observed.state, "dry_run")
        self.assertEqual(observed.results[0][1].action, "release")
        self.assertEqual(observed.results[0][1].reason, "dry_run")
        self.assertEqual(port.writes, [])
        self.assertFalse(port.locked)

        for invalid in (None, [0], [True], [1191, 1191],
                        ["1191"], list(range(101))):
            with self.subTest(invalid=type(invalid).__name__):
                self.assertEqual(
                    run_cycle(invalid, NoAccessPort()).state, "invalid_batch")
        self.assertEqual(
            run_cycle([1191], NoAccessPort(),
                      feature_enabled="true").state, "invalid_flags",
        )

    def test_verified_stale_grace_and_resume_serialized_with_kill_switch(self):
        self.assertEqual(
            decision_from_snapshot(snapshot(recovery=False)).action,
            "mark_recovery",
        )
        self.assertEqual(
            decision_from_snapshot(snapshot()).action,
            "release",
        )
        self.assertEqual(
            decision_from_snapshot({"untrusted": "input"}).action, "unknown",
        )
        # The Port below is entirely synthetic, never a GitHub API client.
        for recovering, expected_action in (
            (False, "mark_recovery"), (True, "release"),
        ):
            with self.subTest(action=expected_action):
                fake = FakePort(snapshot(recovery=recovering))
                result = run_cycle(
                    [1191], fake, feature_enabled=True,
                    dry_run=False, mutations_authorized=True,
                )
                self.assertEqual(result.results[0][1].action, expected_action)
                self.assertTrue(result.results[0][1].wrote)
                self.assertEqual(result.results[0][1].write_state, "complete")
                self.assertFalse(fake.locked)
                self.assertGreaterEqual(len(fake.writes), 2)

        for change in (
            {"kill_switch_running": False},
            {"ci_running": True},
            {"changes_requested": True},
            {"owner_recovered": True},
            {"complete": False},
            {"phase": "live"},
            {"rate_remaining": 19},
        ):
            with self.subTest(veto=change):
                fake = FakePort(replace(snapshot(), **change))
                result = run_cycle(
                    [1191], fake, feature_enabled=True,
                    dry_run=False, mutations_authorized=True,
                )
                self.assertFalse(result.results[0][1].wrote)
                self.assertEqual(fake.writes, [])

        # A ref change observed on the first read cannot survive the CAS.
        raced = FakePort(snapshot())
        raced.drift = replace(snapshot(), branch_sha="b" * 40)
        result = run_cycle(
            [1191], raced, feature_enabled=True,
            dry_run=False, mutations_authorized=True,
        )
        self.assertFalse(result.results[0][1].wrote)
        self.assertEqual(raced.writes, [])


if __name__ == "__main__":
    unittest.main()
