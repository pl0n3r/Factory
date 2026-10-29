"""Issue #1825: behavior checks for real Factory performance functions.

A = executable offline; B = requires authentic GitHub job evidence;
C = documentary interpretation, not independently executable.
No production, PII, credentials, web access, or coverage matrix edits.
"""
from __future__ import annotations

import copy
from datetime import datetime
import json
from pathlib import Path
import re
import runpy
import unittest

from performance.contract import PerformanceContractError, validate_performance_contract
from performance.detector import detect_performance
from performance.remediation import plan_remediation

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "performance/contracts/grindflow.json"
MATRIX = ROOT / "docs/matriz-cobertura.md"
START = "2026-10-10T00:41:39Z"
END = "2026-10-10T00:42:17Z"
GF = "docs/performance-grindflow.md"
RM = "docs/performance-remediation.md"

A = {
    f"{GF}:L10-U1", f"{GF}:L11-U1", f"{GF}:L22-U1",
    f"{GF}:L22-U2", f"{GF}:L26-U1", f"{GF}:L7-U1",
    f"{GF}:L9-U2", f"{GF}:L9-U3",
    f"{RM}:L11-U1", f"{RM}:L12-U1", f"{RM}:L13-U1",
    f"{RM}:L14-U1", f"{RM}:L17-U1",
}
B = {
    f"{GF}:L7-U2": "Historical main SHA requires authenticated GitHub history.",
    f"{GF}:L8-U1": "Production smoke run needs independent real-job receipt.",
    f"{GF}:L9-U1": "Real job start and end need authenticated GitHub Jobs REST.",
}
C = {
    f"{GF}:L10-U2": "One sample is not evidence of a statistical trend.",
    f"{GF}:L11-U2": "SLA and RTO are policy decisions, not runtime behavior.",
    f"{GF}:L11-U3": "Single-sample percentiles are not statistically proven.",
    f"{GF}:L22-U3": "New web surfaces need authorized evidence and scope change.",
}
IDS = A | set(B) | set(C)
ID_REGEX = re.compile(
    r"^\|\s*.(docs/performance-(?:grindflow|remediation)\.md:L\d+-U\d+).\s*\|"
)


def coverage_rows(text: str) -> dict[str, tuple[str, ...]]:
    """Read full rows, rejecting duplicate and premature promotion."""
    if not isinstance(text, str):
        raise ValueError("UNKNOWN matrix")
    result: dict[str, tuple[str, ...]] = {}
    for line in text.splitlines():
        match = ID_REGEX.match(line)
        if not match or match.group(1) not in IDS:
            continue
        key = match.group(1)
        cells = tuple(part.strip() for part in line.split("|"))
        if (key in result or len(cells) < 6
                or cells[1] != chr(96) + key + chr(96)
                or not cells[2] or cells[3] != "NO_VERIFICABLE"):
            raise ValueError("UNKNOWN matrix row " + key)
        result[key] = cells
    if set(result) != IDS:
        raise ValueError("UNKNOWN missing coverage IDs")
    return result


def duration() -> int:
    t0 = datetime.fromisoformat(START.replace("Z", "+00:00"))
    t1 = datetime.fromisoformat(END.replace("Z", "+00:00"))
    return int((t1 - t0).total_seconds())


def observation(**changes: object) -> dict:
    value = {
        "version": 1, "project": "grindflow", "surface": "ci.production_smoke",
        "metric": "job_duration", "value": 38, "unit": "s",
        "observed_at": END, "window_seconds": 38, "sample_count": 1,
        "severity": "low", "operational_impact": False,
        "bottleneck": "unknown", "evidence_ref": "run:synthetic",
        "sha": "a" * 40, "release": "v1",
    }
    value.update(changes)
    return value


class CoberturaFactory34Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.rows = coverage_rows(MATRIX.read_text(encoding="utf-8"))
        f = runpy.run_path(str(ROOT / "tests/test_performance_remediation.py"))
        cls.finding, cls.triage, cls.proposal = (
            staticmethod(f["finding"]), staticmethod(f["triage"]),
            staticmethod(f["proposal"]),
        )

    def test_contrato_principal(self) -> None:
        """AC-01: each A row has a distinct production-function predicate."""
        canon = validate_performance_contract(self.raw)
        metric = canon["surfaces"][0]["metrics"][0]
        valid = detect_performance(self.raw, observation(), evaluated_at=END)
        web = detect_performance(
            self.raw, observation(surface="public.home"), evaluated_at=END,
        )
        info = plan_remediation(
            self.finding(classification="PERF_INFO", breach=False),
            self.triage("PERF_INFO"), self.proposal(),
        )
        stale = plan_remediation(
            self.finding(evidence_state="STALE"), self.triage(), self.proposal(),
        )
        risk = plan_remediation(
            self.finding(), self.triage(),
            self.proposal(triggered_conditions=["cost_change"]),
        )
        untested = plan_remediation(
            self.finding(), self.triage(),
            self.proposal(tests_covered=False),
        )
        eligible = plan_remediation(
            self.finding(), self.triage(), self.proposal(),
        )
        proofs = {
            f"{GF}:L10-U1": duration() == metric["window"]["duration_seconds"] == 38,
            f"{GF}:L11-U1": (
                metric["budget"] == {"operator": "lte", "value": 120, "unit": "s"}
                and valid["classification"] == "PERF_INFO"
                and valid["breach"] is False
            ),
            f"{GF}:L22-U1": (
                metric["baseline"]["value"] == 38
                and isinstance(metric["baseline"]["value"], (float, int))
            ),
            f"{GF}:L22-U2": (
                canon["version"] == 1 and metric["baseline"]["unit"] == "s"
            ),
            f"{GF}:L26-U1": (
                web["evidence_state"] == "UNKNOWN"
                and web["breach"] is None
                and web["classification"] == "PERF_REVIEW"
            ),
            f"{GF}:L7-U1": canon["project"] == "grindflow",
            f"{GF}:L9-U2": duration() == metric["baseline"]["value"] == 38,
            f"{GF}:L9-U3": (
                len(canon["surfaces"]) == 1
                and canon["surfaces"][0]["id"] == "ci.production_smoke"
                and metric["id"] == "job_duration"
                and web["budget"] is None
            ),
            f"{RM}:L11-U1": (
                info["decision"] == "NO_ACTION" and info["execute_actions"] is False
            ),
            f"{RM}:L12-U1": stale["decision"] == "BLOCKED",
            f"{RM}:L13-U1": (
                risk["decision"] == "ESCALATE"
                and risk["human_gate_required"] is True
                and "cost_change" in risk["reasons"]
            ),
            f"{RM}:L14-U1": untested["decision"] == "BLOCKED",
            f"{RM}:L17-U1": (
                eligible["decision"] == "AUTO_REPAIR"
                and eligible["queue_required"] is True
                and eligible["execute_actions"] is False
                and eligible["authority"] == "unchanged"
            ),
        }
        self.assertEqual((len(A), len(B), len(C)), (13, 3, 4))
        self.assertEqual(set(proofs), A)
        self.assertEqual(set(self.rows), IDS)
        for key, good in proofs.items():
            with self.subTest(row=key):
                self.assertIs(good, True, key + ": production behavior failed")
        for key, reason in {**B, **C}.items():
            with self.subTest(non_offline=key):
                self.assertGreater(len(reason), 28)
                self.assertEqual(self.rows[key][3], "NO_VERIFICABLE")

    def test_falla_cerrado(self) -> None:
        """AC-02: invalid measurements, absent authority and stale evidence."""
        for invalid in ("UNKNOWN", None, True, float("nan"), float("inf")):
            payload = copy.deepcopy(self.raw)
            payload["surfaces"][0]["metrics"][0]["baseline"]["value"] = invalid
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(payload)
        for extra in ({"reason": "unverified"}, {"observed_at": "tomorrow"}):
            payload = copy.deepcopy(self.raw)
            payload["surfaces"][0]["metrics"][0]["evidence"].update(extra)
            with self.subTest(evidence=extra):
                with self.assertRaises(PerformanceContractError):
                    validate_performance_contract(payload)
        old = detect_performance(
            self.raw, observation(), evaluated_at="2026-10-29T00:00:00Z",
        )
        self.assertEqual(old["evidence_state"], "STALE")
        self.assertEqual(old["classification"], "PERF_REVIEW")
        self.assertEqual(old["breach"], False)
        no_authority = plan_remediation(
            self.finding(), self.triage(),
            self.proposal(within_authority=False),
        )
        self.assertEqual(no_authority["decision"], "ESCALATE")
        self.assertTrue(no_authority["human_gate_required"])
        irreversible = plan_remediation(
            self.finding(), self.triage(), self.proposal(reversible=False),
        )
        self.assertEqual(irreversible["decision"], "BLOCKED")
        self.assertFalse(irreversible["execute_actions"])

    def test_sin_datos_reales(self) -> None:
        """AC-03: only checked-in synthetic inputs, no network or credentials."""
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^import (requests|httpx|urllib|socket)\b")
        self.assertNotRegex(source, r"(?m)^from (requests|httpx|urllib|socket) ")
        self.assertNotIn("api." + "hostinger.com", source)
        self.assertEqual(
            plan_remediation(self.finding(), self.triage(),
                             self.proposal())["authority"], "unchanged",
        )
        self.assertFalse(
            plan_remediation(self.finding(), self.triage(),
                             self.proposal())["execute_actions"]
        )

    def test_ci_gate_contract(self) -> None:
        """AC-04: check CI wiring; exact-SHA Github terminal success is separate."""
        workflow = (ROOT / ".github/workflows/factory-ci.yml").read_text(
            encoding="utf-8",
        )
        self.assertIn("name: CI factory", workflow)
        self.assertIn("name: Tests de scripts", workflow)
        self.assertIn("python3 -m unittest discover -s tests -p 'test_*.py'", workflow)
        self.assertIn("name: Validar", workflow)


if __name__ == "__main__":
    unittest.main()
