"""QA offline del observador GET-only de salud de cola Factory."""
from pathlib import Path
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from scripts.salud_cola_observar import (
    MAX_RESPONSE_BYTES, ObservationError, REPO, github_get_json, main, observe,
)

ROOT = Path(__file__).resolve().parents[1]


class SaludColaObservadorTests(unittest.TestCase):
    def test_bounded_local_issue_inventory_does_not_write(self):
        calls = []
        def get(path):
            calls.append(path)
            if path == "/rate_limit":
                return {"resources": {"core": {"limit": 5000, "remaining": 5000}}}
            if path.endswith("page=1"):
                return [
                    {"number": n, "labels": [{"name": "estado: disponible"}]}
                    for n in range(1, 100)
                ] + [{"number": 500, "pull_request": {}}]
            if path.endswith("page=2"):
                return [{"number": 100, "labels": [{"name": "estado: bloqueado"}]}]
            self.fail("unexpected endpoint")
        report = observe(get)
        self.assertEqual(report["status"], "OBSERVED_LOCAL_ONLY")
        self.assertEqual(report["counts"]["available"], 99)
        self.assertEqual(report["counts"]["blocked"], 1)
        self.assertEqual(report["excluded_prs"], 1)
        self.assertEqual(report["issues"], 100)
        self.assertEqual(report["pages"], 2)
        self.assertEqual(report["writes"], 0)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(path == "/rate_limit" or path.startswith(f"/repos/{REPO}/issues?") for path in calls))

        def incomplete(path):
            if path == "/rate_limit":
                return {"resources": {"core": {"limit": 5000, "remaining": 5000}}}
            page = int(path.rsplit("=", 1)[-1])
            return [{"number": n, "labels": [{"name": "estado: disponible"}]}
                    for n in range(1 + (page - 1) * 100, 101 + (page - 1) * 100)]
        with self.assertRaisesRegex(ObservationError, "pagination_incomplete"):
            observe(incomplete)

    def test_low_quota_defers_and_unknown_never_green(self):
        def budget_only(path):
            self.assertEqual(path, "/rate_limit")
            return {"resources": {"core": {"limit": 100, "remaining": 19}}}
        deferred = observe(budget_only)
        self.assertEqual(deferred["status"], "DEFERRED_LOW_QUOTA")
        self.assertEqual(deferred["writes"], 0)
        self.assertNotIn("counts", deferred)

        def ambiguous(path):
            if path == "/rate_limit":
                return {"resources": {"core": {"limit": 100, "remaining": 100}}}
            return [{"number": 1, "labels": []}]
        report = observe(ambiguous)
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["undecidable"], 1)
        self.assertEqual(report["counts"]["available"], 0)
        with self.assertRaises(ObservationError):
            observe(lambda path: {"resources": {"core": {"limit": 100, "remaining": True}}})

    def test_workflow_has_read_only_permissions(self):
        workflow = (ROOT / ".github/workflows/salud-cola.yml").read_text(encoding="utf-8")
        source = (ROOT / "scripts/salud_cola_observar.py").read_text(encoding="utf-8")
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("issues: read", workflow)
        self.assertIn("contents: read", workflow)
        # El job observador y el permiso global permanecen GET-only.
        # Una hoja distinta autorizada puede añadir publicador opt-in.
        observer, marker, publisher = workflow.partition("\n  publicar:\n")
        self.assertNotIn("issues: write", observer)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("GITHUB_TOKEN: ${{ secrets.", workflow)
        if marker:
            self.assertIn("issues: write", publisher)
            self.assertIn("default: false", observer)
            self.assertIn("inputs.publicar == true", publisher)
        self.assertIn('method="GET"', source)
        self.assertNotIn('method="POST"', source)
        self.assertNotIn('method="PATCH"', source)


    def test_bad_quota_pages_and_duplicate_issues_fail_closed(self):
        good_budget = {"resources": {"core": {"limit": 100, "remaining": 100}}}
        for invalid in (None, [], {}, {"resources": []},
                        {"resources": {}}, {"resources": {"core": []}}):
            with self.subTest(quota=repr(invalid)):
                with self.assertRaises(ObservationError):
                    observe(lambda path, payload=invalid: payload)

        for core in ({"limit": 0, "remaining": 0},
                     {"limit": 100, "remaining": -1},
                     {"limit": 100, "remaining": 101},
                     {"limit": True, "remaining": 99},
                     {"limit": 100, "remaining": "100"}):
            with self.subTest(core=core):
                with self.assertRaises(ObservationError):
                    observe(lambda path, item=core: {
                        "resources": {"core": item}
                    })

        variants = (
            {"items": {}},
            {"items": [None]},
            {"items": [{"number": 1}]},
            {"items": [{"number": True, "labels": []}]},
            {"items": [{"number": 0, "labels": []}]},
            {"items": [{"number": 1, "labels": [{"name": None}]}]},
            {"items": [{"number": 1, "labels": []}] * 2},
            {"items": [{"number": n, "labels": []} for n in range(1, 102)]},
        )
        for case in variants:
            def source(path):
                return good_budget if path == "/rate_limit" else case["items"]
            with self.subTest(items=str(case["items"])[:80]):
                with self.assertRaises(ObservationError):
                    observe(source)

        states = (
            "estado: disponible", "estado: reservado", "estado: bloqueado",
            "estado: planificado", "estado: en revisión",
            "estado: requiere recuperación",
        )
        def classify(path):
            if path == "/rate_limit":
                return good_budget
            return [{"number": n, "labels": [{"name": label}]}
                    for n, label in enumerate(states, start=1)]
        report = observe(classify)
        self.assertEqual(report["issues"], len(states))
        self.assertEqual(set(report["counts"].values()), {1})
        self.assertEqual(report["status"], "OBSERVED_LOCAL_ONLY")

    def test_authenticated_get_rejects_unsafe_paths_and_bad_responses(self):
        class Response:
            def __init__(self, status, raw):
                self.status = status
                self.raw = raw

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, length):
                self.read_limit = length
                return self.raw

        for path in ("/repos/pl0n3r/Factory/issues", "/user",
                     "https://other.test/", "/rate_limit?extra=1"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ObservationError, "endpoint_forbidden"):
                    github_get_json(path)

        with patch.dict(os.environ, {"GITHUB_TOKEN": "",
                                    "GITHUB_REPOSITORY": REPO}):
            with self.assertRaisesRegex(ObservationError, "local_authority_missing"):
                github_get_json("/rate_limit")

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-only-not-real",
                                    "GITHUB_REPOSITORY": "not-local"}):
            with self.assertRaisesRegex(ObservationError, "local_authority_missing"):
                github_get_json("/rate_limit")

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-only-not-real",
                                    "GITHUB_REPOSITORY": REPO}):
            response = Response(200, b'{"resources":{}}')
            with patch("scripts.salud_cola_observar.urlopen",
                       return_value=response) as opened:
                self.assertEqual(github_get_json("/rate_limit"), {"resources": {}})
                request = opened.call_args.args[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(request.full_url, "https://api.github.com/rate_limit")
                self.assertEqual(opened.call_args.kwargs["timeout"], 15)
                self.assertEqual(response.read_limit, MAX_RESPONSE_BYTES + 1)

            for status, raw, label in (
                (403, b"{}", "http_non_200"),
                (200, b"x" * (MAX_RESPONSE_BYTES + 1), "payload_oversized"),
            ):
                with self.subTest(label=label):
                    with patch("scripts.salud_cola_observar.urlopen",
                               return_value=Response(status, raw)):
                        with self.assertRaisesRegex(ObservationError, label):
                            github_get_json("/rate_limit")

            with patch("scripts.salud_cola_observar.urlopen",
                       return_value=Response(200, b"not valid json")):
                with self.assertRaises(ValueError):
                    github_get_json("/rate_limit")

    def test_cli_help_unknown_and_sanitized_summary_without_network(self):
        with patch.object(sys, "argv", ["queue.py", "--help"]):
            with patch("scripts.salud_cola_observar.urlopen",
                       side_effect=AssertionError("network forbidden")):
                with redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main(), 0)
                    self.assertIn("GET-only", output.getvalue())

        with patch.object(sys, "argv", ["queue.py", "--unknown"]):
            with redirect_stderr(io.StringIO()) as output:
                self.assertEqual(main(), 2)
                self.assertIn("no reconocidos", output.getvalue())

        with tempfile.TemporaryDirectory() as dirname:
            summary_path = Path(dirname) / "summary.md"
            with patch.object(sys, "argv", ["queue.py"]):
                with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_path)}):
                    report = {"status": "OBSERVED_LOCAL_ONLY", "scope": REPO, "writes": 0}
                    with patch("scripts.salud_cola_observar.observe",
                               return_value=report) as reader:
                        with redirect_stdout(io.StringIO()) as output:
                            self.assertEqual(main(), 0)
                            self.assertEqual(json.loads(output.getvalue()), report)
                        reader.assert_called_once()
                    content = summary_path.read_text(encoding="utf-8")
                    self.assertIn("OBSERVED_LOCAL_ONLY", content)
                    self.assertIn("No concede reservas", content)
                    self.assertNotIn("GITHUB_TOKEN", content)

                    with patch("scripts.salud_cola_observar.observe",
                               side_effect=ObservationError("fail closed")):
                        with redirect_stdout(io.StringIO()) as output:
                            self.assertEqual(main(), 2)
                            self.assertEqual(json.loads(output.getvalue())["status"],
                                             "UNKNOWN")
                    self.assertIn("UNKNOWN", summary_path.read_text(encoding="utf-8"))



if __name__ == "__main__":
    unittest.main()
