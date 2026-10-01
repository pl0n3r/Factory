#!/usr/bin/env python3
"""Regresiones del candidato Factory 1.0.15."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.politica_kit import PolicyError, validate_required_bot_review


HEAD = "a" * 40
STALE = "b" * 40


def review(*, commit_id=HEAD, state="APPROVED", body=""):
    return json.dumps({
        "id": 1,
        "state": state,
        "body": body,
        "commit_id": commit_id,
        "user": {"type": "Bot", "login": "coderabbitai[bot]"},
    })


def coverage_comment(*, covered=HEAD, duplicate=False):
    marker = (
        '<!-- final_review_risk_coverage:'
        + json.dumps({
            "sourceCommitId": HEAD,
            "coveredCommitId": covered,
            "kind": "reviewed",
        }, separators=(",", ":"))
        + " -->"
    )
    body = marker + (marker if duplicate else "")
    return json.dumps({
        "id": 2,
        "body": body,
        "user": {"type": "Bot", "login": "coderabbitai[bot]"},
    })


class ReleaseCandidate1015Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_candidate_is_at_least_1_0_15_and_keeps_1_0_15_guarantees(self) -> None:
        payload = json.loads(
            (self.root / "config/version.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(payload), {"version"})
        parts = payload["version"].split(".")
        self.assertEqual(len(parts), 3)
        self.assertGreaterEqual(tuple(map(int, parts)), (1, 0, 15))

        # Las garantías empaquetadas en 1.0.15 siguen siendo parte del canal.
        self.test_candidate_contains_exact_head_reviewer_comment_transport()
        self.test_candidate_contains_explicit_human_decision_materialization()
        self.test_candidate_keeps_human_release_boundary()

    def test_candidate_contains_exact_head_reviewer_comment_transport(self) -> None:
        workflow = (
            self.root / ".github/workflows/politica.yml"
        ).read_text(encoding="utf-8")
        kit = (self.root / "scripts/politica_kit.py").read_text(encoding="utf-8")

        for token in (
            'pulls/$PR/reviews?per_page=100',
            'issues/$PR/comments?per_page=100',
            '--comments-file "$comments_file"',
            'github.event.pull_request.head.sha',
            'github.event.pull_request.base.sha',
        ):
            self.assertIn(token, workflow)

        self.assertIn('review.get("commit_id") == head_sha', kit)
        self.assertIn("len(matches) != 1", kit)
        self.assertIn('covered_sha == head_sha', kit)

        validate_required_bot_review(
            [review()],
            "coderabbitai[bot]",
            HEAD,
        )
        validate_required_bot_review(
            [],
            "coderabbitai[bot]",
            HEAD,
            comment_lines=[coverage_comment()],
        )
        for comments in (
            [coverage_comment(covered=STALE)],
            [coverage_comment(duplicate=True)],
            [json.dumps({
                "id": 3,
                "body": "CodeRabbit status: success",
                "user": {"type": "Bot", "login": "coderabbitai[bot]"},
            })],
        ):
            with self.subTest(comments=comments):
                with self.assertRaises(PolicyError):
                    validate_required_bot_review(
                        [],
                        "coderabbitai[bot]",
                        HEAD,
                        comment_lines=comments,
                    )

    def test_candidate_contains_explicit_human_decision_materialization(self) -> None:
        implementation = (
            self.root / "seguridad/decision_respuesta.py"
        ).read_text(encoding="utf-8")
        workflow = (
            self.root / ".github/workflows/seguridad.yml"
        ).read_text(encoding="utf-8")

        for token in (
            'AUTHORIZED = {"OWNER"}',
            '"gate_sha256": gate_sha256',
            '"version": 2',
            "event_gate_sha256",
            'existing != expected_evidence',
            '"state": "closed"',
            '"state_reason": "completed"',
        ):
            self.assertIn(token, implementation)

        self.assertIn(
            "if: github.event_name == 'issues' && github.event.issue.state == 'open'",
            workflow,
        )
        materializer = workflow.split("  materializar-respuesta:", 1)[1].split(
            "  sincronizar-decision:", 1
        )[0]
        self.assertIn("OWNER) trusted=true", materializer)
        self.assertNotIn("OWNER|MEMBER|COLLABORATOR) trusted=true", materializer)

        for forbidden in ("billing", "go-live", "parent_issue", "rollout"):
            self.assertNotIn(forbidden, implementation)

    def test_candidate_contains_comment_revalidation_liveness(self) -> None:
        workflow = (
            self.root / ".github/workflows/politica-comentario.yml"
        ).read_text(encoding="utf-8")
        caller = (
            self.root / "template/.github/workflows/politica.yml"
        ).read_text(encoding="utf-8")

        for token in (
            "issue_comment:",
            "github.event.issue.pull_request != null",
            "checks: write",
        ):
            self.assertIn(token, caller)

        for token in (
            "repository: pl0n3r/factory",
            "path: .factory",
            "python3 .factory/scripts/politica_kit.py",
            "repos/$HEAD_REPO/contents/decisiones.yml?ref=$CURRENT_HEAD",
            'PR_JSON_FINAL="$(gh api "repos/$REPOSITORY/pulls/$PR")"',
            '"$FINAL_HEAD" != "$PR_HEAD_SHA"',
            '"$FINAL_BASE" != "$PR_BASE_SHA"',
            '"$FINAL_HEAD_REPO" != "$PR_HEAD_REPO"',
            '"$FINAL_BASE_REPO" != "$PR_BASE_REPO"',
            '"repos/$REPOSITORY/check-runs"',
        ):
            self.assertIn(token, workflow)

        self.assertNotIn("repository: ${{ github.repository }}", workflow)
        self.assertNotIn("pull_request_target", workflow)

    def test_candidate_preserves_comment_reviewer_bootstrap(self) -> None:
        workflow = (
            self.root / ".github/workflows/politica-comentario.yml"
        ).read_text(encoding="utf-8")
        caller = (
            self.root / "template/.github/workflows/politica.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'required_review_bot: {required: false, type: string, default: ""}',
            workflow,
        )
        self.assertEqual(caller.count('required_review_bot: ""'), 2)
        for token in (
            'CALLER_REQUIRED_REVIEW_BOT: ${{ inputs.required_review_bot }}',
            'EFFECTIVE_REQUIRED="$CALLER_REQUIRED_REVIEW_BOT"',
            'if [[ -n "$BASE_REQUIRED" ]]',
            '"$CALLER_REQUIRED_REVIEW_BOT" == "$BASE_REQUIRED"',
            "Caller no puede cambiar reviewer-bot de BASE",
            'EFFECTIVE_REQUIRED="$BASE_REQUIRED"',
            'args=(--required-review-bot "$CALLER_REQUIRED_REVIEW_BOT"',
            '[[ -z "${BASE_POLICY_FILE:-}" ]] || args+=(--base-policy-file "$BASE_POLICY_FILE")',
        ):
            self.assertIn(token, workflow)

    def test_candidate_keeps_human_release_boundary(self) -> None:
        workflow = (
            self.root / ".github/workflows/release-bootstrap.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "workflow_dispatch:",
            "expected_sha:",
            "gate_issue:",
            "needs: preflight",
            'EXPECTED_SHA: ${{ inputs.expected_sha }}',
            'GATE_ISSUE: ${{ inputs.gate_issue }}',
        ):
            self.assertIn(token, workflow)
        self.assertNotIn("\n  push:", workflow)


if __name__ == "__main__":
    unittest.main()
