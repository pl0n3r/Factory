import copy
import unittest

from performance.detector import detect_performance
from performance.team_compiler_bridge import (
    PerformanceTeamCompilerBridgeError,
    compile_performance_team,
)
from scripts.roles_kit import load_catalog

NOW = "2026-09-28T20:06:00Z"


def detected(value=300, **overrides):
    metric = {
        "id": "latency_p95", "label": "Latency p95",
        "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "ci", "ref": "run:1", "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["create_work_item", "measure_before_after"],
        "escalation_conditions": ["architecture_change", "cost_change"],
    }
    contract = {"version": 1, "project": "condor", "surfaces": [
        {"id": "inventory", "label": "Inventory", "metrics": [metric]},
    ]}
    observation = {
        "version": 1, "project": "condor", "surface": "inventory",
        "metric": "latency_p95", "value": value, "unit": "ms",
        "observed_at": "2026-09-28T20:05:00Z", "window_seconds": 300,
        "sample_count": 30, "severity": "high", "operational_impact": False,
        "bottleneck": "database", "evidence_ref": "run:2",
        "sha": "a" * 40, "release": "v1.2.3",
    }
    observation.update(overrides)
    return detect_performance(contract, observation, evaluated_at="2026-09-28T20:06:00Z")


class PerformanceTeamCompilerBridgeTests(unittest.TestCase):
    def test_database_current_composes_real_team_with_dba(self):
        team = compile_performance_team(detected(300, bottleneck="database"), evaluated_at=NOW)
        self.assertEqual(team["decision"], "TEAM_RECOMMENDED")
        self.assertEqual(team["primary"], "dba")
        self.assertTrue({"dba", "ingenieria-software", "qa"} <= set(team["roles"]))
        self.assertIn(team["compiler_primary"], team["roles"])
        self.assertEqual(team["classification"], "PERF_DEGRADATION")

    def test_frontend_and_incident_preserve_professional_roles(self):
        front = compile_performance_team(detected(300, bottleneck="frontend"), evaluated_at=NOW)
        self.assertEqual(front["primary"], "frontend")
        self.assertTrue({"frontend", "qa"} <= set(front["roles"]))
        incident = compile_performance_team(detected(
            300, bottleneck="sre", severity="critical", operational_impact=True,
        ), evaluated_at=NOW)
        self.assertEqual(incident["classification"], "PERF_INCIDENT")
        self.assertEqual(incident["primary"], "sre")
        self.assertTrue({"sre", "qa"} <= set(incident["roles"]))
        self.assertFalse(incident["execute_actions"])

    def test_stale_unknown_and_incomplete_catalog_fail_closed(self):
        samples = (
            detected(300, observed_at="2026-09-28T19:00:00Z"),
            detected(300, metric="missing_metric"),
            {"classification": "PERF_DEGRADATION", "bottleneck": "database"},
        )
        for item in samples:
            with self.subTest(state=item.get("evidence_state")):
                with self.assertRaises(PerformanceTeamCompilerBridgeError):
                    compile_performance_team(item, evaluated_at=NOW)
        catalog = dict(load_catalog())
        del catalog["dba"]
        with self.assertRaises(PerformanceTeamCompilerBridgeError):
            compile_performance_team(detected(300), evaluated_at=NOW, catalog=catalog)
        info = compile_performance_team(detected(220), evaluated_at=NOW)
        self.assertEqual(info["decision"], "NO_ASSIGNMENT")
        self.assertEqual(info["roles"], [])

    def test_nonexecuting_output_and_catalog_unchanged(self):
        catalog = load_catalog()
        before = copy.deepcopy(catalog)
        result = compile_performance_team(detected(300), evaluated_at=NOW, catalog=catalog)
        self.assertEqual(catalog, before)
        for prop in ("execute_actions", "create_work_item", "dispatch"):
            self.assertIs(result[prop], False)
        self.assertEqual(result["authority"], "unchanged")
        self.assertEqual(result["evidence_refs"], ["run:2"])
        for private in ("token", "secret", "password", "authorization", "work_item"):
            self.assertNotIn(private, result)


    def test_detection_current_but_now_stale_is_rejected(self):
        current = detected(300)
        with self.assertRaisesRegex(PerformanceTeamCompilerBridgeError, "CURRENT"):
            compile_performance_team(current, evaluated_at="2026-09-28T20:31:00Z")
        for invalid_at in ("2026-09-28T20:04:00Z", "2026-09-28T20:06:00", "not-a-date"):
            with self.subTest(evaluated_at=invalid_at):
                with self.assertRaises(PerformanceTeamCompilerBridgeError):
                    compile_performance_team(current, evaluated_at=invalid_at)

    def test_catalog_extra_role_and_modified_canonical_entry_are_rejected(self):
        catalog = load_catalog()
        malicious = copy.deepcopy(catalog)
        malicious["synthetic-admin"] = {
            "slug": "synthetic-admin", "label_es": "rol: synthetic-admin",
            "label_en": "role: synthetic-admin", "file": "agentes/roles/synthetic-admin.md",
        }
        with self.assertRaisesRegex(PerformanceTeamCompilerBridgeError, "Catalogo"):
            compile_performance_team(detected(300), evaluated_at=NOW, catalog=malicious)
        modified = copy.deepcopy(catalog)
        modified["dba"]["file"] = "outside.md"
        with self.assertRaisesRegex(PerformanceTeamCompilerBridgeError, "Catalogo"):
            compile_performance_team(detected(300), evaluated_at=NOW, catalog=modified)



if __name__ == "__main__":
    unittest.main()
