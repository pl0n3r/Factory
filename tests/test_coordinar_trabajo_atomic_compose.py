#!/usr/bin/env python3
"""Regresión fail-closed del plan GET-only de composición V3 de #1395.

La autoridad CAS, transferencia y squash NO están implementadas aquí:
el preview nunca concede escritura, aun cuando todos los GET sean correctos.
"""
from __future__ import annotations

import copy
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


if __name__ == "__main__":
    unittest.main()
