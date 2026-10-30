"""Synthetic, no-network contract tests for the exact-SHA release-gate verdict."""
from __future__ import annotations

import io
import json
import re
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.dictamen_gates import CHECKS, ISSUERS, EvidenceError, collect, evaluate, main, verdict

SHA = "a" * 40
OTHER = "b" * 40


def run(name: str, *, id: int, status: str = "completed", conclusion: str = "success", sha: str = SHA):
    slug, app_id = ISSUERS.get(name, ("github-actions", 15368))
    return {"id": id, "name": name, "status": status, "conclusion": conclusion, "head_sha": sha,
            "app": {"slug": slug, "id": app_id}}


def green():
    return [run(name, id=i + 1) for i, name in enumerate(CHECKS)]


class DictamenGatesTests(unittest.TestCase):
    def test_criterio_principal(self):
        report = evaluate(SHA, green(), "2026-10-30 03:15:00 PM -05")
        self.assertEqual(report["status"], "GO")
        self.assertEqual(set(report["checks"]), set(CHECKS))
        self.assertFalse(report["authorizes_release"])
        self.assertRegex(report["checked_at_colombia"], r"03:15:00 PM")
        for name in CHECKS:
            self.assertEqual(report["checks"][name]["head_sha"], SHA)

    def test_no_go_for_every_non_success_or_incomplete_check(self):
        for bad_status, conclusion in (
            ("queued", None), ("in_progress", None), ("pending", None),
            ("completed", "skipped"), ("completed", "cancelled"),
            ("completed", "failure"), ("completed", None),
            ("completed", "neutral"), ("completed", "timed_out"),
            ("unknown", "success"),
        ):
            for gate in CHECKS:
                with self.subTest(status=bad_status, conclusion=conclusion, gate=gate):
                    rows = green()
                    for row in rows:
                        if row["name"] == gate:
                            row.update(status=bad_status, conclusion=conclusion)
                    self.assertEqual(evaluate(SHA, rows)["status"], "NO-GO")

    def test_missing_wrong_sha_ambiguous_and_newest_failure_fail_closed(self):
        self.assertEqual(evaluate(SHA, green()[:-1])["status"], "NO-GO")
        self.assertEqual(evaluate(SHA, green() + [run("CodeQL", id=5, sha=OTHER)])["status"], "NO-GO")
        self.assertEqual(evaluate(SHA, green() + [run("CodeQL", id=3)])["status"], "NO-GO")
        self.assertEqual(evaluate(SHA, green() + [run("CodeQL", id=10, conclusion="failure")])["status"], "NO-GO")
        self.assertEqual(evaluate("not-a-sha", green())["status"], "NO-GO")
        self.assertEqual(evaluate(SHA, {"fake": "list"})["status"], "NO-GO")
        self.assertEqual(evaluate(SHA, green() + [run("unrelated check", id=9, conclusion="skipped")])["status"], "GO")

    def test_spoofed_check_issuer_never_authorizes_release(self):
        for gate in CHECKS:
            with self.subTest(gate=gate):
                rows = green()
                target = next(item for item in rows if item["name"] == gate)
                target["app"] = {"slug": "attacker-app", "id": 999}
                self.assertEqual(evaluate(SHA, rows)["status"], "NO-GO")

    def test_pagination_exact_inventory(self):
        rows = [run("test-" + str(i), id=i + 1) for i in range(105)] + green()
        for i, item in enumerate(rows):
            item["id"] = i + 1
        calls = []
        def fake(path):
            calls.append(path)
            page = int(path.rsplit("=", 1)[1])
            return {"total_count": len(rows), "check_runs": rows[(page - 1) * 100:page * 100]}
        self.assertEqual(len(collect(SHA, fake)), len(rows))
        self.assertEqual(len(calls), 2)
        self.assertEqual(verdict(SHA, fake)["status"], "GO")

    def test_missing_truncated_changed_and_duplicate_pages_no_go(self):
        for page in (
            {"total_count": 3, "check_runs": green()[:-1]},
            {"total_count": -1, "check_runs": []},
            {"total_count": 3, "check_runs": [{"id": 1}] * 3},
            {"total_count": 3, "check_runs": "invalid"},
            {"check_runs": green()},
        ):
            with self.subTest(page=page), self.assertRaises(EvidenceError):
                collect(SHA, lambda path: page)
            self.assertEqual(verdict(SHA, lambda path: page)["status"], "NO-GO")

    def test_errors_do_not_leak_data_or_authorize_publication(self):
        report = verdict(SHA, lambda path: (_ for _ in ()).throw(EvidenceError("secret-token")))
        self.assertEqual(report["status"], "NO-GO")
        self.assertNotIn("secret-token", json.dumps(report))
        self.assertFalse(report["authorizes_release"])
        with patch("scripts.dictamen_gates.verdict", return_value=report):
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["--sha", SHA])
            self.assertEqual(rc, 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "NO-GO")

    def test_colombia_clock_is_12_hour(self):
        report = evaluate(SHA, green())
        self.assertRegex(report["checked_at_colombia"], r"\d{2}:\d{2}:\d{2} (?:AM|PM) (?:-05|COT)")

if __name__ == "__main__":
    unittest.main()
