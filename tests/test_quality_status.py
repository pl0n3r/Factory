import copy
import unittest
from pathlib import Path

from quality.regression import analyze_regression
from quality.status import (
    QualityStatusError,
    derive_quality_health,
    quality_work_item_classes,
    readiness_projection,
)
from scripts.dispatcher_v2 import (
    WorkItemReadinessContext,
    candidate_from_work_item,
    classify_readiness,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-29T03:00:00Z"


def contract(*, external=False):
    required = external
    return {
        "version": 1,
        "project": "factory",
        "surfaces": [
            {"id": "admin", "criticality": "critical",
             "required_gates": ["security", "unit"]},
            {"id": "public-web", "criticality": "medium",
             "required_gates": ["browser"]},
        ],
        "invariants": ["authorization"],
        "compatibility": {"runtimes": ["python-3"], "browsers": [], "devices": []},
        "accessibility": {"target": "NOT_APPLICABLE"},
        "migration": {"strategy": "NOT_APPLICABLE"},
        "smoke": {"required": False, "source_ref": None},
        "evidence_freshness_seconds": 3600,
        "dimensions": {
            "performance": {
                "required": required,
                "source_ref": "pl0n3r/Factory#304" if required else None,
            },
            "recovery": {
                "required": required,
                "source_ref": "pl0n3r/Factory#305" if required else None,
            },
        },
    }


def gates():
    return [
        {"surface": "admin", "gate": "security", "status": "PASS",
         "observed_at": "2026-09-29T02:30:00Z", "evidence_ref": "ci:admin:security"},
        {"surface": "admin", "gate": "unit", "status": "PASS",
         "observed_at": "2026-09-29T02:30:00Z", "evidence_ref": "ci:admin:unit"},
        {"surface": "public-web", "gate": "browser", "status": "PASS",
         "observed_at": "2026-09-29T02:30:00Z", "evidence_ref": "ci:web:browser"},
    ]


def regression(*, before_runs=3, before_failures=3, after_failures=0, test_ref="tests/regression.py::test_fix"):
    return analyze_regression({
        "version": 1,
        "regression_id": "quality-regression-001",
        "project": "pl0n3r/Factory",
        "surface": "admin",
        "signature": "quality gate oscillates",
        "occurred_at": "2026-09-29T02:00:00Z",
        "source": "pl0n3r/Factory#347",
        "root_cause": "Unstable evidence was treated as conclusive.",
        "prevention": "Require reproducible failure and clean after evidence.",
        "before": {"runs": before_runs, "failures": before_failures,
                   "evidence_ref": "ci:quality:before",
                   "observed_at": "2026-09-29T02:10:00Z"},
        "after": {"runs": 3, "failures": after_failures,
                  "evidence_ref": "ci:quality:after",
                  "observed_at": "2026-09-29T02:20:00Z"},
        "regression_test_ref": test_ref,
    }, evaluated_at="2026-09-29T02:40:00Z")


def performance(state="HEALTHY"):
    return {
        "status": state,
        "reasons": [] if state == "HEALTHY" else ["performance_degradation"],
        "evidence_refs": ["run:performance:001"],
        "evidence_state": "CURRENT",
        "project": "factory", "surface": "admin", "metric": "latency",
        "authority": "unchanged", "execute_actions": False,
    }


def recovery(state="HEALTHY"):
    classes = [] if state == "HEALTHY" else ["backup_stale"]
    return {
        "version": 1, "project": "factory", "state": state,
        "reasons": ["RECOVERY_EVIDENCE_CURRENT"] if state == "HEALTHY" else ["BACKUP_STALE"],
        "work_item_classes": classes,
        "authority": "unchanged", "execute": False,
    }


def health(gate_rows=None, regressions=None, *, external=False, perf=None, rec=None):
    return derive_quality_health(
        contract(external=external),
        gates() if gate_rows is None else gate_rows,
        [] if regressions is None else regressions,
        observed_at=NOW,
        project_ref="pl0n3r/Factory",
        performance_status=perf,
        recovery_health=rec,
    )


class QualityStatusTests(unittest.TestCase):
    def test_quality_health_derives_pass_degraded_unknown_blocked_with_reasons_and_freshness(self):
        passed = health()
        self.assertEqual(passed["state"], "PASS")
        self.assertEqual(passed["freshness"], {
            "state": "CURRENT", "max_age_seconds": 3600, "oldest_age_seconds": 1800,
        })

        degraded_rows = gates(); degraded_rows[2]["status"] = "FAIL"
        degraded = health(degraded_rows)
        self.assertEqual(degraded["state"], "DEGRADED")
        self.assertIn("quality_gate_failed", degraded["work_item_classes"])

        unknown = health(gates()[:-1])
        self.assertEqual(unknown["state"], "UNKNOWN")
        self.assertEqual(unknown["freshness"]["state"], "DEGRADED")

        blocked_rows = gates(); blocked_rows[0]["status"] = "FAIL"
        self.assertEqual(health(blocked_rows)["state"], "BLOCKED")

    def test_required_gate_matrix_comes_only_from_quality_contract_without_hidden_defaults(self):
        result = health()
        actual = {(row["surface"], row["gate"]) for row in result["required_gates"]}
        self.assertEqual(actual, {
            ("admin", "security"), ("admin", "unit"), ("public-web", "browser"),
        })
        invented = gates() + [{
            "surface": "admin", "gate": "e2e", "status": "PASS",
            "observed_at": "2026-09-29T02:30:00Z", "evidence_ref": "ci:admin:e2e",
        }]
        with self.assertRaises(QualityStatusError):
            health(invented)

    def test_flaky_observed_or_unverified_regression_never_passes_and_critical_reproduced_failure_blocks(self):
        flaky = health(regressions=[regression(before_failures=1)])
        self.assertEqual(flaky["state"], "DEGRADED")
        self.assertIn("quality_regression_flaky", flaky["work_item_classes"])

        observed = health(regressions=[regression(before_runs=1, before_failures=1)])
        self.assertEqual(observed["state"], "UNKNOWN")

        unresolved = health(regressions=[regression(after_failures=3)])
        self.assertEqual(unresolved["state"], "BLOCKED")
        self.assertIn("quality_regression_unresolved", unresolved["work_item_classes"])

    def test_performance_and_recovery_are_external_dimensions_without_recalculation(self):
        passed = health(external=True, perf=performance(), rec=recovery())
        self.assertEqual(passed["state"], "PASS")
        self.assertEqual(passed["external_dimensions"]["performance"]["status"], "HEALTHY")
        self.assertIn("run:performance:001", passed["evidence_refs"])
        self.assertFalse(passed["external_dimensions"]["recovery"]["recalculated"])

        degraded = health(external=True, perf=performance("DEGRADED"), rec=recovery())
        self.assertEqual(degraded["state"], "DEGRADED")
        unknown = health(external=True, perf=performance(), rec=recovery("UNKNOWN"))
        self.assertEqual(unknown["state"], "UNKNOWN")

        missing = health(external=True, perf=None, rec=None)
        self.assertEqual(missing["state"], "UNKNOWN")
        self.assertEqual(
            missing["external_dimensions"]["performance"]["status"],
            "UNKNOWN",
        )
        self.assertEqual(
            missing["external_dimensions"]["recovery"]["status"],
            "UNKNOWN",
        )

    def test_readiness_projection_reuses_quality_health_and_unknown_or_blocked_never_ready(self):
        passed = health()
        projected = readiness_projection(passed)
        self.assertTrue(projected["ready"])
        self.assertEqual(projected["quality_health"], passed["state"])
        self.assertFalse(projected["recalculated"])

        degraded_rows = gates(); degraded_rows[2]["status"] = "FAIL"
        degraded = health(degraded_rows)
        self.assertTrue(readiness_projection(degraded)["ready"])

        for candidate in (
            health(gates()[:-1]),
            health([{**gates()[0], "status": "FAIL"}, *gates()[1:]]),
        ):
            projected = readiness_projection(candidate)
            self.assertFalse(projected["ready"])
            self.assertTrue(projected["critical_blocker"])
            self.assertEqual(projected["quality_health"], candidate["state"])

    def test_corrective_classes_materialize_through_existing_work_item_and_dispatcher_contracts(self):
        rows = gates(); rows[0]["status"] = "FAIL"
        blocked = health(rows)
        classes = quality_work_item_classes(blocked)
        self.assertIn("quality_gate_failed", classes)
        payload = {
            "work_id": "quality-fix-347", "origin_mode": "automatic",
            "origin_system": "factory", "group_id": "pl0n3r",
            "work_type": "engineering", "requested_capabilities": ["python"],
            "required_roles": ["qa"], "authority_level": "standard",
            "producer_ref": "quality-health-v1", "priority_class": "high",
            "depends_on": [], "claims": ["quality/status.py"],
            "policy_ref": "factory:quality", "evidence_refs": blocked["evidence_refs"],
            "idempotency_key": classes[0],
        }
        context = WorkItemReadinessContext(
            authority_valid=True, policy_valid=True,
            freshness_valid=True, evidence_valid=True,
        )
        candidate = candidate_from_work_item(payload, context)
        self.assertTrue(classify_readiness(candidate).ready)

    def test_invalid_sensitive_future_stale_or_incoherent_evidence_fails_closed_without_echo(self):
        sensitive = gates(); sensitive[0]["evidence_ref"] = "token=supersecretvalue"
        with self.assertRaises(QualityStatusError) as caught:
            health(sensitive)
        self.assertNotIn("supersecretvalue", str(caught.exception))

        future = gates(); future[0]["observed_at"] = "2026-09-29T04:00:00Z"
        with self.assertRaises(QualityStatusError):
            health(future)

        stale = gates(); stale[0]["observed_at"] = "2026-09-29T00:00:00Z"
        self.assertEqual(health(stale)["state"], "UNKNOWN")
        self.assertIn("quality_evidence_stale", health(stale)["work_item_classes"])

        duplicate = gates() + [copy.deepcopy(gates()[0])]
        with self.assertRaises(QualityStatusError):
            health(duplicate)

        leaked_recovery = recovery()
        leaked_recovery["reasons"] = ["token=supersecretvalue"]
        with self.assertRaises(QualityStatusError) as caught:
            health(external=True, perf=performance(), rec=leaked_recovery)
        self.assertNotIn("supersecretvalue", str(caught.exception))

    def test_docs_define_quality_health_boundary_without_parallel_queue_or_recalculation(self):
        text = (ROOT / "docs" / "quality-health.md").read_text(encoding="utf-8")
        for marker in (
            "PASS", "DEGRADED", "UNKNOWN", "BLOCKED", "Readiness #293",
            "Factory Queue #269", "Performance #304", "Recovery #305",
            "authority = unchanged", "execute_actions = false",
            "sin scheduler", "sin recalcular",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
