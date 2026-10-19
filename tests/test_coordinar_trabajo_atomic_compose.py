#!/usr/bin/env python3
"""Regresión fail-closed del plan GET-only de composición V3 de #1395.

La autoridad CAS, transferencia y squash NO están implementadas aquí:
el preview nunca concede escritura, aun cuando todos los GET sean correctos.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import scripts.coordinar_trabajo as coord


MAIN = "a" * 40
OWNER = "pl0n3r"
ISSUES = [2001, 2002, 2003]
ACCEPTANCE = "c" * 64
TASK = "d" * 64


def paths(number: int) -> list[str]:
    return [f"docs/compose-{number}.md", f"tests/compose-{number}.py"]


class ReadOnlyFake:
    """Fake sin operaciones de escritura: un intento de POST rompe la prueba."""

    def __init__(self) -> None:
        self.repo = "pl0n3r/Factory"
        self.main = MAIN
        self.branches = {f"trabajo/issue-{n}": f"{n:040x}" for n in ISSUES}
        self.issues = {
            n: {
                "number": n,
                "state": "open",
                "body": str(n),
                "labels": [{"name": coord.STATUS_RESERVED}],
            }
            for n in ISSUES
        }
        self.comments = {}
        self.pulls = {}
        self.changed = {}
        self.pr_by_issue = {}
        self.extra_issues = []
        self.pr_override = None
        for n in ISSUES:
            branch = f"trabajo/issue-{n}"
            uuid = "00000000-0000-4000-8000-" + f"{n:012x}"
            reservation = coord.reservation_marker(
                OWNER, uuid, branch, True, "tomar",
                ACCEPTANCE,
                task_snapshot={
                    "task_marker_sha256": TASK,
                    "task_paths": paths(n),
                    "task_depends_on": [],
                },
            )
            self.comments[n] = [{"user": {"login": "github-actions[bot]"}, "body": reservation}]
            pr = {
                "number": n + 1000,
                "state": "open",
                "head": {
                    "sha": self.branches[branch],
                    "ref": branch,
                    "repo": {"full_name": self.repo, "name": "Factory",
                             "owner": {"login": "pl0n3r"}},
                },
                "base": {"sha": MAIN, "ref": "main"},
                "body": f"<!-- condor-reserva-id: {uuid} -->",
            }
            self.pulls[pr["number"]] = pr
            self.pr_by_issue[n] = pr["number"]
            self.changed[pr["number"]] = {
                "complete": True,
                "head_sha": self.branches[branch],
                "base_sha": MAIN,
                "files": paths(n),
            }
        self.log = []
        # Candidato de integración simulado, distinto de los tres PRs fuente.
        # El mock almacena identidad de contenido por blob, no solo nombres.
        self.candidate_sha = "b" * 40
        self.candidate_ref = "trabajo/issue-3000"
        self.branches[self.candidate_ref] = self.candidate_sha
        files = [path for n in ISSUES for path in paths(n)]
        self.blobs = {}
        for n in ISSUES:
            for path in paths(n):
                self.blobs[(path, self.branches[f"trabajo/issue-{n}"])] = hashlib.sha1(
                    path.encode("utf-8")
                ).hexdigest()
        for path in files:
            self.blobs[(path, self.candidate_sha)] = hashlib.sha1(
                path.encode("utf-8")
            ).hexdigest()
        self.pulls[4000] = {
            "number": 4000,
            "state": "open",
            "draft": False,
            "head": {
                "ref": self.candidate_ref,
                "sha": self.candidate_sha,
                "repo": {"full_name": self.repo, "name": "Factory",
                         "owner": {"login": "pl0n3r"}},
            },
            "base": {"ref": "main", "sha": MAIN},
        }
        self.changed[4000] = {
            "complete": True, "head_sha": self.candidate_sha,
            "base_sha": MAIN, "files": files,
        }
        self.checks = [{
            "name": "Validar", "head_sha": self.candidate_sha,
            "status": "completed", "conclusion": "success",
        }]

    def blob_sha_at(self, path, sha):
        self.log.append(("blob_sha_at", path, sha))
        return self.blobs[(path, sha)]

    def exact_check_runs(self, sha):
        self.log.append(("exact_check_runs", sha))
        return copy.deepcopy(self.checks)

    def issue(self, number):
        self.log.append(("issue", number))
        return copy.deepcopy(self.issues[number])

    def issue_comments(self, number):
        self.log.append(("issue_comments", number))
        return copy.deepcopy(self.comments[number])

    def open_pulls(self):
        self.log.append(("open_pulls",))
        return copy.deepcopy(list(self.pulls.values()))

    def pull(self, number):
        self.log.append(("pull", number))
        if self.pr_override:
            return self.pr_override(number)
        return copy.deepcopy(self.pulls[number])

    def pull_files_exact_head(self, number):
        self.log.append(("pull_files_exact_head", number))
        return copy.deepcopy(self.changed[number])

    def branch_sha(self, branch):
        self.log.append(("branch_sha", branch))
        return self.main if branch == "main" else self.branches.get(branch)

    def open_issues(self):
        self.log.append(("open_issues",))
        return copy.deepcopy(list(self.issues.values()) + self.extra_issues)


class AtomicComposeTests(unittest.TestCase):
    def setUp(self):
        self.api = ReadOnlyFake()

    def plan(self):
        # Los contratos externos se prueban exhaustivamente en sus suites
        # canónicas. Aquí se prueban claims, pinning y lectura del plan.
        with (
            patch.object(coord, "require_global_running"),
            patch.object(
                coord, "parse_task_marker",
                side_effect=lambda body: {
                    "paths": paths(int(body)),
                    "depends_on": [],
                },
            ),
            patch.object(coord, "task_marker_fingerprint", return_value=TASK),
            patch.object(coord, "contract_fingerprint", return_value=ACCEPTANCE),
        ):
            return coord.plan_atomic_compose_v3(self.api, ISSUES, OWNER)

    def test_three_disjoint_leases_plan_no_mutation(self):
        result = self.plan()
        self.assertEqual(result["mode"], "plan_only")
        self.assertIs(result["write_authorized"], False)
        self.assertEqual(result["main_sha"], MAIN)
        self.assertEqual(result["file_count"], 6)
        self.assertEqual([s["issue"] for s in result["sources"]], ISSUES)
        self.assertEqual(sum(len(s["claims"]) for s in result["sources"]), 6)
        self.assertEqual(
            [s["reservation_id"] for s in result["sources"]],
            ["00000000-0000-4000-8000-" + f"{n:012x}" for n in ISSUES],
        )
        self.assertFalse(any(entry[0] in {"POST", "PATCH", "DELETE"} for entry in self.api.log))

    def test_malformed_paused_collision_and_race_fail_closed(self):
        with self.subTest("identidad duplicada"):
            with self.assertRaises(coord.CoordinationError):
                coord.plan_atomic_compose_v3(self.api, [2001, 2001, 2003], OWNER)
        with self.subTest("pausa"):
            with patch.object(
                coord, "require_global_running",
                side_effect=coord.CoordinationError("PAUSED"),
            ):
                with self.assertRaisesRegex(coord.CoordinationError, "PAUSED"):
                    coord.plan_atomic_compose_v3(self.api, ISSUES, OWNER)
        with self.subTest("colision"):
            api = self.api
            api.changed[api.pr_by_issue[2003]]["files"] = [*paths(2003), paths(2001)[0]]
            with self.assertRaises(coord.CoordinationError):
                self.plan()
            api.changed[api.pr_by_issue[2003]]["files"] = paths(2003)
        with self.subTest("diff incompleto"):
            api = self.api
            api.changed[api.pr_by_issue[2003]]["complete"] = False
            with self.assertRaises(coord.CoordinationError):
                self.plan()
            api.changed[api.pr_by_issue[2003]]["complete"] = True
        with self.subTest("lease falsa"):
            api = self.api
            original = api.comments[2003][0]["user"]["login"]
            api.comments[2003][0]["user"]["login"] = "attacker"
            with self.assertRaises(coord.CoordinationError):
                self.plan()
            api.comments[2003][0]["user"]["login"] = original
        with self.subTest("cambio de main"):
            api = self.api
            old = api.branch_sha
            calls = {"main": 0}

            def drifting(branch):
                if branch == "main":
                    calls["main"] += 1
                    if calls["main"] > 1:
                        return "f" * 40
                return old(branch)

            api.branch_sha = drifting
            with self.assertRaises(coord.CoordinationError):
                self.plan()
            api.branch_sha = old

    def test_unowned_branch_or_head_mismatch_is_rejected(self):
        self.api.branches.pop("trabajo/issue-2002")
        with self.assertRaises(coord.CoordinationError):
            self.plan()

    def test_source_pr_changes_during_revalidation(self):
        old = self.api.pulls[self.api.pr_by_issue[2003]]
        changed = copy.deepcopy(old)
        changed["head"]["sha"] = "f" * 40
        self.api.pr_override = lambda number: changed if number == old["number"] else copy.deepcopy(self.api.pulls[number])
        with self.assertRaises(coord.CoordinationError):
            self.plan()

    def test_fourth_active_lease_claim_collision_is_rejected(self):
        number = 2004
        branch = f"trabajo/issue-{number}"
        reservation = coord.reservation_marker(
            OWNER, "00000000-0000-4000-8000-000000002004", branch,
            True, "tomar", ACCEPTANCE,
            task_snapshot={"task_marker_sha256": TASK,
                           "task_paths": [paths(2001)[0]],
                           "task_depends_on": []},
        )
        self.api.extra_issues.append({"number": number, "state": "open"})
        self.api.comments[number] = [{"user": {"login": "github-actions[bot]"}, "body": reservation}]
        with self.assertRaisesRegex(coord.CoordinationError, "tercero"):
            self.plan()


    def test_invalid_identity_and_wrong_status_fail_closed(self):
        for candidate, who in (([2001, 2002], OWNER), (ISSUES, ""),
                               ([2001, 2001, 2002], OWNER)):
            with self.subTest(candidate=candidate, owner=who):
                with self.assertRaises(coord.CoordinationError):
                    coord.plan_atomic_compose_v3(self.api, candidate, who)
        with self.subTest("issue no reservado"):
            self.api.issues[2002]["labels"] = [{"name": coord.STATUS_BLOCKED}]
            with self.assertRaisesRegex(coord.CoordinationError, "no reservado"):
                self.plan()
            self.api.issues[2002]["labels"] = [{"name": coord.STATUS_RESERVED}]

    def test_untrusted_lease_contract_and_owner_are_rejected(self):
        original = self.api.comments[2001][0]["body"]
        cases = [
            original.replace('"owner":"pl0n3r"', '"owner":"attacker"'),
            original.replace(ACCEPTANCE, "e" * 64),
            original.replace(TASK, "f" * 64),
            original.replace("compose-2001", "compose-9999"),
        ]
        for value in cases:
            with self.subTest(marker=value[-60:]):
                self.api.comments[2001][0]["body"] = value
                with self.assertRaises(coord.CoordinationError):
                    self.plan()
        self.api.comments[2001][0]["body"] = original

    def test_pr_base_body_and_changed_file_scope_rejected(self):
        pr_id = self.api.pr_by_issue[2002]
        original = copy.deepcopy(self.api.pulls[pr_id])
        with self.subTest("base stale"):
            self.api.pulls[pr_id]["base"]["sha"] = "b" * 40
            with self.assertRaises(coord.CoordinationError):
                self.plan()
        self.api.pulls[pr_id] = copy.deepcopy(original)
        with self.subTest("body sin reserva"):
            self.api.pulls[pr_id]["body"] = "sin marker de reserva"
            with self.assertRaises(coord.CoordinationError):
                self.plan()
        self.api.pulls[pr_id] = copy.deepcopy(original)
        with self.subTest("archivo fuera del claim"):
            self.api.changed[pr_id]["files"] = [*paths(2002), "new/unauthorized.py"]
            with self.assertRaisesRegex(coord.CoordinationError, "fuera de claims"):
                self.plan()
        self.api.changed[pr_id]["files"] = paths(2002)
        with self.subTest("diff vacío"):
            self.api.changed[pr_id]["files"] = []
            with self.assertRaises(coord.CoordinationError):
                self.plan()
        self.api.changed[pr_id]["files"] = paths(2002)

    def test_third_party_legacy_lease_rejected_without_claims(self):
        self.api.extra_issues.append({"number": 2004, "state": "open"})
        self.api.comments[2004] = [{
            "user": {"login": "github-actions[bot]"},
            "body": coord.reservation_marker(
                OWNER, "00000000-0000-4000-8000-000000002004",
                "trabajo/issue-2004", True, "tomar", ACCEPTANCE),
        }]
        with self.assertRaisesRegex(coord.CoordinationError, "sin claims V3"):
            self.plan()

    def test_third_party_disjoint_v3_does_not_block_read_only_plan(self):
        self.api.extra_issues.append({"number": 2004, "state": "open"})
        self.api.comments[2004] = [{
            "user": {"login": "github-actions[bot]"},
            "body": coord.reservation_marker(
                OWNER, "00000000-0000-4000-8000-000000002004",
                "trabajo/issue-2004", True, "tomar", ACCEPTANCE,
                task_snapshot={"task_marker_sha256": TASK,
                               "task_paths": ["unrelated.txt"],
                               "task_depends_on": []}),
        }]
        plan = self.plan()
        self.assertIs(plan["write_authorized"], False)
        self.assertEqual(plan["file_count"], 6)



    def test_contract_drift_during_final_read_is_rejected(self):
        initial_issue = self.api.issue
        counts = {}

        def drifted(number):
            row = initial_issue(number)
            counts[number] = counts.get(number, 0) + 1
            if number == 2002 and counts[number] > 1:
                row["body"] = "2099"
            return row

        self.api.issue = drifted
        with self.assertRaisesRegex(coord.CoordinationError, "contrato cambió"):
            self.plan()


    def candidate_ci(self, plan=None):
        if plan is None:
            plan = self.plan()
        with patch.object(coord, "require_global_running"):
            return coord.verify_exact_integrator_ci_v3(self.api, plan, 4000)

    def test_exact_integrator_sha_ci_never_reuses_child_checks(self):
        proof = self.candidate_ci()
        self.assertEqual(proof["mode"], "ci_evidence_only")
        self.assertIs(proof["write_authorized"], False)
        self.assertEqual(proof["files_verified"], 6)
        self.assertEqual(proof["integrator_sha"], self.api.candidate_sha)
        self.assertIn(("exact_check_runs", self.api.candidate_sha), self.api.log)
        self.assertFalse(any(event[0] in ("POST", "PATCH", "DELETE")
                             for event in self.api.log))
        for field, value in (
            ("status", "in_progress"), ("conclusion", "failure"),
            ("head_sha", "c" * 40), ("name", "other-job"),
        ):
            with self.subTest(check_field=field):
                self.api.checks[0][field] = value
                with self.assertRaisesRegex(coord.CoordinationError, "Validar"):
                    self.candidate_ci()
                self.api.checks[0][field] = {
                    "status": "completed", "conclusion": "success",
                    "head_sha": self.api.candidate_sha, "name": "Validar",
                }[field]
        with self.subTest("reused child green"):
            self.api.checks[0]["head_sha"] = self.api.branches["trabajo/issue-2001"]
            with self.assertRaisesRegex(coord.CoordinationError, "Validar"):
                self.candidate_ci()

    def test_candidate_rejects_missing_files_modified_blobs_and_draft(self):
        with self.subTest("filename missing"):
            self.api.changed[4000]["files"] = self.api.changed[4000]["files"][:-1]
            with self.assertRaisesRegex(coord.CoordinationError, "seis archivos"):
                self.candidate_ci()
            self.api.changed[4000]["files"] = [
                p for number in ISSUES for p in paths(number)
            ]
        with self.subTest("blob altered"):
            path = paths(2003)[1]
            self.api.blobs[(path, self.api.candidate_sha)] = "e" * 40
            with self.assertRaisesRegex(coord.CoordinationError, "contenido distinto"):
                self.candidate_ci()
            self.api.blobs[(path, self.api.candidate_sha)] = hashlib.sha1(
                path.encode("utf-8")
            ).hexdigest()
        with self.subTest("draft"):
            self.api.pulls[4000]["draft"] = True
            with self.assertRaisesRegex(coord.CoordinationError, "fuera de main"):
                self.candidate_ci()
            self.api.pulls[4000]["draft"] = False

    def test_candidate_fails_closed_for_duplicate_or_unknown_checks(self):
        with self.subTest("no checks"):
            self.api.checks = []
            with self.assertRaisesRegex(coord.CoordinationError, "Validar"):
                self.candidate_ci()
        with self.subTest("duplicated checks"):
            self.api.checks = [{
                "name": "Validar", "head_sha": self.api.candidate_sha,
                "status": "completed", "conclusion": "success",
            }] * 2
            with self.assertRaisesRegex(coord.CoordinationError, "Validar"):
                self.candidate_ci()

    def test_candidate_rejects_main_and_head_race(self):
        first = self.api.pull
        calls = {"candidate": 0}

        def drifting_pr(number):
            item = first(number)
            if number == 4000:
                calls["candidate"] += 1
                if calls["candidate"] > 1:
                    item["head"]["sha"] = "c" * 40
            return item

        self.api.pull = drifting_pr
        with self.assertRaisesRegex(coord.CoordinationError, "cambió"):
            self.candidate_ci()



    def test_candidate_rejects_revoked_or_racing_source_reservation(self):
        original = self.api.comments[2002][0]["body"]
        with self.subTest("revoked before candidate"):
            self.api.comments[2002][0]["body"] = original.replace(
                '"active":true', '"active":false'
            )
            with self.assertRaisesRegex(coord.CoordinationError, r"lease #2002 inválida"):
                self.candidate_ci()
            self.api.comments[2002][0]["body"] = original
        with self.subTest("revoked during checks"):
            original_reader = self.api.exact_check_runs

            def revoked_during_checks(sha):
                checks = original_reader(sha)
                self.api.comments[2002][0]["body"] = original.replace(
                    '"active":true', '"active":false'
                )
                return checks

            self.api.exact_check_runs = revoked_during_checks
            with self.assertRaisesRegex(coord.CoordinationError, r"fuente cambió tras el check"):
                self.candidate_ci()
            self.assertIn(("exact_check_runs", self.api.candidate_sha), self.api.log)
            self.assertFalse(any(event[0] in ("POST", "PATCH", "DELETE")
                                 for event in self.api.log))
            self.api.exact_check_runs = original_reader
            self.api.comments[2002][0]["body"] = original

    def test_candidate_reauthenticates_source_reservations_and_prs(self):
        # Un plan de preview no es autoridad: revalidar V3 y PR fuente.
        for field, forged in (
            ("acceptance_sha256", "e" * 64),
            ("task_marker_sha256", "e" * 64),
            ("claims", ["docs/not-reserved.md"]),
        ):
            with self.subTest(forged_pin=field):
                plan = self.plan()
                plan["sources"][1][field] = forged
                with self.assertRaisesRegex(
                    coord.CoordinationError, "fuente sin lease V3 exacta"
                ):
                    self.candidate_ci(plan)
        plan = self.plan()
        pr_number = self.api.pr_by_issue[2002]
        original = copy.deepcopy(self.api.pulls[pr_number])
        for case in ("head", "base", "body", "state"):
            with self.subTest(source_pr=case):
                tampered = copy.deepcopy(original)
                if case == "head":
                    tampered["head"]["sha"] = "f" * 40
                elif case == "base":
                    tampered["base"]["sha"] = "f" * 40
                elif case == "body":
                    tampered["body"] = "<!-- condor-reserva-id: fabricated -->"
                else:
                    tampered["state"] = "closed"
                self.api.pulls[pr_number] = tampered
                with self.assertRaisesRegex(
                    coord.CoordinationError, "PR fuente perdió identidad V3"
                ):
                    self.candidate_ci(plan)
                self.api.pulls[pr_number] = copy.deepcopy(original)
        original_checks = self.api.exact_check_runs

        def race_after_checks(sha):
            checked = original_checks(sha)
            self.api.pulls[pr_number]["body"] = "PR changed"
            return checked

        self.api.exact_check_runs = race_after_checks
        with self.assertRaisesRegex(
            coord.CoordinationError, "PR fuente cambió tras el check"
        ):
            self.candidate_ci(plan)
        self.api.exact_check_runs = original_checks
        self.api.pulls[pr_number] = original
        self.assertFalse(any(event[0] in ("POST", "PATCH", "DELETE")
                             for event in self.api.log))


    def prepare_composition(self):
        """API sintética: las escrituras son eventos atómicos observables."""
        api = self.api
        api.issues[3000] = {
            "number": 3000, "state": "open", "body": "3000",
            "labels": [{"name": coord.STATUS_REVIEW}],
        }
        api.comments[3000] = []
        api.grant = None
        api.lock_held = False
        api.fail_commit = None
        api.fail_comment = False
        api.fail_close_at = None
        api.close_count = 0
        api.branches[coord.recovery_lock_branch(2147483647)] = None
        original_branch_sha = api.branch_sha

        def branch_sha(branch):
            if branch == coord.recovery_lock_branch(2147483647):
                return "f" * 40 if api.lock_held else None
            return original_branch_sha(branch)

        def acquire_issue_lock(number, sha):
            api.log.append(("acquire_lock", number, sha))
            if api.lock_held or number != 2147483647:
                return None
            api.lock_held = True
            return "f" * 40

        def release_owned_issue_lock_after_pause(number, token):
            api.log.append(("release_lock", number, token))
            if api.lock_held and token == "f" * 40:
                api.lock_held = False

        def composite_authority_v3(number):
            api.log.append(("authority_read", number))
            return copy.deepcopy(api.grant)

        def commit_composite_authority_v3(number, main, record):
            api.log.append(("CAS", number, main))
            if api.fail_commit == "pre":
                raise ConnectionError("failed before CAS")
            if api.grant is not None:
                return False
            api.grant = copy.deepcopy(record)
            if api.fail_commit == "after":
                raise ConnectionError("lost CAS response")
            return True

        def comment(number, body):
            api.log.append(("POST", number))
            if api.fail_comment:
                raise ConnectionError("lost comment response")
            api.comments[number].append({
                "user": {"login": "github-actions[bot]"}, "body": body
            })

        def close_pull(number):
            api.log.append(("PATCH", number))
            api.close_count += 1
            if api.fail_close_at == api.close_count:
                raise ConnectionError("partial GitHub response")
            api.pulls[number]["state"] = "closed"

        api.branch_sha = branch_sha
        api.acquire_issue_lock = acquire_issue_lock
        api.release_owned_issue_lock_after_pause = release_owned_issue_lock_after_pause
        api.composite_authority_v3 = composite_authority_v3
        api.commit_composite_authority_v3 = commit_composite_authority_v3
        api.comment = comment
        api.close_pull = close_pull

        plan = self.plan()
        intention = {
            "version": 1, "integrator_issue": 3000,
            "candidate_pr": 4000, "candidate_sha": api.candidate_sha,
            "main_sha": MAIN, "owner": OWNER,
            "sources": [[r["issue"], r["pr"], r["branch_sha"],
                         r["reservation_id"]] for r in plan["sources"]],
            "claims": sorted(p for n in ISSUES for p in paths(n)),
        }
        digest = hashlib.sha256(json.dumps(
            intention, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")).hexdigest()
        api.comments[3000].append({
            "user": {"login": OWNER},
            "body": '<!-- factory-compose-approval ' + json.dumps(
                {"version": 1, "intention_sha256": digest},
                separators=(",", ":"), sort_keys=True
            ) + ' -->',
        })
        return plan

    def atomic_compose(self):
        with (
            patch.object(coord, "require_global_running"),
            patch.object(
                coord, "parse_task_marker",
                side_effect=lambda body: {
                    "paths": sorted(p for n in ISSUES for p in paths(n))
                    if body == "3000" else paths(int(body)),
                    "depends_on": [],
                },
            ),
            patch.object(coord, "task_marker_fingerprint", return_value=TASK),
            patch.object(coord, "contract_fingerprint", return_value=ACCEPTANCE),
        ):
            return coord.authorize_atomic_compose_v3(
                self.api, ISSUES, 3000, 4000, OWNER, "OWNER"
            )

    def test_authorized_cas_compose_preserves_source_refs(self):
        plan = self.prepare_composition()
        before = {n: self.api.branch_sha(f"trabajo/issue-{n}")
                  for n in ISSUES}
        before_prs = {n: copy.deepcopy(self.api.pulls[self.api.pr_by_issue[n]])
                      for n in ISSUES}
        grant = self.atomic_compose()
        self.assertEqual(grant["version"], 3)
        self.assertEqual(grant["integrator_sha"], self.api.candidate_sha)
        self.assertEqual(grant["approval_sha256"], hashlib.sha256(json.dumps({
            "version": 1, "integrator_issue": 3000, "candidate_pr": 4000,
            "candidate_sha": self.api.candidate_sha, "main_sha": MAIN,
            "owner": OWNER,
            "sources": [[r["issue"], r["pr"], r["branch_sha"],
                         r["reservation_id"]] for r in plan["sources"]],
            "claims": sorted(p for n in ISSUES for p in paths(n)),
        }, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest())
        self.assertEqual(grant["reservation"]["version"], 3)
        self.assertEqual(grant["reservation"]["task_paths"],
                         sorted(p for n in ISSUES for p in paths(n)))
        self.assertEqual(self.api.grant, grant)
        self.assertEqual(self.api.log.count(("CAS", 3000, MAIN)), 1)
        self.assertEqual(coord.active_reservation(self.api, 3000),
                         grant["reservation"])
        for n in ISSUES:
            self.assertEqual(self.api.branch_sha(f"trabajo/issue-{n}"),
                             before[n])
            self.assertEqual(self.api.pulls[self.api.pr_by_issue[n]],
                             before_prs[n])
            self.assertTrue(coord.active_reservation(self.api, n)["active"])
        # Reintentos no crean segunda concesión ni otra nota de autoridad.
        comment_count = len(self.api.comments[3000])
        self.assertEqual(self.atomic_compose(), grant)
        self.assertEqual(len(self.api.comments[3000]), comment_count)
        self.assertEqual(self.api.log.count(("CAS", 3000, MAIN)), 1)

    def test_simultaneous_attempts_and_partial_api_rollback(self):
        self.prepare_composition()
        self.api.lock_held = True
        with self.assertRaisesRegex(coord.CoordinationError, "repo-wide ocupado"):
            self.atomic_compose()
        self.assertIsNone(self.api.grant)
        self.api.lock_held = False
        self.api.fail_commit = "pre"
        with self.assertRaisesRegex(ConnectionError, "before CAS"):
            self.atomic_compose()
        self.assertIsNone(self.api.grant)
        self.assertFalse(self.api.lock_held)
        self.api.fail_commit = "after"
        first = self.atomic_compose()
        self.assertEqual(first, self.api.grant)
        self.assertEqual(self.api.log.count(("CAS", 3000, MAIN)), 2)
        self.api.fail_commit = None
        self.assertEqual(self.atomic_compose(), first)
        self.assertEqual(self.api.log.count(("CAS", 3000, MAIN)), 2)
        self.assertFalse(any(ev[0] == "DELETE" for ev in self.api.log))
        with self.subTest("approval not owner"):
            self.api = ReadOnlyFake()
            self.prepare_composition()
            self.api.comments[3000][0]["user"]["login"] = "attacker"
            with self.assertRaisesRegex(coord.CoordinationError, "aprobación owner"):
                self.atomic_compose()
            self.assertIsNone(self.api.grant)
        with self.subTest("lost bot marker response and idempotent recovery"):
            self.api = ReadOnlyFake()
            self.prepare_composition()
            self.api.fail_comment = True
            with self.assertRaisesRegex(ConnectionError, "comment"):
                self.atomic_compose()
            self.assertIsNotNone(self.api.grant)
            self.assertIsNone(coord.active_reservation(self.api, 3000))
            self.api.fail_comment = False
            recovered = self.atomic_compose()
            self.assertEqual(coord.active_reservation(self.api, 3000),
                             recovered["reservation"])
            self.assertEqual(self.api.log.count(("CAS", 3000, MAIN)), 1)
        with self.subTest("CI pending never authorizes squash"):
            self.api = ReadOnlyFake()
            self.prepare_composition()
            self.api.checks[0]["status"] = "in_progress"
            # Árbol autorizado por CAS, pero Validar sigue siendo puerta dura.
            candidate = self.atomic_compose()
            self.assertEqual(self.api.grant, candidate)
            with self.assertRaisesRegex(coord.CoordinationError, "Validar"):
                self.candidate_ci()
            self.assertFalse(any(event[0] == "DELETE" for event in self.api.log))

    def test_reconcile_only_after_merge_and_main_ci(self):
        self.prepare_composition()
        grant = self.atomic_compose()
        with patch.object(coord, "require_global_running"):
            with self.assertRaisesRegex(coord.CoordinationError, "merge integrador"):
                coord.reconcile_atomic_compose_v3(self.api, 3000, OWNER, "OWNER")
        self.assertEqual(self.api.close_count, 0)
        self.api.pulls[4000]["merged"] = True
        self.api.pulls[4000]["state"] = "closed"
        self.api.pulls[4000]["merge_commit_sha"] = "d" * 40
        self.api.main = "d" * 40
        self.api.checks[0]["head_sha"] = "d" * 40
        self.api.checks[0]["status"] = "in_progress"
        with patch.object(coord, "require_global_running"):
            with self.assertRaisesRegex(coord.CoordinationError, "Validar exact-main"):
                coord.reconcile_atomic_compose_v3(self.api, 3000, OWNER, "OWNER")
        self.assertEqual(self.api.close_count, 0)
        self.api.checks[0]["status"] = "completed"
        self.api.fail_close_at = 2
        with patch.object(coord, "require_global_running"):
            with self.assertRaisesRegex(ConnectionError, "partial"):
                coord.reconcile_atomic_compose_v3(self.api, 3000, OWNER, "OWNER")
        self.assertEqual(self.api.pulls[self.api.pr_by_issue[2001]]["state"],
                         "closed")
        self.assertEqual(self.api.pulls[self.api.pr_by_issue[2002]]["state"],
                         "open")
        self.api.fail_close_at = None
        with patch.object(coord, "require_global_running"):
            proof = coord.reconcile_atomic_compose_v3(
                self.api, 3000, OWNER, "OWNER"
            )
        self.assertEqual(proof["mode"], "reconciled_after_merge")
        self.assertEqual(proof["source_prs"],
                         [self.api.pr_by_issue[n] for n in ISSUES])
        self.assertEqual(self.api.grant, grant)
        for n in ISSUES:
            self.assertEqual(self.api.pulls[self.api.pr_by_issue[n]]["state"],
                             "closed")
            self.assertTrue(coord.active_reservation(self.api, n)["active"])
            self.assertIsNotNone(self.api.branch_sha(f"trabajo/issue-{n}"))

    def test_candidate_rejects_unclaimed_files_in_forged_plan(self):
        plan = self.plan()
        plan["sources"][0]["claims"] = ["docs/not-a-claim.md"]
        with self.assertRaisesRegex(coord.CoordinationError, "fuente sin lease V3 exacta"):
            self.candidate_ci(plan)



if __name__ == "__main__":
    unittest.main()
