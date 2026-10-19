"""Factory #1389 / D-070: reviewer sin cupo no bloquea si el resto de gates está verde sobre el HEAD exacto."""
import unittest

from scripts import politica_kit as policy
from scripts.politica_kit import (
    PolicyError,
    validate_required_bot_review_or_fallback,
)
from tests.test_politica_kit import (
    HEAD,
    check,
    green_gate_checks,
    rate_limit_comment,
    review,
    review_thread,
)

BOT = "coderabbitai[bot]"
COMMITTED = "2026-10-04T04:59:00Z"


def run(*, comments=None, checks=None, reviews=None, threads=None, flag=True, phase_file=None):
    return validate_required_bot_review_or_fallback(
        reviews if reviews is not None else [],
        BOT,
        HEAD,
        head_committed_at=COMMITTED,
        comment_lines=comments if comments is not None else [
            rate_limit_comment(comment_id=300, created_at="2026-10-04T05:00:00Z")],
        check_lines=checks if checks is not None else green_gate_checks(),
        thread_lines=threads if threads is not None else [],
        phase_file=phase_file,
        no_block_without_quota=flag,
    )


class PoliticaSinCupoTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.phase = Path(self._tmp.name) / "datos.yml"
        self.phase.write_text('{"phase": "construccion"}', encoding="utf-8")

    def test_rate_limited_does_not_block_when_sonar_codeql_and_validar_pass(self):
        result = run(phase_file=self.phase)
        self.assertTrue(result["review_fallback"])
        self.assertEqual(result["review_reason"], policy.NO_QUOTA_REASON)
        self.assertEqual(result["rate_limit_comment_id"], 300)

    def test_rate_limited_still_blocks_with_open_high_or_critical_finding(self):
        with self.assertRaises(PolicyError):
            run(phase_file=self.phase, threads=[review_thread(resolved=False)])
        with self.assertRaises(PolicyError):
            run(phase_file=self.phase,
                reviews=[review(state="CHANGES_REQUESTED", body="Bloquea")])

    def test_other_skips_unknown_or_stale_head_still_block(self):
        # sin evidencia de rate-limit (p. ej. skip por otra causa o UNKNOWN)
        with self.assertRaises(PolicyError):
            run(phase_file=self.phase, comments=[])
        # gates en rojo o sobre otro HEAD
        red = green_gate_checks() + [check(check_id=99, name="tests", conclusion="failure")]
        with self.assertRaises(PolicyError):
            run(phase_file=self.phase, checks=red)
        with self.assertRaises(PolicyError):
            run(phase_file=self.phase, checks=green_gate_checks(head_sha="b" * 40))
        # con la regla apagada (parámetro por defecto) se mantiene el comportamiento anterior
        with self.assertRaises(PolicyError):
            run(phase_file=self.phase, flag=False)
        # fuera de construccion nunca aplica
        live = self.phase.parent / "live.yml"
        live.write_text('{"phase": "live"}', encoding="utf-8")
        with self.assertRaises(PolicyError):
            run(phase_file=live)


if __name__ == "__main__":
    unittest.main()
