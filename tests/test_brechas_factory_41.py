"""Factory #1659: regresión offline de 16 unidades del Performance Loop.

Fixtures sintéticos exclusivamente; no se acredita producción, remediación ni go-live.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from performance.contract import PerformanceContractError, validate_performance_contract
from performance.detector import PerformanceDetectionError, detect_performance
from performance.github_actions_ci import (
    PerformanceCiObservationError, evaluate_factoryrunner_ci_run,
)
from performance.status import (
    PerformanceStatusError, derive_performance_status, readiness_projection,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-28T20:06:00Z"
IDS = (
    "docs/performance-contract.md:L7-U1",
    "docs/performance-contract.md:L9-U1",
    "docs/performance-detection.md:L9-U1",
    "docs/performance-detection.md:L11-U1",
    "docs/performance-detection.md:L12-U1",
    "docs/performance-detection.md:L13-U1",
    "docs/performance-detection.md:L16-U1",
    "docs/performance-engineering.md:L11-U1",
    "docs/performance-engineering.md:L12-U1",
    "docs/performance-engineering.md:L13-U1",
    "docs/performance-engineering.md:L14-U1",
    "docs/performance-engineering.md:L16-U1",
    "docs/performance-engineering.md:L20-U1",
    "docs/performance-github-actions-ci.md:L11-U1",
    "docs/performance-github-actions-ci.md:L11-U2",
    "docs/performance-github-actions-ci.md:L13-U1",
)


def contract():
    metric = {
        "id": "duration", "label": "Duration",
        "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "synthetic", "ref": "fixture:perf41", "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["observe", "diagnose", "benchmark"],
        "escalation_conditions": ["capacity_budget"],
    }
    return {"version": 1, "project": "syntheticapp",
            "surfaces": [{"id": "api", "label": "Synthetic API", "metrics": [metric]}]}


def observation(**changes):
    row = {
        "version": 1, "project": "syntheticapp", "surface": "api", "metric": "duration",
        "value": 300, "unit": "ms", "observed_at": "2026-09-28T20:05:00Z",
        "window_seconds": 300, "sample_count": 30,
        "severity": "high", "operational_impact": False, "bottleneck": "unknown",
        "evidence_ref": "fixture:observation41", "sha": "a" * 40, "release": "v1.0.0",
    }
    row.update(changes)
    return row


def detect(**changes):
    return detect_performance(contract(), observation(**changes), evaluated_at=NOW)


def ci_run(**changes):
    row = {
        "id": 12345678, "name": "CI", "event": "push", "head_branch": "main",
        "head_sha": "b" * 40, "status": "completed", "conclusion": "success",
        "run_attempt": 1, "run_started_at": "2026-10-23T21:53:07Z",
        "updated_at": "2026-10-23T21:56:09Z",
        "repository": {"full_name": "pl0n3r/FactoryRunner"},
    }
    row.update(changes)
    return row


def ci_contract():
    return json.loads((ROOT / "performance/contracts/factoryrunner.json").read_text(encoding="utf-8"))


def ci_evaluate(**changes):
    return evaluate_factoryrunner_ci_run(
        ci_contract(), ci_run(**changes), evaluated_at="2026-10-24T16:27:00Z",
    )


class BrechasFactory41Tests(unittest.TestCase):
    def test_contrato_principal(self):
        validated = validate_performance_contract(contract())
        metric = validated["surfaces"][0]["metrics"][0]
        stale = detect(observed_at="2026-09-28T19:00:00Z")
        short = detect(window_seconds=30)
        insufficient = detect(sample_count=2)
        missing = detect(metric="missing_metric")
        good = detect(value=220)
        breach = detect()
        critical = detect(severity="critical", operational_impact=False)
        incident = detect(severity="critical", operational_impact=True)
        good_state = derive_performance_status(good)
        bad_state = derive_performance_status(breach)
        incident_state = derive_performance_status(incident)
        stale_state = derive_performance_status(stale)
        blocked = derive_performance_status(good, remediation={
            "decision": "BLOCKED", "authority": "unchanged", "execute_actions": False,
        })
        not_adopted = derive_performance_status(good, comparison={
            "decision": "REVERT_OR_REPLAN", "authority": "unchanged",
            "execute_actions": False, "before_evidence_ref": "fixture:before41",
            "after_evidence_ref": "fixture:after41",
        })
        ci = ci_evaluate()
        ci_result = ci["detection"]
        try:
            ci_evaluate(status="in_progress")
        except PerformanceCiObservationError:
            invalid_rejected = True
        else:
            invalid_rejected = False

        checks = {
            "docs/performance-contract.md:L7-U1": (
                set(metric) == {
                    "id", "label", "baseline", "budget", "window",
                    "freshness", "evidence", "allowed_actions", "escalation_conditions",
                } and metric["budget"] == {"operator": "lte", "value": 250, "unit": "ms"}
            ),
            "docs/performance-contract.md:L9-U1": (
                metric["baseline"] == {"value": 180, "unit": "ms",
                                      "observed_at": "2026-09-28T20:00:00Z"}
            ),
            "docs/performance-detection.md:L9-U1": (
                missing["evidence_state"] == "UNKNOWN" and
                missing["classification"] == "PERF_REVIEW" and missing["breach"] is None
            ),
            "docs/performance-detection.md:L11-U1": all(
                f["classification"] == "PERF_REVIEW" and f["evidence_state"] != "CURRENT"
                for f in (stale, short, insufficient)
            ),
            "docs/performance-detection.md:L12-U1": (
                good["evidence_state"] == "CURRENT" and
                good["classification"] == "PERF_INFO" and good["breach"] is False
            ),
            "docs/performance-detection.md:L13-U1": (
                breach["evidence_state"] == "CURRENT" and
                breach["classification"] == "PERF_DEGRADATION" and breach["breach"] is True
            ),
            "docs/performance-detection.md:L16-U1": (
                critical["classification"] == "PERF_DEGRADATION" and
                incident["classification"] == "PERF_INCIDENT" and
                incident["operational_impact"] is True
            ),
            "docs/performance-engineering.md:L11-U1": stale_state["status"] == "UNKNOWN",
            "docs/performance-engineering.md:L12-U1": (
                incident_state["status"] == "BLOCKED" and blocked["status"] == "BLOCKED"
            ),
            "docs/performance-engineering.md:L13-U1": bad_state["status"] == "DEGRADED",
            "docs/performance-engineering.md:L14-U1": (
                good_state["status"] == "HEALTHY" and not_adopted["status"] == "DEGRADED"
            ),
            "docs/performance-engineering.md:L16-U1": (
                blocked["status"] == "BLOCKED" and incident_state["status"] == "BLOCKED"
                and "score" not in incident_state
            ),
            "docs/performance-engineering.md:L20-U1": (
                readiness_projection(stale_state)["status"] == "UNKNOWN" and
                readiness_projection(stale_state)["evidence_state"] != "CURRENT"
            ),
            "docs/performance-github-actions-ci.md:L11-U1": (
                ci_result["observed"]["sample_count"] == 1 and
                ci_contract()["surfaces"][0]["metrics"][0]["window"]["min_samples"] == 1
                and ci_result["evidence_state"] == "CURRENT"
            ),
            "docs/performance-github-actions-ci.md:L11-U2": (
                ci_result["bottleneck"] == "unknown"
                and ci_result["operational_impact"] is False
                and ci_result["severity"] == "medium"
                and ci["authority"] == "unchanged"
                and ci["execute_actions"] is False
                and ci["create_work_item"] is False
                and ci["candidate_terminal"] is False
            ),
            "docs/performance-github-actions-ci.md:L13-U1": invalid_rejected,
        }
        self.assertEqual(set(checks), set(IDS))
        for requirement, correct in checks.items():
            with self.subTest(requirement=requirement):
                self.assertTrue(correct, "falta evidencia ejecutable: " + requirement)

    def test_falla_cerrado(self):
        for field in ("baseline", "budget", "window", "freshness", "evidence"):
            with self.subTest(missing=field):
                payload = contract()
                del payload["surfaces"][0]["metrics"][0][field]
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(payload)
        for field, invalid in (("unit", "s"), ("observed_at", "no-time")):
            with self.subTest(field=field):
                payload = contract()
                payload["surfaces"][0]["metrics"][0]["baseline"][field] = invalid
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(payload)
        for changes in (
            {"sample_count": 1}, {"window_seconds": 1},
            {"observed_at": "2026-09-28T19:00:00Z"}, {"project": "anotherapp"},
        ):
            with self.subTest(changes=changes):
                finding = detect(**changes)
                self.assertEqual(finding["classification"], "PERF_REVIEW")
                self.assertEqual(derive_performance_status(finding)["status"], "UNKNOWN")
        with self.assertRaises(PerformanceDetectionError):
            detect(value=float("nan"))
        with self.assertRaises(PerformanceStatusError):
            readiness_projection({"status": "HEALTHY", "authority": "changed"})
        for changes in (
            {"name": "CodeQL"}, {"event": "pull_request"}, {"status": "queued"},
            {"head_branch": "feature"}, {"conclusion": "cancelled"},
            {"run_attempt": 0}, {"head_sha": "invalid"},
            {"updated_at": "2026-10-23T21:53:06Z"},
        ):
            with self.subTest(ci=changes), self.assertRaises(PerformanceCiObservationError):
                ci_evaluate(**changes)

    def test_sin_datos_reales(self):
        sample = ci_evaluate()
        self.assertEqual(sample["authority"], "unchanged")
        for field in ("execute_actions", "create_work_item", "candidate_terminal"):
            self.assertIs(sample[field], False)
        self.assertEqual(sample["detection"]["identity"]["sha"], "b" * 40)
        self.assertEqual(
            sample["detection"]["evidence_ref"],
            "github:pl0n3r/FactoryRunner/actions/runs/12345678/attempts/1",
        )
        source = (ROOT / "performance/github_actions_ci.py").read_text(encoding="utf-8")
        for forbidden in (
            "requests.post", "urllib.request", "subprocess.run",
            "gh api", "actions/workflows/dispatches",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertEqual(sample["readiness"]["status"], sample["performance_status"]["status"])
        self.assertFalse(derive_performance_status(detect())["parallel_queue"])

    def test_estados_unknown_explicitos(self):
        # No congelar el estado de la matriz: su reconciliación es otra hoja.
        rows = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8").splitlines()
        for key in IDS:
            matching = [line for line in rows if line.startswith("| " + chr(96) + key + chr(96) + " |")]
            with self.subTest(key=key):
                self.assertEqual(len(matching), 1)
        for finding in (
            detect(metric="nonexistent"), detect(sample_count=1),
            detect(window_seconds=1),
            detect(observed_at="2026-09-28T19:00:00Z"),
        ):
            with self.subTest(freshness=finding["evidence_state"]):
                self.assertEqual(finding["classification"], "PERF_REVIEW")
                self.assertNotEqual(finding["evidence_state"], "CURRENT")
                status = derive_performance_status(finding)
                self.assertEqual(status["status"], "UNKNOWN")
                self.assertEqual(readiness_projection(status)["status"], "UNKNOWN")
        stale_ci = evaluate_factoryrunner_ci_run(
            ci_contract(), ci_run(), evaluated_at="2026-11-02T16:27:00Z",
        )
        self.assertEqual(stale_ci["detection"]["evidence_state"], "STALE")
        self.assertEqual(stale_ci["performance_status"]["status"], "UNKNOWN")
        self.assertEqual(stale_ci["readiness"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
