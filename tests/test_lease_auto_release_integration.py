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


    def test_adoption_pr_drift_never_edits_foreign_pull(self):
        """Adopción no debe reescribir el PR si cambió tras obtener el lock."""
        from scripts.coordinar_trabajo import (
            CoordinationError, adopt_orphaned_contract,
            recovery_lock_branch,
        )
        from test_coordinar_trabajo import FakeGitHub, VALID_ACCEPTANCE_BODY

        for drift in ("closed", "fork", "new_branch",
                      "new_sha", "changed_body", "foreign_lease"):
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
                        elif drift == "changed_body":
                            api.pulls[number]["body"] = "Closes #999"
                        else:
                            api.pulls[number]["body"] = (
                                "Closes #12\n<!-- condor-reserva-id: "
                                "a84bdf99-a23a-4bc1-8c99-df4f3673573a -->"
                            )
                    return original_pull(number)

                api.pull = competing_pr_change
                with self.assertRaises(CoordinationError):
                    adopt_orphaned_contract(api, 12, "pl0n3r", "OWNER")
                self.assertEqual(seen, [1])
                self.assertNotIn(
                    "<!-- condor-reserva-id: ",
                    api.pulls[15]["body"] if drift != "foreign_lease"
                    else api.pulls[15]["body"].replace(
                        "a84bdf99-a23a-4bc1-8c99-df4f3673573a", ""),
                )
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
            return api

        lease = replace(
            snapshot(recovery=False), repository_id=123, issue=21,
            branch="trabajo/issue-21", branch_sha="a" * 40,
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
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), False)
        api.reviews[-1]["state"] = "COMMENTED"
        api.reviews.append({
            "id": 9, "user": {"login": "other"},
            "state": "APPROVED", "submitted_at": "2026-10-11T09:39:00Z",
        })
        self.assertIs(_verified_review_veto(api, lease, NOW, 60, 100), False)

        for scenario in (
            "state", "author", "stamp", "future", "duplicate", "base",
            "repo", "missing_id", "missing_origin", "fork_id_collision",
            "sha", "quota", "error", "number", "no_pr", "race",
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


if __name__ == "__main__":
    unittest.main()
