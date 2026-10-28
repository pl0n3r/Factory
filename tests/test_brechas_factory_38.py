"""Regresiones offline de las 16 unidades de cobertura Factory #1656.

La evidencia sintética no implica performance ni readiness en producción.
"""
from __future__ import annotations

import json
import statistics
import unittest
from pathlib import Path

from scripts.orquestador_kit import (
    PlannedTask, build_task_marker, claims_overlap, reservation_blockers,
    verified_changed_file_overlap,
)
from performance.contract import validate_performance_contract
from performance.detector import detect_performance
from performance.ci_professional_report import diagnose_factoryrunner_ci_professionals
from performance.github_actions_ci import PerformanceCiObservationError

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = "2026-10-01T11:47:49Z"
EVALUATED = "2026-10-01T12:00:00Z"
SAMPLES = {
    "public.home.mobile": {"fcp": (380, 468, 380), "lcp": (1600, 1768, 1624), "cls": (0, 0, 0)},
    "public.home.desktop": {"fcp": (456, 788, 440), "lcp": (1772, 2352, 1748), "cls": (0.005, 0.004, 0.005)},
}
UNITS = (
    "docs/orquestador.md:B02", "docs/orquestador.md:B04",
    "docs/performance-brvtal.md:L3-U1", "docs/performance-brvtal.md:L17-U1",
    "docs/performance-brvtal.md:L18-U1", "docs/performance-brvtal.md:L20-U1",
    "docs/performance-brvtal.md:L20-U2", "docs/performance-brvtal.md:L20-U3",
    "docs/performance-brvtal.md:L26-U1", "docs/performance-brvtal.md:L27-U1",
    "docs/performance-brvtal.md:L28-U1", "docs/performance-brvtal.md:L30-U1",
    "docs/performance-brvtal.md:L34-U1", "docs/performance-brvtal.md:L36-U1",
    "docs/performance-ci-professional-report.md:L14-U1",
    "docs/performance-ci-professional-report.md:L15-U1",
)


def planned(number, paths, *, owner="pl0n3r", status="estado: disponible", dependencies=()):
    marker = build_task_marker(
        epic=1082,
        task=PlannedTask(
            key=f"SYNTH_{number}", title="Fixture synthetic", owner=owner,
            paths=tuple(paths), depends_on=(),
        ),
        order=number, roles=["ingenieria-software"],
        dependency_issues=list(dependencies),
    )
    return {
        "number": number, "state": "open",
        "labels": [{"name": status}], "body": marker,
    }


def observation(surface, metric, *, value=100, observed_at=OBSERVED):
    return {
        "version": 1, "project": "brvtal", "surface": surface,
        "metric": metric, "value": value,
        "unit": "ratio" if metric == "cls" else "ms",
        "observed_at": observed_at, "window_seconds": 1,
        "sample_count": 1, "severity": "info", "operational_impact": False,
        "bottleneck": "frontend", "evidence_ref": "github:synthetic/actions/runs/1",
        "sha": "a" * 40, "release": "test-only",
    }


def ci_run():
    return {
        "id": 40119747013, "name": "CI", "event": "push",
        "head_branch": "main", "head_sha": "b" * 40,
        "status": "completed", "conclusion": "success",
        "run_attempt": 1, "run_started_at": "2026-10-24T18:13:54Z",
        "updated_at": "2026-10-24T18:16:04Z",
        "repository": {"full_name": "pl0n3r/FactoryRunner"},
    }


class BrechasFactory38Tests(unittest.TestCase):
    def setUp(self):
        self.brvtal = validate_performance_contract(json.loads(
            (ROOT / "performance/contracts/brvtal.json").read_text(encoding="utf-8")
        ))
        self.runner = validate_performance_contract(json.loads(
            (ROOT / "performance/contracts/factoryrunner.json").read_text(encoding="utf-8")
        ))

    def test_contrato_principal(self):
        """Cada ID tiene una regresión real o un límite de evidencia explícito."""
        candidate = planned(30, ["tests/unique.py"])
        other = planned(31, ["tests/other.py"], status="estado: reservado")
        orq = (ROOT / "docs/orquestador.md").read_text(encoding="utf-8")
        doc = (ROOT / "docs/performance-brvtal.md").read_text(encoding="utf-8")
        runner_doc = (ROOT / "docs/performance-ci-professional-report.md").read_text(encoding="utf-8")
        metrics = {
            s["id"]: {m["id"]: m for m in s["metrics"]}
            for s in self.brvtal["surfaces"]
        }
        expected = {
            s: {m: statistics.median(values) for m, values in measurements.items()}
            for s, measurements in SAMPLES.items()
        }
        same_sha = "a" * 40
        collision = verified_changed_file_overlap(
            ("src/",), ("src/",),
            left_files=["src/Café.php"], right_files=["src/cafe\u0301.php"],
            left_head=same_sha, right_head=same_sha,
            left_evidence_head=same_sha, right_evidence_head=same_sha,
            left_complete=True, right_complete=True,
            other_issue=31, other_lease="synthetic-only",
        )
        report = diagnose_factoryrunner_ci_professionals(
            self.runner, ci_run(), evaluated_at="2026-10-24T20:00:00Z",
        )
        runner_actions = self.runner["surfaces"][0]["metrics"][0]["allowed_actions"]
        unknown = detect_performance(
            self.brvtal, observation("public.home.mobile", "dom_content_loaded"),
            evaluated_at=EVALUATED,
        )
        checks = {
            "docs/orquestador.md:B02": (
                not reservation_blockers(candidate, [candidate, other], "pl0n3r", {})
                and "actor debe coincidir" in orq
            ),
            "docs/orquestador.md:B04": (
                claims_overlap("src/Café.php", "src/cafe\u0301.php")
                and collision["safe"] is False
                and collision["reason"] == "shared_changed_files"
                and "renombrados" in orq
            ),
            "docs/performance-brvtal.md:L3-U1": (
                self.brvtal["project"] == "brvtal"
                and "laboratorio" in doc and "Factory #304" in doc
            ),
            "docs/performance-brvtal.md:L17-U1": (
                all(metrics["public.home.mobile"][m]["baseline"]["value"] == v
                    for m, v in expected["public.home.mobile"].items())
                and expected["public.home.mobile"] == {"fcp": 380, "lcp": 1624, "cls": 0}
            ),
            "docs/performance-brvtal.md:L18-U1": (
                all(metrics["public.home.desktop"][m]["baseline"]["value"] == v
                    for m, v in expected["public.home.desktop"].items())
                and expected["public.home.desktop"] == {"fcp": 456, "lcp": 1772, "cls": 0.005}
            ),
            "docs/performance-brvtal.md:L20-U1": (
                "production-performance-36853443439" in doc
                and "11160130127" in doc
                and "2026-10-01T11:47:44Z" in doc
            ),
            "docs/performance-brvtal.md:L20-U2": all(
                m["baseline"]["observed_at"] == OBSERVED
                and m["evidence"]["observed_at"] == OBSERVED
                for s in self.brvtal["surfaces"] for m in s["metrics"]
            ),
            "docs/performance-brvtal.md:L20-U3": all(
                v in doc for v in ("36786118661", "36853443439", "attempt 1", "attempt 2", OBSERVED)
            ),
            "docs/performance-brvtal.md:L26-U1": all(
                metrics[s]["fcp"]["budget"] == {"operator": "lte", "value": 1800, "unit": "ms"}
                for s in metrics
            ),
            "docs/performance-brvtal.md:L27-U1": all(
                metrics[s]["lcp"]["budget"] == {"operator": "lte", "value": 2500, "unit": "ms"}
                for s in metrics
            ),
            "docs/performance-brvtal.md:L28-U1": all(
                metrics[s]["cls"]["budget"] == {"operator": "lte", "value": 0.1, "unit": "ratio"}
                for s in metrics
            ),
            "docs/performance-brvtal.md:L30-U1": (
                "p75" in doc and "CrUX" in doc and "solo los valores numéricos" in doc
                and all(
                    m["window"] == {"duration_seconds": 1, "min_samples": 1}
                    for s in self.brvtal["surfaces"] for m in s["metrics"]
                )
            ),
            "docs/performance-brvtal.md:L34-U1": all(
                m["freshness"]["max_age_seconds"] == 604800
                for s in self.brvtal["surfaces"] for m in s["metrics"]
            ),
            "docs/performance-brvtal.md:L36-U1": (
                unknown["classification"] == "PERF_REVIEW"
                and unknown["evidence_state"] == "UNKNOWN"
                and unknown["budget"] is None
            ),
            "docs/performance-ci-professional-report.md:L14-U1": (
                set(runner_actions) == {"observe", "diagnose", "benchmark"}
                and "observe, diagnose, benchmark" in runner_doc
            ),
            "docs/performance-ci-professional-report.md:L15-U1": (
                not ({"create_work_item", "auto_repair"} & set(runner_actions))
                and report["authority"] == "unchanged"
                and all(
                    report[k] is False
                    for k in ("create_work_item", "execute_actions", "dispatch", "adopt", "candidate_terminal")
                )
            ),
        }
        self.assertEqual(set(checks), set(UNITS))
        self.assertEqual(len(UNITS), 16)
        for unit, satisfied in checks.items():
            with self.subTest(unit=unit):
                self.assertTrue(satisfied, f"{unit}: falta evidencia; NO_VERIFICABLE")

    def test_falla_cerrado(self):
        """Owner/depends_on/claims, HEAD obsoleto y CI no canónico deniegan."""
        candidate = planned(30, ["tests/new.py"])
        foreign = planned(31, ["tests/foreign.py"], owner="another-user")
        self.assertTrue(reservation_blockers(foreign, [foreign], "pl0n3r", {}))
        dependent = planned(32, ["tests/dependent.py"], dependencies=(29,))
        self.assertTrue(reservation_blockers(dependent, [dependent], "pl0n3r", {}))
        collision = planned(33, ["tests/new.py"], status="estado: reservado")
        self.assertTrue(reservation_blockers(candidate, [candidate, collision], "pl0n3r", {}))
        stale = verified_changed_file_overlap(
            ("src/",), ("src/",), left_files=["src/a.py"], right_files=["src/b.py"],
            left_head="a" * 40, right_head="b" * 40,
            left_evidence_head="c" * 40, right_evidence_head="b" * 40,
            left_complete=True, right_complete=True,
            other_issue=33, other_lease="synthetic-only",
        )
        self.assertFalse(stale["safe"])
        self.assertEqual(stale["reason"], "diff_stale_or_incomplete")
        with self.assertRaises(PerformanceCiObservationError):
            invalid = ci_run()
            invalid["status"] = "in_progress"
            diagnose_factoryrunner_ci_professionals(
                self.runner, invalid, evaluated_at="2026-10-24T20:00:00Z",
            )

    def test_sin_datos_reales(self):
        """Se usa una proyección sintética y se descartan campos arbitrarios."""
        run = ci_run()
        run["extra_private_payload"] = "synthetic-must-never-appear"
        report = diagnose_factoryrunner_ci_professionals(
            self.runner, run, evaluated_at="2026-10-24T20:00:00Z",
        )
        self.assertNotIn(run["extra_private_payload"], repr(report))
        self.assertFalse(any(k in report for k in (
            "token", "authorization", "headers", "raw_logs",
        )))
        self.assertFalse(report["execute_actions"])
        self.assertEqual(
            observation("public.home.mobile", "fcp")["evidence_ref"],
            "github:synthetic/actions/runs/1",
        )
        self.assertEqual(run["repository"]["full_name"], "pl0n3r/FactoryRunner")

    def test_estados_unknown_explicitos(self):
        """Sin budget o con evidencia stale nunca se infiere aprobación."""
        for metric in ("dom_content_loaded", "load_event_end"):
            with self.subTest(metric=metric):
                state = detect_performance(
                    self.brvtal, observation("public.home.mobile", metric),
                    evaluated_at=EVALUATED,
                )
                self.assertEqual(
                    (state["classification"], state["evidence_state"]),
                    ("PERF_REVIEW", "UNKNOWN"),
                )
                self.assertIsNone(state["budget"])
                self.assertIsNone(state["breach"])
        stale = diagnose_factoryrunner_ci_professionals(
            self.runner, ci_run(), evaluated_at="2026-11-10T20:00:00Z",
        )
        self.assertEqual(stale["status"], "UNKNOWN")
        self.assertEqual(stale["readiness"]["status"], "UNKNOWN")
        self.assertEqual(stale["team"]["decision"], "NO_ASSIGNMENT")
        self.assertFalse(stale["create_work_item"])


if __name__ == "__main__":
    unittest.main()
