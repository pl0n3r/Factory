"""Cobertura offline de las 16 unidades Factory #1660.

Los snapshots son sintéticos. Una referencia documental a un job de Actions
no autentica su respuesta ni convierte observaciones en HEALTH de producción.
"""
from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

from performance.contract import PerformanceContractError, validate_performance_contract
from performance.detector import detect_performance
from performance.github_actions_ci import (
    PerformanceCiObservationError,
    evaluate_factoryrunner_ci_run,
)
from performance.status import derive_performance_status

ROOT = Path(__file__).resolve().parents[1]
RUN = "38010129128"
JOB = "114087986892"
GRINDFLOW_MAIN = "3c137b21654d30bc5ce123853e58934d973ce4b5"
STARTED = "2026-10-10T00:41:39Z"
COMPLETED = "2026-10-10T00:42:17Z"
EVALUATED = "2026-10-10T00:42:20Z"

UNITS = (
    "docs/performance-github-actions-ci.md:L15-U1",
    "docs/performance-github-actions-ci.md:L9-U1",
    "docs/performance-github-actions-ci.md:L9-U3",
    "docs/performance-grindflow.md:L10-U1",
    "docs/performance-grindflow.md:L10-U2",
    "docs/performance-grindflow.md:L11-U1",
    "docs/performance-grindflow.md:L11-U2",
    "docs/performance-grindflow.md:L11-U3",
    "docs/performance-grindflow.md:L22-U1",
    "docs/performance-grindflow.md:L22-U2",
    "docs/performance-grindflow.md:L22-U3",
    "docs/performance-grindflow.md:L26-U1",
    "docs/performance-grindflow.md:L7-U1",
    "docs/performance-grindflow.md:L7-U2",
    "docs/performance-grindflow.md:L8-U1",
    "docs/performance-grindflow.md:L9-U1",
)

# Estos hechos documentados NO son pruebas autenticadas del job remoto.
# Un test offline no eleva la procedencia externa a CURRENT ni GREEN.
EXTERNAL_GAPS = {
    "docs/performance-grindflow.md:L7-U2": "UNKNOWN",
    "docs/performance-grindflow.md:L8-U1": "UNKNOWN",
    "docs/performance-grindflow.md:L9-U1": "UNKNOWN",
}


def load_contract(name: str) -> dict:
    return json.loads(
        (ROOT / "performance" / "contracts" / (name + ".json")).read_text(
            encoding="utf-8"
        )
    )


def elapsed_seconds(start: str, end: str) -> int:
    def parse(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int((parse(end) - parse(start)).total_seconds())


def synthetic_ci_run() -> dict:
    """Snapshot con forma exacta; NO procede de un GET autenticado."""
    return {
        "id": 101, "name": "CI", "event": "push", "head_branch": "main",
        "head_sha": "a" * 40, "status": "completed", "conclusion": "success",
        "run_attempt": 2, "run_started_at": "2026-10-24T18:13:54Z",
        "updated_at": "2026-10-24T18:16:04Z",
        "repository": {"full_name": "pl0n3r/FactoryRunner"},
    }


def synthetic_smoke(*, surface: str = "ci.production_smoke",
                    metric: str = "job_duration", value: int = 38) -> dict:
    return {
        "version": 1, "project": "grindflow", "surface": surface,
        "metric": metric, "value": value, "unit": "s",
        "observed_at": COMPLETED, "window_seconds": 38,
        "sample_count": 1, "severity": "info", "operational_impact": False,
        "bottleneck": "unknown", "evidence_ref": "github:synthetic/actions/runs/1",
        "sha": "b" * 40, "release": "synthetic",
    }


class BrechasFactory42Tests(unittest.TestCase):
    def setUp(self):
        self.gf_raw = load_contract("grindflow")
        self.gf = validate_performance_contract(self.gf_raw)
        self.fr = validate_performance_contract(load_contract("factoryrunner"))
        self.metric = self.gf["surfaces"][0]["metrics"][0]
        self.gf_doc = (ROOT / "docs/performance-grindflow.md").read_text(
            encoding="utf-8"
        )
        self.ci_doc = (ROOT / "docs/performance-github-actions-ci.md").read_text(
            encoding="utf-8"
        )

    def ci_result(self, run=None, *, evaluated_at="2026-10-24T20:00:00Z"):
        return evaluate_factoryrunner_ci_run(
            self.fr, synthetic_ci_run() if run is None else run,
            evaluated_at=evaluated_at,
        )

    def smoke(self, **changes):
        observed = synthetic_smoke(**changes)
        return detect_performance(self.gf, observed, evaluated_at=EVALUATED)

    def test_contrato_principal(self):
        """AC-01: una aserción de contrato o un gap explícito por cada ID."""
        runner_actions = self.fr["surfaces"][0]["metrics"][0]["allowed_actions"]
        injected = synthetic_ci_run()
        injected["private_fixture"] = "synthetic-extra-never-echo"
        ci = self.ci_result(injected)
        current = self.smoke()
        breach = self.smoke(value=121)
        unmeasured = self.smoke(surface="web.landing", metric="ttfb")
        stale = detect_performance(
            self.gf, synthetic_smoke(), evaluated_at="2026-11-10T00:42:20Z",
        )
        actual_duration = elapsed_seconds(STARTED, COMPLETED)
        gaps = EXTERNAL_GAPS

        checks = {
            "docs/performance-github-actions-ci.md:L15-U1": (
                set(runner_actions) == {"observe", "diagnose", "benchmark"}
                and all(ci[field] is False for field in (
                    "execute_actions", "create_work_item", "candidate_terminal"
                ))
                and ci["authority"] == "unchanged"
            ),
            "docs/performance-github-actions-ci.md:L9-U1": (
                ci["detection"]["evidence_ref"].endswith(
                    "/actions/runs/101/attempts/2"
                )
                and "no verifica firmas" in self.ci_doc
                and ci["detection"]["identity"]["sha"] == "a" * 40
            ),
            "docs/performance-github-actions-ci.md:L9-U3": (
                "synthetic-extra-never-echo" not in repr(ci)
                and ci["detection"]["bottleneck"] == "unknown"
                and ci["detection"]["identity"]["release"] == "ci"
            ),
            "docs/performance-grindflow.md:L7-U1": (
                self.gf["project"] == "grindflow"
                and self.gf["version"] == 1
            ),
            "docs/performance-grindflow.md:L7-U2": (
                "main@" + GRINDFLOW_MAIN in self.gf_doc
                and gaps["docs/performance-grindflow.md:L7-U2"] == "UNKNOWN"
            ),
            "docs/performance-grindflow.md:L8-U1": (
                RUN in self.gf_doc and JOB in self.gf_doc
                and "completed/success" in self.gf_doc
                and gaps["docs/performance-grindflow.md:L8-U1"] == "UNKNOWN"
            ),
            "docs/performance-grindflow.md:L9-U1": (
                STARTED in self.gf_doc and COMPLETED in self.gf_doc
                and actual_duration == 38
                and gaps["docs/performance-grindflow.md:L9-U1"] == "UNKNOWN"
            ),
            "docs/performance-grindflow.md:L10-U1": (
                actual_duration == self.metric["baseline"]["value"]
                == self.metric["window"]["duration_seconds"] == 38
                and self.metric["baseline"]["observed_at"] == COMPLETED
            ),
            "docs/performance-grindflow.md:L10-U2": (
                self.metric["window"]["min_samples"] == 1
                and len(self.gf["surfaces"]) == 1
                and "no una tendencia" in self.gf_doc
                and "no TTFB" in self.gf_doc
            ),
            "docs/performance-grindflow.md:L11-U1": (
                self.metric["budget"] ==
                {"operator": "lte", "value": 120, "unit": "s"}
                and breach["classification"] == "PERF_DEGRADATION"
                and breach["breach"] is True
            ),
            "docs/performance-grindflow.md:L11-U2": (
                "no un SLA comercial ni un RTO" in self.gf_doc
                and self.metric["id"] == "job_duration"
            ),
            "docs/performance-grindflow.md:L11-U3": (
                "no acredita percentiles ni tendencias" in self.gf_doc
                and self.metric["window"]["min_samples"] == 1
                and "percentile" not in self.metric
            ),
            "docs/performance-grindflow.md:L22-U1": (
                isinstance(self.metric["baseline"]["value"], (int, float))
                and not isinstance(self.metric["baseline"]["value"], bool)
                and (ROOT / "performance/contract.schema.json").is_file()
            ),
            "docs/performance-grindflow.md:L22-U2": (
                self.metric["baseline"]["value"] != "UNKNOWN"
                and self.metric["baseline"]["value"] != 0
            ),
            "docs/performance-grindflow.md:L22-U3": (
                unmeasured["classification"] == "PERF_REVIEW"
                and unmeasured["evidence_state"] == "UNKNOWN"
                and unmeasured["budget"] is None
                and len(self.gf["surfaces"]) == 1
            ),
            "docs/performance-grindflow.md:L26-U1": (
                current["evidence_state"] == "CURRENT"
                and stale["classification"] == "PERF_REVIEW"
                and derive_performance_status(stale)["status"] == "UNKNOWN"
            ),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(checks), set(UNITS))
        for identifier, passed in checks.items():
            with self.subTest(unit=identifier):
                self.assertTrue(passed, identifier + ": NO_VERIFICABLE")

    def test_falla_cerrado(self):
        """AC-02: un snapshot de procedencia inválida nunca clasifica sano."""
        for change in (
            {"event": "pull_request"}, {"name": "CodeQL"},
            {"head_branch": "feature"}, {"status": "in_progress"},
            {"conclusion": "failure"}, {"head_sha": "invalid"},
            {"repository": {"full_name": "foreign/repo"}},
            {"run_attempt": 0}, {"run_attempt": False},
            {"run_started_at": None},
            {"updated_at": "2026-10-24T18:13:53Z"},
        ):
            with self.subTest(change=change):
                run = synthetic_ci_run()
                run.update(change)
                with self.assertRaises(PerformanceCiObservationError):
                    self.ci_result(run)
        for value in ("UNKNOWN", None, True, float("nan")):
            with self.subTest(invalid_baseline=value):
                invalid = copy.deepcopy(self.gf_raw)
                invalid["surfaces"][0]["metrics"][0]["baseline"]["value"] = value
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(invalid)
        extra = copy.deepcopy(self.gf_raw)
        extra["surfaces"][0]["metrics"][0]["evidence"]["reason"] = "unknown"
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(extra)

    def test_sin_datos_reales(self):
        """AC-03: fixtures sin PII, red, permisos ni datos de clientes."""
        run = synthetic_ci_run()
        run["private_fixture"] = "synthetic-private-unique-marker"
        projection = self.ci_result(run)
        self.assertNotIn(run["private_fixture"], repr(projection))
        self.assertEqual(projection["authority"], "unchanged")
        for forbidden in ("private_fixture", "repository", "run_started_at",
                          "updated_at", "token", "headers", "logs"):
            self.assertNotIn(forbidden, projection)
        for flag in ("execute_actions", "create_work_item", "candidate_terminal"):
            self.assertIs(projection[flag], False)
        code = (ROOT / "performance/github_actions_ci.py").read_text(
            encoding="utf-8"
        )
        for forbidden in ("requests.post(", "urllib.request", "subprocess.run(",
                          "gh api ", "actions/workflows/dispatches"):
            self.assertNotIn(forbidden, code)
        self.assertEqual(
            synthetic_smoke()["evidence_ref"], "github:synthetic/actions/runs/1",
        )
        self.assertEqual(synthetic_ci_run()["head_sha"], "a" * 40)

    def test_estados_unknown_explicitos(self):
        """AC-04: sin GET autenticado o baseline web se conserva UNKNOWN."""
        self.assertEqual(set(EXTERNAL_GAPS), {
            "docs/performance-grindflow.md:L7-U2",
            "docs/performance-grindflow.md:L8-U1",
            "docs/performance-grindflow.md:L9-U1",
        })
        self.assertTrue(all(v == "UNKNOWN" for v in EXTERNAL_GAPS.values()))
        for route in ("web.landing", "web.login", "web.composer", "web.library"):
            with self.subTest(surface=route):
                result = self.smoke(surface=route, metric="ttfb")
                self.assertEqual(result["classification"], "PERF_REVIEW")
                self.assertEqual(result["evidence_state"], "UNKNOWN")
                self.assertIsNone(result["breach"])
                self.assertIsNone(result["budget"])
                self.assertEqual(derive_performance_status(result)["status"], "UNKNOWN")
        self.assertEqual(self.gf_doc.count("| UNKNOWN |"), 4)
        stale = detect_performance(
            self.gf, synthetic_smoke(), evaluated_at="2026-11-10T00:42:20Z",
        )
        self.assertEqual(stale["evidence_state"], "STALE")
        self.assertEqual(derive_performance_status(stale)["status"], "UNKNOWN")
        self.assertFalse(self.ci_result()["execute_actions"])


if __name__ == "__main__":
    unittest.main()
