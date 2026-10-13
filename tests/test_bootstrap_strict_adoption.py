"""Acceptance #1130: generated consumer tests work for both coordination caller generations."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts import bootstrap_coordination as bootstrap

ROOT = Path(__file__).resolve().parents[1]
LEGACY_GUARD = """  comentario:
    if: >-
      github.event_name == 'issue_comment' &&
      github.event.issue.pull_request == null &&
      github.event.sender.login == github.event.comment.user.login &&
      (github.event.comment.body == '/tomar' ||
       startsWith(github.event.comment.body, '/renovar-contrato '))
"""
STRICT_GUARD = """  comentario:
    needs: preflight_comentario
    if: >-
      github.event_name == 'issue_comment' &&
      github.event.issue.pull_request == null &&
      github.event.sender.login == github.event.comment.user.login &&
      github.event.comment.user.type == 'User' &&
      contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association) &&
      needs.preflight_comentario.outputs.route == 'true'
"""
STRICT_PREFLIGHT = """  preflight_comentario:
    if: >-
      github.event_name == 'issue_comment' &&
      github.event.issue.pull_request == null &&
      github.event.sender.login == github.event.comment.user.login &&
      github.event.comment.user.type == 'User' &&
      contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)
    runs-on: ubuntu-latest
    timeout-minutes: 2
    permissions:
      contents: read
    outputs:
      route: ${{ steps.route.outputs.route }}
    steps:
      - id: route
        shell: bash
        run: |
          python3 - <<'PY'
          import json
          import os
          with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as source:
              event = json.load(source)
          body = event.get("comment", {}).get("body", "")
          parts = body.strip().split(maxsplit=1) if isinstance(body, str) else []
          supported = {"/tomar", "/liberar-forzado", "/adoptar-contrato-huerfana", "/liberar", "/transferir", "/migrar-contrato", "/renovar-contrato"}
          route = bool(parts and parts[0] in supported)
          with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
              output.write(f"route={str(route).lower()}\\n")
          PY

"""
CALLER = """name: Coordinación
on:
  pull_request:
    types: [opened, reopened, synchronize, edited, ready_for_review, converted_to_draft, closed]
  issue_comment:
  issues:
concurrency:
  group: coordinacion-${{ github.repository }}
  cancel-in-progress: false
  queue: max
jobs:
""" + LEGACY_GUARD + """    permissions:
      contents: write
      issues: write
      pull-requests: write
      checks: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: comment
      profile: es
  etiqueta:
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: label
  pr:
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: pr
  validar-pr:
    if: >-
      github.event_name == 'pull_request' &&
      !(startsWith(github.event.pull_request.head.ref, 'factory/bootstrap-coordination-') &&
        github.event.pull_request.head.repo.full_name == github.repository &&
        github.event.pull_request.author_association == 'OWNER')
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: validate
      require_reservation: true
  issue:
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: issue
  sweep:
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: sweep
"""


def consumer_caller(*, strict: bool) -> str:
    """Closed test fixtures: no GitHub API, network or external consumer changes."""
    if not strict:
        return CALLER
    assert CALLER.count("jobs:\n") == 1
    assert CALLER.count(LEGACY_GUARD) == 1
    return (CALLER.replace("jobs:\n", "jobs:\n" + STRICT_PREFLIGHT, 1)
            .replace(LEGACY_GUARD, STRICT_GUARD, 1))


class BootstrapStrictAdoptionTests(unittest.TestCase):
    def test_tree_info_rejects_truncated_or_malformed_recursive_tree(self):
        """A partial GitHub tree cannot prove the protected paths are symlink-free."""
        gateway = bootstrap.GitHubGateway("fake-token")
        repo, sha = "pl0n3r/Consumer", "a" * 40
        paths = {".github/workflows/coordinacion.yml", "tests/test_factory_coordination_adoption.py"}
        commit = {"tree": {"sha": "b" * 40}}
        valid = [{"path": ".github/workflows", "mode": "040000"},
                 {"path": ".github/workflows/coordinacion.yml", "mode": "100644"}]
        cases = (
            ({"truncated": True, "tree": valid}, "incompleto"),
            ({"tree": valid}, "incompleto"),
            ({"truncated": "false", "tree": valid}, "incompleto"),
            ({"truncated": False}, "inválido"),
            ({"truncated": False, "tree": None}, "inválido"),
            ({"truncated": False, "tree": [None]}, "inválida"),
            ({"truncated": False, "tree": [{"path": ".github", "mode": None}]}, "inválida"),
            ({"truncated": False, "tree": [{"path": ".github", "mode": "120000"}]}, "symlinks"),
        )
        for returned, reason in cases:
            with self.subTest(response=returned), mock.patch.object(
                gateway, "_request", side_effect=[commit, returned]
            ) as request:
                with self.assertRaisesRegex(bootstrap.BootstrapError, reason):
                    gateway.tree_info(repo, sha, paths)
                self.assertEqual(request.call_count, 2)
                self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))

        with mock.patch.object(gateway, "_request", side_effect=[
            commit, {"truncated": False, "tree": valid}
        ]) as request:
            self.assertEqual(gateway.tree_info(repo, sha, paths), "b" * 40)
            self.assertEqual(request.call_count, 2)

    def test_closed_pr_scans_all_pages_and_fails_closed_on_unknown_history(self):
        """Pagination must not hide a second unmerged PR or authorize partial history."""
        gateway = bootstrap.GitHubGateway("fake-token")
        repo, branch = "pl0n3r/Consumer", "factory/bootstrap-coordination-1130"

        def simulate(pages, open_numbers=(), fail_page=None):
            calls = []
            def fetch(method, path, *args, **kwargs):
                calls.append((method, path))
                self.assertEqual(method, "GET", "Historical listing must be read-only")
                if "/pulls?state=closed&" in path:
                    page = int(path.rsplit("&page=", 1)[1]) if "&page=" in path else 1
                    if page == fail_page:
                        raise bootstrap.BootstrapError("GitHub API 403")
                    return [{"number": value} for value in pages[page-1]]
                if "/pulls/" in path:
                    number = int(path.rsplit("/", 1)[1])
                    return {
                        "number": number, "state": "closed",
                        "merged_at": None if number in open_numbers else "2026-10-01",
                    }
                self.fail(f"Unexpected API route: {path}")
            return fetch, calls

        ten = list(range(200, 210))
        fetch, calls = simulate([ten, [210]], open_numbers=(200, 210))
        with mock.patch.object(gateway, "_request", side_effect=fetch):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "ambiguo"):
                gateway.closed_pr(repo, branch)
        self.assertTrue(any("&page=2" in path for _, path in calls))
        self.assertTrue(all(method == "GET" for method, _ in calls))

        fetch, calls = simulate([ten, [210]], open_numbers=(210,))
        with mock.patch.object(gateway, "_request", side_effect=fetch):
            match = gateway.closed_pr(repo, branch)
        self.assertEqual(match["number"], 210)
        self.assertIsNone(match["merged_at"])
        self.assertTrue(any("&page=2" in path for _, path in calls))

        fetch, calls = simulate([ten, [210]], open_numbers=(210,), fail_page=2)
        with mock.patch.object(gateway, "_request", side_effect=fetch):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "403"):
                gateway.closed_pr(repo, branch)
        self.assertTrue(all(method == "GET" for method, _ in calls))

        pages = [list(range(300+10*i, 310+10*i)) for i in range(5)]
        fetch, calls = simulate(pages)
        with mock.patch.object(gateway, "_request", side_effect=fetch):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "truncado"):
                gateway.closed_pr(repo, branch)
        self.assertTrue(any("&page=5" in path for _, path in calls))
        self.assertTrue(all(method == "GET" for method, _ in calls))

        fetch, calls = simulate([ten, [200]])
        with mock.patch.object(gateway, "_request", side_effect=fetch):
            with self.assertRaisesRegex(bootstrap.BootstrapError, "inválido"):
                gateway.closed_pr(repo, branch)

    def test_closed_pr_page_rejects_invalid_json_identifiers_before_writes(self):
        """The isolated pagination helper must reject booleans and bad detail IDs."""
        gateway = bootstrap.GitHubGateway("fake-token")
        repo = "pl0n3r/Consumer"
        for invalid in (True, False, 0, -1, "7", 7.0):
            with self.subTest(invalid_number=invalid), mock.patch.object(
                gateway, "_request"
            ) as request:
                with self.assertRaisesRegex(bootstrap.BootstrapError, "inválido"):
                    gateway._closed_pr_page(repo, [{"number": invalid}], set())
                request.assert_not_called()

        with mock.patch.object(
            gateway, "_request", return_value={
                "number": True, "state": "closed", "merged_at": None,
            },
        ) as request:
            with self.assertRaisesRegex(bootstrap.BootstrapError, "inválido"):
                gateway._closed_pr_page(repo, [{"number": 1}], set())
            request.assert_called_once_with("GET", f"/repos/{repo}/pulls/1")

        with mock.patch.object(gateway, "_request") as request:
            with self.assertRaisesRegex(bootstrap.BootstrapError, "ambiguo"):
                gateway._closed_pr_page(repo, [{"number": n} for n in range(11)], set())
            request.assert_not_called()

    def test_closed_pr_page_rejects_inconsistent_detail_state_and_merge_field(self):
        """Never interpret missing merge metadata as an unmerged closed PR."""
        gateway = bootstrap.GitHubGateway("fake-token")
        repository = "pl0n3r/Consumer"
        invalid_details = (
            {"number": 1, "state": "open", "merged_at": None},
            {"number": 1, "state": "draft", "merged_at": None},
            {"number": 1, "state": "closed"},
            {"number": 1, "state": "closed", "merged_at": False},
            {"number": 1, "state": "closed", "merged_at": ""},
            {"number": 1, "state": "closed", "merged_at": 1234},
        )
        for detail in invalid_details:
            with self.subTest(detail=detail), mock.patch.object(
                gateway, "_request", return_value=detail
            ) as request:
                with self.assertRaisesRegex(bootstrap.BootstrapError, "inválido"):
                    gateway._closed_pr_page(repository, [{"number": 1}], set())
                request.assert_called_once_with("GET", f"/repos/{repository}/pulls/1")

        for merged_at in (None, "2026-10-13T00:00:00Z"):
            detail = {"number": 1, "state": "closed", "merged_at": merged_at}
            with self.subTest(valid_merge_date=merged_at), mock.patch.object(
                gateway, "_request", return_value=detail
            ):
                self.assertEqual(
                    gateway._closed_pr_page(repository, [{"number": 1}], set()),
                    [detail],
                )

    def test_existing_bootstrap_pr_requires_one_exact_identity_marker(self):
        """A canonical marker hidden among contradictory markers is not sufficient."""
        gateway = bootstrap.GitHubGateway("fake-token")
        req = bootstrap.validate_request({
            "target_repository": "pl0n3r/Consumer",
            "target_issue": "187",
            "expected_main_sha": "a" * 40,
            "governance_ref": bootstrap.GOVERNANCE_REF,
            "idempotency_key": "b" * 64,
        })
        repo, branch = req["target_repository"], bootstrap.branch_name(req)
        canonical = bootstrap.marker(req)
        valid = {
            "number": 77,
            "state": "open",
            "base": {"ref": "main", "sha": req["expected_main_sha"]},
            "head": {"ref": branch, "repo": {"full_name": repo}},
            "body": "Bootstrap gobernado para consumidor.\n\n" + canonical,
        }
        self.assertTrue(gateway.pr_matches(repo, branch, valid, req))

        different_req = {**req, "target_issue": req["target_issue"] + 1}
        contradictory = bootstrap.marker(different_req)
        variants = (
            canonical + "\n" + canonical,
            canonical + "\n" + contradictory,
            contradictory + "\n" + canonical,
            canonical + "\n<!-- factory-coordination-bootstrap {not-json} -->",
        )
        for body in variants:
            with self.subTest(body=body):
                self.assertFalse(gateway.pr_matches(repo, branch, {**valid, "body": body}, req))
        self.assertFalse(gateway.pr_matches(repo, branch, {**valid, "body": contradictory}, req))
        self.assertFalse(gateway.pr_matches(repo, branch, {**valid, "body": None}, req))

    def test_bootstrap_pr_numbers_require_exact_positive_integers(self):
        """Boolean, float and string REST identifiers cannot impersonate PR #1."""
        gateway = bootstrap.GitHubGateway("fake-token")
        req = bootstrap.validate_request({
            "target_repository": "pl0n3r/Consumer",
            "target_issue": "187",
            "expected_main_sha": "a" * 40,
            "governance_ref": bootstrap.GOVERNANCE_REF,
            "idempotency_key": "b" * 64,
        })
        name, branch = req["target_repository"], bootstrap.branch_name(req)
        legitimate = {
            "number": 1,
            "state": "open",
            "base": {"ref": "main", "sha": req["expected_main_sha"]},
            "head": {"ref": branch, "repo": {"full_name": name}},
            "user": {"login": bootstrap.OWNER},
            "body": bootstrap.marker(req),
        }
        self.assertTrue(gateway.pr_matches(name, branch, legitimate, req))
        with mock.patch.object(gateway, "main_descends_from", return_value=True):
            self.assertIsNotNone(gateway.legacy_marker(name, branch, legitimate, req))
            for wrong in (True, False, "1", 1.0, 0, -1):
                with self.subTest(wrong_number=wrong):
                    altered = {**legitimate, "number": wrong}
                    self.assertFalse(gateway.pr_matches(name, branch, altered, req))
                    self.assertIsNone(gateway.legacy_marker(name, branch, altered, req))

        with mock.patch.object(gateway, "open_pr", return_value=legitimate), mock.patch.object(
            gateway, "closed_pr", return_value=None
        ), mock.patch.object(gateway, "main_descends_from", return_value=True):
            for wrong in (True, False, "1", 1.0, 0, -1):
                with self.subTest(wrong_comparison=wrong):
                    self.assertFalse(gateway.legacy_pr_matches_exact(name, branch, wrong, req))
            self.assertTrue(gateway.legacy_pr_matches_exact(name, branch, 1, req))

        for wrong in (True, False, "1", 1.0, 0, -1):
            with self.subTest(create_pr_number=wrong), mock.patch.object(
                gateway, "_request",
                return_value={
                    "number": wrong, "base": {"ref": "main"}, "head": {"ref": branch},
                }
            ), mock.patch.object(gateway, "delete_branch") as delete, mock.patch.object(
                gateway, "classify_bootstrap_pr"
            ) as classify:
                with self.assertRaisesRegex(bootstrap.BootstrapError, "PR bootstrap inválido"):
                    gateway.create_pr(name, branch, "fixture", "fixture")
                classify.assert_not_called()
                delete.assert_called_once_with(name, branch)

        with mock.patch.object(
            gateway, "_request",
            return_value={"number": 71, "base": {"ref": "main"}, "head": {"ref": branch}},
        ), mock.patch.object(gateway, "classify_bootstrap_pr") as classify:
            self.assertEqual(gateway.create_pr(name, branch, "fixture", "fixture"), 71)
            classify.assert_called_once_with(name, 71)

    def test_bootstrap_marker_identity_requires_json_integers(self):
        """Historical bootstrap identity must fail closed on bool, float and strings."""
        canonical = {
            "version": 1,
            "identity": "a" * 64,
            "target_issue": 1130,
            "expected_main_sha": "b" * 40,
            "governance_ref": bootstrap.GOVERNANCE_REF,
        }

        def encoded(marker):
            return "<!-- factory-coordination-bootstrap " + json.dumps(
                marker, sort_keys=True, separators=(",", ":")
            ) + " -->"

        for issue in (1, 1130):
            with self.subTest(valid_issue=issue):
                positive = {**canonical, "target_issue": issue}
                self.assertEqual(bootstrap.parse_marker(encoded(positive)), positive)

        for key, invalid in (
            ("version", True), ("version", False),
            ("version", "1"), ("version", 1.0), ("version", 0),
            ("target_issue", True), ("target_issue", False),
            ("target_issue", "1"), ("target_issue", 1.0),
            ("target_issue", 0), ("target_issue", -1),
        ):
            with self.subTest(field=key, invalid=invalid):
                changed = {**canonical, key: invalid}
                self.assertIsNone(bootstrap.parse_marker(encoded(changed)))

    def run_generated(self, caller: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = root / bootstrap.CALLER_PATH
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(caller, encoding="utf-8")
            test = root / bootstrap.TEST_PATH
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text(bootstrap.adoption_test(bootstrap.CALLER_PATH), encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests",
                 "-p", Path(bootstrap.TEST_PATH).name, "-v"],
                cwd=root, capture_output=True, text=True, timeout=20, check=False,
            )

    def test_generated_consumer_adoption_accepts_legacy_and_strict_callers(self):
        for strict in (False, True):
            with self.subTest(strict=strict):
                result = self.run_generated(consumer_caller(strict=strict))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Ran 3 tests", result.stderr)
                self.assertIn("test_preflight_only_routes_actual_first_token", result.stderr)

    def test_strict_generated_adoption_rejects_embedded_commands(self):
        strict = consumer_caller(strict=True)
        positive = self.run_generated(strict)
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        self.assertNotIn("COMMENT_BODY", strict)
        # Mutation test: a substring router would falsely treat this prose as
        # a real command; the generated adoption test MUST detect it.
        bad = strict.replace(
            "route = bool(parts and parts[0] in supported)",
            "route = bool(parts and any(cmd in body for cmd in supported))",
        )
        self.assertNotEqual(bad, strict)
        negative = self.run_generated(bad)
        self.assertNotEqual(negative.returncode, 0)
        self.assertIn("FAIL", negative.stderr)

    def test_generated_adoption_rejects_untrusted_embedded_python_without_execution(self):
        """Consumer-controlled workflow snippets are parsed, never run unless audited."""
        strict = consumer_caller(strict=True)
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "unauthorized-write"
            payload = (
                "          __import__('pathlib').Path("
                + repr(str(sentinel))
                + ").write_text('unauthorized', encoding='utf-8')\n"
            )
            target = "          route = bool(parts and parts[0] in supported)"
            mutated = strict.replace(target, payload + target, 1)
            self.assertNotEqual(mutated, strict)
            failure = self.run_generated(mutated)
            self.assertNotEqual(failure.returncode, 0, failure.stdout + failure.stderr)
            self.assertIn("FAIL", failure.stderr)
            self.assertFalse(sentinel.exists(), "A rejected script must never execute")

    def test_generated_adoption_preserves_reusable_guards(self):
        source = bootstrap.adoption_test(bootstrap.CALLER_PATH)
        self.assertIn("checks: write", source)
        self.assertIn("github.event.issue.pull_request == null", source)
        self.assertIn("github.event.pull_request.author_association == 'OWNER'", source)
        template = (ROOT / "template/.github/workflows/coordinacion.yml").read_text(encoding="utf-8")
        patch = bootstrap.build_patch(template)
        self.assertEqual(patch[bootstrap.TEST_PATH], source)
        self.assertIn("operation: comment", patch[bootstrap.CALLER_PATH])
        self.assertNotIn("@main", patch[bootstrap.CALLER_PATH])
        for strict in (False, True):
            caller = consumer_caller(strict=strict)
            for before, after in (
                ("checks: write", "checks: read"),
                ("github.event.pull_request.author_association == 'OWNER'", "true"),
            ):
                with self.subTest(strict=strict, removed=before):
                    mutated = caller.replace(before, after, 1)
                    self.assertNotEqual(mutated, caller)
                    result = self.run_generated(mutated)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("FAIL", result.stderr)
        strict = consumer_caller(strict=True)
        for before, after in (
            ("route: ${{ steps.route.outputs.route }}", "route: ${{ steps.wrong.outputs.route }}"),
            ("- id: route", "- id: wrong"),
        ):
            with self.subTest(missing_preflight_binding=before):
                mutated = strict.replace(before, after, 1)
                self.assertNotEqual(mutated, strict)
                result = self.run_generated(mutated)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("FAIL", result.stderr)


    def test_generated_adoption_rejects_spoofed_operations_and_missing_actor_guards(self):
        operation = "      operation: comment"
        spoofed_operation = "      operation: label\n      # operation: comment"
        for strict in (False, True):
            caller = consumer_caller(strict=strict)
            with self.subTest(strict=strict, mutation="comment-only-in-yaml-comment"):
                self.assertEqual(caller.count(operation), 1)
                mutated = caller.replace(operation, spoofed_operation, 1)
                result = self.run_generated(mutated)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stderr)

        # A YAML comment cannot substitute for the actual writer permissions.
        for strict in (False, True):
            caller = consumer_caller(strict=strict)
            for name, before, after in (
                ("comment_checks_write_spoof",
                 "      checks: write",
                 "      checks: read\n      # checks: write"),
                ("comment_extra_write_scope",
                 "      checks: write",
                 "      checks: write\n      actions: write"),
            ):
                with self.subTest(strict=strict, permission_mutation=name):
                    mutated = caller.replace(before, after, 1)
                    self.assertNotEqual(mutated, caller)
                    result = self.run_generated(mutated)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("FAIL", result.stderr)

        for strict in (False, True):
            caller = consumer_caller(strict=strict)
            for name, before, after in (
                ("comment_profile_yaml_spoof",
                 "      profile: es",
                 "      profile: en\n      # profile: es"),
                ("comment_reusable_yaml_spoof",
                 "    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1",
                 "    uses: attacker/fork/.github/workflows/coordinacion.yml@main\n    # uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1"),
            ):
                with self.subTest(strict=strict, spoof=name):
                    mutated = caller.replace(before, after, 1)
                    self.assertNotEqual(mutated, caller)
                    result = self.run_generated(mutated)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("FAIL", result.stderr)

        strict = consumer_caller(strict=True)
        roles = """contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)"""
        for condition in ("github.event.comment.user.type == 'User'", roles):
            self.assertEqual(strict.count(condition), 2)
            for occurrence in (0, 1):
                with self.subTest(condition=condition, occurrence=occurrence):
                    first = strict.find(condition)
                    pos = first if occurrence == 0 else strict.find(
                        condition, first + len(condition)
                    )
                    self.assertGreaterEqual(pos, 0)
                    mutated = strict[:pos] + "true" + strict[pos + len(condition):]
                    result = self.run_generated(mutated)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("FAIL", result.stderr)

    def test_strict_generated_adoption_catches_preflight_regressions(self):
        strict = consumer_caller(strict=True)
        roles = """contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)"""
        route = "needs.preflight_comentario.outputs.route == 'true'"
        for mutation, original, unsafe in (
            ("preflight_negated_role",
             roles + "\n    runs-on:",
             "!(" + roles + ")\n    runs-on:"),
            ("comment_negated_route", route, "!(" + route + ")"),
            ("comment_negated_user",
             "github.event.comment.user.type == 'User' &&\n      " + roles + " &&\n      " + route,
             "!(github.event.comment.user.type == 'User') &&\n      " + roles + " &&\n      " + route),
        ):
            with self.subTest(unsafe_negation=mutation):
                self.assertIn(original, strict)
                modified = strict.replace(original, unsafe, 1)
                self.assertNotEqual(modified, strict)
                result = self.run_generated(modified)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stderr)

        # The generated test must reject any of the seven missing commands.
        for command in ("/tomar", "/liberar-forzado", "/adoptar-contrato-huerfana",
                        "/liberar", "/transferir", "/migrar-contrato",
                        "/renovar-contrato"):
            with self.subTest(removed_command=command):
                mutated = strict.replace('"' + command + '"', '"removed-command"', 1)
                self.assertNotEqual(mutated, strict)
                result = self.run_generated(mutated)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stderr)
        # The preflight job itself must enforce authorization and resources.
        for before, after in (
            ("github.event_name == 'issue_comment'", "github.event_name == 'issues'"),
            ("github.event.issue.pull_request == null", "github.event.issue.pull_request != null"),
            ("github.event.sender.login == github.event.comment.user.login",
             "github.event.sender.login != github.event.comment.user.login"),
            ("      contents: read", "      contents: write"),
            ("    timeout-minutes: 2", "    timeout-minutes: 25"),
        ):
            with self.subTest(preflight_guard=before):
                mutated = strict.replace(before, after, 1)
                self.assertNotEqual(mutated, strict)
                result = self.run_generated(mutated)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stderr)



        # Event subscription, exact preflight condition and job-scoped profile.
        for name, mutated in (
            ("missing_issue_comment", strict.replace("  issue_comment:\n", "", 1)),
            ("preflight_or_true", strict.replace(
                "contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]'), github.event.comment.author_association)\n    runs-on:",
                "contains(fromJSON('[\"OWNER\",\"MEMBER\",\"COLLABORATOR\"]'), github.event.comment.author_association) || true\n    runs-on:", 1)),
            ("comment_or_true", strict.replace(
                "needs.preflight_comentario.outputs.route == 'true'",
                "needs.preflight_comentario.outputs.route == 'true' || true", 1)),
            ("comment_profile_wrong", strict.replace(
                "      profile: es", "      profile: en", 1).replace(
                "      operation: label", "      operation: label\n      profile: es", 1)),
        ):
            with self.subTest(unsafe_metadata=name):
                self.assertNotEqual(mutated, strict)
                result = self.run_generated(mutated)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stderr)

        # Negative mutations: unknown slash commands, case-folding and
        # additional write scopes must not pass consumer adoption tests.
        for name, mutated in (
            ("unexpected_slash", strict.replace(
                "route = bool(parts and parts[0] in supported)",
                "route = bool(parts and parts[0].startswith('/'))", 1)),
            ("case_fold", strict.replace(
                "route = bool(parts and parts[0] in supported)",
                "route = bool(parts and parts[0].lower() in supported)", 1)),
            ("extra_write_scope", strict.replace(
                "      contents: read\n    outputs:",
                "      contents: read\n      issues: write\n    outputs:", 1)),
        ):
            with self.subTest(unsafe_preflight=name):
                self.assertNotEqual(mutated, strict)
                result = self.run_generated(mutated)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("FAIL", result.stderr)

if __name__ == "__main__":
    unittest.main()
