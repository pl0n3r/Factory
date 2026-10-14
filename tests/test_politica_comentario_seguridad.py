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
        # El workflow de comentario usa un motor fijado en un commit histórico.
        # Solo el nuevo gate CLI (helper + invocación) puede diferir de ese
        # motor; toda alteración adicional vuelve a invalidar la huella.
        source = (ROOT / "scripts/politica_kit.py").read_text(encoding="utf-8")
        phase_helper = (
            'def validate_rounds_for_phase(rounds: int, limit: int, phase_file: Path | None) -> None:\n'
            '    """Rondas informativas solo si datos.yml base acredita construccion.\n'
            '\n'
            '    Fase ausente conserva el veto historico. Fase invalida falla cerrado.\n'
            '    El caller obtiene datos.yml desde BASE autenticada, no del HEAD del PR.\n'
            '    """\n'
            '    if load_phase(phase_file) != "construccion":\n'
            '        validate_rounds(rounds, limit)\n\n\n'
        )
        phase_call = (
            '        validate_rounds_for_phase(\n'
            '            rounds,\n'
            '            policy["review_round_limit"],\n'
            '            Path(options.phase_file) if options.phase_file else None,\n'
            '        )\n'
        )
        # El decisor F3C tiene su propia frontera explícita. Al comprobar
        # la huella del motor histórico se retira únicamente esa inserción,
        # nunca otro cambio del motor fijado del caller.
        risk_start = "# F3C_REVIEW_RISK_HELPER_BEGIN\n"
        risk_end = "# F3C_REVIEW_RISK_HELPER_END\n"
        self.assertEqual(source.count(risk_start), 1)
        self.assertEqual(source.count(risk_end), 1)
        risk_block = risk_start + source.split(risk_start, 1)[1].split(
            risk_end, 1
        )[0] + risk_end
        self.assertIn("validate_other_gates_green", risk_block)
        self.assertIn("_has_open_blocking_finding", risk_block)
        self.assertIn("factory-review-risk-summary", risk_block)
        self.assertIn('risk["analyzed"] is not True', risk_block)
        risk_call = (
            '    if phase == "construccion" and _verified_bot_risk_advisory(\n'
            '        comment_lines, check_lines, thread_lines,\n'
            '        required_review_bot=required_review_bot,\n'
            '        head_sha=head_sha,\n'
            '        head_committed_at=head_committed_at,\n'
            '        verified_status_lines=verified_status_lines or [],\n'
            '    ):\n'
            '        return {\n'
            '            "review_fallback": False,\n'
            '            "review_advisory": True,\n'
            '            "review_reason": "reviewer-bot-presence-only",\n'
            '            "risk_status": "clear",\n'
            '        }\n'
        )
        self.assertEqual(source.count(risk_call), 1)
        self.assertEqual(source.count(phase_helper), 1)
        self.assertEqual(source.count(phase_call), 1)
        # Normalizar únicamente el cableado CLI de status verificado de F3C;
        # el resto del motor histórico sigue bajo la huella fija.
        status_arg = '    parser.add_argument("--verified-status-file", default="")\n'
        status_read = (
            '        verified_status_lines = (\n'
            '            _read_bounded_lines(\n'
            '                Path(options.verified_status_file),\n'
            '                max_bytes=MAX_CHECKS_BYTES,\n'
            '                noun="estatus verificados de CodeRabbit",\n'
            '            )\n'
            '            if getattr(options, "verified_status_file", "")\n'
            '            else []\n'
            '        )\n'
        )
        status_forward = '            verified_status_lines=verified_status_lines,\n'
        for chunk in (status_arg, status_read, status_forward):
            self.assertEqual(source.count(chunk), 1)
        source = source.replace(status_arg, "", 1).replace(
            status_read, "", 1
        ).replace(status_forward, "", 1)
        pinned_source = source.replace(
            "\n" + risk_block + "\n", "", 1
        ).replace(
            risk_call, "", 1
        ).replace(
            "    verified_status_lines: list[str] | None = None,\n", "", 1
        ).replace(phase_helper, "", 1).replace(
            phase_call, '        validate_rounds(rounds, policy["review_round_limit"])\n', 1
        ).encode("utf-8")
        git_blob = b"blob " + str(len(pinned_source)).encode("ascii") + b"\0" + pinned_source
        self.assertEqual(
            hashlib.sha1(git_blob).hexdigest(),
            "b55d26779b822d1f619f1f637f790899440f8d40",
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
