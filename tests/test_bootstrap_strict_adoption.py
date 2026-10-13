"""Acceptance #1130: generated consumer tests work for both coordination caller generations."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
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
