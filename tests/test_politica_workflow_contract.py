import copy
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = (ROOT / ".github/workflows/politica.yml").read_text()
COMMENT_W = (ROOT / ".github/workflows/politica-comentario.yml").read_text()
TEMPLATE = (ROOT / "template/.github/workflows/politica.yml").read_text()
TEMPLATE_POLICY_PATH = ROOT / "template/.github/factory-policy.json"
TEMPLATE_POLICY = TEMPLATE_POLICY_PATH.read_text()


class T(unittest.TestCase):
    def test_policy_script_remains_executable(self):
        self.assertTrue((ROOT / "scripts/politica_kit.py").stat().st_mode & 0o111)

    def test_observed_reviews_and_canonical_policy(self):
        self.assertIn("pr_number:", W)
        self.assertNotIn("review_rounds:", W)
        self.assertIn("/pulls/$PR/reviews", W)
        self.assertIn("python3 .factory/scripts/politica_kit.py", W)
        self.assertNotIn("--file", W)

    def test_required_reviewer_policy_is_loaded_from_base_sha_before_candidate_checkout(self):
        self.assertIn("github.event.pull_request.base.sha", W)
        self.assertIn("factory-policy.json?ref=$CURRENT_BASE", W)
        self.assertIn("application/vnd.github.raw+json", W)
        self.assertIn("BASE_POLICY_FILE", W)
        self.assertLess(W.index("factory-policy.json?ref=$CURRENT_BASE"), W.index("actions/checkout@"))
        self.assertLess(W.index("Validar evento, PR, HEAD y policy base antes de checkout"), W.index("actions/checkout@"))

    def test_template_policy_is_versioned_read_only_and_event_bounded(self):
        policy = json.loads(TEMPLATE_POLICY)
        self.assertEqual(policy, {"version": 1, "required_review_bot": None})
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("issue_comment:", TEMPLATE)
        self.assertIn("required_review_bot:", TEMPLATE)
        self.assertIn("contents: read", W)
        self.assertIn("pull-requests: read", W)
        self.assertNotIn("issues: write", W)
        self.assertNotIn("checks: read", W)
        policy_job = TEMPLATE.split("  politica:\n", 1)[1].split(
            "\n  politica-comentario:",
            1,
        )[0]
        self.assertNotIn("permissions:", policy_job)
        for forbidden in ("contents: write", "pull-requests: write", "secrets:"):
            self.assertNotIn(forbidden, W + COMMENT_W + TEMPLATE)
        self.assertNotIn("issues: write", COMMENT_W)
        for event in ("pull_request_target:", "workflow_run:", "check_run:", "repository_dispatch:"):
            self.assertNotIn(event, W + COMMENT_W + TEMPLATE)

    def test_candidate_caller_cannot_disable_base_required_reviewer(self):
        self.assertIn('CURRENT_BASE="$(jq -r', W)
        self.assertIn('[[ "$CURRENT_BASE" == "$EVENT_BASE" ]]', W)
        self.assertIn("--base-policy-file", W)
        self.assertIn('required_review_bot: ""', TEMPLATE)
        self.assertNotIn("factory-policy.json?ref=$PR_HEAD_SHA", W)

    def test_required_reviewer_context_is_read_only_and_event_bounded(self):
        self.assertIn("required_review_bot:", W)
        self.assertIn("pull_request|pull_request_review", W)
        self.assertIn("github.event.pull_request.head.sha", W)
        self.assertIn('CURRENT_HEAD="$(jq -r', W)

    def test_template_rechecks_policy_on_review_events(self):
        self.assertIn("pull_request_review:", TEMPLATE)
        self.assertIn("types: [submitted, dismissed]", TEMPLATE)
        self.assertIn("issue_comment:", TEMPLATE)
        self.assertIn("types: [created, edited]", TEMPLATE)
        self.assertIn("github.event_name == 'pull_request' || github.event_name == 'pull_request_review'", TEMPLATE)
        self.assertIn("github.event.issue.pull_request != null", TEMPLATE)
        self.assertNotIn("pull_request_target", TEMPLATE)

    def test_required_reviewer_comments_are_read_only_bounded_and_exact_pr(self):
        self.assertIn('issues/$PR/comments?per_page=100', W)
        self.assertIn('--comments-file "$comments_file"', W)
        self.assertIn('MAX_EVIDENCE_BYTES: "2000000"', W)
        self.assertIn('comments_bytes="$(wc -c < "$comments_file")"', W)
        self.assertIn('(( comments_bytes <= MAX_EVIDENCE_BYTES ))', W)
        self.assertIn('PR_JSON="$(gh api "repos/$REPOSITORY/pulls/$INPUT_PR")"', W)
        self.assertIn('[[ "$CURRENT_HEAD" == "$EVENT_HEAD" ]]', W)
        self.assertIn('[[ "$CURRENT_BASE" == "$EVENT_BASE" ]]', W)
        self.assertNotIn("issues: write", W)
        self.assertNotIn("issue_comment", W)

    def test_comment_revalidation_never_executes_consumer_code(self):
        self.assertIn("repository: pl0n3r/factory", COMMENT_W)
        self.assertIn("path: .factory", COMMENT_W)
        self.assertIn("python3 .factory/scripts/politica_kit.py", COMMENT_W)
        self.assertIn("repos/$HEAD_REPO/contents/decisiones.yml?ref=$CURRENT_HEAD", COMMENT_W)
        self.assertNotIn("repository: ${{ github.repository }}", COMMENT_W)
        self.assertLess(COMMENT_W.index("Validar evento, PR, comentario y policy base antes de checkout"), COMMENT_W.index("actions/checkout@"))

    def test_comment_revalidation_supports_bootstrap_reviewer_input(self):
        self.assertIn('required_review_bot: {required: false, type: string, default: ""}', COMMENT_W)
        self.assertIn('CALLER_REQUIRED_REVIEW_BOT: ${{ inputs.required_review_bot }}', COMMENT_W)
        self.assertEqual(TEMPLATE.count('required_review_bot: ""'), 2)
        self.assertIn('EFFECTIVE_REQUIRED="$CALLER_REQUIRED_REVIEW_BOT"', COMMENT_W)
        self.assertIn('echo "BASE_POLICY_FILE="', COMMENT_W)

    def test_comment_revalidation_preserves_monotonic_base_reviewer(self):
        self.assertIn('BASE_REQUIRED="$(jq -r', COMMENT_W)
        self.assertIn('if [[ -n "$BASE_REQUIRED" ]]', COMMENT_W)
        self.assertIn('"$CALLER_REQUIRED_REVIEW_BOT" == "$BASE_REQUIRED"', COMMENT_W)
        self.assertIn("Caller no puede cambiar reviewer-bot de BASE", COMMENT_W)
        self.assertIn('EFFECTIVE_REQUIRED="$BASE_REQUIRED"', COMMENT_W)

    def test_comment_revalidation_filters_non_pr_and_wrong_actor(self):
        self.assertIn("github.event.issue.pull_request != null", TEMPLATE)
        self.assertIn('EVENT_IS_PR: ${{ github.event.issue.pull_request != null }}', COMMENT_W)
        self.assertIn('COMMENT_TYPE="$(jq -r', COMMENT_W)
        self.assertIn('COMMENT_LOGIN="$(jq -r', COMMENT_W)
        self.assertIn('if [[ "$COMMENT_TYPE" != "Bot" ]]', COMMENT_W)
        self.assertIn('if [[ -z "$EFFECTIVE_REQUIRED" || "$COMMENT_LOGIN" != "$EFFECTIVE_REQUIRED" ]]', COMMENT_W)
        self.assertIn('echo "RELEVANT=false"', COMMENT_W)

    def test_comment_revalidation_delegates_reviewer_resolution_to_policy_kit(self):
        self.assertIn('args=(--required-review-bot "$CALLER_REQUIRED_REVIEW_BOT"', COMMENT_W)
        self.assertIn('[[ -z "${BASE_POLICY_FILE:-}" ]] || args+=(--base-policy-file "$BASE_POLICY_FILE")', COMMENT_W)
        self.assertIn('python3 .factory/scripts/politica_kit.py "${args[@]}"', COMMENT_W)
        self.assertNotIn('--required-review-bot "$EFFECTIVE_REQUIRED"', COMMENT_W)

    def test_comment_revalidation_materializes_exact_head_success_check(self):
        self.assertIn("CHECK_NAME: Factory policy / Validar decisiones y límite de revisión", COMMENT_W)
        self.assertIn('CONCLUSION="success"', COMMENT_W)
        self.assertIn('"repos/$REPOSITORY/check-runs"', COMMENT_W)
        self.assertIn('--arg head_sha "$PR_HEAD_SHA"', COMMENT_W)
        self.assertIn('head_sha:$head_sha', COMMENT_W)

    def test_comment_revalidation_keeps_invalid_required_bot_evidence_failed(self):
        self.assertIn('CONCLUSION="failure"', COMMENT_W)
        self.assertIn('if (( POLICY_STATUS != 0 )); then', COMMENT_W)
        self.assertIn('--comments-file "$COMMENTS_FILE"', COMMENT_W)
        self.assertIn('--base-policy-file "$BASE_POLICY_FILE"', COMMENT_W)

    def test_comment_revalidation_rechecks_head_before_check_publish(self):
        self.assertIn('PR_JSON_FINAL="$(gh api "repos/$REPOSITORY/pulls/$PR")"', COMMENT_W)
        self.assertIn('"$FINAL_HEAD" != "$PR_HEAD_SHA"', COMMENT_W)
        self.assertIn('"$FINAL_BASE" != "$PR_BASE_SHA"', COMMENT_W)
        self.assertIn('"$FINAL_HEAD_REPO" != "$PR_HEAD_REPO"', COMMENT_W)
        self.assertIn('"$FINAL_BASE_REPO" != "$PR_BASE_REPO"', COMMENT_W)
        self.assertLess(COMMENT_W.index("PR_JSON_FINAL="), COMMENT_W.index("check-runs"))

    def test_comment_revalidation_permissions_are_minimal(self):
        self.assertIn("checks: write", COMMENT_W)
        self.assertIn("contents: read", COMMENT_W)
        self.assertIn("pull-requests: read", COMMENT_W)
        self.assertIn("issues: read", COMMENT_W)
        self.assertIn("checks: write", TEMPLATE)
        for forbidden in ("contents: write", "pull-requests: write", "issues: write", "secrets:"):
            self.assertNotIn(forbidden, COMMENT_W)
        self.assertNotIn("pull_request_target", COMMENT_W)


class PoliticaWorkflowContractTests(unittest.TestCase):
    def test_sha_less_fallback_preserves_canonical_gates_and_ref_revalidation(self):
        self.assertNotIn('PRIMARY_STATUS == 0', W)
        self.assertIn('recheck_pr_identity "$PR_JSON_FINAL" || {', W)
        self.assertLess(W.index('reviewThreads(first:100)'), W.index('POLICY_OUTPUT='))
        self.assertLess(W.index('checks_url_base='), W.index('POLICY_OUTPUT='))
        self.assertIn('repos/$REPOSITORY/pulls/$PR', W)
        for gate in ('"$PR_HEAD_SHA"', '"$PR_BASE_SHA"', '"$PR_HEAD_REF"',
                     '"$PR_BASE_REF"', '"$PR_HEAD_REPO"', '"$PR_BASE_REPO"'):
            self.assertIn(gate, W)
        self.assertLess(W.index('recheck_pr_identity "$PR_JSON_FINAL" || {'),
                        W.index('printf \'%s\\n\' "$POLICY_OUTPUT"'))
        self.assertIn('GITHUB_RUN_ATTEMPT > 1', W)
        self.assertIn('validate_rate_limit_fallback', (
            ROOT / 'scripts/politica_kit.py').read_text(encoding='utf-8'))

    def test_primary_and_fallback_apply_same_trusted_gates(self):
        """AC-04: ambos caminos utilizan el mismo inventario autenticado."""
        from scripts.politica_kit import (
            PolicyError, validate_rate_limit_fallback,
            validate_required_bot_review_or_fallback,
        )
        head = "a" * 40

        def item(identifier, name, slug="github-actions", app_id=15368,
                 status="completed", conclusion="success"):
            return json.dumps({
                "id": identifier, "name": name, "head_sha": head,
                "app": {"slug": slug, "id": app_id},
                "status": status, "conclusion": conclusion,
                "completed_at": "2026-10-04T05:01:00Z",
            })

        checks = [
            item(10, "validate"),
            item(11, "SonarCloud Code Analysis", "sonarqubecloud", 12526),
            item(12, "CodeQL", "github-advanced-security", 57789),
            item(13, "tests"),
            item(14, "validar-pr / Validar coordinación"),
            item(15, "privacidad / Privacidad como código"),
        ]
        review = json.dumps({
            "id": 1, "state": "COMMENTED", "body": "Revisión sustantiva",
            "commit_id": head, "user": {"login": "coderabbitai[bot]", "type": "Bot"}
        })

        def primary(rows):
            return validate_required_bot_review_or_fallback(
                [review], "coderabbitai[bot]", head,
                comment_lines=[], check_lines=rows, thread_lines=[],
                phase_file=None)

        def fallback(rows):
            return validate_rate_limit_fallback(
                required_review_bot="coderabbitai[bot]", head_sha=head,
                head_committed_at="2026-10-04T04:59:00Z",
                phase="construccion", review_lines=[], comment_lines=[],
                check_lines=rows, thread_lines=[], run_attempt=2)

        self.assertEqual(primary(checks), {"review_fallback": False})
        wrong_issuer = [*checks[:2], item(12, "CodeQL", "foreign", 9999),
                        *checks[3:]]
        for bad in (
            wrong_issuer,
            checks[:-1],
            [*checks[:3], item(13, "tests", status="in_progress",
                              conclusion=None), *checks[4:]],
            [*checks[:3], item(13, "tests", conclusion="failure"), *checks[4:]],
        ):
            for method in (primary, fallback):
                with self.subTest(method=method.__name__, rows=bad):
                    with self.assertRaises(PolicyError):
                        method(bad)

    def test_primary_review_requires_complete_checks_threads_and_final_refs(self):
        """AC-05: bash real de recheck y vetos previos a emitir éxito."""
        from scripts.politica_kit import PolicyError, validate_required_bot_review_or_fallback
        self.assertNotIn("PRIMARY_STATUS == 0", W)
        self.assertLess(W.index('checks_url_base='), W.index('POLICY_OUTPUT='))
        self.assertLess(W.index('reviewThreads(first:100)'), W.index('POLICY_OUTPUT='))
        self.assertLess(W.index('recheck_pr_identity "$PR_JSON_FINAL"'), W.index(
            "printf '%s\\n' \"$POLICY_OUTPUT\""))
        # Ejecuta el helper Bash real contra respuesta REST mockeada, incluyendo
        # HEAD/BASE drift y PR cerrado, no solamente búsqueda de strings.
        self.test_primary_review_revalidates_head_and_base_before_success()
        head = "a" * 40
        review = json.dumps({
            "id": 1, "state": "COMMENTED", "body": "Revisión sustantiva",
            "commit_id": head, "user": {"login": "coderabbitai[bot]", "type": "Bot"}
        })
        checks = [
            (10, "validate", "github-actions", 15368),
            (11, "SonarCloud Code Analysis", "sonarqubecloud", 12526),
            (12, "CodeQL", "github-advanced-security", 57789),
            (13, "tests", "github-actions", 15368),
            (14, "validar-pr / Validar coordinación", "github-actions", 15368),
            (15, "privacidad / Privacidad como código", "github-actions", 15368),
        ]
        rows = [json.dumps({
            "id": idx, "name": name, "head_sha": head,
            "app": {"slug": slug, "id": app_id},
            "status": "completed", "conclusion": "success",
        }) for idx, name, slug, app_id in checks]
        args = dict(required_review_bot="coderabbitai[bot]", head_sha=head,
                    comment_lines=[], phase_file=None)
        self.assertEqual(validate_required_bot_review_or_fallback(
            [review], check_lines=rows, thread_lines=[], **args),
            {"review_fallback": False})
        malformed = [
            rows[:-1],
            [*rows[:3], json.dumps({
                "id": 13, "name": "tests", "head_sha": head,
                "app": {"slug": "github-actions", "id": 15368},
                "status": "completed", "conclusion": "failure",
            }), *rows[4:]],
        ]
        for case in malformed:
            with self.assertRaises(PolicyError):
                validate_required_bot_review_or_fallback(
                    [review], check_lines=case, thread_lines=[], **args)
        unresolved = [json.dumps({
            "isResolved": False,
            "comments": {"pageInfo": {"hasNextPage": False},
                         "nodes": [{"author": {"login": "coderabbitai"}}]},
        })]
        with self.assertRaises(PolicyError):
            validate_required_bot_review_or_fallback(
                [review], check_lines=rows, thread_lines=unresolved, **args)

    def test_primary_review_revalidates_head_and_base_before_success(self):
        """Ejecuta el helper Bash exacto del workflow contra GET REST simulado."""
        if shutil.which('jq') is None:
            self.skipTest('jq requerido para simular el workflow real')
        start = '          # POLICY_PR_RECHECK_BEGIN\n'
        stop = '          # POLICY_PR_RECHECK_END'
        self.assertEqual(W.count(start), 1)
        self.assertEqual(W.count(stop), 1)
        helper = textwrap.dedent(W.split(start, 1)[1].split(stop, 1)[0])
        self.assertIn('gh api "repos/$REPOSITORY/pulls/$PR"', helper)
        self.assertIn('jq -e', helper)

        repo = 'pl0n3r/Factory'
        head = 'a' * 40
        base = 'b' * 40
        stable = {
            'state': 'open',
            'head': {'sha': head, 'ref': 'trabajo/issue-17',
                     'repo': {'full_name': repo}},
            'base': {'sha': base, 'ref': 'main',
                     'repo': {'full_name': repo}},
        }
        with tempfile.TemporaryDirectory() as directory:
            gh = Path(directory) / 'gh'
            gh.write_text('#!/bin/sh\nprintf "%s\\n" "$PR_JSON_FIXTURE"\n',
                          encoding='utf-8')
            gh.chmod(0o755)
            env = dict(os.environ)
            env.update({
                'PATH': directory + os.pathsep + env.get('PATH', ''),
                'REPOSITORY': repo, 'PR': '17',
                'PR_HEAD_SHA': head, 'PR_BASE_SHA': base,
                'PR_HEAD_REF': 'trabajo/issue-17',
                'PR_BASE_REF': 'main',
                'PR_HEAD_REPO': repo,
                'PR_BASE_REPO': repo,
            })
            cases = [('estable', None, True),
                     ('HEAD SHA distinto', ('head', 'sha', 'c' * 40), False),
                     ('BASE SHA distinto', ('base', 'sha', 'd' * 40), False),
                     ('BASE ref retarget sin cambio SHA',
                      ('base', 'ref', 'dev'), False),
                     ('PR cerrado', ('state', '', 'closed'), False),
                     ('fork distinto', ('head', 'repo', {'full_name': 'other/Factory'}),
                      False),
                     ('base de otra fuente', ('base', 'repo',
                         {'full_name': 'other/Factory'}), False)]
            for label, mutation, should_pass in cases:
                with self.subTest(case=label):
                    observed = copy.deepcopy(stable)
                    if mutation:
                        first, second, value = mutation
                        if second:
                            observed[first][second] = value
                        else:
                            observed[first] = value
                    env['PR_JSON_FIXTURE'] = json.dumps(observed)
                    result = subprocess.run(
                        ['bash', '-c', 'set -euo pipefail\n' + helper
                         + '\nrecheck_pr_identity'],
                        env=env, capture_output=True, text=True, timeout=8)
                    self.assertEqual(result.returncode == 0, should_pass,
                                     msg=result.stderr)

    @staticmethod
    def _mock_check_page(total, ids):
        return {"total_count": total, "check_runs": [
            {"id": value, "name": f"test-{value}", "head_sha": "a" * 40,
             "app": {"slug": "github-actions", "id": 15368},
             "status": "completed", "conclusion": "success"} for value in ids
        ]}

    def _execute_checks_snapshot_shell(self, responses, *, expected_pass,
                                       expected_count=0):
        """Ejecuta el Bash de producción con gh REST simulado y contador."""
        if shutil.which("jq") is None:
            self.skipTest("jq no disponible")
        start = "          # POLICY_CHECK_SNAPSHOT_BEGIN\n"
        end = "          # POLICY_CHECK_SNAPSHOT_END"
        self.assertEqual(W.count(start), 1)
        self.assertEqual(W.count(end), 1)
        shell = textwrap.dedent(W.split(start, 1)[1].split(end, 1)[0])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mock = root / "gh"
            mock.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
counter = Path(os.environ["MOCK_GH_COUNTER"])
index = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(index + 1))
pages = json.loads(os.environ["MOCK_GH_RESPONSES"])
if index >= len(pages) or pages[index] is None:
    sys.exit(22)
if not any("check-runs?per_page=100&page=" in x for x in sys.argv):
    sys.exit(23)
print(json.dumps(pages[index]))
''', encoding="utf-8")
            mock.chmod(0o755)
            checks = root / "checks.ndjson"
            marker = root / "evaluated"
            env = dict(os.environ)
            env.update({
                "PATH": directory + os.pathsep + env.get("PATH", ""),
                "REPOSITORY": "pl0n3r/Factory", "PR_HEAD_SHA": "a" * 40,
                "checks_file": str(checks),
                "checks_json": str(root / "page.json"),
                "MAX_EVIDENCE_BYTES": "2000000", "MAX_PUBLIC_CHECKS": "500",
                "MOCK_GH_COUNTER": str(root / "calls"),
                "MOCK_GH_RESPONSES": json.dumps(responses),
                "EVAL_MARKER": str(marker),
            })
            result = subprocess.run(
                ["bash", "-c", "set -euo pipefail\n" + shell +
                 '\nprintf "1" > "$EVAL_MARKER"\n'],
                env=env, capture_output=True, text=True, timeout=25)
            self.assertEqual(result.returncode == 0, expected_pass,
                             msg=result.stderr[-2500:])
            if expected_pass:
                self.assertEqual(marker.read_text(), "1")
                rows = [json.loads(x) for x in checks.read_text().splitlines()]
                self.assertEqual(len(rows), expected_count)
                self.assertEqual(len({row["id"] for row in rows}), expected_count)
            else:
                self.assertFalse(marker.exists(), "No ejecutar evaluador sin prueba")
            return int((root / "calls").read_text())

    def test_authenticated_checks_restart_complete_snapshot_after_total_drift(self):
        """AC-01: deriva inicial 119->120 y dos snapshots íntegros de 120."""
        p = self._mock_check_page
        cases = [
            p(119, range(1, 101)), p(120, range(101, 121)),
            p(120, range(1, 101)), p(120, range(101, 121)),
            p(120, range(1, 101)), p(120, range(101, 121)),
        ]
        self.assertEqual(self._execute_checks_snapshot_shell(
            cases, expected_pass=True, expected_count=120), 6)

    def test_authenticated_checks_persistent_drift_and_partial_snapshot_fail_closed(self):
        """AC-02: drift persistente, IDs variables, truncado, duplicado y >500."""
        p = self._mock_check_page
        cases = {
            "drift persistente": [
                p(119, range(1, 101)), p(120, range(101, 121))] * 3,
            "igual total e IDs distintos": [
                p(2, (1, 2)), p(2, (1, 3)), p(2, (1, 4))],
            "igual total y estado distinto": [
                p(1, (1,)),
                {"total_count": 1, "check_runs": [
                    {**p(1, (1,))["check_runs"][0], "conclusion": "failure"}]},
                p(1, (1,))],
            "incompleto": [
                p(120, range(1, 101)), p(120, range(101, 111)),
                p(120, ()), p(120, ()), p(120, ())],
            "ID duplicado": [p(2, (1, 1))],
            "más de 500": [p(501, range(1, 101))],
            "HTTP no-200": [None],
        }
        for reason, pages in cases.items():
            with self.subTest(reason=reason):
                self._execute_checks_snapshot_shell(pages, expected_pass=False)

    def test_check_collection_does_not_bypass_policy_gates_or_authentication(self):
        """AC-03: REST autenticada read-only, exact SHA y Policy obligatoria."""
        from scripts.politica_kit import PolicyError, validate_other_gates_green
        self.assertIn("GH_TOKEN: ${{ github.token }}", W)
        self.assertIn('"${checks_url_base}&page=$page"', W)
        self.assertIn('--checks-file "$checks_file"', W)
        self.assertLess(W.index("# POLICY_CHECK_SNAPSHOT_END"),
                        W.index("POLICY_OUTPUT="))
        self.assertIn('recheck_pr_identity "$PR_JSON_FINAL"', W)
        self.assertNotIn("checks: write", W)
        good = [
            (10, "validate", "github-actions", 15368),
            (11, "SonarCloud Code Analysis", "sonarqubecloud", 12526),
            (12, "CodeQL", "github-advanced-security", 57789),
            (13, "tests", "github-actions", 15368),
            (14, "validar-pr / Validar coordinación", "github-actions", 15368),
            (15, "privacidad / Privacidad como código", "github-actions", 15368),
        ]
        def records(items):
            return [json.dumps({
                "id": num, "name": name, "head_sha": "a" * 40,
                "app": {"slug": slug, "id": app_id},
                "status": "completed", "conclusion": "success",
            }) for num, name, slug, app_id in items]
        validate_other_gates_green(records(good), head_sha="a" * 40)
        with self.assertRaises(PolicyError):
            validate_other_gates_green(
                records([*good[:2], (12, "CodeQL", "fake-app", 1234),
                         *good[3:]]), head_sha="a" * 40)

    def test_authenticated_paginated_timeline_is_bounded_fail_closed(self):
        self.assertIn('repos/$REPOSITORY/issues/$PR/timeline?per_page=100&page=$page', W)
        self.assertIn('if (( GITHUB_RUN_ATTEMPT > 1 )); then', W)
        self.assertIn('for page in 1 2 3 4 5 6; do', W)
        self.assertIn('(( page_count == 0 ))', W)
        self.assertIn('timeline_complete=true', W)
        self.assertIn('jq -e \'type == "array" and length <= 100\'', W)
        self.assertIn('<= MAX_EVIDENCE_BYTES', W)
        self.assertIn('IDs de timeline incompletos o duplicados', W)
        self.assertIn('timeline_args=(--timeline-file "$timeline_file")', W)
        self.assertIn('"${timeline_args[@]}"', W)
        self.assertIn('PR_JSON_FINAL=', W)
        self.assertIn('HEAD cambió durante validación de timeline', W)
        self.assertIn('BASE cambió durante validación de timeline', W)
        self.assertIn('GH_TOKEN: ${{ github.token }}', W)
        self.assertNotIn('issues: write', W)
        self.assertNotIn('pull-requests: write', W)


    def test_rate_limit_fallback_keeps_legacy_caller_permissions(self):
        self.assertIn(
            "permissions:\n  contents: read\n  pull-requests: read\njobs:",
            W,
        )
        policy_job = W.split("  politica:\n", 1)[1].split(
            "\n    runs-on:",
            1,
        )[0]
        self.assertNotIn("permissions:", policy_job)
        self.assertNotIn("issues: write", W)
        self.assertNotIn("checks: read", W)

    def test_rate_limit_fallback_reads_public_checks_without_token(self):
        start = W.index(
            'checks_url_base="repos/$REPOSITORY/'
            'commits/$PR_HEAD_SHA/check-runs?per_page=100"'
        )
        end = W.index('owner="${REPOSITORY%%/*}"', start)
        checks_transport = W[start:end]

        self.assertIn("gh api", checks_transport)
        self.assertIn(
            "X-GitHub-Api-Version: 2022-11-28",
            checks_transport,
        )
        self.assertIn(
            "Página autenticada de check-runs excede el tamaño permitido",
            checks_transport,
        )
        self.assertIn(
            'and (.check_runs | type == "array")',
            checks_transport,
        )
        self.assertIn('MAX_PUBLIC_CHECKS: "500"', W)
        self.assertIn('"${checks_url_base}&page=$page"', checks_transport)
        self.assertIn('GH_TOKEN: ${{ github.token }}', W)
        self.assertNotIn("curl --silent", checks_transport)
        self.assertNotIn("Authorization:", checks_transport)

    def test_public_check_transport_paginates_bounded_exact_head_evidence(self):
        self.assertIn('MAX_PUBLIC_CHECKS: "500"', W)
        self.assertIn(
            'checks_url_base="repos/$REPOSITORY/'
            'commits/$PR_HEAD_SHA/check-runs?per_page=100"',
            W,
        )
        self.assertIn("for page in 1 2 3 4 5; do", W)
        self.assertIn('"${checks_url_base}&page=$page"', W)
        self.assertIn('expected_total="$current_total"', W)
        self.assertIn('observed_count="$(wc -l < "$checks_file")"', W)
        self.assertIn("(( observed_count == expected_total ))", W)

    def test_public_check_transport_fails_closed_above_bound_or_inconsistent_pages(self):
        self.assertIn("(( current_total <= MAX_PUBLIC_CHECKS ))", W)
        self.assertIn("total_count cambió entre páginas de check-runs", W)
        self.assertIn("Evidencia incompleta de check-runs autenticados", W)
        self.assertIn("Se observaron más check-runs que total_count", W)
        self.assertIn("IDs de check-runs autenticados inválidos o duplicados", W)
        self.assertIn("([.[].id] | unique | length)", W)

    def test_public_check_transport_remains_anonymous_and_bounded(self):
        start = W.index('checks_url_base="repos/$REPOSITORY/')
        end = W.index('owner="${REPOSITORY%%/*}"', start)
        checks_transport = W[start:end]
        self.assertIn("gh api", checks_transport)
        self.assertIn('MAX_PUBLIC_CHECKS: "500"', W)
        self.assertIn("for page in 1 2 3 4 5; do", checks_transport)
        self.assertIn("Página autenticada de check-runs excede el tamaño permitido", checks_transport)
        self.assertIn('(( $(wc -c < "$checks_file") <= MAX_EVIDENCE_BYTES ))', W)
        self.assertIn('GH_TOKEN: ${{ github.token }}', W)
        self.assertNotIn("curl --silent", checks_transport)
        self.assertNotIn("Authorization:", checks_transport)

    def test_rate_limit_fallback_reads_authenticated_checks_with_github_token(self):
        self.test_rate_limit_fallback_reads_public_checks_without_token()

    def test_authenticated_check_transport_paginates_bounded_exact_head_evidence(self):
        self.test_public_check_transport_paginates_bounded_exact_head_evidence()

    def test_authenticated_check_transport_fails_closed_above_bound_or_inconsistent_pages(self):
        self.test_public_check_transport_fails_closed_above_bound_or_inconsistent_pages()

    def test_authenticated_check_transport_cannot_regress_to_anonymous_curl(self):
        self.test_public_check_transport_remains_anonymous_and_bounded()

    def test_rate_limit_fallback_audit_is_read_only(self):
        self.assertIn("datos.yml?ref=$PR_BASE_SHA", W)
        self.assertIn("commits/$PR_HEAD_SHA", W)
        self.assertIn("HEAD_COMMITTED_AT", W)
        self.assertIn('--head-committed-at "$HEAD_COMMITTED_AT"', W)
        self.assertIn("reviewThreads(first:100)", W)
        self.assertIn("comments(first:100){pageInfo{hasNextPage}", W)
        self.assertIn('--checks-file "$checks_file"', W)
        self.assertIn('--threads-file "$threads_file"', W)
        self.assertIn("rate_limit_comment_id", W)
        self.assertIn("rate_limit_created_at", W)
        self.assertIn("GITHUB_STEP_SUMMARY", W)
        self.assertIn("::notice title=Reviewer rate-limit fallback::", W)
        self.assertIn("#issuecomment-$retry_id", W)
        self.assertNotIn("factory-reviewer-rate-limit-fallback", W)
        self.assertNotIn("--method PATCH", W)
        self.assertNotIn("--method POST", W)
        self.assertNotIn("issues: write", W)

    def test_template_policy_caller_stays_legacy_compatible(self):
        policy_job = TEMPLATE.split("  politica:\n", 1)[1].split(
            "\n  politica-comentario:",
            1,
        )[0]
        self.assertIn(
            "uses: pl0n3r/factory/.github/workflows/politica.yml@v1",
            policy_job,
        )
        self.assertNotIn("permissions:", policy_job)
        self.assertIn(
            "permissions:\n  contents: read\n  pull-requests: read",
            TEMPLATE,
        )
        self.assertNotIn("issues: write", policy_job)
        self.assertNotIn("checks: read", policy_job)

    def test_fallback_still_preserves_exact_head_and_bounded_evidence(self):
        self.assertIn("phase_args=()", W)
        self.assertIn('phase_args=(--phase-file "$phase_file")', W)
        self.assertIn('"${phase_args[@]}"', W)
        self.assertIn("check-runs?per_page=100", W)
        self.assertIn(
            '(( $(wc -c < "$checks_file") <= MAX_EVIDENCE_BYTES ))',
            W,
        )
        self.assertIn(
            '(( $(wc -c < "$threads_file") <= MAX_EVIDENCE_BYTES ))',
            W,
        )


if __name__ == "__main__":
    unittest.main()
