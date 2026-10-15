"""Integración QA V3 offline: no escribe en GitHub ni arma el Port real."""
import unittest
from unittest.mock import patch
from dataclasses import replace
from datetime import timedelta

from scripts.lease_activity_collector import collect_activity
from scripts.lease_auto_release_run import run_cycle
from test_lease_activity_collector import API, NOW, marker
import json
import scripts.coordinar_trabajo as coordinator


def canonical_review_pr_body():
    payload = json.loads(marker().split("<!-- condor-reserva ", 1)[1]
                         .split(" -->", 1)[0])
    return (f'Closes #21\n<!-- condor-reserva-id: '
            f'{payload["reservation_id"]} -->')


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


    def test_adoption_pr_drift_never_edits_foreign_pull(self):
        """Adopción no debe reescribir el PR si cambió tras obtener el lock."""
        from scripts.coordinar_trabajo import (
            CoordinationError, adopt_orphaned_contract,
            recovery_lock_branch,
        )
        from test_coordinar_trabajo import FakeGitHub, VALID_ACCEPTANCE_BODY

        for drift in ("closed", "fork", "new_branch",
                      "new_sha", "missing_sha", "changed_body",
                      "foreign_lease"):
            with self.subTest(drift=drift):
                api = FakeGitHub()
                branch = "trabajo/issue-12"
                api.issue_data["body"] = VALID_ACCEPTANCE_BODY
                api.branches[branch] = "abc123"
                api.pulls[15] = {
                    "number": 15, "state": "open",
                    "head": {"ref": branch, "sha": "abc123",
                             "repo": {"full_name": api.repo}},
                    "base": {"ref": "main"}, "body": "Closes #12",
                }
                original_pull = api.pull
                seen = [0]
                rival_body = ["Closes #12"]

                def competing_pr_change(number):
                    seen[0] += 1
                    if seen[0] == 1:
                        if drift == "closed":
                            api.pulls[number]["state"] = "closed"
                        elif drift == "fork":
                            api.pulls[number]["head"]["repo"]["full_name"] = (
                                "adversary/fork"
                            )
                        elif drift == "new_branch":
                            api.pulls[number]["head"]["ref"] = "other-branch"
                        elif drift == "new_sha":
                            api.pulls[number]["head"]["sha"] = "b" * 40
                        elif drift == "missing_sha":
                            api.pulls[number]["head"].pop("sha")
                        elif drift == "changed_body":
                            api.pulls[number]["body"] = "Closes #999"
                        else:
                            api.pulls[number]["body"] = (
                                "Closes #12\n<!-- condor-reserva-id: "
                                "a84bdf99-a23a-4bc1-8c99-df4f3673573a -->"
                            )
                        rival_body[0] = api.pulls[number]["body"]
                    return original_pull(number)

                api.pull = competing_pr_change
                with self.assertRaises(CoordinationError):
                    adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
                self.assertEqual(seen, [1])
                self.assertEqual(api.pulls[15]["body"], rival_body[0])
                self.assertNotIn(recovery_lock_branch(12), api.branches)
                self.assertEqual(api.branches[branch], "abc123")

    def test_explicit_orphan_adoption_cannot_rotate_concurrent_v3(self):
        """La adopción no publica UUID propio sobre una lease ajena surgida."""
        from scripts.aceptacion_kit import contract_fingerprint
        from scripts.coordinar_trabajo import (
            CoordinationError, active_reservation, adopt_orphaned_contract,
            recovery_lock_branch, reservation_marker,
        )
        from scripts.orquestador_kit import (
            PlannedTask, build_task_marker, parse_task_marker,
        )
        from test_coordinar_trabajo import (
            BOT, FakeGitHub, SESSION_A, VALID_ACCEPTANCE_BODY,
        )

        def prepare():
            api = FakeGitHub()
            task = PlannedTask(
                key="LEASE_ORPHAN_RACE", title="Race de adopción",
                owner="pl0n3r", paths=("scripts/orphan_path.py",),
                depends_on=(),
            )
            body = VALID_ACCEPTANCE_BODY + "\n### Rutas reclamadas\n" + (
                "- scripts/orphan_path.py\n" + build_task_marker(
                    epic=12, task=task, order=1,
                    roles=["ingenieria-software"], dependency_issues=[],
                )
            )
            api.issue_data["body"] = body
            api.branches["trabajo/issue-12"] = "a" * 40
            return api, body

        api, body = prepare()
        native_sha = api.branch_sha
        installed = False
        def race_before_lock(ref):
            nonlocal installed
            if ref == "trabajo/issue-12" and not installed:
                installed = True
                api.comments.append({
                    "user": {"login": BOT, "type": "Bot"},
                    "body": reservation_marker(
                        "otro-agente", SESSION_A, ref, True, "tomar",
                        contract_fingerprint(body), parse_task_marker(body)),
                    "created_at": START.isoformat(),
                    "updated_at": START.isoformat(),
                })
            return native_sha(ref)
        api.branch_sha = race_before_lock
        with self.assertRaisesRegex(
            CoordinationError, "reserva activa|cambió"
        ):
            adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
        self.assertEqual(len(api.comments), 1)
        self.assertEqual(active_reservation(api, 12)["reservation_id"],
                         SESSION_A)
        self.assertEqual(api.branches["trabajo/issue-12"], "a" * 40)
        self.assertNotIn(recovery_lock_branch(12), api.branches)
        self.assertEqual(api.pulls, {})

        # Un lock legítimamente ocupado devuelve no-adopción sin publicar.
        api, _ = prepare()
        api.branches[recovery_lock_branch(12)] = "lock-de-otro"
        self.assertIsNone(adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER"))
        self.assertEqual(api.comments, [])
        self.assertEqual(api.branches["trabajo/issue-12"], "a" * 40)
        self.assertEqual(api.branches[recovery_lock_branch(12)],
                         "lock-de-otro")

        # Un Issue bloqueado o con estado terminal no se convierte en
        # reservado mediante adopción huérfana, aunque exista la rama.
        for status in ("estado: bloqueado", "estado: completado",
                       "estado: cancelado"):
            with self.subTest(disallowed_status=status):
                api, _ = prepare()
                api.set_status(12, status)
                with self.assertRaisesRegex(
                    CoordinationError, "estado incompatible"
                ):
                    adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
                self.assertEqual(api.comments, [])
                self.assertEqual(api.branches["trabajo/issue-12"], "a" * 40)

        # Transición AVAILABLE -> BLOCKED después del GET y del lock:
        # el nuevo marker no debe publicarse ni debe perderse el lock ajeno.
        api, _ = prepare()
        acquire = api.acquire_issue_lock
        def blocked_after_acquire(issue_number, sha):
            token = acquire(issue_number, sha)
            api.set_status(12, "estado: bloqueado")
            return token
        api.acquire_issue_lock = blocked_after_acquire
        with self.assertRaisesRegex(CoordinationError, "estado incompatible"):
            adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
        self.assertEqual(api.comments, [])
        self.assertEqual(api.issue_data["labels"][-1]["name"],
                         "estado: bloqueado")
        self.assertEqual(api.branches["trabajo/issue-12"], "a" * 40)
        self.assertNotIn(recovery_lock_branch(12), api.branches)


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
        def create_fixture(*, recovery_label=True):
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
            if recovery_label:
                api.set_status(12, STATUS_RECOVERY)
            else:
                api.set_status(12, "estado: reservado")
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

        # En el fallo parcial nota->etiqueta, RECOVERY aún no aparece.
        # No permitir que /tomar oculte el marker bot en esa ventana.
        for actor in ("otro-agente", owner):
            with self.subTest(no_label_actor=actor):
                api = create_fixture(recovery_label=False)
                with self.assertRaisesRegex(
                    CoordinationError, "solo el titular con /recuperar"
                ):
                    reserve_work(api, 12, actor, "OWNER")
                self.assertEqual(active_reservation(api, 12)["reservation_id"],
                                 SESSION_A)
                self.assertEqual(api.issue_data["labels"][-1]["name"],
                                 "estado: reservado")
                self.assertEqual(api.branches[branch], "a" * 40)

        # Un marker de nota suplantado, duplicado o ambiguo tampoco
        # habilita /tomar: la fuente de recuperación debe ser integral.
        for scenario, reason in (
            ("spoofed_bot", "sin procedencia de bot"),
            ("missing_bot_type", "sin procedencia de bot"),
            ("duplicate_note", "Notas V3 duplicadas"),
            ("duplicate_header", "sin procedencia de bot"),
            ("duplicate_json_key", "automática inválida"),
            ("malformed_header", "automática malformada"),
            ("missing_required_key", "sin contrato válido"),
        ):
            with self.subTest(proof_case=scenario):
                api = create_fixture(recovery_label=False)
                note = api.comments[-1]
                if scenario == "spoofed_bot":
                    note["user"] = {"login": "other", "type": "User"}
                elif scenario == "missing_bot_type":
                    note["user"] = {"login": BOT}
                elif scenario == "duplicate_note":
                    api.comments.append(dict(note))
                elif scenario == "duplicate_header":
                    note["body"] += "\n<!-- FACTORY-LEASE-RECOVERY {} -->"
                elif scenario == "duplicate_json_key":
                    note["body"] = note["body"].replace(
                        '"version": 1', '"version": 1, "version": 1')
                elif scenario == "malformed_header":
                    note["body"] = note["body"].replace(
                        "<!-- factory-lease-recovery ",
                        "<!-- factory-lease-recovery INVALID ")
                elif scenario == "missing_required_key":
                    note["body"] = note["body"].replace(
                        '"owner": "agente-original", ', "")
                with self.assertRaisesRegex(CoordinationError, reason):
                    reserve_work(api, 12, "otro-agente", "OWNER")
                self.assertEqual(active_reservation(api, 12)["reservation_id"],
                                 SESSION_A)
                self.assertEqual(api.branches[branch], "a" * 40)
                self.assertEqual(api.issue_data["labels"][-1]["name"],
                                 "estado: reservado")

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


    def test_authenticated_review_veto_complete(self):
        """Nadie convierte reviews incompletas o aprobaciones ajenas en permiso."""
        from scripts.lease_auto_release_integration import _verified_review_veto

        def ready():
            api = API()
            api.pulls[0]["state"] = "open"
            api.pulls[0]["base"] = {"ref": "main"}
            api.pulls[0]["body"] = canonical_review_pr_body()
            return api

        pinned = json.loads(marker().split("<!-- condor-reserva ", 1)[1]
                            .split(" -->", 1)[0])
        lease = replace(
            snapshot(recovery=False), repository_id=123, issue=21,
            branch="trabajo/issue-21", branch_sha="a" * 40,
            reservation_id=pinned["reservation_id"],
            status="estado: en revisión",
        )
        for state, verdict in (
            ("COMMENTED", False), ("APPROVED", False),
            ("DISMISSED", False), ("PENDING", False),
            ("CHANGES_REQUESTED", True),
        ):
            with self.subTest(review=state):
                api = ready()
                api.reviews[0]["state"] = state
                self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100),
                              verdict)
                self.assertTrue(all(p.startswith("/repos/")
                                    for p in api.calls))

        api = ready()
        api.reviews[0]["state"] = "CHANGES_REQUESTED"
        api.reviews.append({
            "id": 7, "user": {"login": "other-reviewer"},
            "state": "APPROVED", "submitted_at": "2026-10-11T09:35:00Z",
        })
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), True)
        api.reviews.append({
            "id": 8, "user": {"login": "other"},
            "state": "COMMENTED", "submitted_at": "2026-10-11T09:38:00Z",
        })
        # Un comentario posterior NO levanta una solicitud de cambios.
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), True)
        api.reviews[-1]["state"] = "DISMISSED"
        # La revisión #8 descartada no descarta la solicitud #5.
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), True)
        # Si se descarta la revisión original CHANGES_REQUESTED, la
        # API devuelve DISMISSED sobre ese mismo ID; ya no hay veto.
        api.reviews[0]["state"] = "DISMISSED"
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), False)
        api.reviews[0]["state"] = "CHANGES_REQUESTED"
        api.reviews[-1]["state"] = "COMMENTED"
        api.reviews.append({
            "id": 9, "user": {"login": "other"},
            "state": "APPROVED", "submitted_at": "2026-10-11T09:39:00Z",
        })
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), False)

        # IDs REST ordenan creación, no necesariamente submitted_at.
        # Una aprobación enviada ANTES del veto no debe levantarlo.
        api = ready()
        api.reviews[0]["state"] = "CHANGES_REQUESTED"
        api.reviews.append({
            "id": 6, "user": {"login": "other"},
            "state": "APPROVED", "submitted_at": "2026-10-11T09:24:00Z",
        })
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), True)
        api.reviews[-1]["submitted_at"] = "2026-10-11T09:26:00Z"
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), False)
        # Dos conclusiones opuestas con la misma hora no forman un
        # orden certificable; tratar como UNKNOWN.
        api.reviews[-1]["submitted_at"] = "2026-10-11T09:25:00Z"
        self.assertIsNone(_verified_review_veto(api, lease, NOW, 60, 100))

        for scenario in (
            "state", "author", "stamp", "future", "duplicate", "base",
            "repo", "missing_id", "missing_origin", "fork_id_collision",
            "sha", "quota", "error", "number", "no_pr", "race",
            "missing_contract", "wrong_issue", "wrong_session",
            "duplicate_session", "duplicate_closes",
            "review_bool_id", "review_float_id", "review_zero_id",
        ):
            with self.subTest(unknown=scenario):
                api = ready()
                quota = 60
                if scenario == "state":
                    api.reviews[0]["state"] = "UNLISTED"
                elif scenario == "author":
                    api.reviews[0]["user"] = {}
                elif scenario == "stamp":
                    del api.reviews[0]["submitted_at"]
                elif scenario == "future":
                    api.reviews[0]["submitted_at"] = "2026-10-11T10:01:00Z"
                elif scenario == "duplicate":
                    api.reviews.append(dict(api.reviews[0]))
                elif scenario == "review_bool_id":
                    api.reviews[0]["id"] = True
                elif scenario == "review_float_id":
                    api.reviews[0]["id"] = 4.5
                elif scenario == "review_zero_id":
                    api.reviews[0]["id"] = 0
                elif scenario == "base":
                    del api.pulls[0]["base"]
                elif scenario == "repo":
                    api.pulls[0]["head"]["repo"]["id"] = 456
                elif scenario == "missing_id":
                    api.pulls[0]["head"]["repo"].pop("id")
                elif scenario == "missing_origin":
                    api.pulls[0]["head"]["repo"].pop("full_name")
                elif scenario == "fork_id_collision":
                    api.pulls[0]["head"]["repo"]["full_name"] = "other/fork"
                elif scenario == "sha":
                    api.pulls[0]["head"]["sha"] = "b" * 40
                elif scenario == "missing_contract":
                    api.pulls[0].pop("body")
                elif scenario == "wrong_issue":
                    api.pulls[0]["body"] = canonical_review_pr_body().replace(
                        "Closes #21", "Closes #22")
                elif scenario == "wrong_session":
                    api.pulls[0]["body"] = canonical_review_pr_body().replace(
                        "e33f1859-0304-4fa8-8ce3-776de22c9707",
                        "a84bdf99-a23a-4bc1-8c99-df4f3673573a")
                elif scenario == "duplicate_session":
                    body = canonical_review_pr_body()
                    api.pulls[0]["body"] = body + "\n" + body.split("\n")[1]
                elif scenario == "duplicate_closes":
                    api.pulls[0]["body"] = (
                        canonical_review_pr_body() + "\nCloses #22")
                elif scenario == "quota":
                    quota = 20
                elif scenario == "error":
                    api.block = "/pulls/35/reviews?"
                elif scenario == "number":
                    api.pulls[0]["number"] = "invalid"
                elif scenario == "no_pr":
                    api.pulls = []
                elif scenario == "race":
                    request = api.request
                    calls = [0]
                    def change_on_recheck(method, path):
                        if "/pulls/35/reviews?" in path and "page=1" in path:
                            calls[0] += 1
                            if calls[0] == 2:
                                api.reviews[0]["state"] = "CHANGES_REQUESTED"
                        return request(method, path)
                    api.request = change_on_recheck
                self.assertIs(_verified_review_veto(api, lease, NOW, quota, 100),
                              None)

    def test_collector_and_port_preview_agree_without_release_authority(self):
        from dataclasses import FrozenInstanceError
        from scripts.lease_auto_release_integration import (
            IntegrationPreview, preview_integrated_activity,
        )
        from test_lease_activity_collector import marker
        import json

        def review_ready_api():
            candidate = API()
            candidate.pulls[0]["state"] = "open"
            candidate.pulls[0]["base"] = {"ref": "main"}
            candidate.pulls[0]["body"] = canonical_review_pr_body()
            return candidate

        api = review_ready_api()
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
            rate_remaining=40, ci_running=False,
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
        self.assertIs(observed.lock_verified, False)
        self.assertIs(observed.cas_verified, False)
        self.assertEqual(port.reads, 1)
        with self.assertRaises(TypeError):
            replace(observed, release_authorized=True)
        with self.assertRaises(TypeError):
            replace(observed, lock_verified=True)
        with self.assertRaises(TypeError):
            replace(observed, cas_verified=True)
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
                outcome = preview_integrated_activity(review_ready_api(), other, 21,
                                                       now=NOW)
                self.assertEqual(outcome.state, "UNKNOWN")
                self.assertFalse(outcome.release_authorized)
        broken = review_ready_api()
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
        api.pulls[0]["state"] = "open"
        api.pulls[0]["base"] = {"ref": "main"}
        api.pulls[0]["body"] = canonical_review_pr_body()
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
            rate_remaining=40, ci_running=False,
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


    def test_read_only_transport_allows_exact_repository_identity_and_denies_writes(self):
        from unittest.mock import patch
        from scripts.lease_auto_release_integration import _GhReadOnlyAPI

        api = _GhReadOnlyAPI()
        response = type("Response", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *args: False,
            "stdout": '{"id":123,"full_name":"pl0n3r/Factory"}',
        })()
        with patch("subprocess.run", return_value=response) as run:
            value = api.request("GET", "/repos/pl0n3r/Factory")
        self.assertEqual(value, {"id": 123, "full_name": "pl0n3r/Factory"})
        run.assert_called_once()
        self.assertIn("/repos/pl0n3r/Factory", run.call_args.args[0])

        # La allowlist de identidad no habilita ningún método mutante ni rutas externas.
        for method, path in (
            ("POST", "/repos/pl0n3r/Factory/issues"),
            ("GET", "/repos/other/Factory"),
            ("GET", "https://api.github.com/repos/pl0n3r/Factory"),
            ("GET", "/repos/pl0n3r/Factory/../../other"),
            ("GET", "/repos/pl0n3r/Factory/%2e%2e/secrets"),
            ("GET", "/repos/pl0n3r/Factory%2f..%2fother"),
            ("GET", "/repos/pl0n3r/Factory\\..\\secrets"),
            ("GET", "/repos/pl0n3r/Factory/issues/1185\ncomments"),
            ("GET", "/repos/pl0n3r/Factory/issues/1185\x00/comments"),
            ("GET", "/repos/pl0n3r/Factory/issues/1185\t/comments"),
        ):
            with self.subTest(method=method, path=path):
                with patch("subprocess.run") as run:
                    with self.assertRaises(PermissionError):
                        api.request(method, path)
                    run.assert_not_called()

    def test_observer_uses_canonical_actions_concurrency_group(self):
        from datetime import timezone
        from unittest.mock import patch
        from scripts.lease_auto_release_integration import (
            IntegrationPreview, _GhReadOnlyAPI, observe_issue_cli,
        )

        healthy = IntegrationPreview(
            1185, "read_only", "wait", "not_old_enough",
        )
        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "pl0n3r/Factory"}):
            with patch.object(
                _GhReadOnlyAPI, "request",
                return_value={"id": 987654, "full_name": "pl0n3r/Factory"},
            ) as request:
                with patch(
                    "scripts.lease_github_port.LeaseGithubPort"
                ) as port_type:
                    with patch(
                        "scripts.lease_auto_release_integration.preview_integrated_activity",
                        return_value=healthy,
                    ) as preview:
                        result = observe_issue_cli(1185)
        self.assertIs(result, healthy)
        request.assert_called_once_with("GET", "/repos/pl0n3r/Factory")
        kwargs = port_type.call_args.kwargs
        self.assertTrue(kwargs["armed"])
        self.assertEqual(kwargs["concurrency_group"],
                         "factory-coordination-987654")
        self.assertEqual(kwargs["clock"]().tzinfo, timezone.utc)
        preview.assert_called_once()
        self.assertIs(preview.call_args.args[1], port_type.return_value)

        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "pl0n3r/Factory"}):
            with patch.object(
                _GhReadOnlyAPI, "request",
                return_value={"id": 987654, "full_name": "different/repo"},
            ):
                with patch("scripts.lease_github_port.LeaseGithubPort") as port_type:
                    rejected = observe_issue_cli(1185)
        self.assertEqual(rejected.state, "UNKNOWN")
        self.assertEqual(rejected.reason, "repository_identity_unknown")
        self.assertFalse(rejected.release_authorized)
        port_type.assert_not_called()

        # La excepción de un adaptador externo no sale a logs o callers.
        for broken in ("port", "preview"):
            with self.subTest(broken=broken):
                with patch.dict("os.environ",
                                {"GITHUB_REPOSITORY": "pl0n3r/Factory"}):
                    with patch.object(
                        _GhReadOnlyAPI, "request",
                        return_value={"id": 987654,
                                      "full_name": "pl0n3r/Factory"},
                    ):
                        with patch("scripts.lease_github_port.LeaseGithubPort") as port_type:
                            with patch(
                                "scripts.lease_auto_release_integration."
                                "preview_integrated_activity",
                            ) as preview:
                                if broken == "port":
                                    port_type.side_effect = RuntimeError(
                                        "private-token-must-not-leak"
                                    )
                                else:
                                    preview.side_effect = RuntimeError(
                                        "private-token-must-not-leak"
                                    )
                                rejected = observe_issue_cli(1185)
                self.assertEqual(rejected.state, "UNKNOWN")
                self.assertEqual(rejected.reason, "observer_failed")
                self.assertFalse(rejected.release_authorized)
                self.assertNotIn("private-token", str(rejected))

    def test_cli_unknown_causes_nonzero_exit(self):
        """Ejecutar el entrypoint real con fakes, sin Github ni escrituras."""
        import contextlib
        import io
        from pathlib import Path
        from unittest.mock import patch
        import sys
        from scripts.lease_auto_release_integration import IntegrationPreview

        path = Path(__file__).resolve().parents[1] / "scripts" / (
            "lease_auto_release_integration.py"
        )
        source = path.read_text(encoding="utf-8")
        entrypoint = "if __name__ == '__main__':" + source.split(
            'if __name__ == "__main__":', 1
        )[1]
        for state, action, code in (
            ("read_only", "wait", 0),
            ("UNKNOWN", "unknown", 1),
            ("read_only", "unknown", 1),
        ):
            with self.subTest(state=state, action=action):
                result = IntegrationPreview(21, state, action, "synthetic")
                scope = {"__name__": "__main__",
                         "observe_issue_cli": lambda _: result}
                output = io.StringIO()
                with patch.object(sys, "argv", ["observer", "21"]):
                    with contextlib.redirect_stdout(output):
                        try:
                            exec(compile(entrypoint, str(path), "exec"), scope)
                            observed_exit = 0
                        except SystemExit as exc:
                            observed_exit = exc.code
                self.assertEqual(observed_exit, code)
                payload = json.loads(output.getvalue())
                self.assertEqual(payload["state"], state)
                self.assertEqual(payload["release_authorized"], False)
                self.assertEqual(payload["lock_verified"], False)
                self.assertEqual(payload["cas_verified"], False)
                self.assertEqual(payload["mutations"], 0)

        def failing(_):
            raise RuntimeError("private-token-must-not-leak")

        output = io.StringIO()
        with patch.object(sys, "argv", ["observer", "21"]):
            with contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as exit_status:
                    exec(compile(entrypoint, str(path), "exec"),
                         {"__name__": "__main__", "observe_issue_cli": failing})
        self.assertEqual(exit_status.exception.code, 1)
        failed_payload = json.loads(output.getvalue())
        self.assertEqual(failed_payload["state"], "UNKNOWN")
        self.assertFalse(failed_payload["release_authorized"])
        self.assertFalse(failed_payload["lock_verified"])
        self.assertFalse(failed_payload["cas_verified"])
        self.assertEqual(failed_payload["mutations"], 0)
        self.assertNotIn("private-token", output.getvalue())

    def test_gh_cli_observer_transport_is_get_only(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.lease_auto_release_integration import (
            _GhReadOnlyAPI, observe_issue_cli,
        )

        api = _GhReadOnlyAPI()
        with patch("subprocess.run",
                   return_value=SimpleNamespace(stdout='{"ok":true}')) as run:
            self.assertEqual(api.request("GET", "/rate_limit"), {"ok": True})
            args = run.call_args.args[0]
            self.assertEqual(args[:2], ["gh", "api"])
            self.assertIn("/rate_limit", args)
            kwargs = run.call_args.kwargs
            self.assertTrue(kwargs["check"])
            self.assertTrue(kwargs["capture_output"])
            self.assertEqual(kwargs["timeout"], 20)

        for method, path in (
            ("POST", "/repos/pl0n3r/Factory/issues/1185/comments"),
            ("PATCH", "/repos/pl0n3r/Factory/issues/1185"),
            ("DELETE", "/repos/pl0n3r/Factory/issues/1185/labels/1"),
            ("GET", "https://github.com/repos/pl0n3r/Factory/issues/767"),
            ("GET", "/repos/pl0n3r/Factory/../secrets"),
            ("GET", "/repos/pl0n3r/Factory/issues/767;echo"),
            ("GET", "/repos/other/repo/issues/1"),
        ):
            with self.subTest(method=method, path=path):
                with patch("subprocess.run") as run:
                    with self.assertRaises(PermissionError):
                        api.request(method, path)
                    run.assert_not_called()

        with patch.dict("os.environ", {"GITHUB_REPOSITORY": "attacker/fork"}):
            result = observe_issue_cli(1185)
        self.assertEqual(result.state, "UNKNOWN")
        self.assertFalse(result.release_authorized)



    def test_public_mutation_entrypoints_share_issue_lock_v3(self):
        # Todas las entradas del coordinador que pueden escribir la reserva
        # deben pasar por el lock CAS por Issue; operaciones internas de
        # recovery/renewal conservan sus propios guards.
        for name in (
            "reserve_available_work",
            "transfer_work",
            "migrate_legacy_reservation",
            "sync_review_status",
            "close_pr_reservation",
            "release_work",
            "update_issue_state",
            "update_issue_label_state",
            "update_pr_state",
        ):
            with self.subTest(entrypoint=name):
                self.assertTrue(
                    getattr(coordinator, name).__factory_issue_lock_serialized__,
                    f"{name} debe usar el lock V3 compartido",
                )


    def test_issue_lock_wrapper_acquires_revalidates_and_releases_its_own_token(self):
        class FakeGitHub:
            def __init__(self, mode="ok"):
                self.mode = mode
                self.work_reads = 0
                self.released = []
                self.released_owned = []
                self.acquired = []

            def branch_sha(self, branch):
                if branch == "work-12":
                    self.work_reads += 1
                    if self.mode == "work-drift" and self.work_reads > 1:
                        return "b" * 40
                    return "a" * 40
                if branch == "lock-12":
                    return "z" * 40 if self.mode == "lock-replaced" else "c" * 40
                raise AssertionError(f"unexpected branch {branch}")

            def acquire_issue_lock(self, issue_number, head_sha):
                self.acquired.append((issue_number, head_sha))
                return None if self.mode == "busy" else "c" * 40

            def release_issue_lock(self, issue_number, token):
                self.released.append((issue_number, token))

            def release_owned_issue_lock_after_pause(self, issue_number, token):
                self.released_owned.append((issue_number, token))

        def mutate(api, issue_number, **kwargs):
            return ("mutated", issue_number, kwargs)

        wrapped = coordinator._serialize_issue_mutation(
            mutate, issue_resolver=coordinator._issue_from_first_argument,
        )
        for mode, expected_error in (
            ("ok", None),
            ("busy", coordinator.CoordinationError),
            ("lock-replaced", coordinator.CoordinationError),
            ("work-drift", coordinator.CoordinationError),
            ("paused-after-lock", coordinator.CoordinationError),
        ):
            with self.subTest(mode=mode):
                api = FakeGitHub(mode)
                with patch.object(coordinator, "GitHub", FakeGitHub), patch.object(
                    coordinator, "require_global_running",
                    side_effect=(
                        [None, coordinator.CoordinationError("global pause")]
                        if mode == "paused-after-lock" else None
                    ),
                ) as running, patch.object(
                    coordinator, "branch_for_issue", side_effect=lambda n: f"work-{n}"
                ), patch.object(
                    coordinator, "recovery_lock_branch", side_effect=lambda n: f"lock-{n}"
                ):
                    if expected_error is None:
                        result = wrapped(api, 12)
                        self.assertEqual(result, ("mutated", 12, {}))
                    else:
                        with self.assertRaises(expected_error):
                            wrapped(api, 12)
                self.assertEqual(api.acquired[0][0], 12)
                self.assertEqual(api.acquired[0][1], "a" * 40)
                if mode == "busy":
                    self.assertEqual(api.released, [])
                    self.assertEqual(api.released_owned, [])
                else:
                    # La mutación puede cruzar RUNNING -> PAUSED; el wrapper
                    # debe limpiar solo su token con la ruta pause-safe.
                    self.assertEqual(api.released, [])
                    self.assertEqual(api.released_owned, [(12, "c" * 40)])
                if mode in ("ok", "paused-after-lock"):
                    self.assertEqual(running.call_count, 2)
                if mode == "paused-after-lock":
                    self.assertEqual(api.released, [])
                    self.assertEqual(api.released_owned, [(12, "c" * 40)])
                self.assertFalse(hasattr(api, "_factory_issue_lock_context"))

    def test_issue_lock_wrapper_rejects_invalid_and_missing_heads_closed(self):
        class FakeGitHub:
            def __init__(self, work_sha, main_sha="d" * 40):
                self.work_sha = work_sha
                self.main_sha = main_sha
                self.acquisitions = 0
            def branch_sha(self, branch):
                return self.work_sha if branch == "work-9" else self.main_sha
            def acquire_issue_lock(self, issue_number, head_sha):
                self.acquisitions += 1
                return "e" * 40
            def release_issue_lock(self, issue_number, token):
                raise AssertionError("must not release before successful acquisition")

        wrapper = coordinator._serialize_issue_mutation(
            lambda api, issue_number: issue_number,
            issue_resolver=coordinator._issue_from_first_argument,
        )
        for work_sha, main_sha in (("bad", "d" * 40), (None, None)):
            with self.subTest(work_sha=work_sha, main_sha=main_sha):
                api = FakeGitHub(work_sha, main_sha)
                with patch.object(coordinator, "GitHub", FakeGitHub), patch.object(
                    coordinator, "require_global_running"
                ), patch.object(
                    coordinator, "branch_for_issue", return_value="work-9"
                ):
                    with self.assertRaises(coordinator.CoordinationError):
                        wrapper(api, 9)
                self.assertEqual(api.acquisitions, 0)

        api = FakeGitHub("a" * 40)
        wrapper_invalid = coordinator._serialize_issue_mutation(
            lambda *_args, **_kwargs: self.fail("invalid Issue must not mutate"),
            issue_resolver=lambda *_args, **_kwargs: 0,
        )
        with patch.object(coordinator, "GitHub", FakeGitHub):
            with self.assertRaises(coordinator.CoordinationError):
                wrapper_invalid(api)
        self.assertEqual(api.acquisitions, 0)

    def test_issue_lock_wrapper_handles_non_github_and_nested_context_without_relocking(self):
        calls = []
        wrapper = coordinator._serialize_issue_mutation(
            lambda api, issue_number, **kwargs: calls.append((issue_number, kwargs)) or "ok",
            issue_resolver=coordinator._issue_from_first_argument,
        )
        class NotGithub:
            pass
        self.assertEqual(wrapper(NotGithub(), 4), "ok")
        self.assertEqual(calls, [(4, {})])

        class FakeGitHub:
            def __init__(self):
                self._factory_issue_lock_context = {"issue": 4, "token": "f" * 40}
        api = FakeGitHub()
        with patch.object(coordinator, "GitHub", FakeGitHub), patch.object(
            coordinator, "require_global_running"
        ) as running:
            self.assertEqual(wrapper(api, 4), "ok")
            with self.assertRaises(coordinator.CoordinationError):
                wrapper(api, 5)
        running.assert_not_called()
        self.assertEqual(len(calls), 2)

    def test_pr_lock_wrapper_rejects_unmapped_branch_before_mutation(self):
        class FakeGitHub:
            def __init__(self):
                self.acquisitions = 0
            def pull(self, number):
                return {"head": {"ref": "main"}}
            def acquire_issue_lock(self, issue_number, head_sha):
                self.acquisitions += 1
                return "c" * 40

        api = FakeGitHub()
        wrapper = coordinator._serialize_issue_mutation(
            lambda *_args, **_kwargs: self.fail("unmapped PR must not mutate"),
            issue_resolver=coordinator._issue_from_pull_argument,
            validate_pr_issue=True,
        )
        with patch.object(coordinator, "GitHub", FakeGitHub):
            with self.assertRaisesRegex(
                coordinator.CoordinationError, "PR sin Issue de trabajo verificable"
            ):
                wrapper(api, 27)
        self.assertEqual(api.acquisitions, 0)

    def test_pr_lock_wrapper_revalidates_issue_binding_inside_lock(self):
        class FakeGitHub:
            def __init__(self, branch):
                self.branch = branch
                self.work_reads = 0
                self.released = []
            def pull(self, number):
                return {"head": {"ref": self.branch}}
            def branch_sha(self, branch):
                if branch == "trabajo/issue-12":
                    self.work_reads += 1
                    return "a" * 40
                if branch == "lock-12":
                    return "c" * 40
                raise AssertionError(branch)
            def acquire_issue_lock(self, issue_number, head_sha):
                return "c" * 40
            def release_issue_lock(self, issue_number, token):
                self.released.append((issue_number, token))

        def update(api, pr_number, action, *, _expected_issue_number=None):
            return _expected_issue_number

        wrapped = coordinator._serialize_issue_mutation(
            update, issue_resolver=lambda api, _pr, *_a, **_k: 12,
            validate_pr_issue=True,
        )
        for branch, should_pass in (("trabajo/issue-12", True), ("trabajo/issue-13", False)):
            with self.subTest(branch=branch):
                api = FakeGitHub(branch)
                with patch.object(coordinator, "GitHub", FakeGitHub), patch.object(
                    coordinator, "require_global_running"
                ), patch.object(
                    coordinator, "branch_for_issue", return_value="trabajo/issue-12"
                ), patch.object(
                    coordinator, "recovery_lock_branch", return_value="lock-12"
                ):
                    if should_pass:
                        self.assertEqual(wrapped(api, 77, "opened"), 12)
                    else:
                        with self.assertRaises(coordinator.CoordinationError):
                            wrapped(api, 77, "opened")
                self.assertEqual(api.released, [(12, "c" * 40)])

    def test_sweep_state_transitions_take_shared_issue_lock(self):
        token = "c" * 40

        class FakeSweepAPI:
            repo = "pl0n3r/Factory"
            _force_v3_lock_test = True

            def __init__(self, replace_lock=False):
                self.events = []
                self.acquired = False
                self.replace_lock = replace_lock

            def branch_sha(self, branch):
                if branch == "trabajo/issue-12":
                    self.events.append("read-work")
                    return "a" * 40
                if branch == "main":
                    self.events.append("read-main")
                    return "b" * 40
                if branch == "lock-12":
                    self.events.append("read-lock")
                    if not self.acquired:
                        return None
                    return ("z" * 40) if self.replace_lock else token
                raise AssertionError(branch)

            def acquire_issue_lock(self, issue_number, parent_sha):
                self.events.append(("acquire", issue_number, parent_sha))
                self.acquired = True
                return token

            def release_issue_lock(self, issue_number, lock_token):
                self.events.append(("release", issue_number, lock_token))
                self.acquired = False

        def operation():
            api.events.append("write-transition")
            return True

        for replace_lock, should_pass in ((False, True), (True, False)):
            with self.subTest(replace_lock=replace_lock):
                api = FakeSweepAPI(replace_lock=replace_lock)
                with patch.object(coordinator, "require_sweep_running"), patch.object(
                    coordinator, "branch_for_issue", return_value="trabajo/issue-12"
                ), patch.object(
                    coordinator, "recovery_lock_branch", return_value="lock-12"
                ):
                    if should_pass:
                        self.assertTrue(coordinator._with_sweep_issue_lock(api, 12, operation))
                        self.assertLess(
                            api.events.index(("acquire", 12, "a" * 40)),
                            api.events.index("write-transition"),
                        )
                        self.assertLess(
                            api.events.index("write-transition"),
                            api.events.index(("release", 12, token)),
                        )
                    else:
                        with self.assertRaisesRegex(
                            coordinator.CoordinationError, "Lock V3 del barrido sustituido"
                        ):
                            coordinator._with_sweep_issue_lock(api, 12, operation)
                        self.assertNotIn("write-transition", api.events)
                        self.assertIn(("release", 12, token), api.events)


    def test_own_lock_cas_cleanup_is_allowed_after_global_pause(self):
        token = "d" * 40
        api = coordinator.GitHub("pl0n3r/Factory", "fake-token")
        calls = []

        def request(method, path, payload=None, allow=()):
            calls.append((method, path, payload))
            if method == "GET" and path == "/repos/pl0n3r/Factory":
                return {"node_id": "R_123"}
            if method == "POST" and path == "/graphql":
                return {"data": {"updateRefs": {"clientMutationId": "ok"}}}
            raise AssertionError((method, path))

        api.request = request
        with patch.object(
            coordinator, "require_global_running",
            side_effect=AssertionError("cleanup must work while PAUSED"),
        ):
            api.release_owned_issue_lock_after_pause(12, token)

        self.assertEqual([call[:2] for call in calls], [
            ("GET", "/repos/pl0n3r/Factory"), ("POST", "/graphql"),
        ])
        mutation = calls[-1][2]["variables"]["input"]["refUpdates"][0]
        self.assertEqual(mutation["beforeOid"], token)
        self.assertEqual(mutation["afterOid"], "0" * 40)
        self.assertTrue(mutation["force"])


    def test_owned_lock_cas_cleanup_fails_closed_on_ambiguous_graphql_response(self):
        token = "e" * 40
        responses = (
            {"errors": [{"message": "ref moved"}]},
            {"data": {}},
            {"data": {"updateRefs": None}},
            None,
        )
        for response in responses:
            with self.subTest(response=response):
                api = coordinator.GitHub("pl0n3r/Factory", "fake-token")
                calls = []

                def request(method, path, payload=None, allow=()):
                    calls.append((method, path, payload))
                    if method == "GET" and path == "/repos/pl0n3r/Factory":
                        return {"node_id": "R_123"}
                    if method == "POST" and path == "/graphql":
                        return response
                    raise AssertionError((method, path))

                api.request = request
                with self.assertRaisesRegex(
                    coordinator.CoordinationError, "CAS V3 denegado"
                ):
                    api.release_owned_issue_lock_after_pause(12, token)
                self.assertEqual([call[:2] for call in calls], [
                    ("GET", "/repos/pl0n3r/Factory"), ("POST", "/graphql"),
                ])
                mutation = calls[-1][2]["variables"]["input"]["refUpdates"][0]
                self.assertEqual(mutation["beforeOid"], token)
                self.assertEqual(mutation["afterOid"], "0" * 40)


if __name__ == "__main__":
    unittest.main()
