"""Factory #1657: 16 offline performance-evidence gaps, never production proof.

Synthetic inputs exercise canonical performance adapters. Neither an untrusted
GitHub snapshot nor a local benchmark authorizes diagnosis, adoption, dispatch,
or a measured remediation in FactoryRunner.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest

from performance.ci_professional_report import diagnose_factoryrunner_ci_professionals
from performance.github_actions_ci import PerformanceCiObservationError
from performance.ci_suite_benchmark import (
    SuiteBenchmarkError, compare_unittest_summaries, parse_unittest_summary,
)
from performance.classifier import (
    AUTHORITY, PerformanceClassifierError, classify_performance_envelope,
)
from tests.test_brechas_factory_40 import fixture_contract, fixture_envelope
from tests.test_performance_ci_suite_benchmark import identity, summary

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
SYNTH_SHA = "b" * 40
EVALUATED = "2026-10-24T20:00:00Z"
ROWS = (
    "docs/performance-ci-professional-report.md:L20-U1",
    "docs/performance-ci-professional-report.md:L23-U1",
    "docs/performance-ci-professional-report.md:L28-U1",
    "docs/performance-ci-professional-report.md:L6-U1",
    "docs/performance-ci-suite-benchmark.md:L22-U1",
    "docs/performance-ci-suite-benchmark.md:L22-U2",
    "docs/performance-ci-suite-benchmark.md:L5-U1",
    "docs/performance-ci-suite-benchmark.md:L7-U1",
    "docs/performance-ci-suite-benchmark.md:L7-U2",
    "docs/performance-classification.md:L11-U1",
    "docs/performance-classification.md:L3-U1",
    "docs/performance-classification.md:L5-U1",
    "docs/performance-classification.md:L5-U2",
    "docs/performance-classification.md:L7-U1",
    "docs/performance-classifier.md:L14-U1",
    "docs/performance-classifier.md:L16-U1",
)
SOURCES = (
    "docs/performance-ci-professional-report.md",
    "docs/performance-ci-suite-benchmark.md",
    "docs/performance-classification.md",
    "docs/performance-classifier.md",
)


def synthetic_run() -> dict:
    """An invented CI record; never represented as an authenticated GET."""
    return {
        "id": 1600, "name": "CI", "event": "push",
        "head_branch": "main", "head_sha": SYNTH_SHA,
        "status": "completed", "conclusion": "success",
        "run_attempt": 1,
        "run_started_at": "2026-10-24T18:13:54Z",
        "updated_at": "2026-10-24T18:16:04Z",
        "repository": {"full_name": "pl0n3r/FactoryRunner"},
    }


def matrix_state(raw: object, identifier: str) -> str:
    """Exact, unique inventory row: never infer coverage from a candidate."""
    if not isinstance(raw, str) or identifier not in ROWS:
        return UNKNOWN
    prefix = "| " + chr(96) + identifier + chr(96) + " |"
    rows = [line for line in raw.splitlines() if line.startswith(prefix)]
    if len(rows) != 1:
        return UNKNOWN
    cells = [part.strip() for part in rows[0].strip("|").split("|")]
    if len(cells) != 6 or cells[0] != chr(96) + identifier + chr(96):
        return UNKNOWN
    if cells[2] != "NO_VERIFICABLE" or "Contraste #1572" not in cells[3]:
        return UNKNOWN
    return "NO_VERIFICABLE"


def operational_state(_identifier: object, _claim: object = None) -> str:
    """An offline fixture does not authenticate a run, AFTER, or readiness."""
    return UNKNOWN


def status(value: object) -> str:
    return "TEST_EXECUTED" if value is True else UNKNOWN


class BrechasFactory39Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((
            ROOT / "performance/contracts/factoryrunner.json"
        ).read_text(encoding="utf-8"))

    def test_contrato_principal(self):
        """AC-01: every one of 16 exact matrix units has an executable claim."""
        raw_matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        docs = {
            name: (ROOT / name).read_text(encoding="utf-8")
            for name in SOURCES
        }
        for ident in ROWS:
            with self.subTest(source=ident):
                self.assertEqual("NO_VERIFICABLE", matrix_state(raw_matrix, ident))
                self.assertEqual(UNKNOWN, operational_state(ident))

        ci = diagnose_factoryrunner_ci_professionals(
            self.contract, synthetic_run(), evaluated_at=EVALUATED
        )
        extra = synthetic_run()
        extra["private_arbitrary_payload"] = "SYNTHETIC_DO_NOT_ECHO"
        sanitized = diagnose_factoryrunner_ci_professionals(
            self.contract, extra, evaluated_at=EVALUATED
        )
        parsed = parse_unittest_summary(summary(616, "104.376"))
        before = parse_unittest_summary(summary(616, "120.000"))
        delta = compare_unittest_summaries(
            before, parsed,
            identity(100, "a" * 40, 101),
            identity(101, "b" * 40, 102),
        )
        env = fixture_envelope()
        classified = classify_performance_envelope(
            fixture_contract(), env, evaluated_at="2026-10-28T12:05:00Z"
        )
        extended = copy.deepcopy(env)
        extended["release_contract"] = {
            "design": "synthetic_v1", "minimum_release": "0.9.0",
        }
        with_optional = classify_performance_envelope(
            fixture_contract(), extended, evaluated_at="2026-10-28T12:05:00Z"
        )
        cli = (ROOT / "scripts/performance-classify.py").read_text(encoding="utf-8")
        report_doc = docs["docs/performance-ci-professional-report.md"]
        suite_doc = docs["docs/performance-ci-suite-benchmark.md"]
        class_doc = docs["docs/performance-classification.md"]
        meta_doc = docs["docs/performance-classifier.md"]
        assertions = {
            ROWS[0]: (
                ci["classification"] == "PERF_DEGRADATION"
                and ci["team"]["decision"] == "TEAM_RECOMMENDED"
                and ci["team"]["authority"] == "unchanged"
                and ci["dispatch"] is False
                and "no asignación ni diagnóstico causal verificado" in report_doc
            ),
            ROWS[1]: (
                sanitized == ci
                and "SYNTHETIC_DO_NOT_ECHO" not in repr(sanitized)
                and "campos canónicos saneados" in report_doc
            ),
            ROWS[2]: (
                all(ci[field] is False for field in (
                    "execute_actions", "create_work_item", "dispatch",
                    "adopt", "candidate_terminal",
                ))
                and ci["authority"] == "unchanged"
                and "no cumple" in report_doc
            ),
            ROWS[3]: (
                ci["identity"]["sha"] == SYNTH_SHA
                and "autenticar por su cuenta" in report_doc
                and ci["readiness"]["status"] == "DEGRADED"
                and operational_state(ROWS[3], synthetic_run()) == UNKNOWN
            ),
            ROWS[4]: (
                parsed == {
                    "suite": "python.unittest", "tests": 616,
                    "duration_ms": 104376, "status": "DIAGNOSTIC_ONLY",
                }
                and "Las cuatro pruebas verifican" in suite_doc
            ),
            ROWS[5]: (
                delta["status"] == "COMPARABLE_DIAGNOSTIC"
                and delta["sample_pairs"] == 1
                and delta["causality"] == "unproven"
                and delta["adopt"] is False
                and "nuevas mediciones reales" in suite_doc
            ),
            ROWS[6]: (
                parsed["status"] == "DIAGNOSTIC_ONLY"
                and parsed["duration_ms"] < 120000
                and "ejecución completa" in suite_doc
                and delta["execute_actions"] is False
            ),
            ROWS[7]: (
                delta["duration_delta_ms"] == -15624
                and delta["authority"] == "unchanged"
                and "GET autenticado" in suite_doc
                and operational_state(ROWS[7], delta) == UNKNOWN
            ),
            ROWS[8]: (
                operational_state(ROWS[8], parsed) == UNKNOWN
                and "no autentica el origen" in suite_doc
                and not any(k in parsed for k in ("token", "log", "payload"))
            ),
            ROWS[9]: (
                classified["create_work_item"] is False
                and classified["execute_actions"] is False
                and "regresión material real" in class_doc
            ),
            ROWS[10]: (
                classified["summary"]["total"] == 1
                and classified["results"][0]["classification"] == "PERF_INFO"
                and "performance.detector.detect_performance" in class_doc
            ),
            ROWS[11]: (
                env["version"] == 1
                and env["classification_authority"] == AUTHORITY
                and env["classification"] is None
                and classified["identity"] == env["identity"]
            ),
            ROWS[12]: (
                classified["identity"] == env["identity"]
                and classified["evidence_ref"] == env["evidence_ref"]
                and classified["summary"]["evidence_states"] == {"CURRENT": 1}
            ),
            ROWS[13]: (
                all(token in cli for token in (
                    "--evaluated-at", "--contract", "--envelope", "--output"
                ))
                and "No usa red" in class_doc
            ),
            ROWS[14]: (
                with_optional == classified
                and "lista cerrada de dos nombres" in meta_doc
            ),
            ROWS[15]: (
                "Se rechazan campos" in meta_doc
                and "release_contract" not in classified
                and classified["authority"] == "unchanged"
            ),
        }
        self.assertEqual(set(ROWS), set(assertions))
        for ident, result in assertions.items():
            with self.subTest(requirement=ident):
                self.assertEqual("TEST_EXECUTED", status(result))

    def test_falla_cerrado(self):
        """AC-02: counterfeit provenance, bad envelopes and ambiguous rows."""
        for ident in ROWS:
            with self.subTest(unit=ident):
                self.assertEqual(UNKNOWN, status(None))
                self.assertEqual(UNKNOWN, status(False))
                self.assertEqual(UNKNOWN, matrix_state("", ident))
                self.assertEqual(UNKNOWN, operational_state(ident, {"ci": "success"}))
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        for ident in ROWS:
            prefix = "| " + chr(96) + ident + chr(96) + " |"
            line = next(x for x in matrix.splitlines() if x.startswith(prefix))
            self.assertEqual(UNKNOWN, matrix_state(matrix + "\n" + line, ident))
            self.assertEqual(UNKNOWN, matrix_state(matrix.replace(
                line, line.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1
            ), ident))
        for changed in (
            {"event": "pull_request"}, {"head_branch": "feature"},
            {"name": "CodeQL"}, {"head_sha": "unknown"},
            {"repository": {"full_name": "other/repo"}},
            {"status": "in_progress"}, {"conclusion": "failure"},
        ):
            run = {**synthetic_run(), **changed}
            with self.subTest(changed=changed), self.assertRaises(
                PerformanceCiObservationError
            ):
                diagnose_factoryrunner_ci_professionals(
                    self.contract, run, evaluated_at=EVALUATED
                )
        for raw in ("", summary(616, "104.376") * 2,
                    summary(616, "104.376").replace("OK", "FAILED (errors=1)")):
            with self.assertRaises(SuiteBenchmarkError):
                parse_unittest_summary(raw)
        base = fixture_envelope()
        for changed in (
            {"version": 2}, {"classification": "PERF_INFO"},
            {"classification_authority": "producer"}, {"extra": "do_not_echo"},
            {"identity": {"sha": "invalid", "release": "1.0.0"}},
        ):
            with self.subTest(changed=changed), self.assertRaises(
                PerformanceClassifierError
            ):
                classify_performance_envelope(
                    fixture_contract(), {**base, **changed},
                    evaluated_at="2026-10-28T12:05:00Z"
                )
        for field, value in (
            ("sha", "c" * 40), ("release", "2.0.0"),
            ("evidence_ref", "synthetic:other"),
        ):
            mismatch = copy.deepcopy(base)
            mismatch["observations"][0][field] = value
            with self.subTest(field=field), self.assertRaises(
                PerformanceClassifierError
            ):
                classify_performance_envelope(
                    fixture_contract(), mismatch, evaluated_at="2026-10-28T12:05:00Z"
                )
        invalid_release = copy.deepcopy(base)
        invalid_release["release_contract"] = {
            "design": "synthetic_v1", "minimum_release": "2.0.0",
        }
        with self.assertRaises(PerformanceClassifierError):
            classify_performance_envelope(
                fixture_contract(), invalid_release,
                evaluated_at="2026-10-28T12:05:00Z"
            )
        with self.assertRaises(SuiteBenchmarkError):
            before = parse_unittest_summary(summary(616, "120.000"))
            compare_unittest_summaries(
                before, before, identity(100, "a" * 40, 101),
                identity(100, "a" * 40, 101),
            )

    def test_sin_datos_reales(self):
        """AC-03: stdlib fixtures, no tokens, network, chat text or PII."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = {
            alias.name.split(".")[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        }
        names |= {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertFalse(names & {
            "requests", "urllib", "httpx", "socket", "subprocess",
            "selenium", "playwright",
        })
        run = synthetic_run()
        run["arbitrary_private_payload"] = "SYNTHETIC_REDACT_ME"
        report = diagnose_factoryrunner_ci_professionals(
            self.contract, run, evaluated_at=EVALUATED
        )
        self.assertNotIn("SYNTHETIC_REDACT_ME", repr(report))
        self.assertNotIn("arbitrary_private_payload", repr(report))
        self.assertTrue(all(p.startswith("docs/") for p in SOURCES))
        self.assertEqual(16, len(set(ROWS)))

    def test_estados_unknown_explicitos(self):
        """AC-04: all rows fail closed for operational status, never fake ADOPT."""
        for ident in ROWS:
            with self.subTest(unit=ident):
                for fake in (
                    None, {}, True, {"run": "success", "auth": True},
                    {"release": "1.0.0", "sha": SYNTH_SHA},
                    {"after": "faster", "adopt": True},
                    {"work_item": "created"}, {"readiness": "GREEN"},
                ):
                    self.assertEqual(UNKNOWN, operational_state(ident, fake))
        report = diagnose_factoryrunner_ci_professionals(
            self.contract, synthetic_run(), evaluated_at=EVALUATED
        )
        benchmark = compare_unittest_summaries(
            parse_unittest_summary(summary(616, "120.000")),
            parse_unittest_summary(summary(616, "100.000")),
            identity(100, "a" * 40, 101),
            identity(101, "b" * 40, 102),
        )
        result = classify_performance_envelope(
            fixture_contract(), fixture_envelope(),
            evaluated_at="2026-10-28T12:05:00Z"
        )
        self.assertFalse(any(benchmark[k] for k in (
            "adopt", "create_work_item", "execute_actions"
        )))
        self.assertEqual("unproven", benchmark["causality"])
        self.assertIs(report["candidate_terminal"], False)
        self.assertIs(report["create_work_item"], False)
        self.assertIs(result["create_work_item"], False)
        self.assertEqual(UNKNOWN, operational_state(ROWS[9], result))


if __name__ == "__main__":
    unittest.main()
