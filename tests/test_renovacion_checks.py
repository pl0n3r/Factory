"""Negativos del decisor de recuperación de aceptación renovada."""
import copy
import unittest
from pathlib import Path

from scripts.renovacion_checks import evaluate


SHA = "a" * 40
BASE_SHA = "f" * 40
UUID = "11111111-2222-4333-8444-555555555555"
PIN = "b" * 64
TIME = "2026-10-11T18:00:00Z"
FRESH = "2026-10-11T18:10:00Z"
FINISH = "2026-10-11T18:12:00Z"
GATES = {
    "Tests de scripts": "github-actions",
    "Validar claims V3 del PR": "github-actions",
    "Presupuesto del PR": "github-actions",
    "Validar": "github-actions",
    "Criterios de aceptación": "github-actions",
    "Validar coordinación": "github-actions",
    "Ventana de release Factory": "github-actions",
    "CodeQL": "github-advanced-security",
    "SonarCloud Code Analysis": "sonarqubecloud",
}


def fresh_evidence():
    identity = {"repo": "pl0n3r/Factory", "issue": 1114, "uuid": UUID,
                "pin": PIN, "head_sha": SHA, "base_sha": BASE_SHA,
                "branch": "trabajo/issue-1114"}
    return {
        "repo": "pl0n3r/Factory",
        "issue": {"number": 1114, "state": "open",
                  "status": "estado: en revisión", "owner": "pl0n3r",
                  "version": 3, "active": True, "branch": identity["branch"],
                  "reservation_id": UUID, "acceptance_sha256": PIN},
        "pr": {"state": "open", "draft": False, "repo": identity["repo"],
               "branch": identity["branch"], "head_sha": SHA,
               "base_sha": BASE_SHA},
        "before": identity.copy(), "after": identity.copy(),
        "renewal": {"user": "github-actions[bot]", "reason": "renovar-contrato",
                    "uuid": UUID, "pin": PIN, "created_at": TIME},
        "reviewer_required": True,
        "review_threads": [],
        "reviewer_permissions": {"independent-reviewer": "write"},
        "statuses": [{"context": "CodeRabbit", "state": "success",
                      "description": "Review completed",
                      "creator": "coderabbitai[bot]",
                      "created_at": FRESH}],
        "reviews": [{"id": 501, "actor": "independent-reviewer", "state": "APPROVED",
                     "head_sha": SHA, "submitted_at": FINISH}],
        "checks": [{
            "id": i, "name": name, "app": app, "head_sha": SHA,
            "status": "completed", "conclusion": "success",
            "run_attempt": 1, "run_created_at": FRESH, "completed_at": FINISH,
        } for i, (name, app) in enumerate(GATES.items(), 101)],
    }


class RenovacionChecksTests(unittest.TestCase):
    def test_draft_pr_read_only_evidence_allowed(self):
        evidence = fresh_evidence()
        evidence["pr"]["draft"] = True
        before = copy.deepcopy(evidence)
        decision = evaluate(evidence)
        self.assertFalse(decision.ready)
        self.assertEqual(decision.reason, "draft_read_only_evidence")
        self.assertIsNotNone(decision.fingerprint)
        self.assertEqual(evidence, before)

    def test_draft_snapshot_decision_does_not_mask_review_veto(self):
        # A successful external status alone must not make Draft evidence ready.
        evidence = fresh_evidence()
        evidence["pr"]["draft"] = True
        evidence["statuses"][0]["description"] = "Review skipped"
        self.assertFalse(evaluate(evidence).ready)
        self.assertNotEqual(evaluate(evidence).reason, "draft_read_only_evidence")
        evidence = fresh_evidence()
        evidence["pr"]["draft"] = True
        evidence["reviews"] = []
        self.assertFalse(evaluate(evidence).ready)
        self.assertNotEqual(evaluate(evidence).reason, "draft_read_only_evidence")

    def test_draft_fork_fails_closed(self):
        evidence = fresh_evidence()
        evidence["pr"].update(draft=True, repo="outsider/Factory")
        self.assertFalse(evaluate(evidence).ready)
        self.assertNotEqual(evaluate(evidence).reason, "draft_read_only_evidence")

    def test_draft_wrong_base_fails_closed(self):
        evidence = fresh_evidence()
        evidence["pr"].update(draft=True, base_sha="c" * 40)
        self.assertFalse(evaluate(evidence).ready)
        self.assertNotEqual(evaluate(evidence).reason, "draft_read_only_evidence")

    def test_draft_head_change_between_snapshots_fails_closed(self):
        evidence = fresh_evidence()
        evidence["pr"]["draft"] = True
        evidence["after"]["head_sha"] = "c" * 40
        self.assertEqual(evaluate(evidence).reason, "identity_changed_during_revalidation")

    def test_draft_review_missing_or_skipped_fails_closed(self):
        for reviews in ([], [{"id": 501, "actor": "independent-reviewer",
                               "state": "COMMENTED", "head_sha": SHA,
                               "submitted_at": FINISH}],
                        [{"id": 501, "actor": "independent-reviewer",
                          "state": "APPROVED", "head_sha": "c" * 40,
                          "submitted_at": FINISH}],
                        [{"id": 501, "actor": "independent-reviewer",
                          "state": "APPROVED", "head_sha": SHA,
                          "submitted_at": None}]):
            with self.subTest(reviews=reviews):
                evidence = fresh_evidence()
                evidence["pr"]["draft"] = True
                evidence["reviews"] = reviews
                self.assertFalse(evaluate(evidence).ready)
                self.assertNotEqual(evaluate(evidence).reason, "draft_read_only_evidence")

    def test_draft_recovery_never_changes_pr_state(self):
        evidence = fresh_evidence()
        evidence["pr"]["draft"] = True
        original = copy.deepcopy(evidence)
        for _ in range(2):
            decision = evaluate(evidence)
            self.assertFalse(decision.ready)
            self.assertEqual(decision.reason, "draft_read_only_evidence")
        self.assertEqual(evidence, original)

    def test_approval_requires_authenticated_reviewer_write_permission(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import (
            _trusted_reviewer_permissions, EvidenceUnavailable)
        e = fresh_evidence()
        self.assertTrue(evaluate(e).ready)
        e["reviews"][0]["actor"] = "unauthorized-outsider"
        self.assertEqual(evaluate(e).reason, "review_authority_unverified")
        e["reviewer_permissions"]["unauthorized-outsider"] = "read"
        self.assertEqual(evaluate(e).reason, "review_authority_unverified")
        e["reviewer_permissions"]["unauthorized-outsider"] = "write"
        self.assertTrue(evaluate(e).ready)
        e["reviews"][0]["actor"] = "pl0n3r"
        e["reviewer_permissions"]["pl0n3r"] = "admin"
        self.assertEqual(evaluate(e).reason, "required_review_not_approved")
        e["reviews"][0]["actor"] = "unauthorized-outsider"
        e["reviews"][0]["head_sha"] = "c" * 40
        self.assertEqual(evaluate(e).reason, "required_review_not_approved")
        e["reviews"][0]["head_sha"] = SHA
        e["reviews"][0]["state"] = "CHANGES_REQUESTED"
        self.assertEqual(evaluate(e).reason, "requested_changes")

        api = Mock()
        api.repo = "pl0n3r/Factory"
        review = {"state": "APPROVED",
                  "user": {"login": "Independent-Reviewer"}}
        api.request.return_value = {
            "user": {"login": "independent-reviewer"},
            "permission": "maintain"}
        self.assertEqual(
            _trusted_reviewer_permissions(api, [review]),
            {"independent-reviewer": "maintain"})
        self.assertEqual(
            api.request.call_args.args,
            ("GET", "/repos/pl0n3r/Factory/collaborators/"
             "independent-reviewer/permission"))
        for bad in (
            {"permission": "write", "user": {"login": "attacker"}},
            {"permission": "unknown", "user": {"login": "independent-reviewer"}},
            {"permission": "write", "user": None},
            None,
        ):
            api.request.return_value = bad
            with self.subTest(bad=bad), self.assertRaises(EvidenceUnavailable):
                _trusted_reviewer_permissions(api, [review])
        api.request.side_effect = PermissionError("permission endpoint forbidden")
        with self.assertRaises(EvidenceUnavailable):
            _trusted_reviewer_permissions(api, [review])

    def test_snapshot_requires_single_live_assignee_matching_v3_owner(self):
        from unittest.mock import Mock, patch
        from scripts.renovacion_checks import (
            _verified_lease_assignee, collect_snapshot, EvidenceUnavailable)
        from scripts.coordinar_trabajo import reservation_marker
        from scripts.aceptacion_kit import contract_fingerprint
        import datetime

        for names in ([], ["outsider"], ["pl0n3r", "second"]):
            issue = {"assignees": [{"login": name} for name in names]}
            with self.subTest(names=names), self.assertRaises(EvidenceUnavailable):
                _verified_lease_assignee(issue, "pl0n3r")
        self.assertEqual(_verified_lease_assignee(
            {"assignees": [{"login": "Pl0n3r"}]}, "pl0n3r"), "pl0n3r")
        with self.assertRaises(EvidenceUnavailable):
            _verified_lease_assignee(
                {"assignees": [{"login": "pl0n3r"}],
                 "assignee": {"login": "intruso"}}, "pl0n3r")

        api = Mock()
        api.repo = "pl0n3r/Factory"
        body = """### Contexto

Contexto verificable.

### Alcance

La reserva conserva autoridad.

### Fuera de alcance

Ninguno.

### Criterios de aceptación

- [ ] [AC-01] Debe pasar el test principal.

### Contrato ejecutable

<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"check","target":"Tests de scripts"}]} -->
"""
        pin = contract_fingerprint(body)
        issue = {"number": 1114, "state": "open", "body": body,
                 "labels": [{"name": "estado: reservado"}],
                 "assignees": [{"login": "pl0n3r"}],
                 "assignee": {"login": "pl0n3r"}}
        lease = {
            "active": True, "version": 3, "reason": "renovar-contrato",
            "owner": "pl0n3r", "branch": "trabajo/issue-1114",
            "reservation_id": UUID, "acceptance_sha256": pin,
        }
        pr = {"head": {"sha": SHA, "ref": "trabajo/issue-1114",
                       "repo": {"full_name": "pl0n3r/Factory"}},
              "base": {"ref": "main", "sha": BASE_SHA},
              "body": "Reserva: " + UUID,
              "state": "open", "draft": False}
        api.pull.return_value = pr
        api.issue_comments.return_value = [{
            "user": {"login": "github-actions[bot]"},
            "body": reservation_marker(
                "pl0n3r", UUID, "trabajo/issue-1114",
                True, "renovar-contrato", pin,
                task_snapshot={
                    "task_marker_sha256": "c" * 64,
                    "task_paths": ["scripts/coordinar_trabajo.py"],
                    "task_depends_on": [],
                }),
            "created_at": FRESH,
        }]
        api.issue.side_effect = [copy.deepcopy(issue), copy.deepcopy(issue)]
        api.request.return_value = []
        with (patch("scripts.renovacion_checks._trusted_reviewer_permissions",
                    return_value={}),
              patch("scripts.renovacion_checks._snapshot_check_rows", return_value=[]),
              patch("scripts.renovacion_checks._verified_statuses", return_value=[]),
              patch("scripts.renovacion_checks._review_threads",
                    return_value=[]) as thread_reader):
            self.assertEqual(collect_snapshot(api, 123)["issue"]["owner"], "pl0n3r")
            # Draft is collected read-only and retains its real state.
            draft_pr = copy.deepcopy(pr)
            draft_pr["draft"] = True
            api.pull.side_effect = [copy.deepcopy(draft_pr), copy.deepcopy(draft_pr)]
            api.issue.side_effect = [copy.deepcopy(issue), copy.deepcopy(issue)]
            snapshot = collect_snapshot(api, 123)
            self.assertIs(snapshot["pr"]["draft"], True)
            self.assertEqual(snapshot["before"], snapshot["after"])
            self.assertEqual(snapshot["pr"]["head_sha"], SHA)
            self.assertEqual(snapshot["pr"]["base_sha"], BASE_SHA)

            self.assertGreaterEqual(api.request.call_count, 2)
            self.assertTrue(all(call.args[0] == "GET"
                                for call in api.request.call_args_list))
            # Changing Draft status between reads invalidates the evidence.
            api.pull.side_effect = [copy.deepcopy(draft_pr), copy.deepcopy(pr)]
            api.issue.side_effect = [copy.deepcopy(issue), copy.deepcopy(issue)]
            with self.assertRaisesRegex(
                    EvidenceUnavailable, "identity_changed_during_snapshot"):
                collect_snapshot(api, 123)
            api.pull.side_effect = None
            api.pull.return_value = pr

            api.issue.side_effect = [copy.deepcopy(issue),
                                     dict(copy.deepcopy(issue),
                                          assignees=[{"login": "intruso"}])]
            with self.assertRaisesRegex(EvidenceUnavailable, "lease_assignee"):
                collect_snapshot(api, 123)
            api.issue.side_effect = [dict(copy.deepcopy(issue), assignees=[])]
            with self.assertRaisesRegex(EvidenceUnavailable, "lease_assignee"):
                collect_snapshot(api, 123)

            # Un PR cuya segunda lectura conserva SHA/ref pero pierde el
            # repositorio de origen no puede acreditar identidad exact-HEAD.
            for origin in ({"full_name": "pl0n3r/AnotherRepo"},
                           None, {"full_name": 123}):
                second_pr = copy.deepcopy(pr)
                second_pr["head"]["repo"] = origin
                api.pull.side_effect = [copy.deepcopy(pr), second_pr]
                api.issue.side_effect = [copy.deepcopy(issue), copy.deepcopy(issue)]
                with self.subTest(origin=origin), self.assertRaisesRegex(
                        EvidenceUnavailable, "identity_changed_during_snapshot"):
                    collect_snapshot(api, 123)

            # Un hilo nuevo abierto después del inventario inicial no puede
            # obtener un snapshot elegible con approvals anteriores.
            first = [{"id": "PRRT_old", "isResolved": True}]
            changed = first + [{"id": "PRRT_new", "isResolved": False}]
            api.pull.side_effect = [copy.deepcopy(pr), copy.deepcopy(pr)]
            api.issue.side_effect = [copy.deepcopy(issue), copy.deepcopy(issue)]
            thread_reader.side_effect = [first, changed]
            with self.assertRaisesRegex(
                    EvidenceUnavailable, "review_threads_changed_during_snapshot"):
                collect_snapshot(api, 123)

            # La resolución de un hilo también es una carrera: reintentar con
            # un inventario estable y no conceder evidencia parcialmente leída.
            api.pull.side_effect = [copy.deepcopy(pr), copy.deepcopy(pr)]
            api.issue.side_effect = [copy.deepcopy(issue), copy.deepcopy(issue)]
            thread_reader.side_effect = [
                [{"id": "PRRT_one", "isResolved": False}],
                [{"id": "PRRT_one", "isResolved": True}],
            ]
            with self.assertRaisesRegex(
                    EvidenceUnavailable, "review_threads_changed_during_snapshot"):
                collect_snapshot(api, 123)

    def test_renewal_invalidates_old_checks_and_retries_do_not_reenable(self):
        old = fresh_evidence()
        old["checks"][0]["run_created_at"] = TIME
        self.assertFalse(evaluate(old).ready)
        retry = fresh_evidence()
        retry["checks"][0]["run_attempt"] = 2
        self.assertEqual(evaluate(retry).reason, "old_or_retried_required_run")
        incomplete = fresh_evidence()
        incomplete["checks"][0]["status"] = "queued"
        self.assertFalse(evaluate(incomplete).ready)

    def test_fresh_authorized_evidence_reconciles_same_head_and_pin(self):
        e = fresh_evidence()
        result = evaluate(e)
        self.assertTrue(result.ready)
        self.assertEqual(result.reason, "fresh_evidence_candidate_only")
        self.assertEqual(result.fingerprint, evaluate(copy.deepcopy(e)).fingerprint)

    def test_stale_wrong_identity_missing_gate_and_races_fail_closed(self):
        edits = [
            lambda e: e["pr"].update(head_sha="c" * 40),
            lambda e: e["issue"].update(acceptance_sha256="d" * 64),
            lambda e: e["renewal"].update(uuid="2" * 36),
            lambda e: e["renewal"].update(user="pl0n3r"),
            lambda e: e["checks"].pop(),
            lambda e: e["checks"][0].update(conclusion="failure"),
            lambda e: e["checks"][0].update(app="untrusted"),
            lambda e: e["checks"][0].update(head_sha="e" * 40),
            lambda e: e["after"].update(uuid="33333333-3333-4333-8333-333333333333"),
            lambda e: e["reviews"].clear(),
            lambda e: e["reviews"][0].update(state="CHANGES_REQUESTED"),
            lambda e: e.update(reviewer_required=None),
            lambda e: e["checks"].append(copy.deepcopy(e["checks"][0])),
        ]
        for change in edits:
            sample = fresh_evidence()
            change(sample)
            with self.subTest(change=str(change)):
                self.assertFalse(evaluate(sample).ready)

    def test_real_consumer_check_names_are_not_accepted_as_factory_names(self):
        sample = fresh_evidence()
        sample["repo"] = "pl0n3r/FactoryRunner"
        sample["issue"]["number"] = 461
        sample["pr"]["repo"] = "pl0n3r/FactoryRunner"
        sample["pr"]["branch"] = "trabajo/issue-461"
        sample["issue"]["branch"] = "trabajo/issue-461"
        sample["before"].update(repo="pl0n3r/FactoryRunner", issue=461,
                                branch="trabajo/issue-461")
        sample["after"].update(sample["before"])
        self.assertFalse(evaluate(sample).ready)
        # Un check distinto de un reusable workflow no debe crear falsos PASS.
        sample = fresh_evidence()
        sample["checks"][0]["name"] = "ci / Validar"
        self.assertFalse(evaluate(sample).ready)
        sample = fresh_evidence()
        sample["repo"] = "pl0n3r/UnapprovedConsumer"
        self.assertEqual(evaluate(sample).reason, "unsupported_repository_profile")

    def test_optional_failed_or_running_check_blocks(self):
        # Los checks adicionales deben estar verdes: skipped/neutral no bastan.
        for status, conclusion in (("completed", "failure"),
                                    ("in_progress", None),
                                    ("completed", "cancelled"),
                                    ("completed", "timed_out"),
                                    ("completed", "action_required"),
                                    ("completed", "skipped"),
                                    ("completed", "neutral"),
                                    ("completed", None)):
            with self.subTest(status=status, conclusion=conclusion):
                sample = fresh_evidence()
                row = copy.deepcopy(sample["checks"][0])
                row.update(id=999, name="Policy", status=status,
                           conclusion=conclusion)
                sample["checks"].append(row)
                decision = evaluate(sample)
                self.assertFalse(decision.ready)
                self.assertEqual(
                    decision.reason,
                    "other_check_in_progress" if status != "completed"
                    else "other_check_not_green",
                )
        green = fresh_evidence()
        extra = copy.deepcopy(green["checks"][0])
        extra.update(id=999, name="Policy", status="completed",
                     conclusion="success")
        green["checks"].append(extra)
        self.assertTrue(evaluate(green).ready)

    def test_extra_success_requires_fresh_first_attempt_after_renewal(self):
        """Un check Policy antiguo/reintentado nunca restaura Validar."""
        good = fresh_evidence()
        extra = copy.deepcopy(good["checks"][0])
        extra.update(id=999, name="Policy", status="completed",
                     conclusion="success")
        good["checks"].append(extra)
        self.assertTrue(evaluate(good).ready)
        for change in (
            {"run_created_at": TIME},
            {"run_created_at": "2026-10-11T17:58:00Z"},
            {"run_created_at": "2099-01-01T00:00:00Z"},
            {"run_created_at": None},
            {"completed_at": TIME},
            {"completed_at": "2099-01-01T00:00:00Z"},
            {"completed_at": None},
            {"run_attempt": 2},
            {"run_attempt": True},
            {"run_attempt": None},
        ):
            case = fresh_evidence()
            extra = copy.deepcopy(case["checks"][0])
            extra.update(id=999, name="Policy", status="completed",
                         conclusion="success", **change)
            case["checks"].append(extra)
            with self.subTest(change=change):
                self.assertEqual(evaluate(case).reason, "other_check_not_fresh")

    def test_informational_skips_do_not_whitelist_policy_or_alias(self):
        """Solo la simulación exacta de GitHub Actions es informativa."""
        example = fresh_evidence()
        row = copy.deepcopy(example["checks"][0])
        row.update(id=998, name="Auto-merge simulación", app="github-actions",
                   status="completed", conclusion="skipped")
        example["checks"].append(row)
        self.assertTrue(evaluate(example).ready)
        for name, app, conclusion in (
            ("Policy", "github-actions", "skipped"),
            ("Auto-merge simulación", "unknown", "skipped"),
            ("Auto-merge simulacion", "github-actions", "skipped"),
            ("Auto-merge simulación", "github-actions", "neutral"),
            ("Auto-merge simulación", "github-actions", None),
        ):
            row.update(name=name, app=app, conclusion=conclusion)
            with self.subTest(name=name, app=app, conclusion=conclusion):
                self.assertEqual(
                    evaluate(example).reason, "other_check_not_green"
                )

    def test_historical_invalidation_is_not_a_green_job_or_new_fingerprint(self):
        sample = fresh_evidence()
        original = evaluate(sample)
        veto = copy.deepcopy(sample["checks"][0])
        veto.update(id=902, name="Validar", title="Renovación explícita del contrato",
                    conclusion="failure", status="completed",
                    run_created_at=TIME)
        sample["checks"].append(veto)
        result = evaluate(sample)
        self.assertTrue(result.ready)
        self.assertEqual(result.fingerprint, original.fingerprint)
        # Duplicar el job real sí es ambiguo, no se elige el más reciente.
        duplicate = copy.deepcopy(sample["checks"][1])
        duplicate["id"] = 903
        sample["checks"].append(duplicate)
        self.assertFalse(evaluate(sample).ready)

    def test_old_head_changes_requested_remains_veto_after_new_head(self):
        e = fresh_evidence()
        e["reviews"].append({
            "id": 502, "actor": "blocking-reviewer",
            "state": "CHANGES_REQUESTED", "head_sha": "c" * 40,
            "submitted_at": "2026-10-11T18:05:00Z",
        })
        self.assertEqual(evaluate(e).reason, "requested_changes")
        # COMMENTED del mismo actor no resuelve el veto.
        e["reviews"].append({
            "id": 503, "actor": "blocking-reviewer",
            "state": "COMMENTED", "head_sha": SHA,
            "submitted_at": "2026-10-11T18:08:00Z",
        })
        self.assertFalse(evaluate(e).ready)
        # Solo la posterior APPROVED del mismo revisor sobre HEAD actual resuelve.
        e["reviews"].append({
            "id": 504, "actor": "blocking-reviewer",
            "state": "APPROVED", "head_sha": SHA,
            "submitted_at": "2026-10-11T18:11:00Z",
        })
        e["reviewer_permissions"]["blocking-reviewer"] = "maintain"
        self.assertTrue(evaluate(e).ready)

    def test_approval_wrong_head_or_ambiguous_review_sequence_fails_closed(self):
        e = fresh_evidence()
        e["reviews"][0]["head_sha"] = "c" * 40
        self.assertFalse(evaluate(e).ready)
        e = fresh_evidence()
        e["reviews"].append({
            "id": 504, "actor": "blocking-reviewer",
            "state": "CHANGES_REQUESTED", "head_sha": "c" * 40,
            "submitted_at": FINISH,
        })
        self.assertEqual(evaluate(e).reason, "ambiguous_review_order")
        e = fresh_evidence()
        e["reviews"].append(copy.deepcopy(e["reviews"][0]))
        self.assertEqual(evaluate(e).reason, "ambiguous_review_history")
        e = fresh_evidence()
        e["reviews"][0]["state"] = "DISMISSED"
        self.assertFalse(evaluate(e).ready)

    def test_recovery_fingerprint_tracks_authorized_review_not_noise(self):
        e = fresh_evidence()
        initial = evaluate(e)
        self.assertTrue(initial.ready)
        noise = copy.deepcopy(e["checks"][0])
        noise.update(id=9999, name="Auto-merge simulación",
                     status="completed", conclusion="skipped")
        e["checks"].append(noise)
        self.assertEqual(evaluate(e).fingerprint, initial.fingerprint)
        e["reviewer_permissions"]["second-reviewer"] = "admin"
        e["reviews"].append({
            "id": 502, "actor": "second-reviewer", "state": "APPROVED",
            "head_sha": SHA, "submitted_at": "2026-10-11T18:13:00Z",
        })
        self.assertTrue(evaluate(e).ready)
        self.assertNotEqual(evaluate(e).fingerprint, initial.fingerprint)
        # Una revocación por el segundo revisor no queda escondida en el fingerprint.
        e["reviews"].append({
            "id": 503, "actor": "second-reviewer", "state": "CHANGES_REQUESTED",
            "head_sha": SHA, "submitted_at": "2026-10-11T18:14:00Z",
        })
        self.assertEqual(evaluate(e).reason, "requested_changes")

    def test_workflow_permissions_and_idempotence(self):
        # La implementación inicial es PURA: no debe poder escribir checks.
        source = (Path(__file__).resolve().parents[1]
                  / "scripts" / "renovacion_checks.py").read_text()
        self.assertNotIn('"/check-runs"', source)
        self.assertNotIn("GH_TOKEN", source)
        sample = fresh_evidence()
        first = evaluate(sample)
        second = evaluate(sample)
        self.assertEqual(first, second)
        self.assertTrue(first.fingerprint)
        self.assertFalse(evaluate({}).ready)

    def test_required_check_rejects_other_workflow_same_job_name(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _normalized_check, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        row = {"id": 44, "name": "Tests de scripts",
               "app": {"slug": "github-actions"},
               "head_sha": SHA, "status": "completed",
               "conclusion": "success", "completed_at": FINISH,
               "details_url":
                 "https://github.com/pl0n3r/Factory/actions/runs/22/job/33"}
        run = {"id": 22, "event": "pull_request", "head_sha": SHA,
               "repository": {"full_name": "pl0n3r/Factory"},
               "created_at": FRESH, "run_attempt": 1,
               "path": ".github/workflows/factory-ci.yml"}
        job = {"id": 33, "run_id": 22, "name": "Tests de scripts",
               "status": "completed", "conclusion": "success",
               "check_run_url":
                 "https://api.github.com/repos/pl0n3r/Factory/check-runs/44"}
        api.request.side_effect = [run, job]
        self.assertEqual(_normalized_check(api, row, SHA)["run_id"], 22)
        for wrong in (".github/workflows/otro.yml",
                      ".github/workflows/coordinacion-trabajo.yml",
                      "", None):
            api.request.side_effect = [dict(run, path=wrong), job]
            with self.subTest(path=wrong), self.assertRaises(EvidenceUnavailable):
                _normalized_check(api, row, SHA)
        # Un job con el mismo nombre no puede provenir de workflow desconocido.
        row["name"] = "Validar claims V3 del PR"
        job = dict(job, name=row["name"])
        api.request.side_effect = [run, job]
        with self.assertRaises(EvidenceUnavailable):
            _normalized_check(api, row, SHA)
        api.request.side_effect = [
            dict(run, path=".github/workflows/coordinacion-trabajo.yml"), job]
        self.assertEqual(_normalized_check(api, row, SHA)["run_id"], 22)

    def test_collector_rejects_fake_or_old_workflow_job(self):
        from scripts.renovacion_checks import _normalized_check, EvidenceUnavailable
        from unittest.mock import Mock
        api = Mock()
        api.repo = "pl0n3r/Factory"
        row = {"id": 1, "name": "Tests de scripts",
               "app": {"slug": "github-actions"}, "head_sha": SHA,
               "status": "completed", "conclusion": "success",
               "completed_at": FINISH, "details_url": "https://attacker.example/1"}
        with self.assertRaises(EvidenceUnavailable):
            _normalized_check(api, row, SHA)
        row["details_url"] = (
            "https://github.com/pl0n3r/Factory/actions/runs/11/job/12")
        api.request.side_effect = [
            {"id": 11, "event": "pull_request", "head_sha": SHA,
             "repository": {"full_name": "pl0n3r/Factory"},
             "path": ".github/workflows/factory-ci.yml",
             "run_attempt": 2, "created_at": TIME},
            {"id": 12, "run_id": 11, "conclusion": "success",
             "status": "completed", "name": "Tests de scripts",
             "check_run_url": "https://api.github.com/repos/pl0n3r/Factory/check-runs/1"},
        ]
        normalized = _normalized_check(api, row, SHA)
        self.assertEqual(normalized["run_attempt"], 2)
        self.assertEqual(normalized["run_created_at"], TIME)
        e = fresh_evidence()
        e["checks"][0].update(normalized)
        self.assertEqual(evaluate(e).reason, "old_or_retried_required_run")

    def test_collector_rejects_partial_check_inventory_and_unapproved_repo(self):
        from scripts.renovacion_checks import (_check_rows, collect_snapshot,
                                                EvidenceUnavailable)
        from unittest.mock import Mock
        api = Mock()
        api.repo = "pl0n3r/Factory"
        api.request.return_value = {"total_count": 100, "check_runs": [{}] * 100}
        with self.assertRaises(EvidenceUnavailable):
            _check_rows(api, SHA)
        api.repo = "unknown/repo"
        with self.assertRaises(EvidenceUnavailable):
            collect_snapshot(api, 1242)


    def test_check_inventory_reads_more_than_one_page_and_rechecks_stability(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _check_rows, _check_inventory
        api = Mock()
        api.repo = "pl0n3r/Factory"
        records = [{"id": i, "name": f"gate-{i}", "head_sha": SHA}
                   for i in range(1, 136)]
        paths = []

        def fake(_method, path):
            paths.append(path)
            page = 2 if "&page=2" in path else 1
            return {"total_count": len(records),
                    "check_runs": records[(page - 1) * 100:page * 100]}

        api.request.side_effect = fake
        for filtered, reader in (("latest", _check_rows),
                                 ("all", lambda client, sha:
                                  _check_inventory(client, sha, "all"))):
            with self.subTest(filter=filtered):
                paths.clear()
                self.assertEqual([x["id"] for x in reader(api, SHA)],
                                 list(range(1, 136)))
                self.assertEqual(len(paths), 4)
                self.assertIn(f"filter={filtered}&per_page=100", paths[0])
                self.assertTrue(paths[1].endswith("&page=2"))
                self.assertEqual(paths[:2], paths[2:])

    def test_check_inventory_rejects_duplicates_partial_and_concurrent_changes(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _check_rows, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        records = [{"id": i, "name": "gate", "head_sha": SHA}
                   for i in range(1, 102)]

        def result(payloads):
            api.request.side_effect = payloads
            with self.assertRaises(EvidenceUnavailable):
                _check_rows(api, SHA)

        first = {"total_count": 101, "check_runs": records[:100]}
        last = {"total_count": 101, "check_runs": records[100:]}
        result([first, {"total_count": 100, "check_runs": records[100:]}])
        result([first, {"total_count": 101, "check_runs": []}])
        result([first, {"total_count": 101,
                        "check_runs": [dict(records[100], id=records[0]["id"])]}])
        result([first, last,
                {"total_count": 101,
                 "check_runs": [dict(records[0], name="changed")] + records[1:100]},
                last])
        api.request.side_effect = [{
            "total_count": 501, "check_runs": records[:100]}]
        with self.assertRaisesRegex(EvidenceUnavailable, "check_inventory_partial"):
            _check_rows(api, SHA)

    def test_reconcile_requires_trusted_trigger_and_never_writes_on_false(self):
        from unittest.mock import Mock, patch
        from scripts.renovacion_checks import (
            reconcile_from_workflow_run, EvidenceUnavailable,
        )
        api = Mock()
        api.repo = "pl0n3r/Factory"
        # No se acepta input de repo tercero ni ID de run inválido.
        api.repo = "attacker/fork"
        with self.assertRaises(EvidenceUnavailable):
            reconcile_from_workflow_run(api, 12)
        api.repo = "pl0n3r/Factory"
        with patch("scripts.coordinar_trabajo.require_sweep_running"):
            api.request.return_value = {
                "id": 12, "name": "CI factory", "event": "workflow_dispatch",
                "status": "completed", "conclusion": "success",
                "run_attempt": 1, "head_sha": SHA,
                "head_repository": {"full_name": "pl0n3r/Factory"},
                "pull_requests": [{"number": 123}],
            }
            with self.assertRaises(EvidenceUnavailable):
                reconcile_from_workflow_run(api, 12)
        self.assertTrue(all(call.args[0] == "GET"
                            for call in api.request.call_args_list))

    def test_reconcile_fresh_snapshot_cannot_bypass_approval_or_red_gate(self):
        # Cualquier veto de aprobación, fecha o status invalida el candidato
        # incluso si los checks de aceptación nuevos pasaron.
        data = fresh_evidence()
        data["checks"][1]["status"] = "queued"
        self.assertFalse(evaluate(data).ready)
        data = fresh_evidence()
        data["reviews"][0]["submitted_at"] = TIME
        self.assertFalse(evaluate(data).ready)
        data = fresh_evidence()
        data["issue"]["reservation_id"] = "99999999-2222-4333-8444-555555555555"
        self.assertFalse(evaluate(data).ready)


    def test_external_code_review_status_must_be_fresh_and_green(self):
        candidate = fresh_evidence()
        self.assertTrue(evaluate(candidate).ready)
        for change in (
            lambda v: v["statuses"].clear(),
            lambda v: v["statuses"][0].update(state="failure"),
            lambda v: v["statuses"][0].update(created_at=TIME),
            lambda v: v["statuses"][0].update(context="Other"),
        ):
            sample = fresh_evidence()
            change(sample)
            with self.subTest(change=str(change)):
                self.assertFalse(evaluate(sample).ready)

    def test_coderabbit_success_without_completed_review_is_unknown(self):
        # D-069: CodeRabbit SUCCESS no prueba análisis al ser skipped/limitado.
        for description in (
            "Review rate limited",
            "Review skipped: manual review required for this OSS repository",
            "Review skipped: draft pull request",
            "Review pending",
            "Quota exceeded",
            "Analysis unavailable",
            "",
        ):
            with self.subTest(description=description):
                sample = fresh_evidence()
                sample["statuses"][0]["description"] = description
                self.assertEqual(evaluate(sample).reason,
                                 "coderabbit_review_not_verified")
        verified = fresh_evidence()
        verified["statuses"][0]["description"] = "Review completed"
        self.assertTrue(evaluate(verified).ready)

    def test_recovered_renewal_lineage_is_exact_and_fail_closed(self):
        from scripts.coordinar_trabajo import reservation_marker, reservation_from_text
        from scripts.renovacion_checks import (
            _trusted_renewal_lineage, EvidenceUnavailable)

        recovered_id = "22222222-3333-4444-8555-666666666666"
        claims = {"task_marker_sha256": "c" * 64,
                  "task_paths": ["scripts/renovacion_checks.py"],
                  "task_depends_on": [1081]}

        def mark(uuid, reason, when, owner="pl0n3r", active=True,
                 pin=PIN, paths=None, actor_type="Bot"):
            task = copy.deepcopy(claims)
            if paths is not None:
                task["task_paths"] = paths
            body = reservation_marker(
                owner, uuid, "trabajo/issue-1114", active,
                reason, pin, task_snapshot=task)
            return {"user": {"login": "github-actions[bot]", "type": actor_type},
                    "body": body, "created_at": when, "updated_at": when}

        first = mark(UUID, "renovar-contrato", TIME)
        second = mark(recovered_id, "recuperacion-inactividad", FRESH)
        current = reservation_from_text(second["body"])
        proof = _trusted_renewal_lineage([first, second], current)
        self.assertEqual(proof["renewal_uuid"], UUID)
        self.assertEqual(proof["current_uuid"], recovered_id)
        self.assertEqual(proof["acceptance_sha256"], PIN)
        self.assertEqual(proof["recovery_count"], 1)
        self.assertEqual(proof["transfer_count"], 0)
        transferred_id = "33333333-4444-4555-8666-777777777777"
        final_id = "44444444-5555-4666-8777-888888888888"
        transferred = mark(transferred_id, "transferir", FINISH)
        final = mark(final_id, "recuperacion-inactividad",
                     "2026-10-11T18:14:00Z")
        current_final = reservation_from_text(final["body"])
        mixed = _trusted_renewal_lineage(
            [first, second, transferred, final], current_final)
        self.assertEqual(mixed["renewal_uuid"], UUID)
        self.assertEqual(mixed["current_uuid"], final_id)
        self.assertEqual(mixed["recovery_count"], 2)
        self.assertEqual(mixed["transfer_count"], 1)
        direct_transfer = mark(transferred_id, "transferir", FRESH)
        direct = _trusted_renewal_lineage(
            [first, direct_transfer],
            reservation_from_text(direct_transfer["body"]))
        self.assertEqual(direct["recovery_count"], 0)
        self.assertEqual(direct["transfer_count"], 1)
        for bad_transfer in (
            mark(transferred_id, "transferir", FINISH, owner="intruder"),
            mark(transferred_id, "transferir", FINISH, pin="d" * 64),
            mark(transferred_id, "transferir", FINISH,
                 paths=["scripts/foreign.py"]),
            mark(transferred_id, "transferir", FRESH),
            mark(recovered_id, "transferir", FINISH),
            mark(transferred_id, "transferir", FINISH, actor_type="User"),
        ):
            with self.subTest(transfer=bad_transfer["body"]):
                with self.assertRaises(EvidenceUnavailable):
                    _trusted_renewal_lineage(
                        [first, second, bad_transfer],
                        reservation_from_text(bad_transfer["body"]))

        negatives = [
            mark(recovered_id, "recuperacion-inactividad", FRESH, owner="intruder"),
            mark(recovered_id, "recuperacion-inactividad", FRESH, pin="d" * 64),
            mark(recovered_id, "recuperacion-inactividad", FRESH,
                 paths=["scripts/foreign.py"]),
            mark(recovered_id, "recuperacion-inactividad", FRESH, active=False),
            mark(UUID, "recuperacion-inactividad", FRESH),
            mark(recovered_id, "recuperacion-inactividad", TIME),
            mark(recovered_id, "recuperacion-inactividad", FRESH,
                 actor_type="User"),
        ]
        for invalid in negatives:
            with self.subTest(reason=invalid["body"]):
                with self.assertRaises(EvidenceUnavailable):
                    _trusted_renewal_lineage(
                        [first, invalid],
                        reservation_from_text(invalid["body"]))
        edited = dict(second, updated_at=FINISH)
        with self.assertRaises(EvidenceUnavailable):
            _trusted_renewal_lineage([first, edited], current)
        duplicate = dict(second, body=second["body"] +
                         "\n<!-- condor-reserva {} -->")
        with self.assertRaises(EvidenceUnavailable):
            _trusted_renewal_lineage([first, duplicate], current)
        # Última clave prevalente: el parser genérico la normalizaría
        # al mismo V3, pero la procedencia bot debe rechazar la ambigüedad.
        for field, original, tampered in (
            ("active", '"active":true', '"active":false,"active":true'),
            ("reservation_id",
             '"reservation_id":"' + recovered_id + '"',
             '"reservation_id":"' + UUID + '","reservation_id":"' +
             recovered_id + '"'),
        ):
            ambiguous = dict(second, body=second["body"].replace(
                original, tampered))
            self.assertNotEqual(ambiguous["body"], second["body"])
            self.assertEqual(reservation_from_text(ambiguous["body"]), current)
            with self.subTest(duplicated_field=field):
                with self.assertRaisesRegex(
                        EvidenceUnavailable, "renewal_lineage_untrusted_marker"):
                    _trusted_renewal_lineage([first, ambiguous], current)
        malformed_and_valid = dict(second, body=(
            "<!-- condor-reserva {INVALID} -->\n" + second["body"]))
        with self.assertRaisesRegex(
                EvidenceUnavailable, "renewal_lineage_untrusted_marker"):
            _trusted_renewal_lineage([first, malformed_and_valid], current)
        with self.assertRaises(EvidenceUnavailable):
            _trusted_renewal_lineage([second], current)

    def test_recovered_lineage_snapshot_remains_fail_closed_without_ancestry(self):
        from unittest.mock import Mock
        from scripts.aceptacion_kit import contract_fingerprint
        from scripts.coordinar_trabajo import reservation_marker
        from scripts.renovacion_checks import collect_snapshot, EvidenceUnavailable

        body = ("### Contexto\nContexto verificable.\n\n### Alcance\n"
                "Reserva vigente.\n\n### Fuera de alcance\n"
                "Sin datos reales, escritura privilegiada ni producción.\n\n### Criterios de aceptación\n"
                "- [ ] [AC-01] Test.\n\n### Contrato ejecutable\n"
                '<!-- factory-acceptance {"version":1,"criteria":'
                '[{"id":"AC-01","kind":"check","target":"Tests de scripts"}]} -->\n')
        pin = contract_fingerprint(body)
        newer = "22222222-3333-4444-8555-666666666666"
        task = {"task_marker_sha256": "c" * 64,
                "task_paths": ["scripts/renovacion_checks.py"],
                "task_depends_on": [1081]}

        def message(reservation, reason, stamp, pin_value=pin):
            return {"user": {"login": "github-actions[bot]", "type": "Bot"},
                    "created_at": stamp, "updated_at": stamp,
                    "body": reservation_marker(
                        "pl0n3r", reservation, "trabajo/issue-1114", True,
                        reason, pin_value, task_snapshot=task)}

        original = message(UUID, "renovar-contrato", TIME)
        recovery = message(newer, "recuperacion-inactividad", FRESH)
        api = Mock()
        api.repo = "pl0n3r/Factory"
        api.pull.return_value = {
            "head": {"sha": SHA, "ref": "trabajo/issue-1114",
                     "repo": {"full_name": "pl0n3r/Factory"}},
            "base": {"sha": BASE_SHA, "ref": "main"},
            "state": "open", "draft": False,
            "body": "<!-- condor-reserva-id: " + newer + " -->",
        }
        api.issue.return_value = {"number": 1114, "state": "open", "body": body}
        api.issue_comments.return_value = [original, recovery]
        with self.assertRaisesRegex(
                EvidenceUnavailable, "recovered_generation_pending_ancestry_proof"):
            collect_snapshot(api, 1242)
        api.request.assert_not_called()

        bad = copy.deepcopy(recovery)
        bad["user"]["type"] = "User"
        api.issue_comments.return_value = [original, bad]
        with self.assertRaisesRegex(EvidenceUnavailable,
                                    "renewal_lineage_untrusted_marker"):
            collect_snapshot(api, 1242)
        api.request.assert_not_called()

    def test_invalidation_happens_before_bot_reservation_marker(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _invalidation_present
        from datetime import datetime, timezone
        api = Mock()
        api.repo = "pl0n3r/Factory"
        stamp = datetime(2026, 10, 12, 1, 0, 0, tzinfo=timezone.utc)
        row = {
            "id": 34, "name": "Validar", "status": "completed",
            "conclusion": "failure", "head_sha": SHA,
            "completed_at": "2026-10-12T00:59:58Z",
            "app": {"slug": "github-actions"},
            "output": {
                "title": "Renovación explícita del contrato",
                "summary": (
                    f"Issue #1114: contrato renovado explícitamente; "
                    f"reserva V3 {UUID}; aceptación SHA-256 {PIN}; "
                    "la evidencia previa del HEAD no es válida. Ejecuta CI nuevo."
                ),
            },
        }
        api.request.return_value = {"total_count": 1, "check_runs": [row]}
        self.assertTrue(_invalidation_present(api, SHA, stamp, 1114, UUID, PIN))
        row["completed_at"] = "2026-10-12T01:00:04Z"
        self.assertFalse(_invalidation_present(api, SHA, stamp, 1114, UUID, PIN))
        row["completed_at"] = "2026-10-12T00:59:58Z"
        row["output"]["summary"] = "Issue #1000: contrato renovado explícitamente;"
        self.assertFalse(_invalidation_present(api, SHA, stamp, 1114, UUID, PIN))


    def test_two_renewals_on_same_sha_require_own_invalidation(self):
        from datetime import datetime, timezone
        from unittest.mock import Mock
        from scripts.renovacion_checks import _invalidation_present

        api = Mock()
        api.repo = "pl0n3r/Factory"
        prior = {
            "id": 101, "name": "Validar", "head_sha": SHA,
            "status": "completed", "conclusion": "failure",
            "completed_at": "2026-10-12T01:00:01Z",
            "app": {"slug": "github-actions"},
            "output": {"title": "Renovación explícita del contrato",
                       "summary": (
                           f"Issue #1114: contrato renovado explícitamente; "
                           f"reserva V3 {UUID}; aceptación SHA-256 {PIN}; "
                           "la evidencia previa del HEAD no es válida. Ejecuta CI nuevo."
                       )},
        }
        second_uuid = "33333333-4444-4555-8666-777777777777"
        second_pin = "c" * 64
        second_marker = datetime(2026, 10, 12, 1, 2, 30, tzinfo=timezone.utc)
        api.request.return_value = {"total_count": 1, "check_runs": [prior]}
        # El veto previo está en la ventana de 300s, pero no es de la nueva lease.
        self.assertFalse(_invalidation_present(
            api, SHA, second_marker, 1114, second_uuid, second_pin))
        second = copy.deepcopy(prior)
        second["id"] = 102
        second["completed_at"] = "2026-10-12T01:02:28Z"
        second["output"]["summary"] = (
            f"Issue #1114: contrato renovado explícitamente; "
            f"reserva V3 {second_uuid}; aceptación SHA-256 {second_pin}; "
            "la evidencia previa del HEAD no es válida. Ejecuta CI nuevo."
        )
        api.request.return_value = {
            "total_count": 2, "check_runs": [prior, second]}
        self.assertTrue(_invalidation_present(
            api, SHA, second_marker, 1114, second_uuid, second_pin))
        # Duplicado exacto de la misma generación: historial ambiguo, fallo cerrado.
        api.request.return_value["check_runs"].append(dict(second, id=103))
        api.request.return_value["total_count"] = 3
        self.assertFalse(_invalidation_present(
            api, SHA, second_marker, 1114, second_uuid, second_pin))
        # El formato legacy no acredita UUID ni pin y debe rechazarse.
        api.request.return_value = {"total_count": 1, "check_runs": [
            dict(prior, output={"title": "Renovación explícita del contrato",
                                "summary": "Issue #1114: contrato renovado explícitamente;"})
        ]}
        self.assertFalse(_invalidation_present(
            api, SHA, second_marker, 1114, second_uuid, second_pin))

    def test_restoration_refuses_writes_even_if_unsafe_opt_in_is_set(self):
        from unittest.mock import Mock, patch
        from scripts.renovacion_checks import reconcile_from_workflow_run, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        run = {"id": 128, "name": "CI factory", "event": "pull_request",
               "status": "completed", "conclusion": "success",
               "run_attempt": 1, "head_sha": SHA,
               "path": ".github/workflows/factory-ci.yml",
               "created_at": FRESH, "head_repository": {"full_name": "pl0n3r/Factory"},
               "pull_requests": [{"number": 101}]}
        writes = []
        def request(method, path, data=None):
            if method == "POST":
                writes.append((path, data))
                return {"id": 7000}
            if path.endswith("/actions/runs/128"):
                return run
            if "/compare/main..." in path:
                return {"behind_by": 0, "ahead_by": 2}
            raise AssertionError(f"unexpected {method} {path}")
        api.request.side_effect = request
        data = fresh_evidence()
        for row in data["checks"]:
            if row["name"] in ("Tests de scripts", "Validar", "Criterios de aceptación"):
                row["run_id"] = 128
        with (patch.dict("os.environ", {"FACTORY_RENEWAL_CHECK_WRITER_ENABLED": "1"}),
              patch("scripts.coordinar_trabajo.require_sweep_running") as switch,
              patch("scripts.renovacion_checks.collect_snapshot", side_effect=[
                  data, copy.deepcopy(data)]) as read,
              patch("scripts.renovacion_checks._already_restored", return_value=False),
              patch("scripts.renovacion_checks._invalidation_present", return_value=True)):
            with self.assertRaisesRegex(
                EvidenceUnavailable, "shared_v3_cas_not_implemented"
            ):
                reconcile_from_workflow_run(api, 128)
            self.assertEqual(read.call_count, 2)
            self.assertEqual(switch.call_count, 2)
        self.assertEqual(writes, [])
        self.assertFalse(any(c.args[0] == "POST" for c in api.request.call_args_list))

    def test_recovery_writer_aborts_on_second_snapshot_review_change(self):
        from unittest.mock import Mock, patch
        from scripts.renovacion_checks import reconcile_from_workflow_run, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        api.request.side_effect = lambda method, path, data=None: (
            {"id": 128, "name": "CI factory", "event": "pull_request",
             "status": "completed", "conclusion": "success",
             "run_attempt": 1, "head_sha": SHA,
             "path": ".github/workflows/factory-ci.yml",
             "created_at": FRESH,
             "head_repository": {"full_name": "pl0n3r/Factory"},
             "pull_requests": [{"number": 101}]}
            if path.endswith("/actions/runs/128") else
            {"behind_by": 0, "ahead_by": 2}
            if "/compare/main..." in path else
            (_ for _ in ()).throw(AssertionError("unexpected write")))
        good = fresh_evidence()
        for row in good["checks"]:
            if row["name"] in ("Tests de scripts", "Validar", "Criterios de aceptación"):
                row["run_id"] = 128
        revoked = copy.deepcopy(good)
        revoked["reviews"][0]["state"] = "CHANGES_REQUESTED"
        with (patch("scripts.coordinar_trabajo.require_sweep_running"),
              patch("scripts.renovacion_checks.collect_snapshot", side_effect=[
                  good, revoked]),
              patch("scripts.renovacion_checks._already_restored", return_value=False),
              patch("scripts.renovacion_checks._invalidation_present", return_value=True)):
            with self.assertRaises(EvidenceUnavailable):
                reconcile_from_workflow_run(api, 128)

    def test_recovery_workflow_uses_default_branch_and_minimal_writer_job(self):
        text = ((Path(__file__).resolve().parents[1]
                 / ".github/workflows/coordinacion-trabajo.yml").read_text())
        self.assertIn("workflow_run:", text)
        self.assertIn("workflows: ['CI factory']", text)
        self.assertIn("name: Reconciliar Validar con prueba fresca", text)
        block = (text.split("name: Reconciliar Validar con prueba fresca", 1)[1]
                 .split("\n  comando-comentario:", 1)[0])
        # Sin CAS verificado el job tiene permiso solo de lectura.
        self.assertIn("checks: read", block)
        self.assertIn("issues: read", block)
        self.assertIn("pull-requests: read", block)
        self.assertNotIn("pull-requests: write", block)
        self.assertIn("ref: "+"${{ github.event.repository.default_branch }}", block)
        self.assertIn("python3 -m scripts.renovacion_checks", block)
        self.assertEqual(block.count("checks: write"), 0)


    def test_writer_fails_closed_without_shared_cas_activation(self):
        from unittest.mock import Mock, patch
        from scripts.renovacion_checks import reconcile_from_workflow_run
        api = Mock()
        api.repo = "pl0n3r/Factory"
        data = fresh_evidence()
        for row in data["checks"]:
            if row["name"] in ("Tests de scripts", "Validar", "Criterios de aceptación"):
                row["run_id"] = 128
        def only_reads(method, path, payload=None):
            self.assertEqual(method, "GET")
            if path.endswith("/actions/runs/128"):
                return {"id": 128, "name": "CI factory", "event": "pull_request",
                        "status": "completed", "conclusion": "success",
                        "run_attempt": 1, "head_sha": SHA,
                        "path": ".github/workflows/factory-ci.yml",
                        "created_at": FRESH,
                        "head_repository": {"full_name": "pl0n3r/Factory"},
                        "pull_requests": [{"number": 101}]}
            if "/compare/main..." in path:
                return {"behind_by": 0, "ahead_by": 2}
            raise AssertionError("GET no previsto: " + path)
        api.request.side_effect = only_reads
        with (patch.dict("os.environ", {}, clear=True),
              patch("scripts.coordinar_trabajo.require_sweep_running"),
              patch("scripts.renovacion_checks.collect_snapshot",
                    side_effect=[data, copy.deepcopy(data)]),
              patch("scripts.renovacion_checks._already_restored", return_value=False),
              patch("scripts.renovacion_checks._invalidation_present", return_value=True)):
            self.assertEqual(reconcile_from_workflow_run(api, 128),
                             "disabled_pending_cas_and_review_threads")

    def test_future_evidence_uuid_and_review_skipped_are_rejected(self):
        item = fresh_evidence()
        item["issue"]["reservation_id"] = "3945eeb7-1df8-7439-b196-98897eb3a71a"
        item["before"]["uuid"] = item["after"]["uuid"] = item["renewal"]["uuid"] = item["issue"]["reservation_id"]
        self.assertFalse(evaluate(item).ready)
        item = fresh_evidence()
        item["statuses"][0]["description"] = "Review skipped: manual review required"
        self.assertFalse(evaluate(item).ready)
        item = fresh_evidence()
        for row in item["checks"]:
            row["run_created_at"] = "2099-01-01T18:10:00Z"
            row["completed_at"] = "2099-01-01T18:12:00Z"
        item["reviews"][0]["submitted_at"] = "2099-01-01T18:13:00Z"
        self.assertFalse(evaluate(item).ready)

    def test_owner_and_review_threads_are_verifiable_gates(self):
        x = fresh_evidence()
        self.assertTrue(evaluate(x).ready)
        x["issue"].pop("owner")
        x["reviews"][0]["actor"] = "pl0n3r"
        self.assertEqual(evaluate(x).reason, "reservation_owner_untrusted")
        x = fresh_evidence()
        x["issue"]["owner"] = "attacker"
        self.assertFalse(evaluate(x).ready)
        x = fresh_evidence()
        x["review_threads"] = [{"id": "PRRT_123", "isResolved": False}]
        self.assertEqual(evaluate(x).reason, "unresolved_or_untrusted_review_thread")
        x["review_threads"][0]["isResolved"] = True
        self.assertTrue(evaluate(x).ready)

    def test_combined_status_inventory_partial_or_failed_fails_closed(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _verified_statuses, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        status = {"id": 51, "context": "CodeRabbit", "state": "success",
                  "created_at": FRESH, "description": "Review completed"}
        api.request.return_value = {
            "state": "success", "total_count": 31, "statuses": [status] * 30}
        with self.assertRaises(EvidenceUnavailable):
            _verified_statuses(api, SHA)
        api.request.return_value = {
            "state": "failure", "total_count": 1, "statuses": [status]}
        with self.assertRaises(EvidenceUnavailable):
            _verified_statuses(api, SHA)
        combined = {"state": "success", "total_count": 1,
                    "statuses": [status]}
        detail = dict(status, creator={"login": "coderabbitai[bot]"})
        api.request.side_effect = [combined, [detail]]
        records = _verified_statuses(api, SHA)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["creator"], "coderabbitai[bot]")
        paths = [call.args[1] for call in api.request.call_args_list[-2:]]
        self.assertIn("/status?per_page=100", paths[0])
        self.assertIn("/statuses?per_page=100", paths[1])

    def test_dual_status_inventory_requires_authenticated_identity_and_consistency(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _verified_statuses, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        status = {"id": 78, "context": "CodeRabbit", "state": "success",
                  "created_at": FRESH, "description": "Review completed"}
        aggregate = {"state": "success", "total_count": 1,
                     "statuses": [status]}
        genuine = dict(status, creator={"login": "coderabbitai[bot]"})
        cases = (
            [],
            [dict(genuine, id=79)],
            [dict(genuine, state="failure")],
            [dict(genuine, description="Review skipped")],
            [dict(status)],
            [dict(status, creator=None)],
            [dict(status, creator={"login": ""})],
            [genuine, genuine],
        )
        for details in cases:
            with self.subTest(details=details):
                api.request.side_effect = [aggregate, details]
                with self.assertRaises(EvidenceUnavailable):
                    _verified_statuses(api, SHA)
        # Un creator falsificado en el resumen no desplaza el actor auténtico.
        forged = dict(status, creator={"login": "attacker"})
        api.request.side_effect = [
            dict(aggregate, statuses=[forged]), [genuine]]
        self.assertEqual(_verified_statuses(api, SHA)[0]["creator"],
                         "coderabbitai[bot]")

    def test_review_threads_missing_permissions_open_and_paginated_fail_closed(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _review_threads, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        api.request.return_value = {"errors": [{"message": "forbidden"}]}
        with self.assertRaises(EvidenceUnavailable):
            _review_threads(api, 1242)
        api.request.return_value = {"data": {"repository": {
            "pullRequest": {"reviewThreads": {
                "nodes": [{"id": "PRRT_1", "isResolved": False}],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }}}}}
        self.assertFalse(_review_threads(api, 1242)[0]["isResolved"])
        api.request.return_value["data"]["repository"]["pullRequest"]["reviewThreads"]["pageInfo"]["hasNextPage"] = True
        with self.assertRaises(EvidenceUnavailable):
            _review_threads(api, 1242)

    def test_idempotence_scopes_success_to_current_renewal_generation(self):
        from unittest.mock import Mock
        from datetime import datetime, timezone
        from scripts.renovacion_checks import _already_restored, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        generation = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
        old = {"id": 310, "name": "Validar", "head_sha": SHA,
               "status": "completed", "conclusion": "success",
               "app": {"slug": "github-actions"},
               "completed_at": "2026-10-11T17:30:00Z",
               "external_id": "c" * 64,
               "output": {"title": "Contrato renovado: evidencia fresca"}}
        api.request.return_value = {"total_count": 1, "check_runs": [old]}
        self.assertFalse(_already_restored(api, SHA, "d" * 64, generation))
        self.assertIn("filter=all", api.request.call_args.args[1])
        fresh = copy.deepcopy(old)
        fresh.update(id=311, external_id="d" * 64,
                     completed_at="2026-10-11T18:20:00Z")
        api.request.return_value = {"total_count": 2, "check_runs": [old, fresh]}
        self.assertTrue(_already_restored(api, SHA, "d" * 64, generation))
        fresh["external_id"] = "e" * 64
        with self.assertRaises(EvidenceUnavailable):
            _already_restored(api, SHA, "d" * 64, generation)
        fresh["external_id"] = "d" * 64
        api.request.return_value["check_runs"].append(dict(fresh, id=312))
        api.request.return_value["total_count"] = 3
        with self.assertRaises(EvidenceUnavailable):
            _already_restored(api, SHA, "d" * 64, generation)

    def test_renewal_and_recovery_read_complete_history_after_page_one(self):
        from datetime import datetime, timezone
        from unittest.mock import Mock
        from scripts.renovacion_checks import _invalidation_present, _already_restored

        api = Mock()
        api.repo = "pl0n3r/Factory"
        stamp = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)
        ordinary = [{"id": i, "name": "other"} for i in range(1, 101)]
        invalidation = {
            "id": 101, "name": "Validar", "head_sha": SHA,
            "status": "completed", "conclusion": "failure",
            "completed_at": "2026-10-12T00:59:58Z",
            "app": {"slug": "github-actions"},
            "output": {
                "title": "Renovación explícita del contrato",
                "summary": (
                    f"Issue #1114: contrato renovado explícitamente; "
                    f"reserva V3 {UUID}; aceptación SHA-256 {PIN}; "
                    "la evidencia previa del HEAD no es válida. Ejecuta CI nuevo."
                ),
            },
        }
        restored = {
            "id": 102, "name": "Validar", "head_sha": SHA,
            "status": "completed", "conclusion": "success",
            "completed_at": "2026-10-12T01:03:00Z",
            "app": {"slug": "github-actions"},
            "external_id": PIN,
            "output": {"title": "Contrato renovado: evidencia fresca"},
        }
        history = ordinary + [invalidation, restored]
        observed = []

        def fake_request(_method, path):
            observed.append(path)
            page = 2 if "&page=2" in path else 1
            return {"total_count": len(history),
                    "check_runs": history[(page - 1) * 100:page * 100]}

        api.request.side_effect = fake_request
        self.assertTrue(_invalidation_present(api, SHA, stamp, 1114, UUID, PIN))
        self.assertEqual(len(observed), 4)
        observed.clear()
        self.assertTrue(_already_restored(api, SHA, PIN, stamp))
        self.assertEqual(len(observed), 4)
        restored["external_id"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "different_renewal_recovery_detected"):
            _already_restored(api, SHA, PIN, stamp)
        restored["external_id"] = PIN
        invalidation["output"]["summary"] = "tampered"
        self.assertFalse(_invalidation_present(api, SHA, stamp, 1114, UUID, PIN))

    def test_no_idempotence_from_missing_or_partial_history(self):
        from unittest.mock import Mock
        from datetime import datetime, timezone
        from scripts.renovacion_checks import _already_restored, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        api.request.return_value = {"total_count": 31, "check_runs": [{}] * 30}
        with self.assertRaises(EvidenceUnavailable):
            _already_restored(api, SHA, "d" * 64,
                              datetime(2026, 10, 11, tzinfo=timezone.utc))

    def test_coderabbit_sender_must_be_authenticated(self):
        genuine = fresh_evidence()
        self.assertTrue(evaluate(genuine).ready)
        for sender in (None, "", "untrusted-writer", "pl0n3r", "coderabbitai"):
            sample = fresh_evidence()
            sample["statuses"][0]["creator"] = sender
            with self.subTest(sender=sender):
                self.assertEqual(evaluate(sample).reason,
                                 "coderabbit_creator_not_authenticated")
        sample = fresh_evidence()
        del sample["statuses"][0]["creator"]
        self.assertFalse(evaluate(sample).ready)

    def test_canonical_issue_status_denies_competing_labels(self):
        from scripts.renovacion_checks import _canonical_issue_status, EvidenceUnavailable
        ok = {"labels": [{"name": "estado: reservado"},
                         {"name": "prioridad: alta"}]}
        self.assertEqual(_canonical_issue_status(ok), "estado: reservado")
        for extra in ("estado: bloqueado", "estado: requiere recuperación",
                      "estado: completado", "estado: en revisión",
                      "estado: desconocido", "ESTADO: bloqueado",
                      "Estado: requiere recuperación", "STATUS: blocked"):
            issue = {"labels": [{"name": "estado: reservado"}, {"name": extra}]}
            with self.subTest(extra=extra):
                with self.assertRaises(EvidenceUnavailable):
                    _canonical_issue_status(issue)
        for alias in ("ESTADO: reservado", "Estado: en revisión",
                      "STATUS: reserved"):
            with self.subTest(noncanonical_status=alias):
                with self.assertRaises(EvidenceUnavailable):
                    _canonical_issue_status({"labels": [{"name": alias}]})
        with self.assertRaises(EvidenceUnavailable):
            _canonical_issue_status({"labels": []})

    def test_claims_and_budget_required_checks_never_skipped(self):
        for gate in ("Validar claims V3 del PR", "Presupuesto del PR"):
            for status, conclusion in (("completed", "skipped"),
                                       ("completed", "neutral"),
                                       ("completed", None),
                                       ("completed", "failure"),
                                       ("queued", None)):
                example = fresh_evidence()
                row = next(x for x in example["checks"] if x["name"] == gate)
                row.update(status=status, conclusion=conclusion)
                with self.subTest(gate=gate, conclusion=conclusion, status=status):
                    self.assertEqual(evaluate(example).reason,
                                     "required_check_not_green")
        example = fresh_evidence()
        informational = copy.deepcopy(example["checks"][0])
        informational.update(id=9976, name="Auto-merge simulación",
                             status="completed", conclusion="skipped")
        example["checks"].append(informational)
        self.assertTrue(evaluate(example).ready)


    def test_ci_validar_restored_from_history_after_synthetic_recovery(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _snapshot_check_rows, _normalized_check
        api = Mock()
        api.repo = "pl0n3r/Factory"
        job = {"id": 21, "name": "Validar", "head_sha": SHA,
               "status": "completed", "conclusion": "success",
               "completed_at": FINISH, "app": {"slug": "github-actions"},
               "details_url":
                   "https://github.com/pl0n3r/Factory/actions/runs/10/job/11"}
        recovery = {"id": 22, "name": "Validar", "head_sha": SHA,
                    "status": "completed", "conclusion": "success",
                    "completed_at": "2026-10-11T18:15:00Z",
                    "external_id": "d" * 64,
                    "app": {"slug": "github-actions"},
                    "output": {"title": "Contrato renovado: evidencia fresca"}}
        api.request.side_effect = [
            {"total_count": 1, "check_runs": [recovery]},
            {"total_count": 2, "check_runs": [recovery, job]},
        ]
        result = _snapshot_check_rows(api, SHA)
        self.assertEqual([row["id"] for row in result], [21])
        api.request.side_effect = [
            {"id": 10, "event": "pull_request", "head_sha": SHA,
             "repository": {"full_name": "pl0n3r/Factory"},
             "path": ".github/workflows/factory-ci.yml",
             "run_attempt": 1, "created_at": FRESH},
            {"id": 11, "run_id": 10, "name": "Validar",
             "status": "completed", "conclusion": "success",
             "check_run_url":
                 "https://api.github.com/repos/pl0n3r/Factory/check-runs/21"},
        ]
        self.assertEqual(_normalized_check(api, result[0], SHA)["run_id"], 10)

    def test_recovery_never_replaces_missing_untrusted_or_ambiguous_ci(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _snapshot_check_rows, EvidenceUnavailable
        api = Mock()
        api.repo = "pl0n3r/Factory"
        recovery = {"id": 22, "name": "Validar", "head_sha": SHA,
                    "status": "completed", "conclusion": "success",
                    "completed_at": "2026-10-11T18:15:00Z",
                    "external_id": "d" * 64,
                    "app": {"slug": "github-actions"},
                    "output": {"title": "Contrato renovado: evidencia fresca"}}
        for latest, history in (
            ([dict(recovery, external_id="invalid")], [recovery]),
            ([recovery], [recovery]),
            ([recovery], [recovery] * 100),
            ([recovery], [dict(recovery, external_id="e" * 64)]),
        ):
            with self.subTest(latest=latest, history=len(history)):
                api.request.side_effect = [
                    {"total_count": len(latest), "check_runs": latest},
                    {"total_count": len(history), "check_runs": history},
                ]
                with self.assertRaises(EvidenceUnavailable):
                    _snapshot_check_rows(api, SHA)
        ci_url = "https://github.com/pl0n3r/Factory/actions/runs/10/job/11"
        ci = dict(recovery, id=23, output={}, details_url=ci_url)
        duplicate = dict(ci, id=24)
        api.request.side_effect = [
            {"total_count": 1, "check_runs": [recovery]},
            {"total_count": 3, "check_runs": [recovery, ci, duplicate]},
        ]
        with self.assertRaises(EvidenceUnavailable):
            _snapshot_check_rows(api, SHA)


    def test_history_can_contain_old_status_without_overriding_latest(self):
        from unittest.mock import Mock
        from scripts.renovacion_checks import _verified_statuses, EvidenceUnavailable
        current = {"id": 22, "context": "CodeRabbit", "state": "success",
                   "description": "Review completed", "created_at": FRESH}
        previous = {"id": 21, "context": "CodeRabbit", "state": "pending",
                    "description": "Working", "created_at": TIME}
        payload = {"sha": SHA, "state": "success", "total_count": 1,
                   "statuses": [current]}
        bot = {"login": "coderabbitai[bot]"}
        api = Mock()
        api.repo = "pl0n3r/Factory"
        api.request.side_effect = [
            payload, [dict(current, creator=bot), dict(previous, creator=bot)]]
        self.assertEqual(_verified_statuses(api, SHA)[0]["creator"],
                         "coderabbitai[bot]")
        api.request.side_effect = [
            payload, [dict(current, id=23, state="failure", creator=bot),
                      dict(current, creator=bot)]]
        with self.assertRaises(EvidenceUnavailable):
            _verified_statuses(api, SHA)
        api.request.side_effect = [payload, [dict(current, creator=bot)] * 100]
        with self.assertRaises(EvidenceUnavailable):
            _verified_statuses(api, SHA)

    def test_english_status_labels_are_not_ignored(self):
        from scripts.renovacion_checks import _canonical_issue_status, EvidenceUnavailable
        for alias in ("status: blocked", "status: available",
                      "status: reserved", "status: unknown"):
            with self.subTest(alias=alias):
                with self.assertRaises(EvidenceUnavailable):
                    _canonical_issue_status({"labels": [
                        {"name": "estado: reservado"}, {"name": alias}]})

    def test_base_sha_is_part_of_recovery_identity_and_fingerprint(self):
        original = fresh_evidence()
        self.assertTrue(evaluate(original).ready)
        new_base = copy.deepcopy(original)
        new_base["pr"]["base_sha"] = "e" * 40
        new_base["before"]["base_sha"] = new_base["after"]["base_sha"] = "e" * 40
        self.assertNotEqual(evaluate(original).fingerprint,
                            evaluate(new_base).fingerprint)
        changed = fresh_evidence()
        changed["after"]["base_sha"] = "e" * 40
        self.assertEqual(evaluate(changed).reason,
                         "identity_changed_during_revalidation")
        missing = fresh_evidence()
        missing["pr"].pop("base_sha")
        self.assertFalse(evaluate(missing).ready)
