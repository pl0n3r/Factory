"""Pruebas sintéticas, sin red ni escrituras productivas, de epic_closure_leaves."""
from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.epic_closure_leaves import (
    EpicError, Github, _existing, _kind, _labels, _task_parent, main,
    make_leaf, proposals, run,
)
from scripts.unattended_kill_switch import (
    CANONICAL_REPOSITORY_URL, CANONICAL_SOURCE_URL,
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

    def test_human_gate_in_body_blocks_unlabelled_epic(self):
        owner_gate = '<!-- factory-human-gate {"category":"factory-release"} -->'
        candidate = issue(305, "EPIC: aprobación humana", owner_gate)
        self.assertEqual(proposals([candidate], "pl0n3r/Factory", "Tests de scripts"), [])

    def test_sensitive_epic_titles_block_without_labels(self):
        for keyword in ("go-live", "legal", "gasto", "pagos", "privacidad", "live"):
            with self.subTest(keyword=keyword):
                candidate = issue(306, "EPIC: " + keyword)
                self.assertEqual(proposals([candidate], "pl0n3r/Factory", "Tests de scripts"), [])

    def test_regular_epic_still_creates_a_leaf(self):
        candidate = issue(307, "EPIC: robustez de CI")
        self.assertEqual(len(proposals([candidate], "pl0n3r/Factory", "Tests de scripts")), 1)

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


class EpicClosureGithubTests(unittest.TestCase):
    """Ejecución sin red real: cliente, switch, paginación y CLI."""

    def test_reject_invalid_repo_and_request_paths(self):
        for repo in ("factory", "other/repo/third", "../Factory", "a b/Factory"):
            with self.subTest(repo=repo), self.assertRaises(EpicError):
                Github("", repo)
        api = Github("", "pl0n3r/Factory")
        for path in ("/issues", "/repos/../issues", "/repos/Factory/../../tokens"):
            with self.subTest(path=path), self.assertRaises(EpicError):
                api.request(path)

    def test_authenticated_post_and_unauthenticated_get_are_scoped(self):
        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, maximum):
                self.maximum = maximum
                return json.dumps(self.payload).encode("utf-8")

        with patch("scripts.epic_closure_leaves.urllib.request.urlopen",
                   return_value=Response({"number": 42})) as request:
            api = Github("synthetic-token", "pl0n3r/Factory")
            data = api.request("/repos/pl0n3r/Factory/issues", {"title": "synthetic"})
            self.assertEqual(data["number"], 42)
            http = request.call_args.args[0]
            self.assertEqual(http.get_method(), "POST")
            self.assertEqual(http.get_header("Authorization"), "Bearer synthetic-token")
            self.assertEqual(json.loads(http.data), {"title": "synthetic"})
            self.assertEqual(request.call_args.kwargs["timeout"], 15)

        with patch("scripts.epic_closure_leaves.urllib.request.urlopen",
                   return_value=Response([])) as request:
            self.assertEqual(Github("", "pl0n3r/Factory").request(
                "/repos/pl0n3r/Factory/issues"), [])
            http = request.call_args.args[0]
            self.assertEqual(http.get_method(), "GET")
            self.assertIsNone(http.get_header("Authorization"))

    def test_network_or_json_error_fails_closed(self):
        api = Github("", "pl0n3r/Factory")
        with patch("scripts.epic_closure_leaves.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("sin red")):
            with self.assertRaises(EpicError):
                api.request("/repos/pl0n3r/Factory/issues")

        class InvalidJson:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, maximum):
                return b"{incomplete"

        with patch("scripts.epic_closure_leaves.urllib.request.urlopen",
                   return_value=InvalidJson()):
            with self.assertRaises(EpicError):
                api.request("/repos/pl0n3r/Factory/issues")

    def test_full_pagination_and_invalid_page_are_rejected(self):
        api = Github("", "pl0n3r/Factory")
        first = [issue(n, "normal") for n in range(1, 101)]
        with patch.object(api, "request", side_effect=[first, [issue(101, "last")]]) as fetch:
            self.assertEqual(len(api.read_all()), 101)
            self.assertIn("page=1", fetch.call_args_list[0].args[0])
            self.assertIn("page=2", fetch.call_args_list[1].args[0])
        with patch.object(api, "request", return_value={"error": "truncated"}):
            with self.assertRaises(EpicError):
                api.read_all()
        with patch.object(api, "request", return_value=first):
            with self.assertRaisesRegex(EpicError, "Límite de issues"):
                api.read_all()

    def test_canonical_switch_accepts_running_and_rejects_paused(self):
        payload = {
            "number": 767,
            "url": CANONICAL_SOURCE_URL,
            "repository_url": CANONICAL_REPOSITORY_URL,
            "state": "closed",
            "user": {"login": "pl0n3r"},
            "body": '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->',
        }
        api = Github("", "pl0n3r/Factory")
        with patch.object(api, "request", return_value=payload) as fetch:
            api.verify_switch()
            self.assertEqual(fetch.call_args.args[0], "/repos/pl0n3r/Factory/issues/767")
        paused = {**payload, "body": payload["body"].replace("RUNNING", "PAUSED")}
        with patch.object(api, "request", return_value=paused):
            with self.assertRaises(EpicError):
                api.verify_switch()

    def test_create_uses_only_fixed_labels_and_rejects_invalid_response(self):
        api = Github("synthetic-token", "pl0n3r/Factory")
        proposal = make_leaf(issue(999, "EPIC: qa"), "mapeo",
                             "pl0n3r/Factory", "Tests de scripts")
        with patch.object(api, "request", return_value={"number": 7001}) as create:
            self.assertEqual(api.create(proposal), 7001)
            path, payload = create.call_args.args
            self.assertEqual(path, "/repos/pl0n3r/Factory/issues")
            self.assertEqual(payload["title"], proposal.title)
            self.assertEqual(payload["body"], proposal.body)
            self.assertEqual(payload["labels"], [
                "tipo: infraestructura", "prioridad: media", "estado: disponible",
                "rol: ingenieria-software", "rol: qa",
            ])
        for bad in ({"number": "7001"}, {"id": 7001}, None):
            with self.subTest(bad=bad), patch.object(api, "request", return_value=bad):
                with self.assertRaises(EpicError):
                    api.create(proposal)

    def test_malformed_payloads_and_closed_markers_fail_closed(self):
        with self.assertRaises(EpicError):
            _labels({"labels": [12]})
        with self.assertRaises(EpicError):
            _task_parent({"body": [1, 2]})
        with self.assertRaises(EpicError):
            _existing({"body": ["invalid"]})
        with self.assertRaises(EpicError):
            _existing({"body": "<!-- factory-epic-closure {bad} -->"})
        with self.assertRaises(EpicError):
            proposals("not a list", "pl0n3r/Factory", "Tests de scripts")
        with self.assertRaises(EpicError):
            proposals([{"number": True}], "pl0n3r/Factory", "Tests de scripts")

    def test_revalidation_rejects_changed_closure_kind_and_bad_limit(self):
        api = FakeGithub([issue(920, "EPIC: cambio",
                                "### Criterios de aceptación\n- [ ] [AC-01] pendiente")])
        read_original = api.read_all
        reads = [0]

        def changing_read():
            reads[0] += 1
            if reads[0] == 2:
                api.issues[0]["body"] = "### Criterios de aceptación\n- [x] [AC-01] hecho"
            return read_original()

        api.read_all = changing_read
        self.assertEqual(run(api, apply=True, check="Tests de scripts", limit=1)[0]["status"],
                         "skipped_changed")
        self.assertEqual(api.creates, 0)
        with self.assertRaises(EpicError):
            run(api, apply=False, check="Tests de scripts", limit=26)

    def test_cli_dry_run_and_rejected_limits_are_json(self):
        api = FakeGithub([issue(940, "EPIC: CLI")])
        stdout = io.StringIO()
        with patch("scripts.epic_closure_leaves.Github", return_value=api), \
             patch.dict(os.environ, {"GH_TOKEN": ""}), redirect_stdout(stdout):
            self.assertEqual(main(["--repo", "pl0n3r/Factory"]), 0)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertFalse(result["apply"])
        self.assertEqual(result["items"][0]["status"], "proposed")
        self.assertEqual(api.creates, 0)

        stdout = io.StringIO()
        with patch("scripts.epic_closure_leaves.Github", return_value=api), \
             patch.dict(os.environ, {"GH_TOKEN": ""}), redirect_stdout(stdout):
            self.assertEqual(main(["--repo", "pl0n3r/Factory", "--limit", "0"]), 2)
        self.assertFalse(json.loads(stdout.getvalue())["ok"])

    def test_cli_apply_creates_with_synthetic_client(self):
        api = FakeGithub([issue(941, "EPIC: CLI apply")])
        stdout = io.StringIO()
        with patch("scripts.epic_closure_leaves.Github", return_value=api), \
             patch.dict(os.environ, {"GH_TOKEN": "synthetic"}), redirect_stdout(stdout):
            self.assertEqual(main(["--repo", "pl0n3r/Factory", "--apply"]), 0)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertTrue(result["apply"])
        self.assertEqual(result["items"][0]["status"], "created")
        self.assertEqual((api.creates, api.switch_checks), (1, 1))


if __name__ == "__main__":
    unittest.main()
