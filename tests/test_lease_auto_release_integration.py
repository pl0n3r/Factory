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


    def test_real_coordinator_orphan_adoption_is_explicit(self):
        """Integración de comandos, no solo snapshots del ejecutor."""
        from scripts.coordinar_trabajo import (
            CoordinationError, active_reservation, adopt_orphaned_contract,
            reservation_from_pr_body, reserve_work,
        )
        from scripts.orquestador_kit import PlannedTask, build_task_marker
        from test_coordinar_trabajo import FakeGitHub, VALID_ACCEPTANCE_BODY

        api = FakeGitHub()
        task = PlannedTask(
            key="LEASE_ORPHAN", title="Adopción V3",
            owner="pl0n3r", paths=("scripts/orphan_simulation.py",),
            depends_on=(),
        )
        api.issue_data["body"] = (
            VALID_ACCEPTANCE_BODY + "\n### Rutas reclamadas\n"
            "- scripts/orphan_simulation.py\n" + build_task_marker(
                epic=12, task=task, order=1, roles=["ingenieria-software"],
                dependency_issues=[],
            )
        )
        branch = "trabajo/issue-12"
        api.branches[branch] = "abc123"
        api.pulls[15] = {
            "number": 15, "state": "open", "draft": True,
            "body": "Closes #12", "head": {
                "ref": branch, "repo": {"full_name": api.repo},
            }, "base": {"ref": "main"},
        }
        # /tomar no reclama silenciosamente una rama huérfana.
        with self.assertRaisesRegex(
            CoordinationError, "adoptar-contrato-huerfana"
        ):
            reserve_work(api, 12, "pl0n3r", "OWNER")
        self.assertIsNone(active_reservation(api, 12))
        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertEqual(api.branches[branch], "abc123")

        # La adopción explícita genera nueva sesión V3 sobre la misma rama
        # y reescribe únicamente la metadata de reserva del PR.
        session = adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
        self.assertIsNotNone(session)
        current = active_reservation(api, 12)
        self.assertIsNotNone(current)
        self.assertEqual(current["reservation_id"], session)
        self.assertEqual(current["version"], 3)
        self.assertEqual(api.branches[branch], "abc123")
        self.assertEqual(api.pulls[15]["state"], "open")
        self.assertEqual(reservation_from_pr_body(api.pulls[15]["body"]),
                         session)
        self.assertEqual(api.pulls[15]["body"].count("Closes #12"), 1)

        # Una segunda adopción no puede robar una sesión activa.
        with self.assertRaisesRegex(CoordinationError, "reserva activa"):
            adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
        self.assertEqual(active_reservation(api, 12)["reservation_id"],
                         session)


    def test_v3_auto_recovery_grace_rejects_takeover(self):
        """Nota de recuperación automática impide una rotación por /tomar."""
        import json
        from datetime import datetime, timezone
        from scripts.aceptacion_kit import contract_fingerprint
        from scripts.coordinar_trabajo import (
            CoordinationError, STATUS_RECOVERY, active_reservation,
            recover_work, reservation_marker, reserve_work,
        )
        from scripts.orquestador_kit import (
            PlannedTask, build_task_marker, parse_task_marker,
        )
        from test_coordinar_trabajo import (
            BOT, FakeGitHub, SESSION_A, VALID_ACCEPTANCE_BODY,
        )

        branch = "trabajo/issue-12"
        owner = "agente-original"
        def create_fixture():
            api = FakeGitHub()
            api.repo = "pl0n3r/Factory"
            task = PlannedTask(
                key="LEASE_V3_GRACE", title="Gracia",
                owner="pl0n3r", paths=("scripts/x.py",), depends_on=(),
            )
            body = VALID_ACCEPTANCE_BODY + "\n### Rutas reclamadas\n" + (
                "- scripts/x.py\n" + build_task_marker(
                    epic=12, task=task, order=1,
                    roles=["ingenieria-software"], dependency_issues=[],
                )
            )
            api.issue_data["body"] = body
            api.branches[branch] = "a" * 40
            api.commit_times["a" * 40] = START
            api.set_status(12, STATUS_RECOVERY)
            pin = contract_fingerprint(body)
            marker = parse_task_marker(body)
            task_pin = __import__(
                "scripts.orquestador_kit", fromlist=["task_marker_fingerprint"]
            ).task_marker_fingerprint(marker)
            api.comments.append({
                "user": {"login": BOT, "type": "Bot"},
                "body": reservation_marker(
                    owner, SESSION_A, branch, True, "tomar", pin, marker),
                "created_at": START.isoformat(),
                "updated_at": START.isoformat(),
            })
            payload = {
                "version": 1, "owner": owner,
                "reservation_id": SESSION_A, "branch": branch,
                "branch_sha": "a" * 40,
                "last_activity_at": START.isoformat(),
                "acceptance_sha256": pin,
                "task_marker_sha256": task_pin,
            }
            api.comments.append({
                "user": {"login": BOT, "type": "Bot"},
                "body": "<!-- factory-lease-recovery "
                        + json.dumps(payload, sort_keys=True) + " -->",
                "created_at": (START + timedelta(minutes=30)).isoformat(),
                "updated_at": (START + timedelta(minutes=30)).isoformat(),
            })
            return api

        # /tomar bloqueado aun con sesión activa stale y recovery label:
        # sin UUID de la sesión NO equivale a /recuperar.
        for actor in ("otro-agente", owner):
            with self.subTest(actor=actor):
                api = create_fixture()
                with self.assertRaisesRegex(
                    CoordinationError, "solo el titular con /recuperar"
                ):
                    reserve_work(api, 12, actor, "OWNER")
                self.assertEqual(api.comments[-1]["user"]["login"], BOT)
                self.assertEqual(api.branches[branch], "a" * 40)
                self.assertEqual(api.issue_data["labels"][-1]["name"],
                                 STATUS_RECOVERY)
                self.assertEqual(active_reservation(api, 12)["reservation_id"],
                                 SESSION_A)

        # /recuperar UUID desde otra identidad también se rechaza.
        api = create_fixture()
        with self.assertRaisesRegex(
            CoordinationError, "solo el titular con /recuperar"
        ):
            recover_work(api, 12, "otro-agente", "OWNER", SESSION_A)
        self.assertEqual(active_reservation(api, 12)["reservation_id"],
                         SESSION_A)

        # El titular con el UUID explícito conserva rama, PR y contrato.
        api = create_fixture()
        session = recover_work(api, 12, owner, "OWNER", SESSION_A)
        self.assertIsNotNone(session)
        self.assertNotEqual(session, SESSION_A)
        self.assertEqual(active_reservation(api, 12)["reservation_id"],
                         session)
        self.assertEqual(api.branches[branch], "a" * 40)

        # Una nota V3 con SHA discordante no permite recuperación.
        api = create_fixture()
        note = api.comments[-1]
        note["body"] = note["body"].replace("a" * 40, "b" * 40)
        with self.assertRaisesRegex(
            CoordinationError, "no coincide con la lease o rama"
        ):
            recover_work(api, 12, owner, "OWNER", SESSION_A)
        self.assertEqual(active_reservation(api, 12)["reservation_id"],
                         SESSION_A)


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



    def test_preview_boundary_inputs_are_fail_closed(self):
        """No elevar un dato reciente ni un decisor externo a permiso V3."""
        from datetime import tzinfo
        from unittest.mock import patch
        import json

        from scripts.lease_auto_release import Decision
        from scripts.lease_auto_release_integration import (
            preview_integrated_activity,
        )
        from test_lease_activity_collector import marker

        class NoTransport:
            def __getattr__(self, operation):
                raise AssertionError("unexpected transport " + operation)

        for invalid in (None, True, 0, -1, "21"):
            with self.subTest(issue=invalid):
                result = preview_integrated_activity(
                    API(), NoTransport(), invalid, now=NOW)
                self.assertEqual(result.reason, "invalid_issue")
                self.assertFalse(result.release_authorized)

        class MissingOffset(tzinfo):
            def utcoffset(self, dt):
                return None
            def dst(self, dt):
                return None

        for invalid in (None, NOW.replace(tzinfo=None),
                        NOW.replace(tzinfo=MissingOffset())):
            with self.subTest(now=invalid):
                result = preview_integrated_activity(
                    API(), NoTransport(), 21, now=invalid)
                self.assertEqual(result.reason, "invalid_clock")
                self.assertFalse(result.release_authorized)

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

        class ReadPort:
            def read(self, issue):
                if issue != 21:
                    raise AssertionError("unexpected issue")
                return item
            def __getattr__(self, operation):
                raise AssertionError("unexpected write " + operation)

        for forged, reason in (
            (Decision("release", "fake_authority"), "inactivity_not_proven"),
            (object(), "invalid_decision"),
        ):
            with self.subTest(decision=reason):
                with patch("scripts.lease_auto_release_integration."
                           "decision_from_snapshot", return_value=forged):
                    result = preview_integrated_activity(
                        api, ReadPort(), 21, now=NOW)
                    self.assertEqual(result.reason, reason)
                    self.assertFalse(result.release_authorized)

        class FailedPort:
            def read(self, issue):
                raise RuntimeError("private-token-would-leak")

        observed = preview_integrated_activity(api, FailedPort(), 21, now=NOW)
        self.assertEqual(observed.reason, "unverifiable_integration")
        self.assertNotIn("private-token", str(observed))
        self.assertFalse(observed.release_authorized)

        complete = collect_activity(api, 21, now=NOW)
        future = {**complete,
                  "last_activity_at": (NOW + timedelta(minutes=1))
                  .strftime("%Y-%m-%dT%H:%M:%SZ")}
        with patch("scripts.lease_auto_release_integration.collect_activity",
                   return_value=future):
            result = preview_integrated_activity(api, NoTransport(),
                                                 21, now=NOW)
        self.assertEqual(result.reason, "future_activity")
        self.assertFalse(result.release_authorized)


if __name__ == "__main__":
    unittest.main()
