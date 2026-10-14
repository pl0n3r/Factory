"""Integración QA V3 offline: no escribe en GitHub ni arma el Port real."""
import unittest
from dataclasses import replace
from datetime import timedelta

from scripts.lease_activity_collector import collect_activity
from scripts.lease_auto_release_run import run_cycle
from test_lease_activity_collector import API, NOW
from test_lease_release_executor import FakePort, START, snapshot


class LeaseAutoReleaseIntegrationTests(unittest.TestCase):
    def test_authenticated_complete_activity_evidence_fail_closed(self):
        # Un push reciente acredita presencia, no 30 minutos de ausencia.
        api = API()
        observed = collect_activity(api, 21, now=NOW)
        self.assertTrue(observed["evidence_complete"])
        self.assertTrue(observed["ci_running"])
        self.assertEqual(observed["branch_sha"], "a" * 40)
        self.assertTrue(all(path == "/rate_limit" or path.startswith("/repos/")
                            for path in api.calls))

        for scenario in ("quota", "pages", "race", "missing_push",
                         "changes_requested", "unknown_review",
                         "shared_owner", "timestamp"):
            with self.subTest(scenario=scenario):
                fake = API()
                if scenario == "quota":
                    fake.remaining = 19
                elif scenario == "pages":
                    fake.runs_count_override = 2
                elif scenario == "race":
                    fake.race = True
                elif scenario == "missing_push":
                    fake.push_event = "pull_request"
                elif scenario == "changes_requested":
                    fake.reviews[0]["state"] = "CHANGES_REQUESTED"
                elif scenario == "unknown_review":
                    fake.reviews[0].pop("state")
                elif scenario == "shared_owner":
                    fake.comments.append({
                        "id": 3, "user": {"login": "pl0n3r"},
                        "body": "ambiguous shared login",
                        "created_at": "2026-10-11T09:59:00Z",
                    })
                    fake.issue["comments"] = 3
                else:
                    fake.push_created_at = "invalid-time"
                result = collect_activity(fake, 21, now=NOW)
                self.assertEqual(result,
                                 {"status": "UNKNOWN", "evidence_complete": False})
                self.assertTrue(all(path == "/rate_limit" or path.startswith("/repos/")
                                    for path in fake.calls))

        # APPROVED y COMMENTED no equivalen a changes requested.
        for state in ("APPROVED", "COMMENTED", "DISMISSED"):
            api = API()
            api.reviews[0]["state"] = state
            self.assertTrue(collect_activity(api, 21, now=NOW)["evidence_complete"])

        for tampered in (
            replace(snapshot(), complete=False),
            replace(snapshot(), phase="UNKNOWN"),
            replace(snapshot(), kill_switch_running=False),
            replace(snapshot(), changes_requested=True),
            replace(snapshot(), ci_running=True),
            replace(snapshot(), rate_remaining=19),
        ):
            port = FakePort(tampered)
            answer = run_cycle([1191], port, feature_enabled=True,
                               dry_run=False, mutations_authorized=True)
            self.assertFalse(answer.results[0][1].wrote)
            self.assertEqual(port.writes, [])

    def test_lock_cas_atomic_release_keeps_branch_and_pr(self):
        port = FakePort(snapshot())
        original = (port.item.branch, port.item.branch_sha,
                    port.item.reservation_id)
        result = run_cycle([1191], port, feature_enabled=True,
                           dry_run=False, mutations_authorized=True)
        self.assertEqual(result.results[0][1].reason, "released")
        self.assertEqual((port.item.branch, port.item.branch_sha,
                          port.item.reservation_id), original)
        self.assertFalse(port.item.marker["active"])
        self.assertEqual([kind for kind, _ in port.writes],
                         ["comment", "status"])
        # No repetir un release terminal ya consumado.
        before = len(port.writes)
        again = run_cycle([1191], port, feature_enabled=True,
                          dry_run=False, mutations_authorized=True)
        self.assertFalse(again.results[0][1].wrote)
        self.assertEqual(len(port.writes), before)

        # Carrera de SHA dentro del lock, CI o estado ambiguo: cero escrituras.
        changed = FakePort(snapshot())
        changed.drift = replace(changed.item, branch_sha="e" * 40)
        denied = run_cycle([1191], changed, feature_enabled=True,
                           dry_run=False, mutations_authorized=True)
        self.assertFalse(denied.results[0][1].wrote)
        self.assertEqual(changed.writes, [])
        partial = FakePort(snapshot())
        partial.fail_status = True
        outcome = run_cycle([1191], partial, feature_enabled=True,
                            dry_run=False, mutations_authorized=True)
        self.assertFalse(outcome.results[0][1].wrote)
        self.assertEqual(partial.item.branch, original[0])
        self.assertEqual(partial.item.branch_sha, original[1])
        self.assertEqual(len(partial.writes), 1)
        partial.fail_status = False
        final = run_cycle([1191], partial, feature_enabled=True,
                          dry_run=False, mutations_authorized=True)
        self.assertEqual(final.results[0][1].reason, "partial_reconciled")
        self.assertEqual(len(partial.writes), 2)

    def test_grace_recovery_and_orphan_adoption_exclusivity(self):
        # Antes de 30 minutos y durante la gracia no hay liberación.
        early = FakePort(replace(snapshot(recovery=False),
                                 now=START + timedelta(minutes=29)))
        outcome = run_cycle([1191], early, feature_enabled=True,
                            dry_run=False, mutations_authorized=True)
        self.assertFalse(outcome.results[0][1].wrote)
        self.assertEqual(early.writes, [])

        port = FakePort(replace(snapshot(recovery=False),
                                now=START + timedelta(minutes=30)))
        mark = run_cycle([1191], port, feature_enabled=True,
                         dry_run=False, mutations_authorized=True)
        self.assertEqual(mark.results[0][1].reason, "recovery_marked")
        self.assertEqual(port.item.status, "estado: requiere recuperación")
        self.assertEqual(port.item.recovery_since, START + timedelta(minutes=30))
        port.item = replace(port.item, now=START + timedelta(minutes=39))
        within_grace = run_cycle([1191], port, feature_enabled=True,
                                 dry_run=False, mutations_authorized=True)
        self.assertFalse(within_grace.results[0][1].wrote)
        port.item = replace(port.item, now=START + timedelta(minutes=40))
        released = run_cycle([1191], port, feature_enabled=True,
                             dry_run=False, mutations_authorized=True)
        self.assertEqual(released.results[0][1].reason, "released")
        self.assertEqual(port.item.status, "estado: disponible")
        self.assertEqual(port.item.branch, "trabajo/issue-1191")

        # Una rama huérfana AVAILABLE no se adopta mediante el ejecutor.
        for case in (
            replace(snapshot(), status="estado: disponible"),
            replace(snapshot(), owner_recovered=True),
            replace(snapshot(), marker={**snapshot().marker,
                                        "reservation_id": "other"}),
        ):
            orphan = FakePort(case)
            denied = run_cycle([1191], orphan, feature_enabled=True,
                               dry_run=False, mutations_authorized=True)
            self.assertFalse(denied.results[0][1].wrote)
            self.assertEqual(orphan.writes, [])


    def test_collector_and_port_preview_agree_without_release_authority(self):
        from dataclasses import FrozenInstanceError
        from scripts.lease_auto_release_integration import (
            IntegrationPreview, preview_integrated_activity,
        )
        from test_lease_activity_collector import marker
        import json

        api = API()
        api.checks[0]["status"] = "completed"
        lease = json.loads(marker().split("<!-- condor-reserva ", 1)[1]
                           .split(" -->", 1)[0])
        base = snapshot(recovery=False)
        item = replace(
            base, issue=21, branch="trabajo/issue-21",
            reservation_id=lease["reservation_id"],
            marker={**base.marker, "reservation_id": lease["reservation_id"],
                    "branch": "trabajo/issue-21"},
            status="estado: reservado", now=NOW,
            last_activity_at=NOW - timedelta(minutes=20),
            rate_remaining=20, ci_running=False,
        )

        class ReadOnlyPort:
            def __init__(self, item):
                self.item = item
                self.reads = 0
            def read(self, issue):
                assert issue == 21
                self.reads += 1
                return self.item
            def __getattr__(self, operation):
                raise AssertionError("preview cannot write: " + operation)

        port = ReadOnlyPort(item)
        observed = preview_integrated_activity(api, port, 21, now=NOW)
        self.assertEqual((observed.state, observed.action),
                         ("read_only", "wait"))
        self.assertIs(observed.release_authorized, False)
        self.assertEqual(port.reads, 1)
        with self.assertRaises(TypeError):
            replace(observed, release_authorized=True)
        with self.assertRaises(FrozenInstanceError):
            observed.state = "authorized"

        for change in (
            {"branch_sha": "b" * 40},
            {"owner": "different"},
            {"complete": False},
            {"changes_requested": True},
            {"kill_switch_running": False},
            {"phase": "live"},
            {"ci_running": True},
            {"now": NOW + timedelta(minutes=1)},
            {"rate_remaining": 19},
        ):
            with self.subTest(change=change):
                other = ReadOnlyPort(replace(item, **change))
                outcome = preview_integrated_activity(API(), other, 21,
                                                       now=NOW)
                self.assertEqual(outcome.state, "UNKNOWN")
                self.assertFalse(outcome.release_authorized)
        broken = API()
        broken.push_event = "pull_request"
        no_push = ReadOnlyPort(item)
        observed = preview_integrated_activity(broken, no_push, 21, now=NOW)
        self.assertEqual(observed.state, "UNKNOWN")
        self.assertEqual(no_push.reads, 0)



if __name__ == "__main__":
    unittest.main()
