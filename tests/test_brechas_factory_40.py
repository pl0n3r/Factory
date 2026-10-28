"""Factory #1658: synthetic, fail-closed tests for 16 Performance v1 gaps.

These tests never modify docs/matriz-cobertura.md, contact a service or
claim that an offline contract grants operational readiness or authority.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from performance.classifier import (
    AUTHORITY,
    ENVELOPE_FIELDS,
    PerformanceClassifierError,
    classify_performance_envelope,
)
from performance.contract import (
    ESCALATION_CONDITIONS,
    OPERATORS,
    PerformanceContractError,
    validate_performance_contract,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-28T12:05:00Z"
OBSERVED = "2026-10-28T12:00:00Z"
SHA = "a" * 40
EVIDENCE = "run:synthetic-1658"
UNKNOWN = "UNKNOWN"

ROWS = (
    "docs/performance-classifier.md:L21-U1",
    "docs/performance-classifier.md:L31-U1",
    "docs/performance-classifier.md:L33-U1",
    "docs/performance-classifier.md:L5-U1",
    "docs/performance-contract.md:L10-U1",
    "docs/performance-contract.md:L11-U1",
    "docs/performance-contract.md:L12-U1",
    "docs/performance-contract.md:L13-U1",
    "docs/performance-contract.md:L15-U1",
    "docs/performance-contract.md:L17-U2",
    "docs/performance-contract.md:L23-U1",
    "docs/performance-contract.md:L23-U2",
    "docs/performance-contract.md:L27-U1",
    "docs/performance-contract.md:L28-U1",
    "docs/performance-contract.md:L29-U1",
    "docs/performance-contract.md:L30-U1",
)


def fixture_contract() -> dict:
    """Private in-memory project declaration, not a producer or customer sample."""
    return {
        "version": 1,
        "project": "synthetic",
        "surfaces": [{
            "id": "api", "label": "Synthetic API",
            "metrics": [{
                "id": "latency", "label": "Latency",
                "baseline": {"value": 180, "unit": "ms", "observed_at": OBSERVED},
                "budget": {"operator": "lte", "value": 250, "unit": "ms"},
                "window": {"duration_seconds": 300, "min_samples": 20},
                "freshness": {"max_age_seconds": 900},
                "evidence": {"source": "ci", "ref": EVIDENCE, "observed_at": OBSERVED},
                "allowed_actions": ["observe", "diagnose"],
                "escalation_conditions": ["cost_change", "architecture_change"],
            }],
        }],
    }


def fixture_envelope() -> dict:
    return {
        "version": 1,
        "project": "synthetic",
        "classification_authority": AUTHORITY,
        "classification": None,
        "identity": {"sha": SHA, "release": "1.0.0"},
        "evidence_ref": EVIDENCE,
        "observed_at": OBSERVED,
        "observations": [{
            "version": 1, "project": "synthetic",
            "surface": "api", "metric": "latency", "value": 220, "unit": "ms",
            "observed_at": OBSERVED, "window_seconds": 300, "sample_count": 20,
            "severity": "low", "operational_impact": False, "bottleneck": "backend",
            "evidence_ref": EVIDENCE, "sha": SHA, "release": "1.0.0",
        }],
    }


def field_status(value: object) -> str:
    """Evidence UNKNOWN must not turn into a passing operational claim."""
    return "TEST_EXECUTED" if value is True else UNKNOWN


def matrix_row_status(text: str, row_id: str) -> str:
    prefix = "| " + chr(96) + row_id + chr(96) + " |"
    found = [line for line in text.splitlines() if line.startswith(prefix)]
    if len(found) != 1:
        return UNKNOWN
    states = re.findall(r"\|\s*(NO_VERIFICABLE|CUBIERTO|EN_CURSO|SIN_COBERTURA|DESCARTADO)\s*\|", found[0])
    return states[0] if len(states) == 1 else UNKNOWN


def classify(contract: dict, envelope: dict) -> dict:
    return classify_performance_envelope(contract, envelope, evaluated_at=NOW)


def cli_contract() -> bool:
    """Run the actual CLI twice on disposable, checkout-confined synthetic JSON."""
    with tempfile.TemporaryDirectory(prefix="factory-1658-", dir=ROOT) as directory:
        base = Path(directory)
        files = (base / "contract.json", base / "envelope.json")
        for path, content in zip(files, (fixture_contract(), fixture_envelope())):
            path.write_text(json.dumps(content, allow_nan=False), encoding="utf-8")
        argv = [
            sys.executable, "scripts/performance-classify.py",
            "--contract", str(files[0].relative_to(ROOT)),
            "--envelope", str(files[1].relative_to(ROOT)),
            "--evaluated-at", NOW,
        ]
        isolated = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(base),
            "LANG": "C",
        }
        first = subprocess.run(
            argv, cwd=ROOT, env=isolated, capture_output=True, text=True,
            check=False, timeout=40,
        )
        second = subprocess.run(
            argv, cwd=ROOT, env=isolated, capture_output=True, text=True,
            check=False, timeout=40,
        )
        if first.returncode != 0 or second.returncode != 0:
            return False
        parsed = json.loads(first.stdout)
        return (
            first.stdout == second.stdout
            and first.stderr == second.stderr == ""
            and parsed["summary"]["total"] == 1
            and parsed["results"][0]["classification"] == "PERF_INFO"
            and parsed["execute_actions"] is False
            and parsed["create_work_item"] is False
        )


class BrechasFactory40Tests(unittest.TestCase):
    """Four executable factory-acceptance methods, with one claim per row."""

    def test_contrato_principal(self):
        contract, env = fixture_contract(), fixture_envelope()
        canonical = validate_performance_contract(contract)
        original = classify(contract, env)
        metadata = copy.deepcopy(env)
        metadata["release_contract"] = {
            "design": "synthetic_v1", "minimum_release": "0.9.0",
        }
        with_metadata = classify(contract, metadata)
        metric = canonical["surfaces"][0]["metrics"][0]
        result = original["results"][0]
        doc_classifier = (ROOT / "docs/performance-classifier.md").read_text(encoding="utf-8")
        doc_contract = (ROOT / "docs/performance-contract.md").read_text(encoding="utf-8")

        stale = fixture_envelope()
        stale["observations"][0]["observed_at"] = "2026-10-28T10:00:00Z"
        stale_result = classify(contract, stale)["results"][0]
        unknown = fixture_envelope()
        unknown["observations"][0]["metric"] = "not_contracted"
        unknown_result = classify(contract, unknown)["results"][0]
        confidential = fixture_contract()
        confidential["surfaces"][0]["metrics"][0]["label"] = "token=NEVER_ECHO_THIS"
        with self.assertRaises(PerformanceContractError) as error:
            validate_performance_contract(confidential)

        evidence = {
            ROWS[0]: with_metadata == original and
                original["authority"] == "unchanged" and
                result["budget"] == metric["budget"] and
                result["baseline"] == metric["baseline"] and
                result["severity"] == "low" and
                result["freshness"]["max_age_seconds"] == 900,
            ROWS[1]: original["execute_actions"] is False
                and original["create_work_item"] is False
                and "no autorización de remediación" in doc_classifier,
            ROWS[2]: cli_contract(),
            ROWS[3]: set(env) == ENVELOPE_FIELDS
                and "release_contract" not in original and with_metadata == original,
            ROWS[4]: metric["budget"] == {"operator": "lte", "value": 250, "unit": "ms"}
                and OPERATORS == {"lte", "gte"},
            ROWS[5]: metric["window"] == {"duration_seconds": 300, "min_samples": 20},
            ROWS[6]: metric["freshness"] == {"max_age_seconds": 900},
            ROWS[7]: metric["evidence"] == {
                "source": "ci", "ref": EVIDENCE, "observed_at": OBSERVED,
            },
            ROWS[8]: set(metric["escalation_conditions"]) <= ESCALATION_CONDITIONS
                and len(ESCALATION_CONDITIONS) == 7,
            ROWS[9]: "NEVER_ECHO_THIS" not in str(error.exception),
            ROWS[10]: metric["freshness"]["max_age_seconds"] > 0
                and metric["evidence"]["observed_at"] == OBSERVED,
            ROWS[11]: stale_result["evidence_state"] == "STALE"
                and stale_result["classification"] == "PERF_REVIEW"
                and unknown_result["evidence_state"] == UNKNOWN
                and unknown_result["breach"] is None,
            ROWS[12]: "#310: contrato, schema y validación." in doc_contract
                and canonical["version"] == 1,
            ROWS[13]: "#311: detección de regresiones y triage." in doc_contract
                and result["classification"] == "PERF_INFO"
                and stale_result["classification"] == "PERF_REVIEW",
            ROWS[14]: "#312: remediación gobernada + before/after." in doc_contract
                and original["execute_actions"] is False,
            ROWS[15]: "#313: estado consumible por Readiness y escenario E2E." in doc_contract
                and original["create_work_item"] is False,
        }
        self.assertEqual(set(evidence), set(ROWS))
        for row_id, valid in evidence.items():
            with self.subTest(requirement=row_id):
                self.assertEqual("TEST_EXECUTED", field_status(valid))

    def test_falla_cerrado(self):
        for row_id in ROWS:
            with self.subTest(requirement=row_id):
                self.assertEqual(UNKNOWN, field_status(None))
                self.assertEqual(UNKNOWN, field_status(False))
                self.assertEqual(UNKNOWN, field_status("healthy"))

        for missing in ("budget", "window", "freshness", "evidence", "escalation_conditions"):
            item = fixture_contract()
            del item["surfaces"][0]["metrics"][0][missing]
            with self.subTest(missing=missing), self.assertRaises(PerformanceContractError):
                validate_performance_contract(item)

        invalid_fields = (
            ("budget", "operator", "bad_operator"),
            ("budget", "unit", "seconds_not_a_unit"),
            ("window", "min_samples", 0),
            ("window", "duration_seconds", -1),
            ("freshness", "max_age_seconds", 0),
            ("evidence", "observed_at", "2026-10-28T12:00:00"),
            ("evidence", "ref", "token=NEVER_ECHO_THIS"),
        )
        for section, field, value in invalid_fields:
            item = fixture_contract()
            item["surfaces"][0]["metrics"][0][section][field] = value
            with self.subTest(section=section, field=field):
                with self.assertRaises(PerformanceContractError) as caught:
                    validate_performance_contract(item)
                self.assertNotIn("NEVER_ECHO_THIS", str(caught.exception))

        for value in (float("nan"), float("inf")):
            item = fixture_contract()
            item["surfaces"][0]["metrics"][0]["budget"]["value"] = value
            with self.assertRaises(PerformanceContractError):
                validate_performance_contract(item)

        item = fixture_contract()
        item["surfaces"][0]["metrics"][0]["escalation_conditions"] = ["write_production"]
        with self.assertRaises(PerformanceContractError):
            validate_performance_contract(item)

        bad_env = fixture_envelope()
        bad_env["classification"] = "PERF_INFO"
        with self.assertRaises(PerformanceClassifierError):
            classify(item if False else fixture_contract(), bad_env)
        unsafe_env = fixture_envelope()
        unsafe_env["release_contract"] = {"design": "synthetic_v1", "minimum_release": "9.0.0"}
        with self.assertRaises(PerformanceClassifierError):
            classify(fixture_contract(), unsafe_env)

    def test_sin_datos_reales(self):
        fixture = fixture_envelope()
        self.assertEqual("synthetic", fixture["project"])
        self.assertEqual(EVIDENCE, fixture["observations"][0]["evidence_ref"])
        self.assertFalse(fixture["observations"][0]["operational_impact"])
        self.assertNotIn("https://", json.dumps(fixture))
        self.assertNotIn("password", json.dumps(fixture).lower())
        self.assertNotIn("personal_data", json.dumps(fixture))
        self.assertTrue(cli_contract())
        source = (ROOT / "scripts/performance-classify.py").read_text(encoding="utf-8").lower()
        for network in ("urllib.request", "requests.get(", "http.client", "socket.connect("):
            self.assertNotIn(network, source)
        self.assertNotIn("execute_actions", fixture)
        self.assertNotIn("create_work_item", fixture)

    def test_estados_unknown_explicitos(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        self.assertEqual(len(ROWS), len(set(ROWS)))
        self.assertEqual(16, len(ROWS))
        for row_id in ROWS:
            with self.subTest(requirement=row_id):
                self.assertEqual("NO_VERIFICABLE", matrix_row_status(matrix, row_id))
                self.assertEqual(UNKNOWN, matrix_row_status("", row_id))
                self.assertEqual(UNKNOWN, field_status(None))
        result = classify(fixture_contract(), fixture_envelope())
        self.assertFalse(result["execute_actions"])
        self.assertFalse(result["create_work_item"])
        self.assertEqual("unchanged", result["authority"])


if __name__ == "__main__":
    unittest.main()
