"""Factory #1824: veinte requisitos de performance, sin red ni datos reales.

Las aserciones A invocan las funciones de producción con fixtures sintéticos.
La autenticación del caller GitHub (C) no puede probarse en el adaptador puro.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from performance.contract import PerformanceContractError, validate_performance_contract
from performance.detector import PerformanceDetectionError, detect_performance
from performance.status import (
    PerformanceStatusError, derive_performance_status, readiness_projection,
)
from performance.github_actions_ci import (
    PerformanceCiObservationError, evaluate_factoryrunner_ci_run,
)

ROOT = Path(__file__).resolve().parents[1]
AT = "2026-10-29T12:01:00Z"
NOW = "2026-10-29T12:03:00Z"
ROWS = (
    "docs/performance-contract.md:L30-U1",
    "docs/performance-contract.md:L7-U1",
    "docs/performance-contract.md:L9-U1",
    "docs/performance-detection.md:L11-U1",
    "docs/performance-detection.md:L12-U1",
    "docs/performance-detection.md:L13-U1",
    "docs/performance-detection.md:L16-U1",
    "docs/performance-detection.md:L9-U1",
    "docs/performance-engineering.md:L11-U1",
    "docs/performance-engineering.md:L12-U1",
    "docs/performance-engineering.md:L13-U1",
    "docs/performance-engineering.md:L14-U1",
    "docs/performance-engineering.md:L16-U1",
    "docs/performance-engineering.md:L20-U1",
    "docs/performance-github-actions-ci.md:L11-U1",
    "docs/performance-github-actions-ci.md:L11-U2",
    "docs/performance-github-actions-ci.md:L13-U1",
    "docs/performance-github-actions-ci.md:L15-U1",
    "docs/performance-github-actions-ci.md:L9-U1",
    "docs/performance-github-actions-ci.md:L9-U3",
)
EXTERNAL = {
    "docs/performance-github-actions-ci.md:L9-U1": (
        "C: autenticación GET y correlación con run solicitado corresponden "
        "al caller; el adaptador puro no autentica HTTP ni firmas."
    ),
}


def contract(*, project="synthetic", samples=20, window=300, unit="ms"):
    return {
        "version": 1, "project": project,
        "surfaces": [{
            "id": "ci.workflow" if project == "factoryrunner" else "inventory",
            "label": "Synthetic surface", "metrics": [{
                "id": "workflow_elapsed" if project == "factoryrunner" else "latency_p95",
                "label": "Synthetic elapsed",
                "baseline": {"value": 90, "unit": unit, "observed_at": AT},
                "budget": {"operator": "lte", "value": 120, "unit": unit},
                "window": {"duration_seconds": window, "min_samples": samples},
                "freshness": {"max_age_seconds": 3600},
                "evidence": {"source": "synthetic", "ref": "synthetic:baseline",
                             "observed_at": AT},
                "allowed_actions": ["observe", "diagnose", "benchmark"],
                "escalation_conditions": ["capacity_budget"],
            }],
        }],
    }


def observation(**overrides):
    data = {
        "version": 1, "project": "synthetic", "surface": "inventory",
        "metric": "latency_p95", "value": 150, "unit": "ms",
        "observed_at": AT, "window_seconds": 300, "sample_count": 20,
        "severity": "high", "operational_impact": False,
        "bottleneck": "unknown", "evidence_ref": "synthetic:observation",
        "sha": "a" * 40, "release": "test",
    }
    data.update(overrides)
    return data


def ci_run(**overrides):
    data = {
        "id": 42, "name": "CI", "event": "push", "head_branch": "main",
        "head_sha": "b" * 40, "status": "completed", "conclusion": "success",
        "run_attempt": 1, "run_started_at": "2026-10-29T12:00:00Z",
        "updated_at": AT,
        "repository": {"full_name": "pl0n3r/FactoryRunner"},
    }
    data.update(overrides)
    return data


class CoberturaFactory33Tests(unittest.TestCase):
    def detection(self, **changes):
        return detect_performance(contract(), observation(**changes), evaluated_at=NOW)

    def test_contrato_principal(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        expected, found = set(ROWS), {}
        for line in matrix.splitlines():
            match = re.match(r"^\| \`(docs/performance-[^\`]+:L\d+-U\d+)\` \|", line)
            if match and match.group(1) in expected:
                self.assertNotIn(match.group(1), found)
                found[match.group(1)] = line
        self.assertEqual(20, len(expected))
        self.assertEqual(expected, set(found))
        for row, line in found.items():
            with self.subTest(row=row):
                self.assertIn("NO_VERIFICABLE", line)

        proved = set()

        def prove(row, condition):
            self.assertIn(row, expected - EXTERNAL.keys())
            self.assertTrue(condition, "No ejercido: " + row)
            proved.add(row)

        metric = validate_performance_contract(contract())["surfaces"][0]["metrics"][0]
        good = self.detection(value=100)
        breach = self.detection()
        stale = self.detection(observed_at="2026-10-29T09:00:00Z")
        short = self.detection(window_seconds=10)
        sparse = self.detection(sample_count=1)
        incident = self.detection(severity="critical", operational_impact=True)
        healthy = derive_performance_status(good)
        degraded = derive_performance_status(breach)
        blocked = derive_performance_status(incident)
        unknown = derive_performance_status(stale)
        projected = readiness_projection(healthy)

        prove("docs/performance-contract.md:L7-U1", set(metric) == {
            "id", "label", "baseline", "budget", "window", "freshness",
            "evidence", "allowed_actions", "escalation_conditions",
        })
        prove("docs/performance-contract.md:L9-U1", metric["baseline"] == {
            "value": 90, "unit": "ms", "observed_at": AT,
        })
        prove("docs/performance-contract.md:L30-U1",
              projected["dimension"] == "performance" and
              projected["status"] == "HEALTHY" and
              projected["source"] == "performance-v1")
        prove("docs/performance-detection.md:L9-U1",
              stale["classification"] == "PERF_REVIEW" and
              stale["evidence_state"] == "STALE")
        prove("docs/performance-detection.md:L11-U1",
              all(x["classification"] == "PERF_REVIEW" and
                  x["evidence_state"] != "CURRENT" for x in (stale, short, sparse)))
        prove("docs/performance-detection.md:L12-U1",
              good["classification"] == "PERF_INFO" and not good["breach"] and
              good["evidence_state"] == "CURRENT")
        prove("docs/performance-detection.md:L13-U1",
              breach["classification"] == "PERF_DEGRADATION" and
              breach["breach"] and breach["evidence_state"] == "CURRENT")
        prove("docs/performance-detection.md:L16-U1",
              breach["classification"] != "PERF_INCIDENT" and
              self.detection(severity="critical")["classification"] != "PERF_INCIDENT")

        remediation = {
            "decision": "ESCALATE", "authority": "unchanged", "execute_actions": False,
        }
        escalated = derive_performance_status(good, remediation=remediation)
        comparison = {
            "decision": "REVERT_OR_REPLAN", "authority": "unchanged",
            "execute_actions": False, "before_evidence_ref": "synthetic:before",
            "after_evidence_ref": "synthetic:after",
        }
        not_adopted = derive_performance_status(good, comparison=comparison)
        prove("docs/performance-engineering.md:L11-U1",
              unknown["status"] == "UNKNOWN")
        prove("docs/performance-engineering.md:L12-U1",
              blocked["status"] == "BLOCKED" and escalated["status"] == "BLOCKED")
        prove("docs/performance-engineering.md:L13-U1",
              degraded["status"] == "DEGRADED")
        prove("docs/performance-engineering.md:L14-U1",
              healthy["status"] == "HEALTHY" and not_adopted["status"] == "DEGRADED")
        prove("docs/performance-engineering.md:L16-U1",
              derive_performance_status(
                  incident, comparison={**comparison, "decision": "ADOPT"}
              )["status"] == "BLOCKED")
        prove("docs/performance-engineering.md:L20-U1",
              unknown["status"] != "HEALTHY" and
              derive_performance_status(sparse)["status"] == "UNKNOWN")

        ci_contract = contract(project="factoryrunner", samples=1, window=1, unit="s")
        ci = evaluate_factoryrunner_ci_run(
            ci_contract,
            ci_run(actor={"login": "SYNTHETIC_MARKER_33"},
                   jobs=[{"name": "SYNTHETIC_MARKER_33"}]),
            evaluated_at=NOW,
        )
        finding = ci["detection"]
        prove("docs/performance-github-actions-ci.md:L11-U1",
              finding["metric"] == "workflow_elapsed" and
              finding["observed"]["sample_count"] == 1 and
              finding["evidence_state"] == "CURRENT")
        prove("docs/performance-github-actions-ci.md:L11-U2",
              finding["bottleneck"] == "unknown" and
              finding["operational_impact"] is False and
              finding["metric"] != "latency_p95")
        with self.assertRaises(PerformanceCiObservationError):
            evaluate_factoryrunner_ci_run(
                ci_contract, ci_run(status="in_progress"), evaluated_at=NOW,
            )
        prove("docs/performance-github-actions-ci.md:L13-U1", True)
        prove("docs/performance-github-actions-ci.md:L15-U1",
              ci["authority"] == "unchanged" and
              ci["create_work_item"] is False and ci["execute_actions"] is False and
              set(ci_contract["surfaces"][0]["metrics"][0]["allowed_actions"]) ==
              {"observe", "diagnose", "benchmark"})
        prove("docs/performance-github-actions-ci.md:L9-U3",
              "SYNTHETIC_MARKER_33" not in json.dumps(ci) and
              "jobs" not in ci and "actor" not in ci)
        self.assertEqual(set(ROWS) - EXTERNAL.keys(), proved)
        self.assertEqual(1, len(EXTERNAL))
        self.assertIn("caller", next(iter(EXTERNAL.values())))

    def test_falla_cerrado(self):
        for field in ("baseline", "budget", "window", "freshness", "evidence"):
            with self.subTest(field=field):
                payload = contract()
                del payload["surfaces"][0]["metrics"][0][field]
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(payload)
        invalid = contract()
        invalid["surfaces"][0]["metrics"][0]["baseline"]["observed_at"] = "2026-10-29T12:00:00"
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(invalid)
        forbidden = contract()
        forbidden["surfaces"][0]["metrics"][0]["allowed_actions"] = ["write_production"]
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(forbidden)
        unknown = self.detection(metric="does_not_exist")
        self.assertEqual((unknown["evidence_state"], unknown["classification"]),
                         ("UNKNOWN", "PERF_REVIEW"))
        self.assertEqual(derive_performance_status(unknown)["status"], "UNKNOWN")
        with self.assertRaises(PerformanceDetectionError):
            self.detection(unit="s")
        with self.assertRaises(PerformanceDetectionError):
            self.detection(evidence_ref="user@example.invalid")
        with self.assertRaises(PerformanceStatusError):
            derive_performance_status(
                self.detection(value=100),
                remediation={"decision": "AUTO_REPAIR", "authority": "changed",
                             "execute_actions": True},
            )
        with self.assertRaises(PerformanceStatusError):
            readiness_projection({
                "status": "HEALTHY", "authority": "changed", "execute_actions": True,
            })
        ci_contract = contract(project="factoryrunner", samples=1, window=1, unit="s")
        for bad in (
            ci_run(repository={"full_name": "foreign/FactoryRunner"}),
            ci_run(event="pull_request"), ci_run(head_branch="feature"),
            ci_run(conclusion="failure"), ci_run(run_attempt=0),
            ci_run(id=True), ci_run(updated_at="bad-date"),
            ci_run(updated_at="2026-10-29T11:59:00Z"),
        ):
            with self.subTest(run=bad), self.assertRaises(PerformanceCiObservationError):
                evaluate_factoryrunner_ci_run(ci_contract, bad, evaluated_at=NOW)
        stale = evaluate_factoryrunner_ci_run(
            ci_contract, ci_run(), evaluated_at="2026-11-03T12:03:00Z",
        )
        self.assertEqual("UNKNOWN", stale["performance_status"]["status"])
        self.assertFalse(stale["execute_actions"])
        self.assertFalse(stale["create_work_item"])

    def test_sin_datos_reales(self):
        valid = validate_performance_contract(contract())
        self.assertEqual("synthetic", valid["project"])
        self.assertEqual("synthetic",
                         valid["surfaces"][0]["metrics"][0]["evidence"]["source"])
        source = Path(__file__).read_text(encoding="utf-8")
        for module in ("requests", "socket", "urllib", "subprocess"):
            self.assertNotIn("import " + module, source)
        self.assertNotIn("-----BEGIN " + "PRIVATE KEY-----", source)
        self.assertFalse(derive_performance_status(self.detection())["execute_actions"])


if __name__ == "__main__":
    unittest.main()
