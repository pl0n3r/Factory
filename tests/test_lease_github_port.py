"""Pruebas offline del futuro Port GitHub: observación != autoridad de release."""
import unittest
import json
from collections import UserString
from datetime import timedelta

from scripts.lease_auto_release_run import run_cycle
from scripts.lease_github_port import (
    GLOBAL_SWITCH, RECENT, UNKNOWN, LeaseGithubPort, PortNotArmed,
)
from scripts.unattended_kill_switch import (
    CANONICAL_REPOSITORY_URL, CANONICAL_SOURCE_URL,
)
from test_lease_activity_collector import API as ActivityAPI, NOW, SHA


class FakeAPI(ActivityAPI):
    """Solo GET; el switch global es siempre una URL absoluta fija."""

    def __init__(self):
        super().__init__()
        self.switch_body = (
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
        )
        self.switch_reads = 0
        self.pause_on_second = False
        self.fail_switch = False
        self.switch_state = "closed"
        self.omit_switch_state = False

    def request(self, method, path):
        assert method == "GET", "no autorizado a escribir"
        if path == GLOBAL_SWITCH:
            self.calls.append(path)
            self.switch_reads += 1
            if self.fail_switch:
                raise RuntimeError("secret-cannot-be-logged")
            if self.pause_on_second and self.switch_reads == 2:
                body = self.switch_body.replace("RUNNING", "PAUSED")
            else:
                body = self.switch_body
            result = {
                "number": 767,
                "state": self.switch_state,
                "url": CANONICAL_SOURCE_URL,
                "repository_url": CANONICAL_REPOSITORY_URL,
                "user": {"login": "pl0n3r"},
                "body": body,
            }
            if self.omit_switch_state:
                result.pop("state")
            return result
        result = super().request(method, path)
        if "/actions/runs?branch=" in path and isinstance(result, dict):
            for run in result.get("workflow_runs", []):
                if run["id"] == 8:
                    run["event"] = "push"
                    run["created_at"] = "2026-10-11T09:55:00Z"
        return result


class LeaseGithubPortTests(unittest.TestCase):
    def test_read_only_inspection_never_allows_caller_to_set_authority(self):
        from dataclasses import FrozenInstanceError, replace
        from scripts.lease_github_port import Inspection

        sample = Inspection(UNKNOWN, 21)
        self.assertIs(sample.release_authorized, False)
        with self.assertRaises(TypeError):
            Inspection(UNKNOWN, 21, release_authorized=True)
        with self.assertRaises(TypeError):
            replace(sample, release_authorized=True)
        with self.assertRaises(FrozenInstanceError):
            setattr(sample, "release_authorized", True)
        recent = LeaseGithubPort(FakeAPI()).inspect(21, now=NOW)
        self.assertEqual(recent.state, RECENT)
        self.assertIs(recent.release_authorized, False)

    def test_paginated_authenticated_recovery_note_is_read_only_and_fail_closed(self):
        from dataclasses import replace
        from scripts.aceptacion_kit import contract_fingerprint
        from scripts.orquestador_kit import task_marker_fingerprint
        from scripts.lease_release_executor import _note_ok
        from test_aceptacion_kit import issue_body
        from test_lease_release_executor import START, snapshot

        contract = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [{"id": "AC-01", "kind": "check", "target": "Tests de scripts"}],
        )
        # Un proof positivo necesita también el pin de factory-plan-task
        # del Issue real, no solo el contrato de aceptación.
        task = {
            "version": 1, "epic": 1191, "task_key": "LEASE_PROOF",
            "order": 1, "owner": "pl0n3r",
            "roles": ["ingenieria-software"],
            "depends_on": [], "paths": ["scripts/x.py"],
        }
        task_tag = "<!-- factory-plan-task " + json.dumps(task) + " -->"
        original = snapshot()
        target = replace(original, marker={
            **original.marker,
            "acceptance_sha256": contract_fingerprint(contract),
            "task_marker_sha256": task_marker_fingerprint(task),
        })
        payload = {
            "version": 1, "owner": target.owner,
            "reservation_id": target.reservation_id,
            "branch": target.branch, "branch_sha": target.branch_sha,
            "last_activity_at": target.last_activity_at.isoformat(),
            "acceptance_sha256": target.marker["acceptance_sha256"],
            "task_marker_sha256": target.marker["task_marker_sha256"],
        }

        class NoteAPI(FakeAPI):
            def __init__(self):
                super().__init__()
                self.repo = "pl0n3r/Factory"
                self.quota = 90
                self.branch_sha = target.branch_sha
                self.revision = "2026-10-11T10:32:00Z"
                self.notes = [
                    {
                        "id": 1, "user": {
                            "login": "github-actions[bot]", "type": "Bot",
                        },
                        "body": "<!-- condor-reserva " +
                                json.dumps(target.marker) + " -->",
                        "created_at": "2026-10-11T10:00:00Z",
                        "updated_at": "2026-10-11T10:00:00Z",
                    },
                    {
                        "id": 2, "user": {
                            "login": "github-actions[bot]", "type": "Bot",
                        },
                        "body": "<!-- factory-lease-recovery " +
                                json.dumps(payload) + " -->",
                        "created_at": "2026-10-11T10:30:00Z",
                        "updated_at": "2026-10-11T10:30:00Z",
                    },
                ]
                self.sentinel = []
                self.reject = None
                self.issue_reads = 0
                self.drift_labels = False
                self.drift_assignees = False
                self.bad_assignees = None
                self.bad_labels = None
                self.drift_issue_body = False
                self.omit_issue_body = False
                self.issue_body = contract + "\n" + task_tag
                self.comment_page_reads = 0
                self.drift_note_comment = False
                self.drift_marker_comment = False

            def request(self, method, path):
                assert method == "GET"
                if path == GLOBAL_SWITCH:
                    return super().request(method, path)
                self.calls.append(path)
                if path == self.reject:
                    raise RuntimeError("403 token or secret")
                if path == "/rate_limit":
                    return {"resources": {"core": {
                        "remaining": self.quota, "limit": 100,
                    }}}
                if path == "/repos/pl0n3r/Factory":
                    return {"id": 123, "full_name": self.repo}
                if path == "/repos/pl0n3r/Factory/issues/1191":
                    self.issue_reads += 1
                    # Mismo updated_at con nuevo titular o nueva etiqueta:
                    # el segundo GET debe invalidar el proof de la primera.
                    late = self.issue_reads > 1
                    return {
                        "number": 1191, "state": "open",
                        "comments": len(self.notes), "updated_at": self.revision,
                        **({} if self.omit_issue_body else {
                            "body": self.issue_body
                                    + (" cambiado-en-el-mismo-segundo"
                                       if late and self.drift_issue_body else ""),
                        }),
                        "assignees": (
                            self.bad_assignees if self.bad_assignees is not None
                            else [{"login": "intruder" if late and
                                   self.drift_assignees else target.owner}]),
                        "labels": (
                            self.bad_labels if self.bad_labels is not None
                            else [{"name": "estado: disponible" if late and
                                   self.drift_labels else target.status}]),
                    }
                if path == "/repos/pl0n3r/Factory/git/ref/heads/trabajo/issue-1191":
                    return {"object": {"sha": self.branch_sha}}
                if path.endswith("/comments?per_page=100&page=1"):
                    self.comment_page_reads += 1
                    if self.comment_page_reads > 1 and (
                            self.drift_note_comment or self.drift_marker_comment):
                        copied = [dict(row) for row in self.notes]
                        changed = 0 if self.drift_marker_comment else -1
                        copied[changed]["body"] += " edited_same_timestamp"
                        return copied
                    return self.notes
                if path.endswith("/comments?per_page=100&page=2"):
                    return self.sentinel
                raise AssertionError("unexpected GET")

        api = NoteAPI()
        port = LeaseGithubPort(api)
        proof = port.recovery_note(1191, target)
        self.assertTrue(proof.complete)
        self.assertTrue(proof.authenticated)
        self.assertEqual(proof.count, 1)
        self.assertTrue(_note_ok(proof, target))
        self.assertEqual(api.switch_reads, 2)
        self.assertEqual(api.comment_page_reads, 2)
        # Dos GET de #767 cuentan en el presupuesto, aunque no se
        # incluyan en la lista de endpoints de la prueba original.
        exact_floor = NoteAPI()
        exact_floor.quota = 32
        self.assertTrue(LeaseGithubPort(exact_floor).recovery_note(
            1191, target).authenticated)
        self.assertEqual(exact_floor.switch_reads, 2)
        # Un proof compuesto con GETs previos al método debe consumir cuota
        # compartida. Antes del fix, los 12 GET locales dejaban 20/100,
        # ignorando los 9 GET ya consumidos; el estado era falsamente apto.
        cumulative_floor = NoteAPI()
        cumulative_floor.quota = 32
        shared = [9]
        with self.assertRaisesRegex(
            PortNotArmed, "authenticated_recovery_proof_unavailable"):
            LeaseGithubPort(cumulative_floor).recovery_note(
                1191, target, _budget=shared)
        self.assertGreater(shared[0], 9)
        self.assertEqual(cumulative_floor.switch_reads, 2)
        # Los cambios periféricos no alteran el contrato fijado.
        peripheral = NoteAPI()
        peripheral.issue_body = peripheral.issue_body.replace(
            "Contexto verificable.", "Contexto verificable con nota adicional.")
        self.assertTrue(LeaseGithubPort(peripheral).recovery_note(1191, target).authenticated)
        self.assertTrue(all(path.startswith("/repos/") or path == "/rate_limit"
                            for path in api.calls))
        self.assertTrue(all(type(path) is str for path in api.calls))
        with self.assertRaises(PortNotArmed):
            port.read(1191)
        with self.assertRaises(PortNotArmed):
            port.lock("factory-coordination-123")
        with self.assertRaises(PortNotArmed):
            port.append(1191, "forbidden", target)
        with self.assertRaises(PortNotArmed):
            port.status(1191, "estado: disponible", target)

        missing = NoteAPI()
        missing.notes = missing.notes[:1]
        empty = LeaseGithubPort(missing).recovery_note(1191, target)
        self.assertEqual(empty.count, 0)
        self.assertTrue(_note_ok(empty, target))

        # Una marca terminal previa para el MISMO UUID no puede revivir
        # con un marker active:true más nuevo. Tampoco se permiten pins
        # distintos en comentarios de la misma reserva, aunque la nota
        # actual y el último marker concuerden.
        def same_uuid_history(kind):
            api = NoteAPI()
            first = dict(api.notes[0], id=1)
            middle_marker = dict(target.marker)
            if kind == "resurrected":
                middle_marker.update(
                    active=False, reason="auto-inactivity-release")
            elif kind == "pin_changed":
                middle_marker["task_marker_sha256"] = "e" * 64
            else:
                raise AssertionError("unsupported_history")
            middle = {
                **api.notes[0], "id": 2,
                "body": "<!-- condor-reserva " +
                        json.dumps(middle_marker) + " -->",
            }
            latest = dict(api.notes[0], id=3)
            note = dict(api.notes[1], id=4)
            api.notes = [first, middle, latest, note]
            return api

        for history in ("resurrected", "pin_changed"):
            with self.subTest(reused_uuid=history):
                sample = same_uuid_history(history)
                with self.assertRaisesRegex(
                    PortNotArmed, "authenticated_recovery_proof_unavailable"
                ):
                    LeaseGithubPort(sample).recovery_note(1191, target)
                self.assertEqual(sample.switch_reads, 1)
                self.assertTrue(all(
                    call == "/rate_limit" or call.startswith("/repos/")
                    for call in sample.calls))

        # /tomar crea una reserva nueva conservando las notas históricas.
        # La evidencia del UUID vigente no debe confundirse con la anterior.
        def recovered_issue():
            api = NoteAPI()
            old_uuid = "6f5b9b7e-e6a3-4dcc-87af-b37be0f65e23"
            old_marker = {
                **target.marker, "reservation_id": old_uuid,
                "acceptance_sha256": "e" * 64,
                "task_marker_sha256": "f" * 64,
            }
            old_note = {
                **payload, "reservation_id": old_uuid,
                "branch_sha": "d" * 40,
                "last_activity_at": "2026-10-11T09:30:00+00:00",
                "acceptance_sha256": old_marker["acceptance_sha256"],
                "task_marker_sha256": old_marker["task_marker_sha256"],
            }
            old_marker_comment = {
                **api.notes[0], "id": 1,
                "body": "<!-- condor-reserva " +
                        json.dumps(old_marker) + " -->",
            }
            old_note_comment = {
                **api.notes[1], "id": 2,
                "body": "<!-- factory-lease-recovery " +
                        json.dumps(old_note) + " -->",
                "created_at": "2026-10-11T10:05:00Z",
                "updated_at": "2026-10-11T10:05:00Z",
            }
            new_marker_comment = {
                **api.notes[0], "id": 3,
                "created_at": "2026-10-11T10:15:00Z",
                "updated_at": "2026-10-11T10:15:00Z",
            }
            new_note_comment = {**api.notes[1], "id": 4}
            api.notes = [old_marker_comment, old_note_comment,
                         new_marker_comment, new_note_comment]
            return api

        previous = recovered_issue()
        current = LeaseGithubPort(previous).recovery_note(1191, target)
        self.assertEqual(current.count, 1)
        self.assertTrue(_note_ok(current, target))
        self.assertEqual(previous.comment_page_reads, 2)

        def released_prior_lease():
            # El bot publicó un marker terminal para la reserva anterior,
            # después de la nota que acredita esa misma lease.
            api = recovered_issue()
            old_payload = json.loads(
                api.notes[0]["body"].split(
                    "<!-- condor-reserva ", 1)[1].split(" -->", 1)[0])
            terminal = {
                **old_payload,
                "active": False,
                "reason": "auto-inactivity-release",
            }
            api.notes.insert(2, {
                **api.notes[0],
                "id": 3,
                "body": "<!-- condor-reserva " +
                        json.dumps(terminal) + " -->",
                "created_at": "2026-10-11T10:10:00Z",
                "updated_at": "2026-10-11T10:10:00Z",
            })
            api.notes[3]["id"] = 4
            api.notes[4]["id"] = 5
            return api

        terminal = released_prior_lease()
        verified = LeaseGithubPort(terminal).recovery_note(1191, target)
        self.assertEqual(verified.count, 1)
        self.assertTrue(_note_ok(verified, target))
        stale_terminal = released_prior_lease()
        stale_terminal.notes[2]["body"] = (
            stale_terminal.notes[2]["body"].replace(
                '"task_marker_sha256": "' + "f" * 64,
                '"task_marker_sha256": "' + "a" * 64))
        with self.assertRaises(PortNotArmed):
            LeaseGithubPort(stale_terminal).recovery_note(1191, target)

        no_current = recovered_issue()
        no_current.notes.pop()
        self.assertEqual(LeaseGithubPort(no_current).recovery_note(
            1191, target).count, 0)

        def reject_historical(change):
            api = recovered_issue()
            change(api)
            with self.assertRaisesRegex(
                PortNotArmed, "authenticated_recovery_proof_unavailable"
            ):
                LeaseGithubPort(api).recovery_note(1191, target)

        for change in (
            lambda x: x.notes.pop(0),  # nota antigua sin marker V3
            lambda x: x.notes[1].update(id=5),  # nota antigua posterior
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"].replace('"branch_sha": "'
                    + "d" * 40, '"branch_sha": "invalid')),
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"].replace('"acceptance_sha256": "'
                    + "e" * 64, '"acceptance_sha256": "' + "f" * 64)),
            lambda x: x.notes[1]["user"].update(login="untrusted"),
            lambda x: x.notes[2].update(
                body=x.notes[2]["body"].replace(
                    target.reservation_id, "baea9951-9670-401f-81f2-4fb89a4f1f74")),
        ):
            with self.subTest(historical=str(change)):
                reject_historical(change)

        def tampered_case(modifier):
            variant = NoteAPI()
            modifier(variant)
            with self.assertRaisesRegex(
                PortNotArmed, "authenticated_recovery_proof_unavailable"
            ) as caught:
                LeaseGithubPort(variant).recovery_note(1191, target)
            self.assertNotIn("secret", str(caught.exception))
            self.assertTrue(all(path.startswith("/repos/") or path == "/rate_limit"
                                for path in variant.calls))
            return variant

        cases = (
            # Los datos JSON de GitHub deben tener type="Bot" como str
            # auténtico, no un objeto que solo compare igual.
            lambda x: x.notes[0]["user"].update(
                type=UserString(x.notes[0]["user"]["type"])),
            lambda x: x.notes[1]["user"].update(
                type=UserString(x.notes[1]["user"]["type"])),
            lambda x: x.notes[1]["user"].update(login="counterfeit"),
            lambda x: x.notes[1].update(updated_at="2026-10-11T10:31:00Z"),
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"].replace(
                    target.branch_sha, "e" * 40)),
            lambda x: x.notes.append(dict(x.notes[1], id=3)),
            lambda x: x.notes.append(dict(x.notes[0], id=1)),
            lambda x: x.notes[1].update(
                created_at="2026-10-11T10:29:00Z",
                updated_at="2026-10-11T10:29:00Z"),
            lambda x: setattr(x, "sentinel", [{"id": 3}]),
            lambda x: setattr(x, "quota", 19),
            lambda x: setattr(x, "quota", 31),  # 10 GET + 2 de #767 = 19 %
            lambda x: setattr(x, "branch_sha", "f" * 40),
            lambda x: setattr(x, "reject",
                "/repos/pl0n3r/Factory/issues/1191/comments?per_page=100&page=1"),
            lambda x: setattr(x, "pause_on_second", True),
            lambda x: setattr(x, "switch_state", "open"),
            lambda x: setattr(x, "drift_labels", True),
            lambda x: setattr(x, "drift_assignees", True),
            # Una etiqueta válida no puede ocultar otra etiqueta corrupta,
            # ni un subtype str hacerse pasar por login JSON auténtico.
            lambda x: setattr(x, "bad_labels", [
                {"name": target.status}, {"name": None}]),
            lambda x: setattr(x, "bad_labels", [
                {"name": target.status}, {"name": "tipo: producto"},
                {"name": "tipo: producto"}]),
            lambda x: setattr(x, "bad_labels", [
                {"name": target.status}, {"name": "TIPO: PRODUCTO"},
                {"name": "tipo: producto"}]),
            lambda x: setattr(x, "bad_labels", [
                {"name": target.status},
                {"name": "ESTADO: reservado"}]),
            lambda x: setattr(x, "bad_labels", [
                {"name": target.status}, "unexpected-string-label"]),
            lambda x: setattr(x, "bad_assignees", [
                {"login": UserString(target.owner)}]),
            lambda x: setattr(x, "drift_issue_body", True),
            lambda x: setattr(x, "omit_issue_body", True),
            lambda x: setattr(x, "issue_body", x.issue_body.replace(
                "Debe pasar.", "Debe pasar sin revisar.")),
            lambda x: setattr(x, "issue_body", x.issue_body.replace(
                "factory-acceptance", "marker-invalido")),
            # Ningún cambio del plan puede conservar el pin V3 en el Port:
            # AC-03 exige identidad de claims además del UUID y SHA.
            lambda x: setattr(x, "issue_body", x.issue_body.replace(
                '"task_key": "LEASE_PROOF"', '"task_key": "LEASE_DRIFT"')),
            lambda x: setattr(x, "issue_body", x.issue_body.replace(
                "<!-- factory-plan-task ", "<!-- invalid-plan-task ")),
            lambda x: setattr(x, "issue_body", x.issue_body + "\n" + task_tag),
            # Un JSON duplicado con valor idéntico puede conservar la
            # huella semántica; el Port debe rechazarlo igual.
            lambda x: setattr(x, "issue_body", x.issue_body.replace(
                '"task_key": "LEASE_PROOF"',
                '"task_key": "LEASE_PROOF", "task_key": "LEASE_PROOF"')),
            lambda x: setattr(x, "issue_body", x.issue_body +
                "\n<!-- FACTORY-PLAN-TASK {"),
            lambda x: setattr(x, "issue_body", x.issue_body +
                "\n<!-- factory-plan-task {"),
            lambda x: setattr(x, "issue_body", x.issue_body.replace(
                '<!-- factory-plan-task ', '<!-- FACTORY-PLAN-TASK ')),
            lambda x: setattr(x, "drift_note_comment", True),
            lambda x: setattr(x, "drift_marker_comment", True),
            lambda x: x.notes[0].update(body="spoofed bot marker"),
            # El parser compartido tolera JSON duplicate keys por defecto;
            # el Port autenticado no debe aceptarlas ni omitir encabezados.
            lambda x: x.notes[0].update(
                body=x.notes[0]["body"].replace(
                    '"owner": "' + target.owner + '"',
                    '"owner": "' + target.owner + '", '
                    '"owner": "' + target.owner + '"')),
            lambda x: x.notes[0].update(
                body=x.notes[0]["body"] + "\n" + x.notes[0]["body"]),
            lambda x: x.notes[0].update(
                body=x.notes[0]["body"] + "\n<!-- CONDOR-RESERVA {"),
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"] + "\n" + x.notes[1]["body"]),
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"] +
                     "\n<!-- FACTORY-LEASE-RECOVERY {"),
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"] +
                     "\n<!-- factory-lease-recovery {"),
            lambda x: x.notes[1].update(
                body=x.notes[1]["body"].replace(
                    '"version": 1', '"version": 1, "version": 1')),
        )
        for index, change in enumerate(cases):
            with self.subTest(case=index):
                tampered_case(change)

    def test_recovery_timeline_get_only_double_read_and_fail_closed(self):
        from unittest.mock import patch
        from test_lease_release_executor import START, snapshot
        from scripts.lease_release_executor import (
            RecoveryNoteProof, _recovery_label_ok,
        )

        s = snapshot()
        note = RecoveryNoteProof(
            complete=True, authenticated=True, count=1,
            owner=s.owner, reservation_id=s.reservation_id,
            branch=s.branch, branch_sha=s.branch_sha,
            last_activity_at=s.last_activity_at,
            acceptance_sha256=s.marker["acceptance_sha256"],
            task_marker_sha256=s.marker["task_marker_sha256"],
            created_at=START + timedelta(minutes=30),
            author="github-actions[bot]",
        )
        event = {
            "id": 14, "event": "labeled",
            "label": {"name": "estado: requiere recuperación"},
            "actor": {"login": "github-actions[bot]", "type": "Bot"},
            "created_at": "2026-10-11T10:30:00Z",
        }
        class TimelineAPI:
            repo = "pl0n3r/Factory"
            def __init__(self):
                self.rows = [event]
                self.sentinel = []
                self.calls = []
                self.fail = False
                self.race = False
                self.round = 0
            def request(self, verb, path):
                if verb != "GET":
                    raise AssertionError("write forbidden")
                self.calls.append((verb, path))
                if self.fail:
                    raise RuntimeError("403 secret must never leak")
                if path.endswith("page=1"):
                    self.round += 1
                    if self.race and self.round > 1:
                        return [{**event, "id": 15}]
                    return self.rows
                if path.endswith("page=2"):
                    return self.sentinel
                raise AssertionError("unexpected endpoint")

        api = TimelineAPI()
        port = LeaseGithubPort(api)
        with patch.object(port, "recovery_note", return_value=note) as read_note:
            proof = port.recovery_label(1191, s)
        self.assertTrue(_recovery_label_ok(note, proof, s))
        self.assertEqual(read_note.call_count, 2)
        self.assertEqual(len(api.calls), 4)
        self.assertTrue(all(verb == "GET" for verb, _ in api.calls))
        # Prueba compuesta: dos notas y el timeline consumen un solo
        # presupuesto de 32 GET (incluidas lecturas #767 autenticadas).
        metered = TimelineAPI()
        guarded = LeaseGithubPort(metered)
        shared_budgets = []
        def expensive_note(_issue, _expected, *, _budget):
            shared_budgets.append(id(_budget))
            _budget[0] += 15
            return note
        with patch.object(guarded, "recovery_note",
                          side_effect=expensive_note) as reads:
            with self.assertRaisesRegex(
                PortNotArmed, "authenticated_timeline_proof_unavailable"):
                guarded.recovery_label(1191, s)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(len(set(shared_budgets)), 1)
        self.assertEqual(len(metered.calls), 4)
        self.assertTrue(all(verb == "GET" for verb, _ in metered.calls))

        self.assertTrue(all("/repos/pl0n3r/Factory/issues/1191/events?"
                            in path for _, path in api.calls))
        with self.assertRaises(PortNotArmed):
            port.lock("factory-coordination-123")
        with self.assertRaises(PortNotArmed):
            port.status(1191, "estado: disponible", s)

        def rejected(change, override=None):
            fake = TimelineAPI()
            change(fake)
            local = LeaseGithubPort(fake)
            with patch.object(local, "recovery_note",
                              return_value=note if override is None else override):
                with self.assertRaisesRegex(
                    PortNotArmed, "authenticated_timeline_proof_unavailable"
                ) as cm:
                    local.recovery_label(1191, s)
            self.assertNotIn("secret", str(cm.exception))
            self.assertTrue(all(verb == "GET" for verb, _ in fake.calls))

        variants = (
            lambda x: setattr(x, "rows", []),
            lambda x: setattr(x, "rows", [{**event, "id": 14},
                                            {**event, "id": 14}]),
            lambda x: setattr(x, "rows", [event, {**event, "id": 16}]),
            lambda x: setattr(x, "rows", [{**event, "actor": {
                "login": "intruder", "type": "User"}}]),
            lambda x: setattr(x, "rows", [{**event, "actor": {
                **event["actor"],
                "login": UserString(event["actor"]["login"])}}]),
            lambda x: setattr(x, "rows", [{**event, "actor": {
                **event["actor"],
                "type": UserString(event["actor"]["type"])}}]),
            lambda x: setattr(x, "rows", [{**event, "event": "unlabeled"}]),
            lambda x: setattr(x, "rows", [{**event,
                "created_at": "2026-10-11T10:29:00Z"}]),
            lambda x: setattr(x, "rows", [{**event,
                "created_at": "2026-10-11T10:42:00Z"}]),
            lambda x: setattr(x, "rows", [{**event, "label": {
                "name": "estado: reservado"}}]),
            lambda x: setattr(x, "sentinel", [{**event, "id": 17}]),
            lambda x: setattr(x, "fail", True),
            lambda x: setattr(x, "race", True),
        )
        for index, change in enumerate(variants):
            with self.subTest(case=index):
                rejected(change)
        rejected(lambda x: None, override=RecoveryNoteProof(
            **{**note.__dict__, "authenticated": False}
        ))

    def test_recovery_timeline_real_page_boundary_and_second_read_race(self):
        """Los eventos 101+ requieren todas las páginas, no solo la primera."""
        from unittest.mock import patch
        from test_lease_release_executor import START, snapshot
        from scripts.lease_release_executor import (
            RecoveryNoteProof, _recovery_label_ok,
        )
        target = snapshot()
        note = RecoveryNoteProof(
            complete=True, authenticated=True, count=1,
            owner=target.owner, reservation_id=target.reservation_id,
            branch=target.branch, branch_sha=target.branch_sha,
            last_activity_at=target.last_activity_at,
            acceptance_sha256=target.marker["acceptance_sha256"],
            task_marker_sha256=target.marker["task_marker_sha256"],
            created_at=START + timedelta(minutes=30),
            author="github-actions[bot]",
        )
        recover = {
            "id": 101, "event": "labeled",
            "label": {"name": "estado: requiere recuperación"},
            "actor": {"login": "github-actions[bot]", "type": "Bot"},
            "created_at": "2026-10-11T10:30:00Z",
        }

        class PaginatedAPI:
            repo = "pl0n3r/Factory"
            def __init__(self):
                self.events = [{"id": n, "event": "renamed"}
                               for n in range(1, 101)] + [recover]
                self.calls = []
                self.drift = False
                self.page_one_reads = 0
                self.reject = None
                self.short_page = False
                self.sentinel_nonempty = False

            def request(self, verb, path):
                assert verb == "GET"
                self.calls.append(path)
                if path == self.reject:
                    raise RuntimeError("403 secret never printed")
                page = int(path.rsplit("page=", 1)[-1])
                if page == 1:
                    self.page_one_reads += 1
                part = self.events[(page - 1) * 100:page * 100]
                if self.short_page and page == 1:
                    return part[:99]
                if self.sentinel_nonempty and page == 3:
                    return [{"id": 102, "event": "renamed"}]
                if self.drift and self.page_one_reads >= 2 and page == 2:
                    return [{**recover, "id": 102}]
                return part

        api = PaginatedAPI()
        port = LeaseGithubPort(api)
        with patch.object(port, "recovery_note", return_value=note) as read:
            proof = port.recovery_label(target.issue, target)
        self.assertTrue(_recovery_label_ok(note, proof, target))
        self.assertEqual(read.call_count, 2)
        self.assertEqual(api.page_one_reads, 2)
        self.assertEqual([path[-6:] for path in api.calls],
                         ["page=1", "page=2", "page=3"] * 2)

        for fault in ("truncated_first_page", "duplicate_id",
                      "nonempty_sentinel", "race_second_page", "api_403"):
            with self.subTest(fault=fault):
                api = PaginatedAPI()
                if fault == "truncated_first_page":
                    api.short_page = True
                elif fault == "duplicate_id":
                    api.events[-1] = {**recover, "id": 100}
                elif fault == "nonempty_sentinel":
                    api.sentinel_nonempty = True
                elif fault == "race_second_page":
                    api.drift = True
                elif fault == "api_403":
                    api.reject = (
                        "/repos/pl0n3r/Factory/issues/1191/events?"
                        "per_page=100&page=2"
                    )
                port = LeaseGithubPort(api)
                with patch.object(port, "recovery_note", return_value=note):
                    with self.assertRaisesRegex(
                        PortNotArmed, "authenticated_timeline_proof_unavailable"
                    ) as e:
                        port.recovery_label(target.issue, target)
                self.assertNotIn("secret", str(e.exception))
                self.assertTrue(all("/issues/1191/events?" in path
                                    for path in api.calls))

    def test_canonical_switch_and_recent_activity_never_authorize_release(self):
        api = FakeAPI()
        port = LeaseGithubPort(api)
        result = port.inspect(21, now=NOW)
        self.assertEqual(result.state, RECENT)
        self.assertFalse(result.release_authorized)
        self.assertEqual(result.issue, 21)
        self.assertEqual(result.lease_id,
                         "e33f1859-0304-4fa8-8ce3-776de22c9707")
        self.assertEqual(result.branch_sha, SHA)
        self.assertEqual(result.last_activity_at, "2026-10-11T09:55:00Z")
        self.assertEqual(result.libera_en_min, 35)
        self.assertFalse(result.release_authorized)
        self.assertEqual(api.switch_reads, 2)
        self.assertEqual(api.calls[0], GLOBAL_SWITCH)
        self.assertEqual(api.calls[-1], GLOBAL_SWITCH)
        self.assertTrue(all(p == "/rate_limit" or
                            p.startswith("/repos/") for p in api.calls))

        # Incluso una habilitación errónea desde el caller no consigue escribir:
        # falta la prueba de AUSENCIA de actividad + CAS compartido auténtico.
        report = run_cycle(
            [21], port, feature_enabled=True, dry_run=False,
            mutations_authorized=True,
        )
        self.assertEqual(report.results[0][1].action, UNKNOWN.lower())
        self.assertFalse(report.results[0][1].wrote)
        self.assertEqual(report.results[0][1].write_state, "unknown")
        self.assertTrue(all(p == "/rate_limit" or
                            p.startswith("/repos/") for p in api.calls))

    def test_reopened_missing_or_invalid_global_switch_state_fails_closed(self):
        for state in ("open", None, True, "CLOSED"):
            with self.subTest(state=state):
                api = FakeAPI()
                api.switch_state = state
                result = LeaseGithubPort(api).inspect(21, now=NOW)
                self.assertEqual(result.state, UNKNOWN)
                self.assertFalse(result.release_authorized)
                self.assertEqual(api.switch_reads, 1)
                self.assertEqual(api.calls, [GLOBAL_SWITCH])

        api = FakeAPI()
        api.omit_switch_state = True
        missing = LeaseGithubPort(api).inspect(21, now=NOW)
        self.assertEqual(missing.state, UNKNOWN)
        self.assertFalse(missing.release_authorized)
        self.assertEqual(api.calls, [GLOBAL_SWITCH])

        class ReopeningAPI(FakeAPI):
            def request(self, method, path):
                if path == GLOBAL_SWITCH and self.switch_reads == 1:
                    self.switch_state = "open"
                return super().request(method, path)

        racing = ReopeningAPI()
        observed = LeaseGithubPort(racing).inspect(21, now=NOW)
        self.assertEqual(observed.state, UNKNOWN)
        self.assertFalse(observed.release_authorized)
        self.assertEqual(racing.switch_reads, 2)

    def test_global_pause_invalid_json_and_recheck_race_fail_closed(self):
        for marker in (
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"PAUSED","state":"RUNNING",'
            '"owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch '
            '{"version":1,"state":"RUNNING","owner":"other",'
            '"owner":"pl0n3r"} -->',
            '<!-- factory-unattended-kill-switch invalid -->',
            "",
        ):
            with self.subTest(marker=marker[:30]):
                api = FakeAPI()
                api.switch_body = marker
                result = LeaseGithubPort(api).inspect(21, now=NOW)
                self.assertEqual(result.state, UNKNOWN)
                self.assertFalse(result.release_authorized)
                self.assertEqual(api.switch_reads, 1)
        api = FakeAPI()
        api.pause_on_second = True
        self.assertEqual(LeaseGithubPort(api).inspect(21, now=NOW).state,
                         UNKNOWN)
        self.assertEqual(api.switch_reads, 2)
        self.assertEqual(LeaseGithubPort(FakeAPI()).inspect(True, now=NOW).state,
                         UNKNOWN)

    def test_partial_pages_403_429_and_race_fail_closed_without_release(self):
        cases = []
        a = FakeAPI(); a.fail_switch = True; cases.append(a)
        a = FakeAPI(); a.block = "/issues/21/comments"; cases.append(a)
        a = FakeAPI(); a.remaining = 19; cases.append(a)
        a = FakeAPI(); a.issue["comments"] = 500; cases.append(a)
        a = FakeAPI(); a.runs_count_override = 2; cases.append(a)
        a = FakeAPI(); a.race = True; cases.append(a)
        a = FakeAPI(); a.repo_id = None; cases.append(a)
        a = FakeAPI(); a.comments[0]["user"]["type"] = "User"; cases.append(a)
        a = FakeAPI(); a.checks[0]["head_sha"] = "b" * 40; cases.append(a)
        for index, api in enumerate(cases):
            with self.subTest(case=index):
                observed = LeaseGithubPort(api).inspect(21, now=NOW)
                self.assertEqual(observed.state, UNKNOWN)
                self.assertFalse(observed.release_authorized)
                self.assertIsNone(observed.lease_id)
                self.assertIsNone(observed.libera_en_min)
                self.assertTrue(all(p == "/rate_limit" or
                                    p.startswith("/repos/") for p in api.calls))
                self.assertNotIn("secret-cannot-be-logged", str(observed))
                # Even deliberately forcing every caller-level mutation switch
                # cannot override the Port's read/lock/append denial.
                unsafe_attempt = run_cycle(
                    [21], LeaseGithubPort(api), feature_enabled=True,
                    dry_run=False, mutations_authorized=True,
                )
                self.assertEqual(unsafe_attempt.results[0][1].action, "unknown")
                self.assertFalse(unsafe_attempt.results[0][1].wrote)
                self.assertEqual(unsafe_attempt.results[0][1].write_state, "unknown")

    def test_report_boundary_never_accepts_stale_or_spoofed_fields(self):
        from unittest.mock import patch
        from scripts.lease_activity_collector import collect_activity

        baseline = collect_activity(FakeAPI(), 21, now=NOW)
        self.assertTrue(baseline["evidence_complete"])
        # Positive control: authenticated collector payload and bounded time.
        with patch("scripts.lease_github_port.collect_activity",
                   return_value=baseline):
            accepted = LeaseGithubPort(FakeAPI()).inspect(21, now=NOW)
        self.assertEqual(accepted.state, RECENT)
        self.assertFalse(accepted.release_authorized)

        # La segunda lectura canónica de #767 también cuesta una petición:
        # 21/100 antes de ella termina en 20/100; 20/100 cae a 19/100.
        at_boundary = dict(baseline, rate_limit=100, rate_remaining=21)
        boundary_transport = FakeAPI()
        with patch("scripts.lease_github_port.collect_activity",
                   return_value=at_boundary):
            verified = LeaseGithubPort(boundary_transport).inspect(21, now=NOW)
        self.assertEqual(verified.state, RECENT)
        self.assertEqual(boundary_transport.switch_reads, 2)

        bad_fields = (
            ("status", UserString("estado: en revisión")),
            ("repo", UserString("pl0n3r/Factory")),
            ("branch", UserString("trabajo/issue-21")),
            ("repo", "other/repository"),
            ("status", "estado: disponible"),
            ("status", True),
            ("evidence_complete", 1),
            ("issue_number", True),
            ("repository_id", 0),
            ("owner", ""),
            ("branch", "trabajo/issue-999"),
            ("lease_id", "not-a-uuid"),
            ("branch_sha", "b" * 40 + "extra"),
            ("ci_running", 0),
            ("rate_limit", 0),
            ("rate_remaining", 19),
            ("rate_remaining", 20),  # El último GET #767 baja al 19 %.
            ("rate_remaining", True),
            ("api_requests", 33),
            ("pagination", []),
            ("last_activity_at", "2026-10-11T09:29:00Z"),
            ("last_activity_at", "2026-10-11T10:01:00Z"),
            ("last_activity_at", "2026-10-11T09:55:00+00:00"),
            ("last_activity_at", "2026-10-11T09:55:00Z\\Z"),
            ("last_activity_at", "not-a-clock"),
        )
        for field, value in bad_fields:
            with self.subTest(field=field, value=str(value)[:24]):
                invalid = dict(baseline)
                invalid[field] = value
                transport = FakeAPI()
                with patch("scripts.lease_github_port.collect_activity",
                           return_value=invalid):
                    observed = LeaseGithubPort(transport).inspect(21, now=NOW)
                self.assertEqual(observed.state, UNKNOWN)
                self.assertFalse(observed.release_authorized)
                self.assertEqual(transport.switch_reads, 1)

        # A malformed collector response never inherits release authority.
        for invalid in (None, [], "verified", {"status": "RECENT_ACTIVITY"}):
            with self.subTest(payload=str(invalid)[:22]):
                with patch("scripts.lease_github_port.collect_activity",
                           return_value=invalid):
                    result = LeaseGithubPort(FakeAPI()).inspect(21, now=NOW)
                self.assertEqual(result.state, UNKNOWN)

    def test_authenticated_cas_and_canonical_bot_marker(self):
        import base64
        import copy
        from dataclasses import replace
        from scripts.lease_release_executor import (
            AVAILABLE, RECOVERY, _release_marker, _trusted,
        )
        from scripts.orquestador_kit import task_marker_fingerprint

        task = {
            "version": 1, "epic": 1175, "task_key": "LEASE_CAS",
            "order": 1, "owner": "pl0n3r",
            "roles": ["ingenieria-software"],
            "depends_on": [], "paths": ["scripts/x.py"],
        }
        body = "### Contexto\nsintético\n<!-- factory-plan-task " + json.dumps(task) + " -->"
        marker = json.loads(self._marker_json(task_marker_fingerprint(task)))

        class WriteAPI(FakeAPI):
            authenticated = True

            def __init__(self):
                super().__init__()
                self.issue["body"] = body
                self.checks[0]["status"] = "completed"
                self.issue["labels"] = [{"name": "estado: reservado"},
                                        {"name": "prioridad: alta"}]
                self.comments[0]["body"] = "<!-- condor-reserva " + json.dumps(marker) + " -->"
                self.writes = []

            def request(self, method, path, payload=None):
                if method in ("POST", "PATCH"):
                    self.writes.append((method, path, copy.deepcopy(payload)))
                    if method == "POST":
                        self.comments.append({
                            "id": 100 + len(self.writes),
                            "user": {"login": "github-actions[bot]", "type": "Bot"},
                            "body": payload["body"],
                            "created_at": "2026-10-11T09:56:00Z"})
                    else:
                        self.issue["labels"] = [{"name": n} for n in payload["labels"]]
                    return {}
                assert method == "GET", "solo GET/POST/PATCH acotados"
                if path == "/repos/pl0n3r/Factory/contents/datos.yml":
                    return {"encoding": "base64", "content": base64.b64encode(
                        b'{"phase":"construccion"}').decode()}
                result = super().request("GET", path)
                if path == "/repos/pl0n3r/Factory/issues/21":
                    result["comments"] = len(self.comments)
                return result

        group = "factory-coordination-123"
        # Sin armar (valor por defecto) nada escribe ni pasa por el lock.
        quiet = WriteAPI()
        for call in (lambda: LeaseGithubPort(quiet).lock(group),
                     lambda: LeaseGithubPort(quiet).append(21, "x", None),
                     lambda: LeaseGithubPort(quiet).status(21, RECOVERY, None)):
            with self.assertRaises(PortNotArmed):
                call()
        self.assertEqual(quiet.writes, [])

        api = WriteAPI()
        port = LeaseGithubPort(api, armed=True, concurrency_group=group,
                               clock=lambda: NOW)
        # Lock compartido: sólo el grupo de Coordinación de ESTE repositorio.
        with port.lock(group):
            pass
        for other in ("factory-coordination-999", "otro-grupo"):
            with self.assertRaises(PortNotArmed):
                port.lock(other)
        with self.assertRaises(PortNotArmed):
            LeaseGithubPort(api, armed=True, concurrency_group="otro",
                            clock=lambda: NOW).lock(group)

        snap = port.read(21)
        self.assertTrue(_trusted(snap, allow_partial=True))
        self.assertEqual((snap.reservation_id, snap.branch_sha, snap.status),
                         (marker["reservation_id"], SHA, "estado: reservado"))

        # CAS: UUID, SHA, marker/pin o estado distintos no escriben.
        bad_marker = {**snap.marker, "task_marker_sha256": "e" * 64}
        stale = (
            replace(snap, reservation_id="11111111-1111-4111-8111-111111111111"),
            replace(snap, branch_sha="c" * 40),
            replace(snap, marker=bad_marker),
            replace(snap, status=RECOVERY),
            replace(snap, fingerprint="f" * 64),
        )
        for expected in stale:
            with self.subTest(expected=expected.fingerprint[:4]):
                with self.assertRaises(PortNotArmed):
                    port.append(21, _release_marker(snap), expected)
                with self.assertRaises(PortNotArmed):
                    port.status(21, RECOVERY, expected)
        self.assertEqual(api.writes, [])

        # Sólo el marker canónico active:false o la nota de recuperación.
        forged = _release_marker(replace(snap, marker={**snap.marker,
                                                         "reservation_id": "x"}))
        for text in ("texto libre", forged,
                     _release_marker(snap).replace("auto-inactivity-release", "tomar")):
            with self.assertRaises(PortNotArmed):
                port.append(21, text, snap)
        self.assertEqual(api.writes, [])

        # No se libera sin marker inactivo ni desde un estado no RECOVERY.
        with self.assertRaises(PortNotArmed):
            port.status(21, AVAILABLE, snap)
        with self.assertRaises(PortNotArmed):
            port.status(21, "estado: completado", snap)
        self.assertEqual(api.writes, [])

        # Escritura permitida: comentario canónico, luego lectura autenticada.
        port.append(21, _release_marker(snap), snap)
        self.assertEqual([w[:2] for w in api.writes],
                         [("POST", "/repos/pl0n3r/Factory/issues/21/comments")])
        after = port.read(21)
        self.assertIs(after.marker["active"], False)
        self.assertEqual(after.marker["reason"], "auto-inactivity-release")
        self.assertTrue(_trusted(after, allow_partial=True))
        # Un marker falsificado por un humano no sustituye al del bot.
        api.comments.append({
            "id": 900, "user": {"login": "intruso", "type": "User"},
            "body": "<!-- condor-reserva " + json.dumps(snap.marker) + " -->",
            "created_at": "2026-10-11T09:57:00Z"})
        self.assertEqual(port.read(21).marker, after.marker)

        # Cambio de estado: sólo etiquetas estado:, resto preservado.
        fresh = WriteAPI()
        p2 = LeaseGithubPort(fresh, armed=True, concurrency_group=group,
                             clock=lambda: NOW)
        current = p2.read(21)
        p2.status(21, RECOVERY, current)
        self.assertEqual(fresh.writes[-1][0:2],
                         ("PATCH", "/repos/pl0n3r/Factory/issues/21"))
        self.assertEqual(fresh.writes[-1][2],
                         {"labels": ["prioridad: alta", RECOVERY]})

    @staticmethod
    def _marker_json(pin):
        return json.dumps({
            "version": 3, "active": True, "owner": "pl0n3r",
            "branch": "trabajo/issue-21", "reason": "tomar",
            "reservation_id": "e33f1859-0304-4fa8-8ce3-776de22c9707",
            "acceptance_sha256": "c" * 64, "task_marker_sha256": pin,
            "task_paths": ["scripts/example.py"], "task_depends_on": [],
        })

    def test_mutating_port_surface_denied_even_with_fake_evidence(self):
        api = FakeAPI()
        port = LeaseGithubPort(api)
        blocked_calls = [
            lambda: port.read(21),
            lambda: port.lock("factory-coordination-123"),
            lambda: port.append(21, "synthetic", None),
            lambda: port.status(21, "estado: disponible", None),
            lambda: port.recovery_note(21, None),
            lambda: port.recovery_label(21, None),
        ]
        for call in blocked_calls:
            with self.subTest(action=blocked_calls.index(call)):
                with self.assertRaises(PortNotArmed):
                    call()
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
