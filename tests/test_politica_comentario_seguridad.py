"""Regresiones del emisor Policy por issue_comment; no usa API ni datos reales."""
import hashlib
import json
import unittest
from pathlib import Path

from scripts.politica_kit import (
    PolicyError,
    validate_required_bot_review_or_fallback,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/politica-comentario.yml").read_text()
HEAD = "a" * 40
BOT = "coderabbitai[bot]"


def review(state="COMMENTED", body="Revisión sustantiva", sha=HEAD, number=41):
    return json.dumps({
        "id": number, "state": state, "body": body, "commit_id": sha,
        "user": {"type": "Bot", "login": BOT},
    })


def checks(*, bad=None, conclusion="success"):
    names = (
        ("validate", "github-actions", 15368),
        ("SonarCloud Code Analysis", "sonarqubecloud", 12526),
        ("CodeQL", "github-advanced-security", 57789),
        ("tests", "github-actions", 15368),
        ("validar-pr / Validar coordinación", "github-actions", 15368),
        ("privacidad / Privacidad como código", "github-actions", 15368),
    )
    return [json.dumps({
        "id": index, "name": name, "head_sha": HEAD,
        "status": "completed" if bad != index or conclusion != "pending" else "in_progress",
        "conclusion": conclusion if bad == index else "success",
        "app": {"slug": slug, "id": app_id},
    }) for index, (name, slug, app_id) in enumerate(names, start=10)]


def thread(resolved=False, author="coderabbitai"):
    return json.dumps({
        "isResolved": resolved,
        "comments": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [{"author": {"login": author}}],
        },
    })


def evaluate(*, reviews=None, check_lines=None, threads=None, comments=None):
    return validate_required_bot_review_or_fallback(
        reviews if reviews is not None else [review()],
        BOT, HEAD,
        comment_lines=comments if comments is not None else [],
        check_lines=check_lines if check_lines is not None else checks(),
        thread_lines=threads if threads is not None else [thread(resolved=True)],
        phase_file=None,
    )


class PoliticaComentarioSeguridadTests(unittest.TestCase):
    def test_comment_writer_requires_canonical_exact_head_and_threads(self):
        """AC-01: lectura real de seis gates, review threads y ref final."""
        self.assertIn("--checks-file \"$CHECKS_FILE\"", WORKFLOW)
        # La evidencia no sirve si el workflow ejecuta un motor @v1
        # que retorna en el positivo antes de aplicar los vetos.
        self.assertIn(
            "ref: b0713650194e9a0c464d625bc6136eecad776377", WORKFLOW)
        self.assertNotIn("ref: v1", WORKFLOW)
        source = (ROOT / "scripts/politica_kit.py").read_bytes()
        git_blob = b"blob " + str(len(source)).encode("ascii") + b"\0" + source
        self.assertEqual(
            hashlib.sha1(git_blob).hexdigest(),
            "0e39726bb61ccb500e0a2365e49e1030beb48724",
        )
        self.assertIn("--threads-file \"$THREADS_FILE\"", WORKFLOW)
        self.assertIn("check-runs?per_page=100", WORKFLOW)
        self.assertIn("reviewThreads(first:100)", WORKFLOW)
        self.assertIn("pageInfo.hasNextPage", WORKFLOW)
        self.assertIn("POLICY_COMMENT_EVIDENCE_BEGIN", WORKFLOW)
        self.assertIn("POLICY_COMMENT_EVIDENCE_END", WORKFLOW)
        self.assertIn("PR_JSON_FINAL=", WORKFLOW)
        self.assertIn('"$FINAL_HEAD" != "$PR_HEAD_SHA"', WORKFLOW)
        self.assertEqual(evaluate(), {"review_fallback": False})
        with self.assertRaises(PolicyError):
            evaluate(check_lines=checks(bad=12, conclusion="failure"))
        with self.assertRaises(PolicyError):
            evaluate(check_lines=checks(bad=12, conclusion="pending"))
        with self.assertRaises(PolicyError):
            evaluate(check_lines=checks()[:-1])

    def test_commented_then_changes_requested_must_fail(self):
        """AC-02: el último review negativo exact-HEAD veta uno anterior."""
        with self.assertRaises(PolicyError):
            evaluate(reviews=[
                review(number=41),
                review(state="CHANGES_REQUESTED", body="Cambios necesarios", number=42),
            ])
        # Un veto en otro commit no cuenta como autorización del HEAD nuevo.
        with self.assertRaises(PolicyError):
            evaluate(reviews=[review(sha="b" * 40)])

    def test_rate_limited_comment_and_open_thread_each_fail(self):
        """AC-03: rate-limit no es review sustantiva ni cobertura terminal."""
        for message in ("Review rate limited", "Review limit reached"):
            with self.subTest(message=message):
                with self.assertRaises(PolicyError):
                    evaluate(reviews=[review(body=message)])
                coverage = (
                    '<!-- final_review_risk_coverage:'
                    + json.dumps({
                        "kind": "reviewed", "sourceCommitId": HEAD,
                        "coveredCommitId": HEAD,
                    }) + ' -->'
                )
                comment = json.dumps({
                    "id": 99, "body": message + "\n" + coverage,
                    "user": {"type": "Bot", "login": BOT},
                })
                with self.assertRaises(PolicyError):
                    evaluate(reviews=[], comments=[comment])
        with self.assertRaises(PolicyError):
            evaluate(threads=[thread(resolved=False)])

    def test_graphql_fail_closed_and_identity_ref_revalidation(self):
        """AC-04: sin evidencia parcial, sin checkout consumidor o write ajeno."""
        self.assertIn("gh api graphql", WORKFLOW)
        self.assertIn("(.errors // []) | length == 0", WORKFLOW)
        self.assertIn(".reviewThreads.pageInfo.hasNextPage == false", WORKFLOW)
        self.assertIn("all(. == false)", WORKFLOW)
        self.assertIn("check-runs sin dos snapshots completos", WORKFLOW)
        self.assertIn("MAX_PUBLIC_CHECKS", WORKFLOW)
        self.assertIn("IDs de checks duplicados", WORKFLOW)
        self.assertIn('"$FINAL_BASE" != "$PR_BASE_SHA"', WORKFLOW)
        self.assertIn('"$FINAL_HEAD_REPO" != "$PR_HEAD_REPO"', WORKFLOW)
        self.assertIn('"$FINAL_BASE_REPO" != "$PR_BASE_REPO"', WORKFLOW)
        self.assertIn('[[ "$EVENT_NAME" == "issue_comment" ]]', WORKFLOW)
        self.assertIn('[[ "$COMMENT_API_ID" == "$INPUT_COMMENT" ]]', WORKFLOW)
        self.assertIn("persist-credentials: false", WORKFLOW)
        self.assertIn("repository: pl0n3r/factory", WORKFLOW)
        self.assertNotIn("issues: write", WORKFLOW)
        self.assertNotIn("pull-requests: write", WORKFLOW)
        self.assertNotIn("checkout@v", WORKFLOW)
        self.assertEqual(evaluate(), {"review_fallback": False})
        # Un thread parcial jamás se trata como ausencia de findings.
        with self.assertRaises(PolicyError):
            evaluate(threads=[json.dumps({
                "isResolved": False,
                "comments": {
                    "pageInfo": {"hasNextPage": True},
                    "nodes": [{"author": {"login": "coderabbitai"}}],
                },
            })])


if __name__ == "__main__":
    unittest.main()
