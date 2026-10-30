"""Pruebas de comportamiento real de Regression Intelligence para Factory#1835.

Evidencia puramente sintética; ni producción ni estados de matriz.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from lecciones.memoria import validate_lesson
from quality.regression import (
    QualityRegressionError,
    analyze_regression,
    compile_regression_guardrail_candidates,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sonar_watch_factory_44", ROOT / "scripts" / "sonar-watch.py"
)
assert SPEC is not None and SPEC.loader is not None
sonar_watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sonar_watch)

REG = "docs/quality-regression.md:"
OFFLINE = frozenset({
    REG + "L20-U1", REG + "L22-U1", REG + "L23-U1",
    REG + "L24-U1", REG + "L25-U1", REG + "L27-U1",
    REG + "L27-U2", REG + "L31-U1", REG + "L31-U2",
    REG + "L9-U1",
})


def sample(*, source: str = "pl0n3r/Factory#346",
           regression_id: str = "factory-quality-044") -> dict:
    """Regresión sintética con fallo reproducible y fix limpio."""
    return {
        "version": 1,
        "regression_id": regression_id,
        "project": "pl0n3r/Factory",
        "surface": "quality-regression",
        "signature": "synthetic gate regression",
        "occurred_at": "2026-09-28T20:00:00Z",
        "source": source,
        "root_cause": "An unstable gate was treated as passing evidence.",
        "prevention": "Demand repeatable failures and a clean after sample.",
        "before": {
            "runs": 3, "failures": 3, "evidence_ref": "ci://synthetic/before",
            "observed_at": "2026-09-28T20:10:00Z",
        },
        "after": {
            "runs": 3, "failures": 0, "evidence_ref": "ci://synthetic/after",
            "observed_at": "2026-09-28T20:20:00Z",
        },
        "regression_test_ref": "tests/test_quality_regression.py::test_regression",
    }


class CoberturaFactory44Tests(unittest.TestCase):
    """Ejerce código; las unidades de política se clasifican en el PR."""

    def test_contrato_principal(self) -> None:
        seen: set[str] = set()
        result = analyze_regression(sample(), evaluated_at="2026-09-28T23:00:00Z")
        self.assertEqual(result["classification"], "VERIFIED")
        self.assertTrue(result["pass_evidence_eligible"])
        seen.add(REG + "L20-U1")
        self.assertTrue(result["reproduced"])
        self.assertFalse(result["flaky"])
        seen.add(REG + "L22-U1")
        self.assertIn("ci://synthetic/after", result["provenance"])
        self.assertEqual(sample()["after"]["failures"], 0)
        seen.add(REG + "L23-U1")
        self.assertIn("tests/test_quality_regression.py::test_regression", result["provenance"])
        seen.add(REG + "L24-U1")
        self.assertIn("pl0n3r/Factory#346", result["provenance"])
        self.assertIn("ci://synthetic/before", result["provenance"])
        seen.add(REG + "L25-U1")
        lesson = result["guardrail_material"]
        self.assertIsInstance(lesson, dict)
        self.assertEqual(validate_lesson(lesson, "fixture")["source"], "pl0n3r/Factory#346")
        seen.add(REG + "L27-U1")

        partial = sample()
        partial["after"]["failures"] = 3
        dirty = analyze_regression(partial, evaluated_at="2026-09-28T23:00:00Z")
        self.assertEqual(dirty["classification"], "REPRODUCED")
        self.assertIsNone(dirty["guardrail_material"])
        self.assertIn("ci://synthetic/after", dirty["provenance"])
        seen.add(REG + "L27-U2")

        peer = sample(source="pl0n3r/Factory#349", regression_id="factory-quality-045")
        candidates = compile_regression_guardrail_candidates(
            [sample(), peer], evaluated_at="2026-09-28T23:00:00Z"
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["occurrences"], 2)
        self.assertEqual(candidates[0]["sources"], ["pl0n3r/Factory#346", "pl0n3r/Factory#349"])
        seen.add(REG + "L31-U1")
        self.assertEqual(candidates[0]["candidate"]["changes"][0]["value"]["status"], "candidate")
        seen.add(REG + "L31-U2")

        self.assertEqual(
            set(sample()["before"]), {"runs", "failures", "evidence_ref", "observed_at"}
        )
        seen.add(REG + "L9-U1")
        self.assertEqual(seen, OFFLINE)

    def test_falla_cerrado(self) -> None:
        evaluated = "2026-09-28T23:00:00Z"
        cases = []
        for field in ("runs", "failures", "evidence_ref", "observed_at"):
            missing = sample()
            del missing["before"][field]
            cases.append(missing)
        for field, value in (
            ("runs", 0), ("runs", True), ("failures", 4),
            ("failures", -1), ("evidence_ref", "@invalid"),
            ("observed_at", "invalid"),
        ):
            bad = sample()
            bad["before"][field] = value
            cases.append(bad)
        future = sample()
        future["after"]["observed_at"] = "2999-01-01T00:00:00Z"
        cases.append(future)
        reversed_time = sample()
        reversed_time["after"]["observed_at"] = "2026-09-28T20:01:00Z"
        cases.append(reversed_time)
        invalid_source = sample()
        invalid_source["source"] = "https://example.invalid/issue/1"
        cases.append(invalid_source)
        sensitive = sample()
        sensitive["root_cause"] = "token=synthetic-placeholder"
        cases.append(sensitive)
        for index, item in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(QualityRegressionError) as err:
                analyze_regression(item, evaluated_at=evaluated)
            self.assertNotIn("synthetic-placeholder", str(err.exception))

        missing_test = sample()
        missing_test["regression_test_ref"] = None
        no_lesson = analyze_regression(missing_test, evaluated_at=evaluated)
        self.assertFalse(no_lesson["pass_evidence_eligible"])
        self.assertIsNone(no_lesson["guardrail_material"])
        self.assertEqual(
            compile_regression_guardrail_candidates([missing_test], evaluated_at=evaluated), []
        )
        unstable = sample()
        unstable["before"]["failures"] = 1
        flaky = analyze_regression(unstable, evaluated_at=evaluated)
        self.assertEqual(flaky["classification"], "FLAKY")
        self.assertFalse(flaky["pass_evidence_eligible"])
        self.assertIsNone(flaky["guardrail_material"])

        with mock.patch.object(sonar_watch, "urlopen", side_effect=AssertionError("network forbidden")):
            read_only = sonar_watch.HttpJson(token="", base_url="https://sonarcloud.io", read_only=True)
            with self.assertRaises(sonar_watch.SonarWatchError):
                read_only.request("/api/qualitygates/project_status", method="POST", payload={})
        self.assertEqual(sonar_watch.SonarApi.analysis_method_from_settings(
            {"settings": [{"key": "sonar.autoscan.enabled", "value": "false"}]}
        ), "ci")
        for invalid in (
            None, {"settings": []},
            {"settings": [{"key": "sonar.autoscan.enabled", "value": "guess"}]},
        ):
            with self.assertRaises(sonar_watch.SonarWatchError):
                sonar_watch.SonarApi.analysis_method_from_settings(invalid)

    def test_sin_datos_reales(self) -> None:
        own = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(own, r"(?m)^\s*(?:from|import)\s+(?:requests|httpx|socket|subprocess)\b")
        self.assertNotRegex(own, r"(?m)^-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----")
        self.assertEqual(len(OFFLINE), 10)
        self.assertTrue(all(key.startswith(REG) for key in OFFLINE))
        self.assertTrue((ROOT / "quality/regression.py").is_file())
        self.assertTrue((ROOT / "scripts/sonar-watch.py").is_file())
        # No credentials, scheduler, browser, network or production probes.


if __name__ == "__main__":
    unittest.main()
