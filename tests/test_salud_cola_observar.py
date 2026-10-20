"""QA offline del observador GET-only de salud de cola Factory."""
from pathlib import Path
import unittest

from scripts.salud_cola_observar import ObservationError, REPO, observe

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
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("GITHUB_TOKEN: ${{ secrets.", workflow)
        self.assertIn('method="GET"', source)
        self.assertNotIn('method="POST"', source)
        self.assertNotIn('method="PATCH"', source)


if __name__ == "__main__":
    unittest.main()
