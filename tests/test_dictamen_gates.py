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


    def test_api_read_only_endpoint_and_authenticated_request(self):
        from scripts.dictamen_gates import _get_json, API
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit):
                self_limit = limit
                self.__class__.last_read_limit = self_limit
                return b'{"total_count": 0, "check_runs": []}'
        path = f"/repos/pl0n3r/Factory/commits/{SHA}/check-runs?per_page=100&page=1"
        with patch.dict("os.environ", {"GITHUB_TOKEN": "private-test-token"}):
            with patch("scripts.dictamen_gates.urlopen", return_value=Response()) as mocked:
                self.assertEqual(_get_json(path)["total_count"], 0)
                request = mocked.call_args.args[0]
                self.assertEqual(request.full_url, API + path)
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(request.get_header("Authorization"), "Bearer private-test-token")
                self.assertEqual(mocked.call_args.kwargs["timeout"], 15)
                self.assertEqual(Response.last_read_limit, 2_000_001)

    def test_api_rejects_untrusted_paths_and_response_shapes(self):
        from scripts.dictamen_gates import _get_json
        good = f"/repos/pl0n3r/Factory/commits/{SHA}/check-runs?per_page=100&page=1"
        for path in (
            good.replace("page=1", "page=0"),
            good.replace("page=1", "page=11"),
            good.replace("per_page=100", "per_page=200"),
            good.replace(SHA, "../issues/767"),
            good.replace("/check-runs", "/statuses"),
            good.replace("pl0n3r/Factory", "another/repo"),
        ):
            with self.subTest(path=path):
                with self.assertRaises(EvidenceError):
                    _get_json(path)

        class Response:
            def __init__(self, payload, status=200):
                self.payload, self.status = payload, status
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, _limit):
                return self.payload

        for payload, status in (
            (b'{"total_count":0}', 500),
            (b'not-json', 200),
            (b'[]', 200),
            (b'{"a":1,"a":2}', 200),
            (b'x' * 2_000_001, 200),
        ):
            with self.subTest(status=status, length=len(payload)):
                with patch("scripts.dictamen_gates.urlopen", return_value=Response(payload, status)):
                    with self.assertRaises(EvidenceError):
                        _get_json(good)
        with patch("scripts.dictamen_gates.urlopen", side_effect=OSError("token-secret")):
            with self.assertRaises(EvidenceError) as caught:
                _get_json(good)
            self.assertNotIn("token-secret", str(caught.exception))

    def test_rejects_collection_total_drift_and_bad_identifiers(self):
        rows = [run("unrelated " + str(i), id=i + 1) for i in range(100)]
        for bad in ({"total_count": 1, "check_runs": [{"id": 0}]},
                    {"total_count": 1, "check_runs": [{"id": True}]},
                    {"total_count": 1001, "check_runs": []},
                    {"total_count": True, "check_runs": []}):
            with self.subTest(bad=bad), self.assertRaises(EvidenceError):
                collect(SHA, lambda _path: bad)
        def drifting(path):
            if path.endswith("page=1"):
                return {"total_count": 101, "check_runs": rows}
            return {"total_count": 102, "check_runs": [run("last", id=101)]}
        with self.assertRaises(EvidenceError):
            collect(SHA, drifting)

    def test_cli_success_never_authorizes_release(self):
        with patch("scripts.dictamen_gates.verdict", return_value=evaluate(SHA, green())):
            output = io.StringIO()
            with redirect_stdout(output):
                rc = main(["--sha", SHA])
            self.assertEqual(rc, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], "GO")
            self.assertFalse(report["authorizes_release"])

if __name__ == "__main__":
    unittest.main()
