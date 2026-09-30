import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sonar_watch", ROOT / "scripts" / "sonar-watch.py"
)
sonar_watch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sonar_watch)

NOW = "2026-09-30T12:00:00Z"


def contract(project="factory"):
    return {
        "version": 1,
        "project": project,
        "surfaces": [{
            "id": "admin",
            "criticality": "critical",
            "required_gates": ["unit"],
        }],
        "invariants": ["authorization"],
        "compatibility": {
            "runtimes": ["python-3"],
            "browsers": [],
            "devices": [],
        },
        "accessibility": {"target": "NOT_APPLICABLE"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": False, "source_ref": None},
        "evidence_freshness_seconds": 3600,
        "dimensions": {
            "performance": {"required": False, "source_ref": None},
            "recovery": {"required": False, "source_ref": None},
        },
        "sonar": {
            "expected_visibility": "public",
            "analysis_method": "ci",
            "max_analysis_age_seconds": 86400,
            "max_organization_line_usage_percent": 80,
            "max_open_vulnerabilities": 0,
            "max_open_bugs": 0,
            "max_open_hotspots": 0,
            "max_debt_age_days": 30,
        },
    }


def snapshot(project="factory"):
    return {
        "project": project,
        "snapshot_at": "2026-09-30T11:55:00Z",
        "quality_gate": {"status": "OK", "conditions": []},
        "analysis": {
            "analyzed_at": "2026-09-30T11:50:00Z",
            "method": "ci",
            "coverage_available": True,
        },
        "ce_task": {"status": "SUCCESS", "error_message": None},
        "organization": {"line_usage_percent": 50},
        "visibility": "public",
        "debt": [],
        "evidence_refs": [f"sonar:{project}:snapshot:001"],
    }


class FakeIssues:
    def __init__(self):
        self.rows = []
        self.next_number = 1
        self.calls = []

    def find(self, marker):
        return [
            row.copy()
            for row in self.rows
            if marker in row["body"]
        ]

    def create(self, *, title, body):
        row = {
            "number": self.next_number,
            "title": title,
            "body": body,
            "state": "open",
        }
        self.next_number += 1
        self.rows.append(row)
        self.calls.append(("create", row["number"]))

    def update(self, number, *, title, body, state):
        row = next(
            item for item in self.rows
            if item["number"] == number
        )
        row.update({
            "title": title,
            "body": body,
            "state": state,
        })
        self.calls.append(("update", number, state))


def sync(raw, api):
    project = raw["project"]
    refs = {
        "factory": "pl0n3r/Factory",
        "brvtal": "pl0n3r/brvtal",
        "condor": "pl0n3r/Condor",
        "controlbot": "pl0n3r/ControlBot",
        "factoryrunner": "pl0n3r/FactoryRunner",
        "grindflow": "pl0n3r/GrindFlow",
    }
    return sonar_watch.sync_project(
        contract=contract(project),
        snapshot=raw,
        observed_at=NOW,
        project_ref=refs[project],
        origin_ref=f"sonar:{project}",
        origin_url=f"https://sonarcloud.io/project/overview?id={project}",
        issues=api,
    )


class SonarWatchTests(unittest.TestCase):
    def test_workflow_is_scheduled_manual_and_minimum_privilege(self):
        text = (
            ROOT / ".github" / "workflows" / "sonar-watch.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn(
            "permissions:\n  contents: read\n\nconcurrency:",
            text,
        )
        self.assertIn(
            "    permissions:\n      contents: read\n      issues: write",
            text,
        )
        for forbidden in (
            "contents: write",
            "actions: write",
            "deployments: write",
            "packages: write",
            "pull-requests: write",
            "secrets: inherit",
            "SONAR_TOKEN",
            "SONAR_WATCH_CONFIG_JSON",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("schedule|workflow_dispatch", text)
        self.assertIn('refs/heads/$DEFAULT_BRANCH', text)
        self.assertIn("timeout-minutes: 10", text)
        self.assertIn("cancel-in-progress: false", text)
        first_checkout = text.index("uses: actions/checkout@")
        self.assertLess(text.index("Validar contexto confiable"), first_checkout)
        self.assertLess(text.index('refs/heads/$DEFAULT_BRANCH'), first_checkout)
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            text,
        )
        self.assertIn("python3 scripts/sonar-watch.py", text)

    def test_non_pass_signal_upserts_one_issue_by_project_and_signal(self):
        api = FakeIssues()
        raw = snapshot()
        raw["visibility"] = "private"

        first = sync(raw, api)
        second = sync(raw, api)

        marker = sonar_watch.issue_marker("factory", "visibility")
        matches = api.find(marker)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["state"], "open")
        self.assertEqual(
            [x["action"] for x in first if x["signal"] == "visibility"],
            ["created"],
        )
        self.assertEqual(
            [x["action"] for x in second if x["signal"] == "visibility"],
            ["updated"],
        )
        self.assertIn("https://sonarcloud.io/project/overview", matches[0]["body"])

        github = sonar_watch.GitHubIssues(
            repository="pl0n3r/Factory",
            token="github-token",
        )
        captured = []

        def fake_request(path, **kwargs):
            captured.append((path, kwargs))
            return {}

        github.http.request = fake_request
        github.create(title="auto", body="body")
        github.update(1, title="auto", body="body", state="closed")
        self.assertEqual(
            captured[0][1]["payload"]["labels"],
            list(sonar_watch._AUTO_OPEN_LABELS),
        )
        self.assertEqual(
            captured[1][1]["payload"]["labels"],
            list(sonar_watch._AUTO_CLOSED_LABELS),
        )

        request_capture = {}
        original = sonar_watch.urlopen

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, limit):
                return b"{}"

        def fake_urlopen(request, timeout):
            request_capture["method"] = request.get_method()
            request_capture["content_type"] = request.get_header("Content-type")
            return Response()

        sonar_watch.urlopen = fake_urlopen
        try:
            client = sonar_watch.HttpJson(
                token="token",
                base_url="https://api.github.test",
            )
            client.request(
                "/repos/pl0n3r/factory/issues",
                method="POST",
                payload={"title": "x", "body": "y"},
            )
        finally:
            sonar_watch.urlopen = original

        self.assertEqual(request_capture["method"], "POST")
        self.assertEqual(
            request_capture["content_type"],
            "application/json",
        )

    def test_issue_body_contains_concrete_quality_gate_and_ce_failure_evidence(self):
        api = FakeIssues()
        raw = snapshot()
        raw["quality_gate"] = {
            "status": "ERROR",
            "conditions": [{
                "metric": "new_reliability_rating",
                "status": "ERROR",
                "actual": "3",
                "threshold": "1",
            }],
        }
        raw["ce_task"] = {
            "status": "FAILED",
            "error_message": "Organization line limit exceeded at 50000 lines",
        }

        sync(raw, api)

        qg = api.find(
            sonar_watch.issue_marker("factory", "quality_gate")
        )[0]["body"]
        ce = api.find(
            sonar_watch.issue_marker("factory", "ce_task")
        )[0]["body"]
        self.assertIn("new_reliability_rating", qg)
        self.assertIn("actual=`3`", qg)
        self.assertIn("threshold=`1`", qg)
        self.assertIn("Organization line limit exceeded", ce)

        runtime = sonar_watch._snapshot_from_api(
            "factory",
            NOW,
            {"projectStatus": {"status": "OK", "conditions": []}},
            {"analyses": [{"date": "2026-09-30T11:50:00Z"}]},
            {"current": {
                "status": "SUCCESS",
                "errorMessage": None,
                "submitterLogin": "ci-user",
            }},
            {"component": {"measures": [{
                "metric": "coverage",
                "value": "80",
            }]}},
            {"component": {"visibility": "public"}},
            {"issues": []},
            {"hotspots": []},
        )
        self.assertEqual(runtime["analysis"]["method"], "ci")
        self.assertIsNone(runtime["organization"])
        evidence = sonar_watch.normalize_sonar_snapshot(
            contract(),
            runtime,
            observed_at=NOW,
        )
        organization = next(
            item
            for item in evidence["signals"]
            if item["signal"] == "organization_line_usage"
        )
        self.assertEqual(organization["status"], "UNKNOWN")

        automatic = sonar_watch._snapshot_from_api(
            "factory",
            NOW,
            {"projectStatus": {"status": "OK", "conditions": []}},
            {"analyses": [{"date": "2026-09-30T11:50:00Z"}]},
            {"current": {"status": "SUCCESS", "errorMessage": None}},
            {"component": {"measures": []}},
            {"component": {"visibility": "public"}},
            {"issues": []},
            {"hotspots": []},
        )
        self.assertEqual(automatic["analysis"]["method"], "automatic")

    def test_historical_debt_is_grouped_by_severity(self):
        api = FakeIssues()
        raw = snapshot()
        raw["debt"] = [
            {
                "type": "bug",
                "severity": "MAJOR",
                "opened_at": "2026-09-29T12:00:00Z",
                "evidence_ref": "sonar:factory:bug:1",
            },
            {
                "type": "bug",
                "severity": "MAJOR",
                "opened_at": "2026-09-28T12:00:00Z",
                "evidence_ref": "sonar:factory:bug:2",
            },
        ]

        sync(raw, api)
        body = api.find(
            sonar_watch.issue_marker("factory", "historical_debt")
        )[0]["body"]
        self.assertIn("bug/MAJOR", body)
        self.assertIn("2 abiertos", body)
        self.assertIn("bug:2>0", body)

        sonar = sonar_watch.SonarApi()
        calls = []

        def paged_get(path, params):
            calls.append((path, params["p"]))
            if params["p"] == 1:
                return {
                    "issues": [{"key": f"i-{index}"} for index in range(500)],
                    "paging": {
                        "pageIndex": 1, "pageSize": 500, "total": 502,
                    },
                }
            return {
                "issues": [{"key": "i-500"}, {"key": "i-501"}],
                "paging": {
                    "pageIndex": 2, "pageSize": 500, "total": 502,
                },
            }

        sonar.get = paged_get
        page = sonar._all_issues("project-key")
        self.assertEqual(len(page["issues"]), 502)
        self.assertEqual(
            calls,
            [("/api/issues/search", 1), ("/api/issues/search", 2)],
        )

        hotspot_calls = []

        def hotspot_get(path, params):
            hotspot_calls.append((path, params))
            return {
                "hotspots": [{
                    "key": "hs-1",
                    "status": "TO_REVIEW",
                    "vulnerabilityProbability": "HIGH",
                    "creationDate": "2026-09-20T12:00:00Z",
                }],
                "paging": {
                    "pageIndex": 1, "pageSize": 500, "total": 1,
                },
            }

        sonar.get = hotspot_get
        hotspots = sonar._all_hotspots("project-key")
        self.assertEqual(len(hotspots["hotspots"]), 1)
        self.assertEqual(
            hotspot_calls[0][0],
            "/api/hotspots/search",
        )
        self.assertEqual(
            hotspot_calls[0][1]["status"],
            "TO_REVIEW",
        )

        runtime = sonar_watch._snapshot_from_api(
            "factory",
            NOW,
            {"projectStatus": {"status": "OK", "conditions": []}},
            {"analyses": [{"date": "2026-09-30T11:50:00Z"}]},
            {"current": {
                "status": "SUCCESS",
                "errorMessage": None,
                "submitterLogin": "ci-user",
            }},
            {"component": {"measures": [{"metric": "coverage", "value": "80"}]}},
            {"component": {"visibility": "public"}},
            {"issues": []},
            hotspots,
        )
        runtime["organization"] = {"line_usage_percent": 50}
        evidence = sonar_watch.normalize_sonar_snapshot(
            contract(),
            runtime,
            observed_at=NOW,
        )
        debt_signal = next(
            item
            for item in evidence["signals"]
            if item["signal"] == "historical_debt"
        )
        self.assertEqual(debt_signal["status"], "FAIL")
        self.assertIn(
            "hotspot:1>0",
            debt_signal["details"]["exceeded"],
        )

    def test_current_pass_closes_only_matching_auto_issue(self):
        api = FakeIssues()
        failing = snapshot()
        failing["quality_gate"] = {
            "status": "ERROR",
            "conditions": [{
                "metric": "new_security_rating",
                "status": "ERROR",
                "actual": "2",
                "threshold": "1",
            }],
        }
        failing["ce_task"] = {
            "status": "FAILED",
            "error_message": "line limit exceeded",
        }
        sync(failing, api)

        recovering = snapshot()
        recovering["ce_task"] = {
            "status": "FAILED",
            "error_message": "line limit still exceeded",
        }
        sync(recovering, api)

        qg = api.find(
            sonar_watch.issue_marker("factory", "quality_gate")
        )[0]
        ce = api.find(
            sonar_watch.issue_marker("factory", "ce_task")
        )[0]
        self.assertEqual(qg["state"], "closed")
        self.assertEqual(ce["state"], "open")

    def test_retries_are_idempotent_under_duplicate_observation(self):
        api = FakeIssues()
        raw = snapshot()
        raw["organization"] = {"line_usage_percent": 95}

        for _ in range(3):
            sync(raw, api)

        marker = sonar_watch.issue_marker(
            "factory", "organization_line_usage"
        )
        self.assertEqual(len(api.find(marker)), 1)
        create_calls = [
            row for row in api.calls
            if row[0] == "create"
        ]
        self.assertEqual(len(create_calls), 1)

        api.rows.append({
            "number": 999,
            "title": "duplicate",
            "body": api.find(marker)[0]["body"],
            "state": "open",
        })
        with self.assertRaises(sonar_watch.SonarWatchError):
            sync(raw, api)

        github = sonar_watch.GitHubIssues(
            repository="pl0n3r/Factory",
            token="token",
        )
        page_calls = []

        def paged_request(path, **kwargs):
            page_calls.append(path)
            if path.endswith("page=1"):
                return [
                    {
                        "number": index + 1,
                        "title": f"issue-{index}",
                        "body": "",
                        "state": "open",
                        "user": {"login": "github-actions[bot]"},
                    }
                    for index in range(100)
                ]
            return [
                {
                    "number": 101,
                    "title": "spoofed",
                    "body": marker,
                    "state": "open",
                    "user": {"login": "external-user"},
                },
                {
                    "number": 102,
                    "title": "matching",
                    "body": marker,
                    "state": "open",
                    "user": {"login": "github-actions[bot]"},
                },
            ]

        github.http.request = paged_request
        found = github.find(marker)
        self.assertEqual([item["number"] for item in found], [102])
        self.assertEqual(len(page_calls), 2)

    def test_scenarios_use_fakes_without_network(self):
        original = sonar_watch.urlopen

        def no_network(*args, **kwargs):
            raise AssertionError(
                "network should not be used in unit scenarios"
            )

        sonar_watch.urlopen = no_network
        try:
            api = FakeIssues()
            raw = snapshot()
            raw["analysis"]["coverage_available"] = False
            result = sync(raw, api)
        finally:
            sonar_watch.urlopen = original

        self.assertTrue(result)
        self.assertTrue(api.rows)

        expected = set(sonar_watch.factory_project_catalog())
        configured = {row["project"] for row in sonar_watch._PROJECTS}
        self.assertEqual(configured, expected)
        self.assertEqual(len(sonar_watch._PROJECTS), 6)
        keys = {row["sonar_key"] for row in sonar_watch._PROJECTS}
        self.assertEqual(keys, {
            "pl0n3r_brvtal",
            "pl0n3r_Condor",
            "pl0n3r_factory-control",
            "pl0n3r_factory",
            "pl0n3r_FactoryRunner",
            "pl0n3r_GrindFlow",
        })
        methods = {
            row["project"]: sonar_watch.project_contract(row)["sonar"]["analysis_method"]
            for row in sonar_watch._PROJECTS
        }
        self.assertEqual(methods["controlbot"], "ci")
        self.assertTrue(
            all(
                method == "automatic"
                for project, method in methods.items()
                if project != "controlbot"
            )
        )


if __name__ == "__main__":
    unittest.main()
