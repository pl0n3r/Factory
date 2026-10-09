import importlib.util
import unittest
from pathlib import Path

from quality.sonar import normalize_sonar_snapshot

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sonar_watch_superseded", ROOT / "scripts" / "sonar-watch.py"
)
sonar_watch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sonar_watch)

NOW = "2026-10-06T00:10:00Z"
OLD_SHA = "f582680fd50436405329fc8cfd697167004fac32"
NEW_SHA = "c5e09d6f4e9982fd9b6d52d7043fd6c226453401"
SUPERSEDED = (
    f"Report for commit '{OLD_SHA}' can’t be processed: "
    "a newer report has already been processed, and processing older reports is not supported. "
    f"The last processed report was for commit '{NEW_SHA}'."
)


def contract(project="condor"):
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


def snapshot(project="condor"):
    return {
        "project": project,
        "snapshot_at": "2026-10-06T00:06:12Z",
        "quality_gate": {"status": "OK", "conditions": []},
        "analysis": {
            "analyzed_at": "2026-10-06T00:05:00Z",
            "method": "ci",
            "coverage_available": True,
        },
        "ce_task": {"status": "SUCCESS", "error_message": None},
        "organization": {"line_usage_percent": 50},
        "visibility": "public",
        "debt": [],
        "evidence_refs": ["sonar:condor:snapshot:20261006T000612Z"],
    }


def ce_signal(raw):
    normalized = normalize_sonar_snapshot(contract(raw["project"]), raw, observed_at=NOW)
    return next(item for item in normalized["signals"] if item["signal"] == "ce_task")


class FakeIssues:
    def __init__(self):
        marker = sonar_watch.issue_marker("condor", "ce_task")
        self.rows = [{
            "number": 1039,
            "title": "[AUTO] Sonar condor: ce_task",
            "body": marker + "\nold body",
            "state": "open",
        }]
        self.calls = []

    def find(self, marker):
        return [row.copy() for row in self.rows if marker in row["body"]]

    def create(self, *, title, body, labels):
        self.calls.append(("create", title))

    def update(self, number, *, title, body, state, labels):
        row = next(item for item in self.rows if item["number"] == number)
        row.update({"title": title, "body": body, "state": state, "labels": list(labels)})
        self.calls.append(("update", number, state))

    def comment_once(self, number, *, marker, body):
        self.calls.append(("comment_once", number))
        return True


class SonarSupersededCeTests(unittest.TestCase):
    def test_superseded_ce_task_is_pass_with_auditable_reason(self):
        raw = snapshot()
        raw["ce_task"] = {"status": "FAILED", "error_message": SUPERSEDED}

        task = ce_signal(raw)

        self.assertEqual(task["status"], "PASS")
        self.assertEqual(task["reason"], "ce_task_superseded_by_newer_report")
        self.assertEqual(task["freshness"]["state"], "CURRENT")
        self.assertIn("a newer report has already been processed", task["details"]["error_message"])
        self.assertIn(OLD_SHA, task["details"]["error_message"])
        self.assertIn(NEW_SHA, task["details"]["error_message"])

    def test_non_superseded_ce_failure_remains_fail_closed(self):
        raw = snapshot()
        raw["ce_task"] = {
            "status": "FAILED",
            "error_message": "Compute Engine task failed while processing the report.",
        }

        task = ce_signal(raw)

        self.assertEqual(task["status"], "FAIL")
        self.assertEqual(task["reason"], "ce_task_failed")

    def test_superseded_ce_task_closes_existing_watch_issue(self):
        raw = snapshot()
        raw["ce_task"] = {"status": "FAILED", "error_message": SUPERSEDED}
        issues = FakeIssues()

        operations = sonar_watch.sync_project(
            contract=contract(),
            snapshot=raw,
            observed_at=NOW,
            project_ref="pl0n3r/Condor",
            origin_ref="sonar:condor",
            origin_url="https://sonarcloud.io/project/overview?id=pl0n3r_Condor",
            issues=issues,
        )

        self.assertEqual(issues.rows[0]["state"], "closed")
        self.assertEqual(
            issues.rows[0]["labels"],
            ["tipo: calidad", "prioridad: media", "estado: completado"],
        )
        self.assertIn({"action": "closed", "signal": "ce_task"}, operations)
        self.assertNotIn("create", [call[0] for call in issues.calls])

    def test_similar_but_ambiguous_message_does_not_bypass_failure(self):
        raw = snapshot()
        raw["ce_task"] = {
            "status": "FAILED",
            "error_message": (
                "Report for commit 'not-a-sha' can’t be processed: "
                "a newer report has already been processed, and processing older reports is not supported. "
                "The last processed report was for commit 'also-not-a-sha'."
            ),
        }

        task = ce_signal(raw)

        self.assertEqual(task["status"], "FAIL")
        self.assertEqual(task["reason"], "ce_task_failed")


if __name__ == "__main__":
    unittest.main()
