"""Contratos offline del runner V3: ninguna credencial ni red real."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.lease_auto_release_run import (
    decision_from_snapshot, inventory_after_switch_recheck,
    inventory_from_paginated_issues, observe_recent_activity, run_cycle,
    evaluate_phase_a_candidate,
)
from test_lease_release_executor import FakePort, snapshot
from test_lease_github_port import FakeAPI, NOW


class NoAccessPort:
    def __getattr__(self, name):
        raise AssertionError("La ejecución deshabilitada no debe consultar Port")


class LeaseAutoReleaseRunTests(unittest.TestCase):
    def test_read_only_report_types_cannot_be_constructed_with_release_authority(self):
        from dataclasses import FrozenInstanceError
        from scripts.lease_auto_release_run import (
            RecentActivityObservation, RecentActivityReport, RecoveryInventory,
        )

        observed = RecentActivityObservation(21, "RECENT_ACTIVITY", 35)
        report = RecentActivityReport("read_only", (observed,))
        inventory = RecoveryInventory(2, 1, 0, 1)
        for item in (observed, report, inventory):
            with self.subTest(kind=type(item).__name__):
                self.assertIs(item.release_authorized, False)
                with self.assertRaises(TypeError):
                    replace(item, release_authorized=True)
                with self.assertRaises(FrozenInstanceError):
                    setattr(item, "release_authorized", True)
        with self.assertRaises(TypeError):
            RecentActivityObservation(21, "RECENT_ACTIVITY", 35, True)
        with self.assertRaises(TypeError):
            RecentActivityReport("read_only", (observed,), True)
        with self.assertRaises(TypeError):
            RecoveryInventory(2, 1, 0, 1, True)


    def test_phase_a_candidate_requires_authenticated_receipts_and_24h_100_cycles(self):
        from copy import deepcopy
        from dataclasses import FrozenInstanceError

        repo = "pl0n3r/Factory"
        sha = "a" * 40
        now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        manifests, receipts = [], []
        def issue_row(action="wait"):
            return {
                "issue": 21, "state": "read_only", "action": action,
                "reason": "not_old_enough", "activity_age_minutes": 7,
                "activity_source": "workflow_push",
                "release_authorized": False, "lock_verified": False,
                "cas_verified": False, "mutations": 0,
            }
        for n in range(100):
            run = 10001 + n
            manifests.append({
                "schema_version": 1, "repository": repo, "head_sha": sha,
                "run_id": str(run), "status": "candidate_terminal",
                "terminal_certified": False, "release_authorized": False,
                "mutations": 0, "valid_observations": 1,
                "unknown_observations": 0, "issues": [issue_row()],
            })
            receipts.append({
                "id": run, "repository": repo, "head_sha": sha,
                "event": "schedule", "status": "completed",
                "conclusion": "success", "artifact_attested": True,
                "completed_at": (
                    now + timedelta(minutes=15 * n)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        result = evaluate_phase_a_candidate(manifests, receipts, [], repository=repo)
        self.assertEqual(result.status, "candidate_only")
        self.assertEqual(result.valid_cycles, 100)
        self.assertGreaterEqual(result.observed_minutes, 1440)
        self.assertEqual((result.hypothetical_releases, result.qa_correct), (0, 0))
        self.assertIs(result.release_authorized, False)
        with self.assertRaises(TypeError):
            replace(result, release_authorized=True)
        with self.assertRaises(FrozenInstanceError):
            setattr(result, "release_authorized", True)

        short = evaluate_phase_a_candidate(
            manifests[:99], receipts[:99], [], repository=repo,
        )
        self.assertEqual(short.status, "insufficient_observation")
        cramped = deepcopy(receipts)
        for i, receipt in enumerate(cramped):
            receipt["completed_at"] = (
                now + timedelta(minutes=10 * i)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(evaluate_phase_a_candidate(
            manifests, cramped, [], repository=repo,
        ).status, "insufficient_observation")

        for mismatch in (
            {"event": "pull_request"},
            {"status": "queued"},
            {"conclusion": "failure"},
            {"artifact_attested": False},
            {"head_sha": "b" * 40},
            {"repository": "pl0n3r/other"},
        ):
            with self.subTest(mismatch=mismatch):
                altered = deepcopy(receipts)
                altered[0].update(mismatch)
                self.assertEqual(evaluate_phase_a_candidate(
                    manifests, altered, [], repository=repo,
                ).status, "invalid_evidence")
        for mismatch in (
            {"status": "UNKNOWN"},
            {"status": "deferred_low_quota"},
            {"terminal_certified": True},
            {"valid_observations": 2},
            {"unknown_observations": 1},
            {"mutations": 1},
            {"release_authorized": True},
            {"head_sha": "b" * 40},
        ):
            with self.subTest(manifest=mismatch):
                altered = deepcopy(manifests)
                altered[0].update(mismatch)
                self.assertEqual(evaluate_phase_a_candidate(
                    altered, receipts, [], repository=repo,
                ).status, "invalid_evidence")
        duplicated = deepcopy(manifests)
        duplicated[1]["run_id"] = duplicated[0]["run_id"]
        self.assertEqual(evaluate_phase_a_candidate(
            duplicated, receipts, [], repository=repo,
        ).status, "invalid_evidence")

        with_release = deepcopy(manifests)
        # Los candidatos release necesitan ≥40 min y motivo real del decisor;
        # un "release" dentro de ventana activa no puede pasar por QA.
        suspicious = deepcopy(manifests)
        suspicious[0]["issues"] = [issue_row("release")]
        self.assertEqual(evaluate_phase_a_candidate(
            suspicious, receipts, [], repository=repo,
        ).status, "invalid_evidence")
        with_release[0]["issues"] = [{
            **issue_row("release"),
            "reason": "inactive_after_recovery_grace",
            "activity_age_minutes": 45,
            "activity_source": "reservation_marker",
        }]
        missing_qa = evaluate_phase_a_candidate(
            with_release, receipts, [], repository=repo)
        self.assertEqual(missing_qa.status, "qa_incomplete")
        qa = {"run_id": 10001, "issue": 21, "verdict": "correct",
              "evidence_ref": "actions/10001/21"}
        good = evaluate_phase_a_candidate(
            with_release, receipts, [qa], repository=repo)
        self.assertEqual(good.status, "candidate_only")
        self.assertEqual((good.hypothetical_releases, good.qa_correct), (1, 1))
        self.assertIs(good.release_authorized, False)
        wrong = evaluate_phase_a_candidate(
            with_release, receipts, [{**qa, "verdict": "incorrect"}],
            repository=repo)
        self.assertEqual(wrong.status, "false_positive")
        for invalid_qa in ([qa, qa], [{**qa, "issue": 22}],
                           [{**qa, "verdict": "maybe"}]):
            self.assertEqual(evaluate_phase_a_candidate(
                with_release, receipts, invalid_qa, repository=repo,
            ).status, "invalid_evidence")
        malformed = deepcopy(with_release)
        malformed[0]["issues"][0]["mutations"] = 1
        self.assertEqual(evaluate_phase_a_candidate(
            malformed, receipts, [qa], repository=repo,
        ).status, "invalid_evidence")
        for bad in (
            {"reason": "not_old_enough"},
            {"activity_age_minutes": 39},
            {"activity_age_minutes": None},
            {"activity_source": None},
        ):
            with self.subTest(release_inconsistent=bad):
                trial = deepcopy(with_release)
                trial[0]["issues"][0].update(bad)
                self.assertEqual(evaluate_phase_a_candidate(
                    trial, receipts, [qa], repository=repo,
                ).status, "invalid_evidence")
        for inconsistent in (
            {**issue_row("mark_recovery"), "reason": "inactive_30_minutes",
             "activity_age_minutes": 29},
            {**issue_row("mark_recovery"), "reason": "wrong",
             "activity_age_minutes": 31},
            {**issue_row("mark_recovery"), "reason": "inactive_30_minutes",
             "activity_age_minutes": 31, "activity_source": None},
            {**issue_row(), "reason": "inactive_after_recovery_grace"},
        ):
            with self.subTest(action=inconsistent["action"],
                              reason=inconsistent["reason"]):
                trial = deepcopy(manifests)
                trial[0]["issues"] = [inconsistent]
                self.assertEqual(evaluate_phase_a_candidate(
                    trial, receipts, [], repository=repo,
                ).status, "invalid_evidence")
        matching_recovery = deepcopy(manifests)
        matching_recovery[0]["issues"] = [{
            **issue_row("mark_recovery"),
            "reason": "inactive_30_minutes",
            "activity_age_minutes": 32,
        }]
        self.assertEqual(evaluate_phase_a_candidate(
            matching_recovery, receipts, [], repository=repo,
        ).status, "candidate_only")

    def test_authenticated_recent_activity_inventory_is_bounded_and_never_writes(self):
        from datetime import timedelta
        from scripts.lease_github_port import LeaseGithubPort, RECENT, UNKNOWN

        api = FakeAPI()
        observed = observe_recent_activity(
            [21], LeaseGithubPort(api), now=NOW)
        self.assertEqual(observed.state, "read_only")
        self.assertFalse(observed.release_authorized)
        self.assertEqual(len(observed.observations), 1)
        item = observed.observations[0]
        self.assertEqual((item.issue, item.state, item.libera_en_min),
                         (21, RECENT, 35))
        self.assertFalse(item.release_authorized)
        self.assertNotIn("pl0n3r", str(observed))
        self.assertNotIn("e33f1859", str(observed))
        self.assertEqual(api.switch_reads, 2)
        self.assertEqual(api.calls[0], "/repos/pl0n3r/Factory/issues/767")
        self.assertEqual(api.calls[-1], "/repos/pl0n3r/Factory/issues/767")

        for change in ("pause", "quota", "race", "partial"):
            with self.subTest(fail_closed=change):
                fake = FakeAPI()
                if change == "pause":
                    fake.pause_on_second = True
                elif change == "quota":
                    fake.remaining = 19
                elif change == "race":
                    fake.race = True
                else:
                    fake.runs_count_override = 2
                report = observe_recent_activity(
                    [21], LeaseGithubPort(fake), now=NOW)
                self.assertEqual(report.state, "read_only")
                self.assertEqual(
                    (report.observations[0].state,
                     report.observations[0].libera_en_min),
                    (UNKNOWN, None))
                self.assertFalse(report.release_authorized)
                self.assertTrue(all(
                    path == "/rate_limit" or path.startswith("/repos/")
                    for path in fake.calls))

        blocked = FakeAPI()
        port = LeaseGithubPort(blocked)
        for invalid, instant in (
            ([], NOW), ([21, 22], NOW), ([True], NOW),
            ([0], NOW), ([21], NOW.replace(tzinfo=None)),
            ([21], NOW + timedelta(days=400)),
        ):
            with self.subTest(invalid=invalid, now=instant):
                answer = observe_recent_activity(invalid, port, now=instant)
                if instant.tzinfo is not None and instant.year > NOW.year:
                    # Fecha lejana significa UNKNOWN autenticado; NO ETA.
                    self.assertEqual(answer.state, "read_only")
                    self.assertIsNone(answer.observations[0].libera_en_min)
                else:
                    self.assertEqual(answer.state, "invalid_input")
                    self.assertEqual(answer.observations, ())
                self.assertFalse(answer.release_authorized)
        # Los inválidos sin fecha lejana no han tocado el Port; el último
        # caso puede leer solo GET y aun así carece de autoridad.
        self.assertEqual(blocked.switch_reads, 1)

    def test_observation_reports_current_repository_without_writes(self):
        """Fase A informa cada Issue local; lo no atribuible sigue UNKNOWN."""
        from scripts.lease_auto_release_integration import (
            IntegrationPreview, _GhReadOnlyAPI,
        )
        from scripts.lease_github_port import LeaseGithubPort

        api = FakeAPI()
        result = observe_recent_activity(
            [21], LeaseGithubPort(api), now=NOW,
        )
        self.assertEqual(result.state, "read_only")
        self.assertFalse(result.release_authorized)
        self.assertTrue(all(
            path in ("/rate_limit", "/repos/pl0n3r/Factory")
            or path.startswith("/repos/pl0n3r/Factory/")
            for path in api.calls
        ))
        self.assertFalse(any(
            path.startswith("/repos/other") for path in api.calls))
        self.assertEqual(_GhReadOnlyAPI.repo, "pl0n3r/Factory")
        valid = IntegrationPreview(
            21, "read_only", "wait", "not_old_enough", 17,
            "workflow_push",
        )
        note = valid.summary_line
        self.assertIn("Issue #21", note)
        self.assertIn("inactividad=17 min", note)
        self.assertIn("fuente=workflow_push", note)
        self.assertIn("veto/razón=not_old_enough", note)
        self.assertIn("autoridad=NO", note)
        unknown = IntegrationPreview(
            21, "UNKNOWN", "unknown", "collector_unknown",
        )
        self.assertIn("inactividad=UNKNOWN", unknown.summary_line)
        self.assertIn("fuente=UNKNOWN", unknown.summary_line)
        self.assertFalse(unknown.release_authorized)
        malicious = IntegrationPreview(
            21, "UNKNOWN", "unknown", "password_secret\nTOKEN=abc",
        )
        self.assertNotIn("password_secret", malicious.summary_line)
        self.assertNotIn("TOKEN", malicious.summary_line)
        workflow = (Path(__file__).resolve().parents[1]
                    / ".github/workflows" / "liberar-reservas.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("GITHUB_REPOSITORY: ${{ github.repository }}", workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)

    def test_switch_recheck_rejects_pause_and_untrusted_state_during_inventory(self):
        from scripts.unattended_kill_switch import (
            CANONICAL_SOURCE_URL, CANONICAL_REPOSITORY_URL,
        )
        running = {
            "number": 767, "state": "closed",
            "url": CANONICAL_SOURCE_URL,
            "repository_url": CANONICAL_REPOSITORY_URL,
            "user": {"login": "pl0n3r"},
            "body": '<!-- factory-unattended-kill-switch '
                    '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->',
        }
        pages = [[{
            "number": 1175, "state": "open",
            "labels": [{"name": "estado: en revisión"}],
            "body": "texto que jamás sale en logs",
        }]]
        observed = inventory_after_switch_recheck(running, running, pages)
        self.assertIsNotNone(observed)
        self.assertEqual(observed.in_review, 1)
        self.assertFalse(observed.release_authorized)

        for altered in (
            {**running, "state": "open"},
            {key: value for key, value in running.items() if key != "state"},
            {**running, "number": True},
            {**running, "user": {"login": "otro"}},
            {**running, "repository_url": "https://invalid.example"},
            {**running, "body": running["body"].replace("RUNNING", "PAUSED")},
            {**running, "body": running["body"] + running["body"]},
            {**running, "body": "invalid"},
            None,
        ):
            with self.subTest(altered=str(altered)[:48]):
                self.assertIsNone(inventory_after_switch_recheck(running, altered, pages))
                self.assertIsNone(inventory_after_switch_recheck(altered, running, pages))
        self.assertIsNone(inventory_after_switch_recheck(running, running, [
            [{"number": 1, "state": "closed", "labels": []}],
        ]))

    def test_paginated_real_issue_inventory_is_only_an_observation(self):
        def issue(n, state="estado: en revisión", *, is_pr=False):
            row = {
                "number": n, "state": "open",
                "labels": [{"name": state}],
                "title": "private title not printed",
                "body": "private body must not be logged",
            }
            if is_pr:
                row["pull_request"] = {"url": "https://example.invalid/pr"}
            return row

        first_page = [issue(n) for n in range(1, 101)]
        second_page = [
            issue(101, "estado: requiere recuperación"),
            issue(102, "estado: reservado"),
            issue(103, "estado: en revisión", is_pr=True),
        ]
        pages = [first_page, second_page]
        counted = inventory_from_paginated_issues(pages)
        self.assertIsNotNone(counted)
        self.assertEqual(counted.open_issues, 102)
        self.assertEqual(counted.recovery, 1)
        self.assertEqual(counted.reserved, 1)
        self.assertEqual(counted.in_review, 100)
        self.assertFalse(counted.release_authorized)
        self.assertNotIn("private", str(counted))
        # El último bloque lleno no prueba EOF: exigir una página corta o
        # una página centinela vacía antes de publicar cifras agregadas.
        self.assertIsNone(inventory_from_paginated_issues([first_page]))
        full_second = [issue(n) for n in range(101, 201)]
        self.assertIsNone(inventory_from_paginated_issues(
            [first_page, full_second]))
        with_sentinel = inventory_from_paginated_issues([first_page, []])
        self.assertIsNotNone(with_sentinel)
        self.assertEqual(with_sentinel.open_issues, 100)
        self.assertFalse(with_sentinel.release_authorized)

        invalid = [
            [], {}, [[issue(1)], [issue(2)]],  # first page truncated
            [[issue(True)]], [[issue(1), issue(1)]],
            [[{**issue(1), "state": "closed"}]],
            [[{**issue(1), "labels": "estado: reservado"}]],
            [[{**issue(1), "labels": [{"name": "estado: en revisión"},
                                      {"name": "estado: reservado"}]}]],
            [[{**issue(1), "labels": [{"name": "estado: reservado"},
                                      {"name": "estado: reservado"}]}]],
            # Nombres case-insensitive: no aceptar doble alias de GitHub.
            [[{**issue(1), "labels": [
                {"name": "estado: reservado"}, {"name": "ESTADO: RESERVADO"}]}]],
            [[{**issue(1), "labels": [
                {"name": "estado: en revisión"}, {"name": "Tipo: PRODUCTO"},
                {"name": "tipo: producto"}]}]],
            # Estado de etiqueta en otra caja no puede desaparecer del censo.
            [[issue(1, "ESTADO: reservado")]],
            [[issue(1, "estado:reservado")]],
            [[issue(1, "estado: reservado ")]],
            [[{**issue(1), "labels": [
                {"name": "estado: reservado"}, {"name": None}]}]],
            [[{**issue(1), "pull_request": "untrusted"}]],
        ]
        for value in invalid:
            with self.subTest(value=str(value)[:60]):
                self.assertIsNone(inventory_from_paginated_issues(value))
        empty = inventory_from_paginated_issues([[]])
        self.assertIsNotNone(empty)
        self.assertEqual(empty.open_issues, 0)
        self.assertFalse(empty.release_authorized)

    def test_pr_validation_is_offline_and_schedule_keeps_api_budget_gate(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/liberar-reservas.yml").read_text(
                        encoding="utf-8")
        preflight = workflow.split(
            "      - name: Preflight autenticado de cuota API "
            "(no publica datos privados)\n", 1)[1].split(
                "      - name: Tests deterministas del decisor", 1)[0]
        self.assertIn("if: github.event_name != 'pull_request'", preflight)
        self.assertIn("gh api /rate_limit", preflight)
        tests = workflow.split(
            "      - name: Tests deterministas del decisor", 1)[1].split(
                "      - name: Confirmar runner OFF", 1)[0]
        self.assertNotIn("if: steps.budget.outputs.allow", tests)
        self.assertNotIn("gh api", tests)
        self.assertIn("python3 -m unittest discover", tests)
        runner_off = workflow.split(
            "      - name: Confirmar runner OFF", 1)[1].split(
                "      - name: Inventario observado de recuperación", 1)[0]
        self.assertNotIn("if: steps.budget.outputs.allow", runner_off)
        self.assertIn("feature_disabled", runner_off)
        live = workflow.split(
            "      - name: Inventario observado de recuperación", 1)[1]
        self.assertIn("if: steps.budget.outputs.allow == 'true'", live)
        self.assertIn("gh api --paginate --slurp", live)
        self.assertIn("inventory_after_switch_recheck", live)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)

    def test_scheduled_lock_matches_coordinator_and_pr_does_not_take_it(self):
        root = Path(__file__).resolve().parents[1]
        lease = (root / ".github/workflows/liberar-reservas.yml").read_text(
            encoding="utf-8")
        coordination = (root / ".github/workflows/coordinacion-trabajo.yml"
                        ).read_text(encoding="utf-8")
        self.assertEqual(lease.count("\nconcurrency:\n"), 1)
        self.assertEqual(coordination.count("\nconcurrency:\n"), 1)
        # schedule/dispatch heredan EXACTAMENTE el candado del coordinador
        # y conservan cola no destructiva. No es CAS ni habilita escritura.
        self.assertIn(
            "group: factory-coordination-${{ github.repository_id }}",
            coordination)
        self.assertIn("queue: max", coordination)
        self.assertIn("cancel-in-progress: false", coordination)
        self.assertIn(
            "format('factory-coordination-{0}', github.repository_id)",
            lease)
        self.assertIn(
            "github.event_name == 'pull_request' && "
            "format('factory-lease-audit-pr-{0}', "
            "github.event.pull_request.number)",
            lease)
        self.assertNotIn(
            "group: factory-lease-audit-${{ github.repository_id }}",
            lease)
        # actionlint canónico aún no admite queue:max en este cron.
        self.assertNotIn("queue: max", lease)
        self.assertIn("cancel-in-progress: false", lease)
        self.assertIn("permissions:\n  contents: read\n  issues: read",
                      lease)
        self.assertNotIn("issues: write", lease)
        self.assertNotIn("pull-requests: write", lease)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'",
                      lease)

    def test_scheduled_dry_run_defaults_off_and_never_writes(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/liberar-reservas.yml").read_text(
                        encoding="utf-8")
        self.assertIn("cron: '*/10 * * * *'", workflow)
        self.assertIn("permissions:\n  contents: read\n  issues: read", workflow)
        self.assertIn("Inventario observado de recuperación", workflow)
        self.assertIn("gh api --paginate --slurp", workflow)
        self.assertIn("evaluate_unattended_kill_switch", workflow)
        self.assertIn("inventory_after_switch_recheck", workflow)
        self.assertIn("lease-switch-after.json", workflow)
        self.assertNotIn("inventory_from_paginated_issues(pages)", workflow)
        self.assertIn("liberaciones=0", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertIn("scripts.lease_auto_release_run import run_cycle", workflow)
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)
        self.assertIn("Confirmar runner OFF sin transporte ni mutaciones", workflow)
        self.assertIn('assert cycle.state == "feature_disabled"', workflow)
        self.assertIn('assert cycle.results[0][1].wrote is False', workflow)
        self.assertNotIn("from scripts.lease_github_port", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)

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

    def test_authorized_activation_caps_three_releases_and_preserves_pr_branch(self):
        """Un lote autorizado jamás ejecuta cuatro posibles liberaciones."""
        from unittest.mock import patch
        from scripts.lease_release_executor import Result

        port = FakePort(snapshot())
        original = (port.item.branch, port.item.branch_sha,
                    port.item.reservation_id)
        # Caso real aislado: el puerto conserva la rama canónica al liberar.
        single = run_cycle(
            [1191], port, feature_enabled=True,
            dry_run=False, mutations_authorized=True,
        )
        self.assertEqual(single.results[0][1].reason, "released")
        self.assertEqual((port.item.branch, port.item.branch_sha,
                          port.item.reservation_id), original)
        self.assertEqual([kind for kind, _ in port.writes],
                         ["comment", "status"])
        self.assertNotIn("delete_branch", [kind for kind, _ in port.writes])
        self.assertNotIn("close_pr", [kind for kind, _ in port.writes])

        with patch(
            "scripts.lease_auto_release_run.execute",
            return_value=Result("release", "released", True, "complete"),
        ) as simulate:
            cycle = run_cycle(
                [5, 4, 3, 2, 1], object(),
                feature_enabled=True, dry_run=False,
                mutations_authorized=True,
            )
            self.assertEqual(simulate.call_count, 3)
            self.assertEqual([issue for issue, _ in cycle.results],
                             [1, 2, 3, 4, 5])
            self.assertEqual(
                [result.reason for _, result in cycle.results],
                ["released", "released", "released",
                 "cycle_write_cap", "cycle_write_cap"])
            self.assertFalse(cycle.results[3][1].wrote)
            self.assertFalse(cycle.results[4][1].wrote)
        with patch(
            "scripts.lease_auto_release_run.execute",
            return_value=Result("release", "dry_run"),
        ) as simulate:
            cycle = run_cycle([1, 2, 3, 4], object(),
                              feature_enabled=True, dry_run=True)
            self.assertEqual(simulate.call_count, 4)
            self.assertTrue(all(not result.wrote
                                for _, result in cycle.results))
        # En el workflow real Fase B no está activada.
        workflow = (Path(__file__).resolve().parents[1]
                    / ".github" / "workflows" / "liberar-reservas.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)

    def test_cap_skips_vetoes_but_counts_partial_writes(self):
        from unittest.mock import patch
        from scripts.lease_release_executor import Result
        outcomes = [Result("wait", "veto"), Result("release", "ok", True, "complete"),
                    Result("wait", "veto"), Result("release", "partial", False, "partial"),
                    Result("release", "ok", True, "complete")]
        with patch("scripts.lease_auto_release_run.execute", side_effect=outcomes) as fake:
            cycle = run_cycle([1, 2, 3, 4, 5, 6], object(),
                              feature_enabled=True, dry_run=False, mutations_authorized=True)
        self.assertEqual(fake.call_count, 5)
        self.assertEqual([r.reason for _, r in cycle.results],
                         ["veto", "ok", "veto", "partial", "ok", "cycle_write_cap"])

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

    def test_partial_release_reconciles_under_shared_lock_without_new_marker(self):
        # Fallo deliberado DESPUÉS del marker de bot, ANTES de la etiqueta.
        fake = FakePort(snapshot())
        fake.fail_status = True
        first = run_cycle(
            [1191], fake, feature_enabled=True,
            dry_run=False, mutations_authorized=True,
        )
        self.assertEqual(first.results[0][1].reason, "port_failure_or_partial_write")
        self.assertEqual(fake.item.status, "estado: requiere recuperación")
        self.assertFalse(fake.item.marker["active"])
        self.assertEqual(fake.item.marker["reason"], "auto-inactivity-release")
        self.assertEqual(len(fake.writes), 1)
        self.assertEqual(fake.writes[0][0], "comment")

        # El marker inactivo NO se reinterpreta como claim activo.
        planned = decision_from_snapshot(fake.item)
        self.assertEqual(planned.action, "release")
        self.assertEqual(planned.reason, "authenticated_partial_reconciliation")
        dry = run_cycle([1191], fake, feature_enabled=True)
        self.assertEqual(dry.results[0][1].reason, "dry_run_reconcile")
        self.assertEqual(len(fake.writes), 1)

        fake.fail_status = False
        result = run_cycle(
            [1191], fake, feature_enabled=True,
            dry_run=False, mutations_authorized=True,
        )
        self.assertEqual(result.results[0][1].reason, "partial_reconciled")
        self.assertTrue(result.results[0][1].wrote)
        self.assertEqual(result.results[0][1].write_state, "complete")
        self.assertEqual(len(fake.writes), 2)
        self.assertEqual(fake.writes[1], ("status", "estado: disponible"))
        self.assertEqual(fake.item.branch, "trabajo/issue-1191")
        self.assertEqual(fake.item.branch_sha, "a" * 40)
        self.assertFalse(fake.item.marker["active"])
        self.assertFalse(fake.locked)

    def test_partial_release_fails_closed_on_untrusted_evidence_or_missing_proof(self):
        base = snapshot()
        partial = replace(base, marker={
            **base.marker, "active": False, "reason": "auto-inactivity-release",
        })
        for change in (
            {"kill_switch_running": False}, {"ci_running": True},
            {"changes_requested": True}, {"owner_recovered": True},
            {"complete": False}, {"authenticated": False},
            {"phase": "live"}, {"rate_remaining": 19},
            {"marker": {**partial.marker, "reason": "liberar"}},
            {"marker": {**partial.marker, "reservation_id": "bad"}},
        ):
            with self.subTest(changes=change):
                unsafe = replace(partial, **change)
                self.assertNotEqual(decision_from_snapshot(unsafe).action, "release")
                fake = FakePort(unsafe)
                result = run_cycle(
                    [1191], fake, feature_enabled=True,
                    dry_run=False, mutations_authorized=True,
                )
                self.assertFalse(result.results[0][1].wrote)
                self.assertEqual(fake.writes, [])
        for delta in ("note_complete", "note_authenticated", "label_complete",
                      "label_authenticated"):
            with self.subTest(unverified=delta):
                fake = FakePort(partial)
                setattr(fake, delta, False)
                result = run_cycle(
                    [1191], fake, feature_enabled=True,
                    dry_run=False, mutations_authorized=True,
                )
                self.assertFalse(result.results[0][1].wrote)
                self.assertEqual(fake.writes, [])



if __name__ == "__main__":
    unittest.main()
