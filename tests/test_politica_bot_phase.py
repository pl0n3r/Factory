"""F3C: la ausencia de review solo es advisory con evidencia de riesgo del bot auténtica.

Las pruebas no hablan con GitHub ni usan datos de clientes.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import politica_kit

from scripts.politica_kit import PolicyError, validate_required_bot_review_or_fallback

HEAD = "a" * 40
BOT = "coderabbitai[bot]"
APP_IDS = {"github-actions": 15368, "sonarqubecloud": 12526,
           "github-advanced-security": 57789}
GATES = [
    ("validate", "github-actions"),
    ("SonarCloud Code Analysis", "sonarqubecloud"),
    ("CodeQL", "github-advanced-security"),
    ("tests", "github-actions"),
    ("validar-pr / Validar coordinación", "github-actions"),
    ("privacidad / Privacidad como código", "github-actions"),
]


def checks(*, bad=None, stale=False):
    return [
        json.dumps({
            "id": index + 50, "name": name,
            "head_sha": ("b" * 40 if stale and index == 2 else HEAD),
            "status": "completed",
            "conclusion": "failure" if bad == index else "success",
            "app": {"slug": app, "id": APP_IDS[app]},
        })
        for index, (name, app) in enumerate(GATES)
    ]


def attestation(*, author=BOT, user_type="Bot", head=HEAD, status="complete",
                high=0, critical=0, unknown=0, analyzed=True, duplicate=False,
                quoted=False):
    marker = json.dumps({
        "version": 1, "head_sha": head, "status": status,
        "analyzed": analyzed, "high": high, "critical": critical,
        "unknown": unknown,
    }, separators=(",", ":"))
    body = "<!-- factory-review-risk-summary " + marker + " -->"
    if duplicate:
        body += "\n" + body
    if quoted:
        body = "Quoted PR text, not a review: " + body
    return json.dumps({
        "id": 301, "user": {"type": user_type, "login": author},
        "body": body,
    })


def rate_limit_notice():
    return json.dumps({
        "id": 399, "user": {"type": "Bot", "login": BOT},
        "body": "Review rate limited for " + HEAD,
        "created_at": "2026-10-12T00:00:03Z",
    })


def status_receipt(*, description="Review completed", state="success",
                   sha=HEAD, creator="coderabbitai[bot]", creator_id=136622811,
                   creator_type="Bot",
                   updated="2026-10-12T00:00:05Z", total=1):
    # Fixture de la respuesta completa de GET /commits/<sha>/status.
    # En producción este dato NO lo proporciona el comentario del PR.
    return json.dumps({
        "sha": sha, "total_count": total,
        "statuses": [{
            "id": 56183871127, "context": "CodeRabbit", "state": state,
            "description": description,
            "creator": {"login": creator, "id": creator_id, "type": creator_type},
            "created_at": "2026-10-12T00:00:04Z", "updated_at": updated,
        }],
    })


def thread(*, resolved=True, login="coderabbitai"):
    return json.dumps({
        "isResolved": resolved,
        "comments": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [{"author": {"login": login}}],
        },
    })


def bot_review(*, state="CHANGES_REQUESTED"):
    return json.dumps({
        "id": 4, "state": state, "body": "finding", "commit_id": HEAD,
        "user": {"type": "Bot", "login": BOT},
    })


def evaluate(*, phase="construccion", comments=None, reviews=None,
             check_lines=None, threads=None, status_lines=None):
    with tempfile.TemporaryDirectory() as folder:
        phase_file = None
        if phase is not None:
            phase_file = Path(folder) / "datos.yml"
            phase_file.write_text(json.dumps({"phase": phase}), encoding="utf-8")
        return validate_required_bot_review_or_fallback(
            reviews if reviews is not None else [],
            BOT, HEAD, head_committed_at="2026-10-12T00:00:00Z",
            comment_lines=comments if comments is not None else [attestation()],
            check_lines=check_lines if check_lines is not None else checks(),
            thread_lines=threads if threads is not None else [thread()],
            phase_file=phase_file, run_attempt=1,
            verified_status_lines=(status_lines if status_lines is not None
                                   else [status_receipt()]),
        )


class PhaseReviewBotTests(unittest.TestCase):
    def test_cli_accepts_bounded_authenticated_status_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "status.jsonl"
            file.write_text(status_receipt() + "\n", encoding="utf-8")
            with patch("sys.argv", ["politica_kit.py", "--verified-status-file", str(file)]):
                options = politica_kit.args()
            self.assertEqual(options.verified_status_file, str(file))
            lines = politica_kit._read_bounded_lines(
                Path(options.verified_status_file),
                max_bytes=politica_kit.MAX_CHECKS_BYTES,
                noun="estatus verificados de CodeRabbit",
            )
            self.assertEqual(lines, [status_receipt()])
            with self.assertRaises(PolicyError):
                politica_kit._read_bounded_lines(
                    Path(options.verified_status_file), max_bytes=1,
                    noun="estatus verificados de CodeRabbit",
                )

    def test_construction_can_advisory_only_with_complete_trusted_security_evidence(self):
        report = evaluate()
        self.assertEqual(report["review_fallback"], False)
        self.assertEqual(report["review_advisory"], True)
        self.assertEqual(report["risk_status"], "clear")
        self.assertIn("review", report["review_reason"])
        self.assertNotIn("APPROVED", json.dumps(report))

    def test_missing_untrusted_or_serious_security_evidence_fails_closed(self):
        bad_cases = {
            "no-risk-proof": {"comments": []},
            "unverified-status-absent": {"status_lines": []},
            "skipped-draft-green": {"status_lines": [status_receipt(description="Review skipped: draft pull request")]},
            "review-rate-limited-green": {"status_lines": [status_receipt(description="Review rate limited")]},
            "status-wrong-sha": {"status_lines": [status_receipt(sha="b" * 40)]},
            "status-untrusted-app": {"status_lines": [status_receipt(creator="pl0n3r", creator_type="User")]},
            "status-spoofed-bot-id": {"status_lines": [status_receipt(creator_id=123)]},
            "status-human-creator": {"status_lines": [status_receipt(creator_type="User")]},
            "status-pending": {"status_lines": [status_receipt(state="pending")]},
            "status-before-commit": {"status_lines": [status_receipt(updated="2026-10-11T23:59:59Z")]},
            "status-pagination-truncated": {"status_lines": [status_receipt(total=2)]},
            "human-marker": {"comments": [attestation(author="pl0n3r", user_type="User")]},
            "stale-head": {"comments": [attestation(head="b" * 40)]},
            "skipped-analysis": {"comments": [attestation(status="skipped")]},
            "not-analyzed": {"comments": [attestation(analyzed=False)]},
            "unknown-severity": {"comments": [attestation(unknown=1)]},
            "high-finding": {"comments": [attestation(high=1)]},
            "critical-finding": {"comments": [attestation(critical=1)]},
            "duplicate-proof": {"comments": [attestation(duplicate=True)]},
            "quoted-marker": {"comments": [attestation(quoted=True)]},
            "post-head-rate-limit": {"comments": [attestation(), rate_limit_notice()]},
            "untrusted-check-head": {"check_lines": checks(stale=True)},
            "failed-sonar": {"check_lines": checks(bad=1)},
            "truncated-gates": {"check_lines": checks()[:-1]},
            "open-review-thread": {"threads": [thread(resolved=False)]},
            "changes-requested": {"reviews": [bot_review()]},
        }
        for label, kwargs in bad_cases.items():
            with self.subTest(label=label):
                with self.assertRaises(PolicyError):
                    evaluate(**kwargs)

    def test_live_missing_unknown_phase_stays_strict(self):
        for phase in ("live", None, "unknown"):
            with self.subTest(phase=phase):
                with self.assertRaises(PolicyError):
                    evaluate(phase=phase)
