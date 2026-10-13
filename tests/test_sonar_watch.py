import importlib.util
import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

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
        "surfaces": [
            {
                "id": "admin",
                "criticality": "critical",
                "required_gates": ["unit"],
            }
        ],
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
        self.comments = {}

    def find(self, marker):
        return [
            row.copy()
            for row in self.rows
            if marker in row["body"]
        ]

    def create(self, *, title, body, labels):
        row = {
            "number": self.next_number,
            "title": title,
            "body": body,
            "state": "open",
            "labels": list(labels),
        }
        self.next_number += 1
        self.rows.append(row)
        self.calls.append(("create", row["number"]))

    def update(self, number, *, title, body, state, labels):
        row = next(
            item for item in self.rows
            if item["number"] == number
        )
        row.update({
            "title": title,
            "body": body,
            "state": state,
            "labels": list(labels),
        })
        self.calls.append(("update", number, state))

    def comment(self, number, *, body):
        self.comments.setdefault(number, []).append(body)
        self.calls.append(("comment", number, body))

    def comment_once(self, number, *, marker, body):
        existing = self.comments.setdefault(number, [])
        if any(marker in item for item in existing):
            return False
        self.comment(number, body=body)
        return True

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
    def test_oversized_response_identifies_safe_endpoint_family(self):
        original = sonar_watch.urlopen

        class LargeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b"private-token-never-log=" + b"x" * 1_000_001

        sonar_watch.urlopen = lambda _request, timeout: LargeResponse()
        try:
            cases = [
                ("https://sonarcloud.io", "/api/issues/search?token=hidden", "sonar.issues"),
                ("https://sonarcloud.io", "/api/hotspots/search?token=hidden", "sonar.hotspots"),
                ("https://api.github.com", "/repos/pl0n3r/Factory/issues?secret=hidden", "github.issues"),
                ("https://example.invalid", "/my-private-path?secret=hidden", "remote.other"),
            ]
            for base_url, path, family in cases:
                with self.subTest(family=family):
                    client = sonar_watch.HttpJson(token="secret", base_url=base_url)
                    with self.assertRaises(sonar_watch.SonarWatchResponseTooLarge) as caught:
                        client.request(path)
                    message = str(caught.exception)
                    self.assertIn("respuesta remota excede tamaño máximo", message)
                    self.assertIn("source=" + family, message)
                    for forbidden in ("private-token", "secret=hidden", "token=hidden", "my-private-path"):
                        self.assertNotIn(forbidden, message)
        finally:
            sonar_watch.urlopen = original

    def test_bounded_sonar_paging_preserves_all_rows_over_one_mb(self):
        records = [
            {"key": f"issue-{index:04d}", "type": "BUG", "blob": "x" * 2200}
            for index in range(501)
        ]
        calls = []
        original = sonar_watch.urlopen

        class FakeResponse:
            def __init__(self, payload):
                self.payload = json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, limit):
                return self.payload[:limit]

        def fake_urlopen(request, timeout):
            query = parse_qs(urlsplit(request.full_url).query)
            size, page = int(query["ps"][0]), int(query["p"][0])
            calls.append((size, page))
            offset = (page - 1) * size
            return FakeResponse({
                "issues": records[offset:offset + size],
                "paging": {"pageIndex": page, "pageSize": size, "total": len(records)},
            })

        sonar_watch.urlopen = fake_urlopen
        try:
            response = sonar_watch.SonarApi(token="")._all_issues("project-key")
        finally:
            sonar_watch.urlopen = original
        self.assertEqual(
            [item["key"] for item in response["issues"]],
            [item["key"] for item in records],
        )
        self.assertEqual(calls, [(500, 1), (250, 1), (250, 2), (250, 3)])

    def test_unrecoverable_large_page_or_paging_drift_fails_closed(self):
        original = sonar_watch.urlopen
        calls = []

        class Oversized:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, limit):
                return b"x" * limit

        def oversize(request, timeout):
            calls.append(request.full_url)
            return Oversized()

        sonar_watch.urlopen = oversize
        try:
            with self.assertRaises(sonar_watch.SonarWatchResponseTooLarge):
                sonar_watch.SonarApi(token="")._all_issues("project-key")
        finally:
            sonar_watch.urlopen = original
        self.assertEqual(len(calls), 6)  # 500, 250, 125, 62, 31, 25

        sonar = sonar_watch.SonarApi(token="")

        def drift(_path, params):
            size, page = params["ps"], params["p"]
            return {
                "issues": [
                    {"key": f"k-{index}"}
                    for index in range((page - 1) * size, min(page * size, 501))
                ],
                "paging": {
                    "pageIndex": page, "pageSize": size,
                    "total": 501 if page == 1 else 502,
                },
            }

        sonar.get = drift
        with self.assertRaisesRegex(sonar_watch.SonarWatchError, "total Sonar cambió"):
            sonar._all_issues("project-key")

        def duplicated(_path, params):
            size, page = params["ps"], params["p"]
            if page == 1:
                rows = [{"key": f"k-{index}"} for index in range(size)]
            else:
                rows = [{"key": f"k-{size - 1}"}]
            return {
                "issues": rows,
                "paging": {"pageIndex": page, "pageSize": size, "total": size + 1},
            }

        sonar.get = duplicated
        with self.assertRaisesRegex(sonar_watch.SonarWatchError, "duplicada"):
            sonar._all_issues("project-key")

    def test_sonar_retries_preserve_total_and_previously_seen_identities(self):
        sonar = sonar_watch.SonarApi(token="")
        records = [{"key": f"original-{i:04d}"} for i in range(501)]
        for scenario in ("total_drift", "identity_replaced", "same_snapshot"):
            calls = []
            def fake_get(_path, params):
                size, page = params["ps"], params["p"]
                calls.append((size, page))
                if size == 500 and page == 2:
                    raise sonar_watch.SonarWatchResponseTooLarge(
                        "respuesta remota excede tamaño máximo. source=sonar.issues"
                    )
                if size == 500:
                    selected = records
                    total = len(records)
                elif scenario == "total_drift":
                    selected = records[:250]
                    total = 250
                elif scenario == "identity_replaced":
                    selected = [{"key": f"replacement-{i:04d}"} for i in range(501)]
                    total = 501
                else:
                    selected = records
                    total = len(records)
                offset = (page - 1) * size
                return {
                    "issues": selected[offset:offset + size],
                    "paging": {"pageIndex": page, "pageSize": size, "total": total},
                }

            with self.subTest(scenario=scenario):
                sonar.get = fake_get
                if scenario == "same_snapshot":
                    actual = sonar._all_issues("project-key")["issues"]
                    self.assertEqual(actual, records)
                else:
                    expected_error = (
                        "total Sonar cambió" if scenario == "total_drift"
                        else "identidades Sonar cambiaron"
                    )
                    with self.assertRaisesRegex(sonar_watch.SonarWatchError, expected_error):
                        sonar._all_issues("project-key")
                self.assertEqual(calls[:3], [(500, 1), (500, 2), (250, 1)])
                self.assertLessEqual(len(calls), 120)

    def test_sonar_paging_limits_total_requests_across_restarts(self):
        sonar = sonar_watch.SonarApi(token="")
        calls = []
        total = 2500

        def oversized_last_page(_path, params):
            size, page = params["ps"], params["p"]
            calls.append((size, page))
            offset = (page - 1) * size
            if offset <= total - 1 < offset + size:
                raise sonar_watch.SonarWatchResponseTooLarge(
                    "respuesta remota excede tamaño máximo. source=sonar.issues"
                )
            return {
                "issues": [
                    {"key": f"large-list-{index}"}
                    for index in range(offset, min(offset + size, total))
                ],
                "paging": {
                    "pageIndex": page,
                    "pageSize": size,
                    "total": total,
                },
            }

        sonar.get = oversized_last_page
        with self.assertRaisesRegex(
            sonar_watch.SonarWatchError, "presupuesto total de páginas Sonar"
        ):
            sonar._all_issues("project-key")
        self.assertEqual(len(calls), 120)
        self.assertEqual(calls[:6], [(500, 1), (500, 2), (500, 3), (500, 4), (500, 5), (250, 1)])
        self.assertIn((31, 1), calls)

    def test_sonar_rejects_incomplete_and_malformed_page_without_fake_green(self):
        sonar = sonar_watch.SonarApi(token="")
        cases = [
            (None, "paginación Sonar inválida"),
            ([], "paginación Sonar inválida"),
            ({"issues": "not-a-list", "paging": {}}, "paginación Sonar inválida"),
            ({"issues": [], "paging": {"pageIndex": 1, "pageSize": 500,
                                      "total": True}}, "paginación Sonar incoherente"),
            ({"issues": [{"key": "a"}], "paging": {"pageIndex": True,
             "pageSize": 500, "total": 1}}, "paginación Sonar incoherente"),
            ({"issues": [{"key": "a"}], "paging": {"pageIndex": 1.0,
             "pageSize": 500, "total": 1}}, "paginación Sonar incoherente"),
            ({"issues": [{"key": "a"}], "paging": {"pageIndex": 1,
             "pageSize": 500.0, "total": 1}}, "paginación Sonar incoherente"),
            ({"issues": [{"key": f"overflow-{i}"} for i in range(501)],
              "paging": {"pageIndex": 1, "pageSize": 500,
                         "total": 501}}, "paginación Sonar incoherente"),
            ({"issues": [], "paging": {"pageIndex": 2, "pageSize": 500,
                                      "total": 1}}, "paginación Sonar incoherente"),
            ({"issues": [], "paging": {"pageIndex": 1, "pageSize": 500,
                                      "total": 1}}, "Sonar truncó filas"),
            ({"issues": [{"key": ""}], "paging": {"pageIndex": 1,
                   "pageSize": 500, "total": 1}}, "identidad Sonar inválida"),
            ({"issues": [{"key": "a"}, {"key": "b"}],
              "paging": {"pageIndex": 1, "pageSize": 500,
                         "total": 1}}, "Sonar devolvió filas excedentes"),
        ]
        for payload, reason in cases:
            with self.subTest(reason=reason, payload=payload):
                sonar.get = lambda _path, _params, value=payload: value
                with self.assertRaisesRegex(sonar_watch.SonarWatchError, reason):
                    sonar._all_issues("project-key")

    def test_auto_alert_creation_has_canonical_labels_and_block_reason(self):
        api = FakeIssues()
        raw = snapshot()
        raw["visibility"] = "private"
        sync(raw, api)
        row = api.find(sonar_watch.issue_marker("factory", "visibility"))[0]
        self.assertEqual(
            row["labels"],
            ["tipo: calidad", "prioridad: media", "estado: bloqueado"],
        )
        self.assertIn("Motivo del bloqueo:", row["body"])
        self.assertIn("Condición de desbloqueo:", row["body"])
        self.assertIn("PASS/CURRENT", row["body"])

    def test_reconcile_unlabeled_auto_alert_without_duplicates(self):
        api = FakeIssues()
        raw = snapshot()
        raw["visibility"] = "private"
        marker = sonar_watch.issue_marker("factory", "visibility")
        api.rows.append({
            "number": 1, "title": "legacy", "body": marker,
            "state": "open", "labels": ["auditoría: conservar"],
        })
        api.next_number = 2
        sync(raw, api)
        sync(raw, api)
        rows = api.find(marker)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["labels"], [
            "tipo: calidad", "prioridad: media",
            "estado: bloqueado", "auditoría: conservar",
        ])
        self.assertFalse(any(call[0] == "create" for call in api.calls))
        api.rows[0]["labels"].append("estado: reservado")
        with self.assertRaisesRegex(sonar_watch.SonarWatchError, "clasificación ajena"):
            sync(raw, api)
        self.assertEqual(api.rows[0]["state"], "open")

    def test_terminal_signals_do_not_fake_readiness_or_pass(self):
        api = FakeIssues()
        failing = snapshot()
        failing["analysis"]["coverage_available"] = False
        sync(failing, api)
        sync(snapshot(), api)
        coverage = api.find(sonar_watch.issue_marker("factory", "coverage"))[0]
        self.assertEqual(coverage["state"], "closed")
        self.assertIn("estado: completado", coverage["labels"])
        self.assertNotIn("estado: disponible", coverage["labels"])

        configs = {
            row["project"]: row for row in sonar_watch.load_runtime_config()
        }
        cfg = configs["brvtal"]
        legacy = FakeIssues()
        marker = sonar_watch.issue_marker("brvtal", "coverage")
        legacy.rows.append({
            "number": 1, "title": "legacy", "body": marker + "\nSTALE",
            "state": "open",
        })
        legacy.next_number = 2
        raw = snapshot("brvtal")
        raw["analysis"]["method"] = "automatic"
        raw["analysis"]["coverage_available"] = False
        raw["organization"] = None
        sonar_watch.sync_project(
            contract=cfg["contract"], snapshot=raw, observed_at=NOW,
            project_ref=cfg["github_repo"], origin_ref="sonar:brvtal",
            origin_url=f"https://sonarcloud.io/project/overview?id={cfg['sonar_key']}",
            issues=legacy,
        )
        row = legacy.find(marker)[0]
        self.assertEqual(row["state"], "closed")
        self.assertIn("estado: completado", row["labels"])
        self.assertIn("STALE", row["body"])
        self.assertNotIn("PASS", row["body"])
        self.assertEqual(len(legacy.comments.get(1, [])), 1)
        self.assertIn("NOT_APPLICABLE", legacy.comments[1][0])

    def test_issue_api_transports_labels_for_create_and_update(self):
        github = sonar_watch.GitHubIssues(
            repository="pl0n3r/Factory", token="read-only-github-token",
        )
        calls = []
        github.http.request = lambda path, **kw: calls.append((path, kw))
        labels = ["tipo: calidad", "prioridad: media", "estado: bloqueado"]
        github.create(title="watch", body="marker", labels=labels)
        github.update(
            1, title="watch", body="marker", state="open", labels=labels,
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["method"], "POST")
        self.assertEqual(calls[0][1]["payload"]["labels"], labels)
        self.assertEqual(calls[1][1]["method"], "PATCH")
        self.assertEqual(calls[1][1]["payload"]["labels"], labels)
        self.assertEqual(calls[1][1]["payload"]["state"], "open")

    def test_retired_workflow_and_offline_engine_are_preserved(self):
        """F1C suprime el cron sin borrar el motor ni sus parámetros seguros."""
        workflow = ROOT / ".github" / "workflows" / "sonar-watch.yml"
        self.assertFalse(workflow.exists())
        script = ROOT / "scripts" / "sonar-watch.py"
        self.assertTrue(script.is_file())
        self.assertIn("CONFIG_PATH", script.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "quality" / "sonar-watch-config.json").is_file())

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
        self.assertIn(
            "https://sonarcloud.io/project/overview?id=factory",
            matches[0]["body"],
        )
        self.assertEqual(
            [
                item["action"]
                for item in first
                if item["signal"] == "visibility"
            ],
            ["created"],
        )
        self.assertEqual(
            [
                item["action"]
                for item in second
                if item["signal"] == "visibility"
            ],
            ["updated"],
        )

        captured = {}
        original = sonar_watch.urlopen

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, limit):
                return b"{}"

        def fake_urlopen(request, timeout):
            captured["method"] = request.get_method()
            captured["content_type"] = request.get_header("Content-type")
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

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(
            captured["content_type"],
            "application/json",
        )
        with self.assertRaises(sonar_watch.SonarWatchError):
            sonar_watch.sync_project(
                contract=contract(),
                snapshot=snapshot(),
                observed_at=NOW,
                project_ref="pl0n3r/Factory",
                origin_ref="sonar:factory",
                origin_url="https://evil.example/?token=secret",
                issues=FakeIssues(),
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
            "error_message": (
                "Organization line limit exceeded at 50000 lines"
            ),
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
            {"analyses": [{
                "date": "2026-09-30T11:50:00Z",
            }]},
            {"current": {
                "status": "SUCCESS",
                "errorMessage": None,
            }},
            {"component": {"measures": [{
                "metric": "coverage",
                "value": "80",
            }]}},
            {"settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]},
            {"component": {"visibility": "public"}},
            {"issues": []},
            {"hotspots": []},
        )
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
        self.assertEqual(
            organization["reason"],
            "organization_line_usage_missing",
        )

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
            sonar_watch.issue_marker(
                "factory", "historical_debt"
            )
        )[0]["body"]
        self.assertIn("bug/MAJOR", body)
        self.assertIn("2 abiertos", body)
        self.assertIn("bug:2>0", body)

        sonar = sonar_watch.SonarApi(token="read-only")
        calls = []

        def paged_get(path, params):
            calls.append((path, params["p"]))
            page = params["p"]
            page_size = sonar_watch._SONAR_PAGE_SIZE
            if page == 1:
                return {
                    "issues": [
                        {"key": f"i-{index}"}
                        for index in range(page_size)
                    ],
                    "paging": {
                        "pageIndex": 1,
                        "pageSize": page_size,
                        "total": page_size + 2,
                    },
                }
            return {
                "issues": [
                    {"key": f"i-{page_size}"},
                    {"key": f"i-{page_size + 1}"},
                ],
                "paging": {
                    "pageIndex": 2,
                    "pageSize": page_size,
                    "total": page_size + 2,
                },
            }

        sonar.get = paged_get
        page = sonar._all_issues("project-key")
        self.assertEqual(
            len(page["issues"]),
            sonar_watch._SONAR_PAGE_SIZE + 2,
        )
        self.assertEqual(
            calls,
            [
                ("/api/issues/search", 1),
                ("/api/issues/search", 2),
            ],
        )

        sonar.get = lambda path, params: {
            "issues": [],
            "paging": {
                "pageIndex": 1,
                "pageSize": sonar_watch._SONAR_PAGE_SIZE,
                "total": 10001,
            },
        }
        with self.assertRaises(sonar_watch.SonarWatchError):
            sonar._all_issues("project-key")

        hotspot_calls = []

        def hotspot_get(path, params):
            hotspot_calls.append((path, dict(params)))
            return {
                "hotspots": [{
                    "key": "hotspot-1",
                    "status": "TO_REVIEW",
                    "vulnerabilityProbability": "HIGH",
                    "creationDate": "2026-09-29T10:00:00+0000",
                }],
                "paging": {
                    "pageIndex": 1,
                    "pageSize": sonar_watch._SONAR_PAGE_SIZE,
                    "total": 1,
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
            {"analyses": [{
                "date": "2026-09-30T11:50:00Z",
            }]},
            {"current": {
                "status": "SUCCESS",
                "errorMessage": None,
            }},
            {"component": {"measures": [{
                "metric": "coverage",
                "value": "80",
            }]}},
            {"settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]},
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

    def test_coverage_pass_closes_matching_auto_issue(self):
        api = FakeIssues()
        failing = snapshot()
        failing["analysis"]["coverage_available"] = False
        sync(failing, api)

        marker = sonar_watch.issue_marker("factory", "coverage")
        coverage_issue = api.find(marker)[0]
        self.assertEqual(coverage_issue["state"], "open")

        sync(snapshot(), api)

        coverage_issue = api.find(marker)[0]
        self.assertEqual(coverage_issue["state"], "closed")

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
            sonar_watch.issue_marker(
                "factory", "quality_gate"
            )
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
            page_size = sonar_watch._GITHUB_PAGE_SIZE
            if path.endswith("page=1"):
                return [
                    {
                        "number": index + 1,
                        "title": f"issue-{index}",
                        "body": "",
                        "state": "open",
                    }
                    for index in range(page_size)
                ]
            return [{
                "number": page_size + 1,
                "title": "matching",
                "body": marker,
                "state": "open",
                "user": {"login": "github-actions[bot]"},
            }]

        github.http.request = paged_request
        found = github.find(marker)
        self.assertEqual(
            [item["number"] for item in found],
            [sonar_watch._GITHUB_PAGE_SIZE + 1],
        )
        self.assertEqual(len(page_calls), 2)

        original_limit = sonar_watch._MAX_GITHUB_ISSUE_PAGES
        sonar_watch._MAX_GITHUB_ISSUE_PAGES = 2
        github.http.request = lambda path, **kwargs: [
            {
                "number": index + 1,
                "title": f"issue-{index}",
                "body": "",
                "state": "open",
            }
            for index in range(sonar_watch._GITHUB_PAGE_SIZE)
        ]
        try:
            with self.assertRaises(sonar_watch.SonarWatchError):
                github.find(marker)
        finally:
            sonar_watch._MAX_GITHUB_ISSUE_PAGES = original_limit

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
        expected = {
            "brvtal",
            "condor",
            "controlbot",
            "factory",
            "factoryrunner",
            "grindflow",
        }
        self.assertEqual(
            set(sonar_watch.factory_project_catalog()),
            expected,
        )



    def test_live_snapshot_observation_is_taken_after_remote_reads(self):
        api = sonar_watch.SonarApi(token="read-only")
        events = []

        def fake_get(path, params):
            events.append(path)
            payloads = {
                "/api/components/show": {
                    "component": {"visibility": "public"},
                },
                "/api/qualitygates/project_status": {
                    "projectStatus": {"status": "OK", "conditions": []},
                },
                "/api/project_analyses/search": {
                    "analyses": [{"date": "2026-09-30T12:00:05Z"}],
                },
                "/api/ce/component": {
                    "current": {"status": "SUCCESS", "errorMessage": None},
                },
                "/api/measures/component": {
                    "component": {
                        "measures": [{"metric": "coverage", "value": "80"}],
                    },
                },
                "/api/settings/values": {
                    "settings": [{
                        "key": "sonar.autoscan.enabled",
                        "value": "false",
                    }],
                },
            }
            return payloads[path]

        original_now = sonar_watch._utc_now
        api.get = fake_get
        api._all_issues = lambda key: (
            events.append("issues") or {"issues": []}
        )
        api._all_hotspots = lambda key: (
            events.append("hotspots") or {"hotspots": []}
        )
        sonar_watch._utc_now = lambda: (
            events.append("clock") or "2026-09-30T12:00:10Z"
        )
        try:
            result = api.snapshot({
                "project": "factory",
                "sonar_key": "pl0n3r_factory",
            })
        finally:
            sonar_watch._utc_now = original_now

        self.assertEqual(events[-1], "clock")
        self.assertIn("issues", events[:-1])
        self.assertIn("hotspots", events[:-1])
        self.assertEqual(result["snapshot_at"], "2026-09-30T12:00:10Z")

    def test_run_live_uses_each_snapshot_timestamp(self):
        projects = [
            {
                "project": "factory",
                "sonar_key": "pl0n3r_factory",
                "github_repo": "pl0n3r/Factory",
                "contract": contract("factory"),
            },
            {
                "project": "condor",
                "sonar_key": "pl0n3r_Condor",
                "github_repo": "pl0n3r/Condor",
                "contract": contract("condor"),
            },
        ]
        snapshots = {
            "factory": {
                **snapshot("factory"),
                "snapshot_at": "2026-09-30T12:00:10Z",
            },
            "condor": {
                **snapshot("condor"),
                "snapshot_at": "2026-09-30T12:00:20Z",
            },
        }
        observed = []

        class FakeSonar:
            def __init__(self, *, token):
                self.token = token

            def preflight_visibility(self, rows):
                return {row["project"]: "public" for row in rows}

            def snapshot(self, cfg, *, component=None):
                return snapshots[cfg["project"]]

        def fake_sync_project(**kwargs):
            observed.append((
                kwargs["snapshot"]["project"],
                kwargs["observed_at"],
            ))
            return []

        originals = (
            sonar_watch.load_runtime_config,
            sonar_watch.SonarApi,
            sonar_watch.GitHubIssues,
            sonar_watch.sync_project,
        )
        old_env = {
            key: sonar_watch.os.environ.get(key)
            for key in ("SONAR_TOKEN", "GH_TOKEN", "GITHUB_REPOSITORY")
        }
        sonar_watch.load_runtime_config = lambda: projects
        sonar_watch.SonarApi = FakeSonar
        sonar_watch.GitHubIssues = lambda **kwargs: object()
        sonar_watch.sync_project = fake_sync_project
        sonar_watch.os.environ["SONAR_TOKEN"] = "token"
        sonar_watch.os.environ["GH_TOKEN"] = "gh-token"
        sonar_watch.os.environ["GITHUB_REPOSITORY"] = "pl0n3r/Factory"
        try:
            self.assertEqual(sonar_watch.run_live(), 0)
        finally:
            (
                sonar_watch.load_runtime_config,
                sonar_watch.SonarApi,
                sonar_watch.GitHubIssues,
                sonar_watch.sync_project,
            ) = originals
            for key, value in old_env.items():
                if value is None:
                    sonar_watch.os.environ.pop(key, None)
                else:
                    sonar_watch.os.environ[key] = value

        self.assertEqual(observed, [
            ("factory", "2026-09-30T12:00:10Z"),
            ("condor", "2026-09-30T12:00:20Z"),
        ])

    def test_analysis_completed_during_snapshot_is_not_false_future(self):
        api = sonar_watch.SonarApi(token="read-only")

        def fake_get(path, params):
            payloads = {
                "/api/components/show": {
                    "component": {"visibility": "public"},
                },
                "/api/qualitygates/project_status": {
                    "projectStatus": {"status": "OK", "conditions": []},
                },
                "/api/project_analyses/search": {
                    "analyses": [{"date": "2026-09-30T12:00:05Z"}],
                },
                "/api/ce/component": {
                    "current": {"status": "SUCCESS", "errorMessage": None},
                },
                "/api/measures/component": {
                    "component": {
                        "measures": [{"metric": "coverage", "value": "80"}],
                    },
                },
                "/api/settings/values": {
                    "settings": [{
                        "key": "sonar.autoscan.enabled",
                        "value": "false",
                    }],
                },
            }
            return payloads[path]

        original_now = sonar_watch._utc_now
        api.get = fake_get
        api._all_issues = lambda key: {"issues": []}
        api._all_hotspots = lambda key: {"hotspots": []}
        sonar_watch._utc_now = lambda: "2026-09-30T12:00:10Z"
        try:
            raw = api.snapshot({
                "project": "factory",
                "sonar_key": "pl0n3r_factory",
            })
        finally:
            sonar_watch._utc_now = original_now

        normalized = sonar_watch.normalize_sonar_snapshot(
            contract(),
            raw,
            observed_at=raw["snapshot_at"],
        )
        freshness = next(
            item for item in normalized["signals"]
            if item["signal"] == "analysis_freshness"
        )
        self.assertEqual(freshness["status"], "PASS")

    def test_versioned_runtime_config_covers_exact_factory_catalog(self):
        projects = sonar_watch.load_runtime_config()
        expected = set(sonar_watch.factory_project_catalog())
        self.assertEqual(len(projects), 6)
        self.assertEqual({row["project"] for row in projects}, expected)
        self.assertEqual(
            {row["sonar_key"] for row in projects},
            {
                "pl0n3r_brvtal",
                "pl0n3r_Condor",
                "pl0n3r_factory-control",
                "pl0n3r_factory",
                "pl0n3r_FactoryRunner",
                "pl0n3r_GrindFlow",
            },
        )
        expected_policy = {
            "brvtal": ("automatic", 172800, 0, 18),
            "condor": ("automatic", 172800, 0, 0),
            "controlbot": ("ci", 172800, 0, 1),
            "factory": ("ci", 172800, 0, 0),
            "factoryrunner": ("automatic", 604800, 0, 0),
            "grindflow": ("automatic", 172800, 8, 0),
        }
        for row in projects:
            self.assertEqual(row["contract"]["project"], row["project"])
            sonar = row["contract"]["sonar"]
            method, age, vulnerabilities, bugs = expected_policy[row["project"]]
            self.assertEqual(sonar["expected_visibility"], "public")
            self.assertEqual(sonar["analysis_method"], method)
            self.assertEqual(sonar["max_analysis_age_seconds"], age)
            self.assertEqual(sonar["max_organization_line_usage_percent"], 80)
            self.assertEqual(sonar["max_open_vulnerabilities"], vulnerabilities)
            self.assertEqual(sonar["max_open_bugs"], bugs)
            self.assertEqual(sonar["max_open_hotspots"], 0)
            self.assertEqual(sonar["max_debt_age_days"], 30)

    def test_public_projects_need_no_token_and_private_projects_fail_closed_without_one(self):
        projects = sonar_watch.load_runtime_config()
        api = sonar_watch.SonarApi(token="")
        calls = []

        def public_get(path, params):
            calls.append((path, params))
            return {"component": {"visibility": "public"}}

        api.get = public_get
        observed = api.preflight_visibility(projects)
        self.assertEqual(set(observed), {row["project"] for row in projects})
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(path == "/api/components/show" for path, _ in calls))

        private_projects = [dict(row) for row in projects]
        first = projects[0]
        private_projects[0] = {
            **first,
            "contract": {
                **first["contract"],
                "sonar": {
                    **first["contract"]["sonar"],
                    "expected_visibility": "private",
                },
            },
        }
        calls.clear()

        def forbidden_get(path, params):
            calls.append((path, params))
            raise AssertionError("no Sonar request allowed before private-token preflight")

        api.get = forbidden_get
        with self.assertRaises(sonar_watch.SonarWatchError):
            api.preflight_visibility(private_projects)
        self.assertEqual(calls, [])

    def test_analysis_method_uses_read_only_settings_get_only(self):
        api = sonar_watch.SonarApi(token="")
        calls = []

        def fake_request(path, *, method="GET", payload=None):
            calls.append((path, method, payload))
            return {"settings": [{
                "key": "sonar.autoscan.enabled",
                "value": "true",
            }]}

        original = api.http.request
        api.http.request = fake_request
        try:
            api.get(
                "/api/settings/values",
                {"component": "pl0n3r_factory", "keys": "sonar.autoscan.enabled"},
            )
        finally:
            api.http.request = original

        with self.assertRaises(sonar_watch.SonarWatchError):
            api.http.request("/api/settings/values", method="POST", payload={})
        self.assertEqual(calls[0][1], "GET")
        self.assertNotIn("/api/autoscan/activation", calls[0][0])

    def test_autoscan_setting_maps_strictly_to_analysis_method(self):
        self.assertEqual(
            sonar_watch.SonarApi.analysis_method_from_settings(
                {"settings": [{"key": "sonar.autoscan.enabled", "value": "true"}]}
            ),
            "automatic",
        )
        self.assertEqual(
            sonar_watch.SonarApi.analysis_method_from_settings(
                {"settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]}
            ),
            "ci",
        )
        invalid = [
            {},
            {"settings": []},
            {"settings": [
                {"key": "sonar.autoscan.enabled", "value": "true"},
                {"key": "sonar.autoscan.enabled", "value": "false"},
            ]},
            {"settings": [{"key": "other", "value": "true"}]},
            {"settings": [{"key": "sonar.autoscan.enabled", "value": "yes"}]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(sonar_watch.SonarWatchError):
                    sonar_watch.SonarApi.analysis_method_from_settings(payload)

    def test_offline_runtime_loads_versioned_config_without_workflow(self):
        """Conservar la configuración versionada, no los permisos del cron."""
        self.assertFalse((ROOT / ".github" / "workflows" / "sonar-watch.yml").exists())
        script = (ROOT / "scripts" / "sonar-watch.py").read_text(encoding="utf-8")
        self.assertIn("quality/sonar-watch-config.json", script)
        self.assertTrue((ROOT / "quality" / "sonar-watch-config.json").is_file())

    def test_runtime_auth_and_settings_scenarios_are_fail_closed_without_sonar_writes(self):
        api = sonar_watch.SonarApi(token="")
        with self.assertRaises(sonar_watch.SonarWatchError):
            api.http.request("/api/settings/values", method="POST", payload={})
        for payload in (
            {"settings": [{"key": "sonar.autoscan.enabled", "value": None}]},
            {"settings": [{"key": "sonar.autoscan.enabled"}]},
            {"settings": [{"key": "sonar.autoscan.enabled", "value": "TRUE"}]},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(sonar_watch.SonarWatchError):
                    sonar_watch.SonarApi.analysis_method_from_settings(payload)

    def test_github_issue_pagination_bounds_each_remote_response(self):
        self.assertEqual(sonar_watch._GITHUB_PAGE_SIZE, 50)
        self.assertEqual(sonar_watch._MAX_GITHUB_ISSUES, 10_000)
        self.assertEqual(
            sonar_watch._MAX_GITHUB_ISSUE_PAGES,
            (sonar_watch._MAX_GITHUB_ISSUES // sonar_watch._GITHUB_PAGE_SIZE) + 1,
        )
        github = sonar_watch.GitHubIssues(
            repository="pl0n3r/Factory",
            token="token",
        )
        calls = []

        def fake_request(path, **kwargs):
            calls.append(path)
            self.assertIn("per_page=50", path)
            if path.endswith("page=1"):
                return [
                    {
                        "number": index + 1,
                        "title": f"issue-{index}",
                        "body": "",
                        "state": "open",
                    }
                    for index in range(sonar_watch._GITHUB_PAGE_SIZE)
                ]
            return []

        github.http.request = fake_request
        self.assertEqual(github.find("<!-- absent -->"), [])
        self.assertEqual(len(calls), 2)

        original = (
            sonar_watch._GITHUB_PAGE_SIZE,
            sonar_watch._MAX_GITHUB_ISSUES,
            sonar_watch._MAX_GITHUB_ISSUE_PAGES,
        )
        sonar_watch._GITHUB_PAGE_SIZE = 2
        sonar_watch._MAX_GITHUB_ISSUES = 4
        sonar_watch._MAX_GITHUB_ISSUE_PAGES = 3
        try:
            exact = sonar_watch.GitHubIssues(
                repository="pl0n3r/Factory",
                token="token",
            )
            exact.http.request = lambda path, **kwargs: (
                [
                    {
                        "number": 1,
                        "title": "issue",
                        "body": "",
                        "state": "open",
                    },
                    {
                        "number": 2,
                        "title": "issue",
                        "body": "",
                        "state": "open",
                    },
                ]
                if not path.endswith("page=3")
                else []
            )
            self.assertEqual(exact.find("<!-- absent -->"), [])

            overflow = sonar_watch.GitHubIssues(
                repository="pl0n3r/Factory",
                token="token",
            )
            overflow.http.request = lambda path, **kwargs: [
                {
                    "number": 1,
                    "title": "issue",
                    "body": "",
                    "state": "open",
                },
                {
                    "number": 2,
                    "title": "issue",
                    "body": "",
                    "state": "open",
                },
            ]
            with self.assertRaisesRegex(
                sonar_watch.SonarWatchError,
                "excede límite seguro",
            ):
                overflow.find("<!-- absent -->")
        finally:
            (
                sonar_watch._GITHUB_PAGE_SIZE,
                sonar_watch._MAX_GITHUB_ISSUES,
                sonar_watch._MAX_GITHUB_ISSUE_PAGES,
            ) = original

    def test_sonar_watch_no_longer_has_scheduled_or_manual_triggers(self):
        self.assertFalse((ROOT / ".github" / "workflows" / "sonar-watch.yml").exists())
        for active in (ROOT / ".github" / "workflows").glob("*.yml"):
            text = active.read_text(encoding="utf-8")
            self.assertNotIn("python3 scripts/sonar-watch.py", text)

    def test_ci_missing_coverage_remains_actionable(self):
        configs = {
            row["project"]: row
            for row in sonar_watch.load_runtime_config()
        }
        cfg = configs["factory"]
        raw = snapshot("factory")
        raw["analysis"]["method"] = "ci"
        raw["analysis"]["coverage_available"] = False
        raw["organization"] = None
        api = FakeIssues()

        operations = sonar_watch.sync_project(
            contract=cfg["contract"],
            snapshot=raw,
            observed_at=NOW,
            project_ref=cfg["github_repo"],
            origin_ref="sonar:factory",
            origin_url=(
                "https://sonarcloud.io/project/overview"
                f"?id={cfg['sonar_key']}"
            ),
            issues=api,
        )

        marker = sonar_watch.issue_marker("factory", "coverage")
        coverage = api.find(marker)
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]["state"], "open")
        self.assertIn(
            {"action": "created", "signal": "coverage"},
            operations,
        )
        self.assertFalse(
            any(
                call[0] == "comment" and call[1] == coverage[0]["number"]
                for call in api.calls
            )
        )

    def test_not_applicable_closes_auto_issue_once_and_preserves_required_failures(self):
        configs = {
            row["project"]: row
            for row in sonar_watch.load_runtime_config()
        }

        brvtal = configs["brvtal"]
        raw = snapshot("brvtal")
        raw["analysis"]["method"] = "automatic"
        raw["analysis"]["coverage_available"] = False
        raw["organization"] = None
        api = FakeIssues()
        for signal in ("coverage", "organization_line_usage"):
            marker = sonar_watch.issue_marker("brvtal", signal)
            api.rows.append({
                "number": api.next_number,
                "title": f"[AUTO] Sonar brvtal: {signal}",
                "body": marker + "\nexisting",
                "state": "open",
            })
            api.next_number += 1

        original_update = api.update
        failed_once = {"value": False}

        def fail_first_close(number, *, title, body, state, labels):
            if state == "closed" and not failed_once["value"]:
                failed_once["value"] = True
                raise RuntimeError("simulated partial PATCH failure")
            return original_update(
                number,
                title=title,
                body=body,
                state=state,
                labels=labels,
            )

        api.update = fail_first_close
        with self.assertRaisesRegex(RuntimeError, "partial PATCH"):
            sonar_watch.sync_project(
                contract=brvtal["contract"],
                snapshot=raw,
                observed_at=NOW,
                project_ref=brvtal["github_repo"],
                origin_ref="sonar:brvtal",
                origin_url=(
                    "https://sonarcloud.io/project/overview"
                    f"?id={brvtal['sonar_key']}"
                ),
                issues=api,
            )
        self.assertEqual(
            len([call for call in api.calls if call[0] == "comment"]),
            1,
        )
        api.update = original_update

        first = sonar_watch.sync_project(
            contract=brvtal["contract"],
            snapshot=raw,
            observed_at=NOW,
            project_ref=brvtal["github_repo"],
            origin_ref="sonar:brvtal",
            origin_url=(
                "https://sonarcloud.io/project/overview"
                f"?id={brvtal['sonar_key']}"
            ),
            issues=api,
        )
        second = sonar_watch.sync_project(
            contract=brvtal["contract"],
            snapshot=raw,
            observed_at=NOW,
            project_ref=brvtal["github_repo"],
            origin_ref="sonar:brvtal",
            origin_url=(
                "https://sonarcloud.io/project/overview"
                f"?id={brvtal['sonar_key']}"
            ),
            issues=api,
        )

        for signal in ("coverage", "organization_line_usage"):
            row = api.find(sonar_watch.issue_marker("brvtal", signal))[0]
            self.assertEqual(row["state"], "closed")
        comments = [call for call in api.calls if call[0] == "comment"]
        self.assertEqual(len(comments), 2)
        self.assertTrue(
            all("NOT_APPLICABLE" in call[2] for call in comments)
        )
        self.assertEqual(
            sorted(
                item["signal"]
                for item in first
                if item["action"] == "closed_not_applicable"
            ),
            ["coverage", "organization_line_usage"],
        )
        self.assertEqual(
            [
                item for item in second
                if item["action"] == "closed_not_applicable"
            ],
            [],
        )

        factory = configs["factory"]
        required = snapshot("factory")
        required["analysis"]["method"] = "ci"
        required["analysis"]["coverage_available"] = False
        required["organization"] = None
        required_api = FakeIssues()
        sonar_watch.sync_project(
            contract=factory["contract"],
            snapshot=required,
            observed_at=NOW,
            project_ref=factory["github_repo"],
            origin_ref="sonar:factory",
            origin_url=(
                "https://sonarcloud.io/project/overview"
                f"?id={factory['sonar_key']}"
            ),
            issues=required_api,
        )
        coverage = required_api.find(
            sonar_watch.issue_marker("factory", "coverage")
        )
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage[0]["state"], "open")
if __name__ == "__main__":
    unittest.main()
