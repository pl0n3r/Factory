"""Factory#1823: pruebas conductuales del contrato Performance v1.

Todos los payloads son sintéticos y fijos. Este archivo no consulta la matriz,
no usa red, secretos, datos reales ni concede autoridad de remediación.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from performance.classifier import (
    ENVELOPE_FIELDS, PerformanceClassifierError, classify_performance_envelope,
)
from performance.contract import (
    ESCALATION_CONDITIONS, PerformanceContractError,
    validate_performance_contract,
)
from performance.detector import detect_performance

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-29T12:05:00Z"
SHA = "a" * 40


def contract():
    return {
        "version": 1,
        "project": "fixture",
        "surfaces": [{
            "id": "home.mobile", "label": "Synthetic home", "metrics": [{
                "id": "lcp", "label": "Synthetic LCP",
                "baseline": {"value": 300, "unit": "ms", "observed_at": "2026-10-29T12:00:00Z"},
                "budget": {"operator": "lte", "value": 400, "unit": "ms"},
                "window": {"duration_seconds": 60, "min_samples": 2},
                "freshness": {"max_age_seconds": 600},
                "evidence": {"source": "ci", "ref": "fixture:run1", "observed_at": "2026-10-29T12:00:00Z"},
                "allowed_actions": ["observe", "diagnose"],
                "escalation_conditions": ["cost_change", "architecture_change"],
            }],
        }],
    }


def observation(**changes):
    row = {
        "version": 1, "project": "fixture", "surface": "home.mobile", "metric": "lcp",
        "value": 350, "unit": "ms", "observed_at": "2026-10-29T12:04:00Z",
        "window_seconds": 60, "sample_count": 3,
        "severity": "info", "operational_impact": False, "bottleneck": "frontend",
        "evidence_ref": "fixture:batch1", "sha": SHA, "release": "1.2.3",
    }
    row.update(changes)
    return row


def envelope():
    return {
        "version": 1, "project": "fixture",
        "classification_authority": "factory-performance-v1",
        "classification": None, "identity": {"sha": SHA, "release": "1.2.3"},
        "evidence_ref": "fixture:batch1", "observed_at": "2026-10-29T12:04:00Z",
        "observations": [observation()],
    }


def classify(payload=None, spec=None):
    return classify_performance_envelope(
        contract() if spec is None else spec,
        envelope() if payload is None else payload,
        evaluated_at=NOW,
    )


def metric(payload):
    return payload["surfaces"][0]["metrics"][0]


class CoberturaFactory32Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """Cada fila A invoca implementaciones reales en vez de leer status docs."""
        cases = {
            "docs/performance-classification.md:L5-U1": self._producer,
            "docs/performance-classification.md:L5-U2": self._observation_identity,
            "docs/performance-classification.md:L7-U1": self._cli,
            "docs/performance-classifier.md:L5-U1": self._eight_envelope_fields,
            "docs/performance-classifier.md:L14-U1": self._optional_release,
            "docs/performance-classifier.md:L16-U1": self._unknown_metadata,
            "docs/performance-classifier.md:L21-U1": self._metadata_only,
            "docs/performance-classifier.md:L31-U1": self._no_remediation,
            "docs/performance-contract.md:L10-U1": self._budget,
            "docs/performance-contract.md:L11-U1": self._window,
            "docs/performance-contract.md:L12-U1": self._freshness,
            "docs/performance-contract.md:L13-U1": self._dated_evidence,
            "docs/performance-contract.md:L15-U1": self._escalation,
            "docs/performance-contract.md:L17-U2": self._redacted_errors,
            "docs/performance-contract.md:L23-U1": self._validation_only,
            "docs/performance-contract.md:L23-U2": self._stale_is_unknown,
        }
        for clause, case in cases.items():
            with self.subTest(clause=clause):
                case()

    def _producer(self):
        result = classify()
        self.assertEqual(result["classification_authority"], "factory-performance-v1")
        self.assertEqual(result["identity"], {"sha": SHA, "release": "1.2.3"})
        self.assertEqual(result["source_observed_at"], "2026-10-29T12:04:00Z")
        self.assertEqual(result["summary"]["classifications"], {"PERF_INFO": 1})
        self.assertEqual(result["summary"]["evidence_states"], {"CURRENT": 1})

    def _observation_identity(self):
        for changes in ({"project": "another"}, {"sha": "b" * 40},
                        {"release": "1.2.4"}, {"evidence_ref": "fixture:other"}):
            payload = envelope()
            payload["observations"] = [observation(**changes)]
            with self.subTest(changes=changes), self.assertRaises(PerformanceClassifierError):
                classify(payload)
        duplicate = envelope()
        duplicate["observations"].append(copy.deepcopy(duplicate["observations"][0]))
        with self.assertRaises(PerformanceClassifierError):
            classify(duplicate)

    def _cli(self):
        spec = importlib.util.spec_from_file_location(
            "performance_cli_factory_32", ROOT / "scripts/performance-classify.py"
        )
        self.assertIsNotNone(spec)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            tmp = Path(folder)
            contract_path = tmp / "contract.json"
            envelope_path = tmp / "envelope.json"
            output_path = tmp / "result.json"
            contract_path.write_text(json.dumps(contract()), encoding="utf-8")
            envelope_path.write_text(json.dumps(envelope()), encoding="utf-8")
            args = ["performance-classify.py", "--contract", str(contract_path.relative_to(ROOT)),
                    "--envelope", str(envelope_path.relative_to(ROOT)), "--evaluated-at", NOW]
            stdout = io.StringIO()
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(stdout):
                self.assertEqual(cli.main(), 0)
            self.assertEqual(json.loads(stdout.getvalue())["summary"]["total"], 1)
            with patch.object(sys, "argv", args + ["--output", str(output_path.relative_to(ROOT))]):
                self.assertEqual(cli.main(), 0)
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")),
                             json.loads(stdout.getvalue()))
            with patch.object(sys, "argv", args[:-2]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err:
                    cli.main()
            self.assertEqual(err.exception.code, 2)

    def _eight_envelope_fields(self):
        self.assertEqual(set(envelope()), ENVELOPE_FIELDS)
        for key in ENVELOPE_FIELDS:
            payload = envelope()
            del payload[key]
            with self.subTest(missing=key), self.assertRaises(PerformanceClassifierError):
                classify(payload)

    def _optional_release(self):
        payload = envelope()
        payload["release_contract"] = {"design": "concept05", "minimum_release": "1.2.2"}
        self.assertEqual(classify(payload)["summary"]["total"], 1)
        for bad in ({"design": "../bad", "minimum_release": "1.2.2"},
                    {"design": "concept05", "minimum_release": "1.2.4"},
                    {"design": "concept05", "minimum_release": "01.2.2"}):
            payload["release_contract"] = bad
            with self.subTest(bad=bad), self.assertRaises(PerformanceClassifierError):
                classify(payload)

    def _unknown_metadata(self):
        for key, value in (("release_notes", "fixture"), ("credential", "NOT_A_CREDENTIAL")):
            payload = envelope()
            payload[key] = value
            with self.subTest(extra=key), self.assertRaises(PerformanceClassifierError):
                classify(payload)
        payload = envelope()
        payload["release_contract"] = {
            "design": "concept05", "minimum_release": "1.2.2", "extra": "synthetic"
        }
        with self.assertRaises(PerformanceClassifierError):
            classify(payload)

    def _metadata_only(self):
        plain = classify()
        payload = envelope()
        payload["release_contract"] = {"design": "concept05", "minimum_release": "1.2.2"}
        self.assertEqual(classify(payload), plain)
        self.assertEqual(plain["results"][0]["budget"]["value"], 400)
        self.assertEqual(plain["results"][0]["baseline"]["value"], 300)

    def _no_remediation(self):
        result = classify()
        self.assertEqual(result["authority"], "unchanged")
        self.assertIs(result["execute_actions"], False)
        self.assertIs(result["create_work_item"], False)
        self.assertEqual(result["results"][0]["classification"], "PERF_INFO")

    def _budget(self):
        payload = contract()
        self.assertEqual(validate_performance_contract(payload)["surfaces"][0]["metrics"][0]
                         ["budget"]["operator"], "lte")
        metric(payload)["budget"]["operator"] = "gte"
        self.assertTrue(detect_performance(payload, observation(), evaluated_at=NOW)["breach"])
        metric(payload)["budget"]["unit"] = "s"
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)

    def _window(self):
        payload = contract()
        self.assertEqual(metric(validate_performance_contract(payload))["window"],
                         {"duration_seconds": 60, "min_samples": 2})
        result = detect_performance(payload, observation(sample_count=1, window_seconds=1),
                                    evaluated_at=NOW)
        self.assertEqual(result["classification"], "PERF_REVIEW")
        self.assertEqual(result["evidence_state"], "INSUFFICIENT")
        metric(payload)["window"]["duration_seconds"] = 0
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)

    def _freshness(self):
        payload = contract()
        self.assertEqual(metric(validate_performance_contract(payload))["freshness"],
                         {"max_age_seconds": 600})
        metric(payload)["freshness"]["max_age_seconds"] = 0
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)

    def _dated_evidence(self):
        payload = contract()
        self.assertEqual(metric(validate_performance_contract(payload))["evidence"],
                         {"source": "ci", "ref": "fixture:run1",
                          "observed_at": "2026-10-29T12:00:00Z"})
        del metric(payload)["evidence"]["observed_at"]
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)
        payload = contract()
        metric(payload)["evidence"]["observed_at"] = "2026-10-29T12:00:00"
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)

    def _escalation(self):
        payload = contract()
        metric(payload)["escalation_conditions"] = list(ESCALATION_CONDITIONS)
        result = validate_performance_contract(payload)
        self.assertEqual(metric(result)["escalation_conditions"], sorted(ESCALATION_CONDITIONS))
        metric(payload)["escalation_conditions"] = ["self_authorize"]
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)

    def _redacted_errors(self):
        payload = contract()
        metric(payload)["label"] = "token=synthetic-sensitive-fixture"
        with self.assertRaises(PerformanceContractError) as err:
            validate_performance_contract(payload)
        self.assertNotIn("synthetic-sensitive-fixture", str(err.exception))

    def _validation_only(self):
        normalized = validate_performance_contract(contract())
        self.assertIn("max_age_seconds", metric(normalized)["freshness"])
        self.assertIn("observed_at", metric(normalized)["evidence"])
        self.assertNotIn("classification", normalized)
        self.assertNotIn("create_work_item", normalized)

    def _stale_is_unknown(self):
        stale = detect_performance(contract(), observation(),
                                   evaluated_at="2026-10-29T15:00:00Z")
        unknown = detect_performance(contract(), observation(metric="not_configured"),
                                     evaluated_at=NOW)
        self.assertEqual((stale["classification"], stale["evidence_state"]),
                         ("PERF_REVIEW", "STALE"))
        self.assertEqual((unknown["classification"], unknown["evidence_state"]),
                         ("PERF_REVIEW", "UNKNOWN"))

    def test_falla_cerrado(self):
        for change in ("classification", "classification_authority", "observed_at"):
            payload = envelope()
            payload[change] = {"classification": "PERF_INFO",
                               "classification_authority": "producer",
                               "observed_at": "2026-10-29T12:04:00"}[change]
            with self.subTest(field=change), self.assertRaises(PerformanceClassifierError):
                classify(payload)
        payload = envelope()
        payload["identity"]["sha"] = "b" * 40
        with self.assertRaises(PerformanceClassifierError):
            classify(payload)
        for field, invalid in (("budget", {"operator": "lte", "value": 400, "unit": "s"}),
                               ("freshness", {"max_age_seconds": 0}),
                               ("window", {"duration_seconds": 60, "min_samples": 0})):
            payload = contract()
            metric(payload)[field] = invalid
            with self.subTest(field=field), self.assertRaises(PerformanceContractError):
                validate_performance_contract(payload)
        payload = contract()
        metric(payload)["baseline"]["value"] = float("nan")
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(payload)
        payload = envelope()
        payload["observations"] = []
        with self.assertRaises(PerformanceClassifierError):
            classify(payload)

    def test_sin_datos_reales(self):
        """Ejecutar el código real con conexión de salida prohibida y fixtures falsos."""
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("network forbidden")):
            normalized = validate_performance_contract(contract())
            result = classify()
            self.assertEqual(normalized["project"], "fixture")
            self.assertEqual(result["project"], "fixture")
            self.assertFalse(result["execute_actions"])
            self.assertFalse(result["create_work_item"])
            self.assertEqual(result["summary"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
