import unittest

from quality.sonar import (
    FACTORY_PROJECTS,
    SonarEvidenceError,
    factory_project_catalog,
    normalize_sonar_snapshot,
)

NOW = "2026-09-30T12:00:00Z"


def contract(project="factory"):
    return {
        "version": 1,
        "project": project,
        "surfaces": [
            {
                "id": "admin",
                "criticality": "high",
                "required_gates": ["security"],
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
            "max_open_bugs": 10,
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
        "evidence_refs": ["sonar:factory:snapshot:001"],
    }


def signal(result, name):
    return next(item for item in result["signals"] if item["signal"] == name)


class QualitySonarTests(unittest.TestCase):
    def test_quality_gate_and_failed_condition_are_normalized(self):
        raw = snapshot()
        raw["quality_gate"] = {
            "status": "ERROR",
            "conditions": [
                {
                    "metric": "new_reliability_rating",
                    "status": "ERROR",
                    "actual": "3",
                    "threshold": "1",
                }
            ],
        }

        normalized = normalize_sonar_snapshot(contract(), raw, observed_at=NOW)
        gate = signal(normalized, "quality_gate")

        self.assertEqual(gate["status"], "FAIL")
        self.assertEqual(gate["reason"], "quality_gate_failed")
        self.assertEqual(
            gate["details"]["failed_conditions"],
            [{
                "metric": "new_reliability_rating",
                "status": "ERROR",
                "actual": "3",
                "threshold": "1",
            }],
        )
        self.assertEqual(gate["freshness"]["state"], "CURRENT")
        self.assertEqual(gate["evidence_refs"], ["sonar:factory:snapshot:001"])

    def test_failed_ce_task_preserves_sanitized_server_error(self):
        raw = snapshot()
        raw["ce_task"] = {
            "status": "FAILED",
            "error_message": (
                "Organization line limit exceeded: 50,000 lines. "
                "See https://sonarcloud.io/example token=supersecret123"
            ),
        }

        normalized = normalize_sonar_snapshot(contract(), raw, observed_at=NOW)
        task = signal(normalized, "ce_task")
        message = task["details"]["error_message"]

        self.assertEqual(task["status"], "FAIL")
        self.assertIn("Organization line limit exceeded", message)
        self.assertIn("[url removed]", message)
        self.assertIn("[sensitive removed]", message)
        self.assertNotIn("https://", message)
        self.assertNotIn("supersecret123", message)

    def test_freshness_visibility_analysis_method_and_coverage_fail_closed(self):
        raw = snapshot()
        raw["analysis"] = {
            "analyzed_at": "2026-09-28T11:00:00Z",
            "method": "automatic",
            "coverage_available": False,
        }
        raw["visibility"] = "private"
        raw["organization"] = None

        normalized = normalize_sonar_snapshot(contract(), raw, observed_at=NOW)

        self.assertEqual(
            signal(normalized, "analysis_freshness")["status"], "STALE"
        )
        self.assertEqual(signal(normalized, "visibility")["status"], "FAIL")
        self.assertEqual(signal(normalized, "analysis_method")["status"], "STALE")
        self.assertEqual(signal(normalized, "coverage")["status"], "STALE")
        self.assertEqual(
            signal(normalized, "organization_line_usage")["status"], "UNKNOWN"
        )

        current = snapshot()
        current["analysis"]["method"] = "automatic"
        current["analysis"]["coverage_available"] = False
        normalized_current = normalize_sonar_snapshot(
            contract(), current, observed_at=NOW
        )
        self.assertEqual(
            signal(normalized_current, "analysis_method")["status"], "FAIL"
        )
        self.assertEqual(
            signal(normalized_current, "coverage")["status"], "UNKNOWN"
        )

        stale_snapshot = snapshot()
        stale_snapshot["snapshot_at"] = "2026-09-30T09:00:00Z"
        stale_snapshot["analysis"]["analyzed_at"] = "2026-09-30T09:00:00Z"
        normalized_stale = normalize_sonar_snapshot(
            contract(), stale_snapshot, observed_at=NOW
        )
        self.assertTrue(
            all(item["status"] == "STALE" for item in normalized_stale["signals"])
        )
        self.assertTrue(
            all(
                item["freshness"]["state"] == "STALE"
                for item in normalized_stale["signals"]
            )
        )

    def test_historical_debt_is_grouped_against_explicit_thresholds(self):
        raw = snapshot()
        raw["debt"] = [
            {
                "type": "vulnerability",
                "severity": "CRITICAL",
                "opened_at": "2026-08-01T12:00:00Z",
                "evidence_ref": "sonar:factory:vulnerability:1",
            },
            {
                "type": "vulnerability",
                "severity": "MAJOR",
                "opened_at": "2026-09-25T12:00:00Z",
                "evidence_ref": "sonar:factory:vulnerability:2",
            },
            {
                "type": "bug",
                "severity": "MAJOR",
                "opened_at": "2026-09-29T12:00:00Z",
                "evidence_ref": "sonar:factory:bug:1",
            },
        ]

        normalized = normalize_sonar_snapshot(contract(), raw, observed_at=NOW)
        debt = signal(normalized, "historical_debt")

        self.assertEqual(debt["status"], "FAIL")
        self.assertEqual(
            debt["details"]["counts"],
            [
                {"type": "bug", "severity": "MAJOR", "count": 1},
                {"type": "vulnerability", "severity": "CRITICAL", "count": 1},
                {"type": "vulnerability", "severity": "MAJOR", "count": 1},
            ],
        )
        self.assertEqual(debt["details"]["oldest_age_days"], 60)
        self.assertIn("vulnerability:2>0", debt["details"]["exceeded"])
        self.assertIn("age_days:60>30", debt["details"]["exceeded"])

    def test_invalid_sensitive_or_incomplete_payload_fails_closed(self):
        cases = []

        missing = snapshot()
        del missing["ce_task"]
        cases.append(missing)

        sensitive_ref = snapshot()
        sensitive_ref["evidence_refs"] = ["token=supersecret123"]
        cases.append(sensitive_ref)

        url_ref = snapshot()
        url_ref["evidence_refs"] = ["https://sonarcloud.io/example"]
        cases.append(url_ref)

        sensitive_condition = snapshot()
        sensitive_condition["quality_gate"] = {
            "status": "ERROR",
            "conditions": [{
                "metric": "new_reliability_rating",
                "status": "ERROR",
                "actual": "token=supersecret123",
                "threshold": "1",
            }],
        }
        cases.append(sensitive_condition)

        future = snapshot()
        future["snapshot_at"] = "2026-10-01T12:00:00Z"
        cases.append(future)

        for raw in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(SonarEvidenceError):
                    normalize_sonar_snapshot(contract(), raw, observed_at=NOW)

    def test_factory_project_catalog_is_explicit_and_bounded(self):
        expected = [
            "brvtal",
            "condor",
            "controlbot",
            "factory",
            "factoryrunner",
            "grindflow",
        ]
        self.assertEqual(factory_project_catalog(), expected)
        self.assertEqual(tuple(expected), FACTORY_PROJECTS)
        self.assertEqual(len(factory_project_catalog()), 6)

        for project in expected:
            raw = snapshot(project)
            normalized = normalize_sonar_snapshot(
                contract(project), raw, observed_at=NOW
            )
            self.assertEqual(normalized["project"], project)

        with self.assertRaises(SonarEvidenceError):
            normalize_sonar_snapshot(
                contract("unknown-project"),
                snapshot("unknown-project"),
                observed_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
