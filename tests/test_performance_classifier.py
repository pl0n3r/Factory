import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from performance.classifier import PerformanceClassifierError, classify_performance_envelope

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "performance/contracts/brvtal.json").read_text(encoding="utf-8"))
SHA = "7ac39afa8ad205cc3c3668906a6d1ffa873ac1cf"
REF = "github:pl0n3r/brvtal/actions/runs/36853443439"
NOW = "2026-10-01T12:00:00Z"


def observation(surface, metric, value, unit):
    observed_at = (
        "2026-10-01T11:47:44Z"
        if surface == "public.home.mobile"
        else "2026-10-01T11:47:49Z"
    )
    return {
        "version": 1,
        "project": "brvtal",
        "surface": surface,
        "metric": metric,
        "value": value,
        "unit": unit,
        "observed_at": observed_at,
        "window_seconds": 1,
        "sample_count": 1,
        "severity": "info",
        "operational_impact": False,
        "bottleneck": "unknown",
        "evidence_ref": REF,
        "sha": SHA,
        "release": "0.1.101",
    }


def envelope():
    rows = []
    values = {
        "public.home.mobile": {
            "fcp": (380, "ms"),
            "lcp": (1624, "ms"),
            "cls": (0, "ratio"),
            "dom_content_loaded": (419.3, "ms"),
            "load_event_end": (1724.1, "ms"),
        },
        "public.home.desktop": {
            "fcp": (440, "ms"),
            "lcp": (1748, "ms"),
            "cls": (0.005, "ratio"),
            "dom_content_loaded": (492.9, "ms"),
            "load_event_end": (1841.4, "ms"),
        },
    }
    for surface, metrics in values.items():
        for metric, (value, unit) in metrics.items():
            rows.append(observation(surface, metric, value, unit))
    return {
        "version": 1,
        "project": "brvtal",
        "classification_authority": "factory-performance-v1",
        "classification": None,
        "identity": {"sha": SHA, "release": "0.1.101"},
        "evidence_ref": REF,
        "observed_at": "2026-10-01T11:47:49Z",
        "observations": rows,
    }


class PerformanceClassifierTests(unittest.TestCase):
    def test_valid_brvtal_envelope_uses_canonical_detector(self):
        result = classify_performance_envelope(CONTRACT, envelope(), evaluated_at=NOW)
        self.assertEqual(result["summary"]["total"], 10)
        self.assertEqual(
            result["summary"]["classifications"],
            {"PERF_INFO": 6, "PERF_REVIEW": 4},
        )
        self.assertEqual(
            result["summary"]["evidence_states"],
            {"CURRENT": 6, "UNKNOWN": 4},
        )
        self.assertEqual(result["authority"], "unchanged")
        self.assertFalse(result["execute_actions"])
        self.assertFalse(result["create_work_item"])
        contracted = [row for row in result["results"] if row["budget"] is not None]
        self.assertEqual(len(contracted), 6)
        self.assertTrue(all(row["breach"] is False for row in contracted))

    def test_identity_provenance_and_shape_fail_closed(self):
        cases = []
        wrong_project = envelope(); wrong_project["project"] = "other"; cases.append(wrong_project)
        wrong_sha = envelope(); wrong_sha["identity"]["sha"] = "b" * 40; cases.append(wrong_sha)
        wrong_ref = envelope(); wrong_ref["evidence_ref"] = "github:other"; cases.append(wrong_ref)
        classified = envelope(); classified["classification"] = "PERF_INFO"; cases.append(classified)
        extra = envelope(); extra["secret_payload"] = "DO_NOT_ECHO"; cases.append(extra)
        duplicate = envelope(); duplicate["observations"].append(copy.deepcopy(duplicate["observations"][0])); cases.append(duplicate)
        for payload in cases:
            with self.subTest(keys=set(payload)), self.assertRaises(PerformanceClassifierError) as caught:
                classify_performance_envelope(CONTRACT, payload, evaluated_at=NOW)
            self.assertNotIn("DO_NOT_ECHO", str(caught.exception))

    def test_unbudgeted_metrics_remain_unknown_through_classifier(self):
        result = classify_performance_envelope(CONTRACT, envelope(), evaluated_at=NOW)
        unknown = [
            row
            for row in result["results"]
            if row["metric"] in {"dom_content_loaded", "load_event_end"}
        ]
        self.assertEqual(len(unknown), 4)
        self.assertTrue(
            all(
                row["classification"] == "PERF_REVIEW"
                and row["evidence_state"] == "UNKNOWN"
                and row["budget"] is None
                and row["breach"] is None
                for row in unknown
            )
        )

    def test_cli_is_deterministic_and_offline(self):
        source = (ROOT / "scripts/performance-classify.py").read_text(encoding="utf-8")
        for forbidden in (
            "urllib", "requests", "http://", "https://", "github",
            "socket", "http.client",
        ):
            self.assertNotIn(forbidden, source.lower())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_path = root / "contract.json"
            envelope_path = root / "envelope.json"
            contract_path.write_text(json.dumps(CONTRACT), encoding="utf-8")
            envelope_path.write_text(json.dumps(envelope()), encoding="utf-8")
            cmd = [
                sys.executable, str(ROOT / "scripts/performance-classify.py"),
                "--contract", str(contract_path),
                "--envelope", str(envelope_path),
                "--evaluated-at", NOW,
            ]
            first = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
            second = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stderr, "")
        self.assertEqual(json.loads(first.stdout)["summary"]["total"], 10)


if __name__ == "__main__":
    unittest.main()
