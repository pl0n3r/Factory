"""Pruebas sintéticas, sin red ni escrituras productivas, de epic_closure_leaves."""
from __future__ import annotations

import json
import unittest

from scripts.epic_closure_leaves import (
    EpicError, _existing, _kind, make_leaf, proposals, run,
)
from scripts.issue_contract_preflight import evaluate_issue_body


def issue(number, title, body="", state="open", labels=(), **more):
    return {"number": number, "title": title, "body": body, "state": state,
            "labels": [{"name": label} for label in labels], **more}


def child(number, epic, state="closed"):
    marker = {"version": 1, "epic": epic, "task_key": f"TEST_{number}",
              "order": number, "owner": "pl0n3r", "roles": ["qa"],
              "depends_on": [], "paths": [f"docs/test-{number}.md"]}
    return issue(number, f"leaf #{number}",
                 body=f"<!-- factory-plan-task {json.dumps(marker)} -->", state=state)


class FakeGithub:
    repo = "pl0n3r/Factory"

    def __init__(self, rows):
        self.issues = list(rows)
        self.creates = 0
        self.switch_checks = 0

    def read_all(self):
        return list(self.issues)

    def verify_switch(self):
        self.switch_checks += 1

    def create(self, item):
        self.creates += 1
        number = 8000 + self.creates
        self.issues.append(issue(number, item.title, body=item.body))
        return number


class EpicClosureLeavesTests(unittest.TestCase):
    def test_finished_epic_yields_closure(self):
        epic = issue(101, "EPIC: example",
                     "### Criterios de aceptación\n- [x] [AC-01] Hecho\n- [X] [AC-02] Hecho")
        result = proposals([epic, child(102, 101)], "pl0n3r/Factory", "Tests de scripts")
        self.assertEqual([(x.epic, x.kind) for x in result], [(101, "cierre")])

    def test_pending_criteria_yields_mapping(self):
        epic = issue(201, "Roadmap: tests",
                     "### Criterios de aceptación\n- [x] [AC-01] Listo\n- [ ] [AC-02] Pendiente")
        result = proposals([epic], "pl0n3r/Factory", "Tests de scripts")
        self.assertEqual(result[0].kind, "mapeo")
        self.assertIn("factory-epic-splitter", result[0].body)

    def test_without_criteria_fails_closed_as_mapping(self):
        self.assertEqual(_kind("body sin AC"), "mapeo")

    def test_github_link_is_candidate_only(self):
        sha = "a" * 40
        self.assertEqual(_kind(
            f"- [ ] [AC-01] evidencia https://github.com/pl0n3r/Factory/commit/{sha}"
        ), "cierre")
        self.assertEqual(_kind("- [ ] [AC-01] Issue #1"), "mapeo")

    def test_owner_live_legal_cost_are_excluded(self):
        rows = [
            issue(300, "EPIC: owner", labels=("tipo: decisión del dueño",)),
            issue(301, "Roadmap: live", labels=("fase: live",)),
            issue(302, "EPIC: legal", labels=("rol: legal-privacidad",)),
            issue(303, "EPIC: spend", labels=("tipo: gasto",)),
            issue(304, "Decisión: humana"),
        ]
        self.assertEqual(proposals(rows, "pl0n3r/Factory", "Tests de scripts"), [])

    def test_active_children_block_closed_children_do_not(self):
        epic = issue(401, "EPIC: review")
        self.assertEqual(proposals([epic, child(402, 401, "open")],
                                   "pl0n3r/Factory", "Tests de scripts"), [])
        self.assertEqual(len(proposals([epic, child(402, 401)],
                                       "pl0n3r/Factory", "Tests de scripts")), 1)

    def test_dedup_survives_closed_leaf(self):
        epic = issue(500, "Roadmap: pending")
        api = FakeGithub([epic])
        first = run(api, apply=True, check="Tests de scripts", limit=10)
        self.assertEqual(first[0]["status"], "created")
        self.assertEqual(api.creates, 1)
        self.assertEqual(run(api, apply=True, check="Tests de scripts", limit=10), [])
        api.issues[-1]["state"] = "closed"
        self.assertEqual(run(api, apply=True, check="Tests de scripts", limit=10), [])
        self.assertEqual(api.creates, 1)
        self.assertEqual(api.switch_checks, 1)

    def test_dry_run_does_not_write(self):
        api = FakeGithub([issue(501, "EPIC: dry-run")])
        self.assertEqual(run(api, apply=False, check="Tests de scripts", limit=10)[0]["status"],
                         "proposed")
        self.assertEqual((api.creates, api.switch_checks), (0, 0))

    def test_concurrent_new_child_prevents_create(self):
        api = FakeGithub([issue(601, "EPIC: concurrency")])
        original = api.read_all
        calls = [0]
        def change():
            calls[0] += 1
            if calls[0] == 2:
                api.issues.append(child(602, 601, "open"))
            return original()
        api.read_all = change
        result = run(api, apply=True, check="Tests de scripts", limit=10)
        self.assertEqual(result[0]["status"], "skipped_changed")
        self.assertEqual(api.creates, 0)

    def test_generated_contracts_pass_real_preflight(self):
        for kind in ("cierre", "mapeo"):
            with self.subTest(kind=kind):
                item = make_leaf(issue(700, "EPIC: demo"), kind,
                                 "pl0n3r/Factory", "Tests de scripts")
                result = evaluate_issue_body(item.body)
                self.assertTrue(result["valid"])
                self.assertEqual(result["task_key"],
                                 "EPIC_700_CLOSE" if kind == "cierre" else "EPIC_700_MAP")
                self.assertEqual(len(result["criteria"]), 2)
                self.assertEqual(_existing(issue(701, "generated", body=item.body)), 700)

    def test_malformed_markers_and_duplicate_issues_fail_closed(self):
        with self.assertRaises(EpicError):
            proposals([issue(1, "EPIC: a"), issue(1, "EPIC: b")],
                      "pl0n3r/Factory", "Tests de scripts")
        with self.assertRaises(EpicError):
            proposals([issue(2, "EPIC: a", "<!-- factory-plan-task {bad} -->")],
                      "pl0n3r/Factory", "Tests de scripts")
        with self.assertRaises(EpicError):
            make_leaf(issue(3, "EPIC: bad"), "mapeo",
                      "pl0n3r/Factory", "Validar")

    def test_completed_generated_leaf_still_prevents_new_one(self):
        epic = issue(800, "Roadmap: remain")
        existing = make_leaf(epic, "mapeo", "pl0n3r/Factory", "Tests de scripts")
        result = proposals([epic, issue(801, existing.title, existing.body, state="closed")],
                           "pl0n3r/Factory", "Tests de scripts")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
