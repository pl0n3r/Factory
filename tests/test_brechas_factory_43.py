"""Factory #1661: prueba sintética de 16 brechas de contratos de performance.

No consulta servicios externos, no aporta evidencia de producción ni modifica matriz.
"""
from __future__ import annotations

import copy
from datetime import datetime
import json
from pathlib import Path
import runpy
import unittest

from performance.contract import validate_performance_contract
from performance.remediation import (
    PerformanceRemediationError, evaluate_before_after, plan_remediation,
)
from scripts.work_origin import validate_work_item

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = runpy.run_path(str(ROOT / "tests/test_performance_remediation.py"))
finding, triage, proposal = (FIXTURES[name] for name in ("finding", "triage", "proposal"))

UNITS = (
    "docs/performance-grindflow.md:L9-U2",
    "docs/performance-grindflow.md:L9-U3",
    "docs/performance-remediation.md:L3-U1",
    "docs/performance-remediation.md:L9-U1",
    "docs/performance-remediation.md:L11-U1",
    "docs/performance-remediation.md:L12-U1",
    "docs/performance-remediation.md:L13-U1",
    "docs/performance-remediation.md:L14-U1",
    "docs/performance-remediation.md:L17-U1",
    "docs/performance-remediation.md:L21-U1",
    "docs/performance-remediation.md:L23-U2",
    "docs/performance-remediation.md:L25-U1",
    "docs/performance-remediation.md:L25-U2",
    "docs/performance-remediation.md:L25-U4",
    "docs/performance-remediation.md:L25-U5",
    "docs/performance-remediation.md:L29-U1",
)


def improved():
    before = finding()
    return finding(
        classification="PERF_INFO", breach=False, evidence_ref="synthetic:after",
        identity={"sha": "b" * 40, "release": "v1.2.4"},
        observed={**before["observed"], "value": 220,
                  "observed_at": "2026-09-28T20:06:00Z"},
    )


class BrechasFactory43Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grindflow = (ROOT / "docs/performance-grindflow.md").read_text(encoding="utf-8")
        cls.remediation = (ROOT / "docs/performance-remediation.md").read_text(encoding="utf-8")
        cls.contract = validate_performance_contract(json.loads(
            (ROOT / "performance/contracts/grindflow.json").read_text(encoding="utf-8")
        ))
        cls.rows = {}
        for line in (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            parts = [part.strip() for part in line.split("|")]
            key = parts[1].strip(chr(96) + " ") if len(parts) > 4 else ""
            if key in UNITS:
                if key in cls.rows:
                    raise AssertionError("Fila duplicada en matriz: " + key)
                cls.rows[key] = parts

    def test_contrato_principal(self):
        """AC-01: una aserción trazable por cada unidad del issue (16 reales)."""
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(self.rows), set(UNITS))
        metric = self.contract["surfaces"][0]["metrics"][0]
        started = datetime.fromisoformat("2026-10-10T00:41:39+00:00")
        finished = datetime.fromisoformat("2026-10-10T00:42:17+00:00")
        duration = (finished - started).total_seconds()
        safe = plan_remediation(finding(), triage(), proposal())
        info = plan_remediation(finding(classification="PERF_INFO"), triage("PERF_INFO"), proposal())
        stale = plan_remediation(finding(evidence_state="STALE"), triage(), proposal())
        escalation = plan_remediation(
            finding(), triage(), proposal(triggered_conditions=["cost_change"])
        )
        unsafe = plan_remediation(finding(), triage(), proposal(reversible=False))
        adopted = evaluate_before_after(finding(), improved())
        same_build = improved()
        same_build["identity"] = finding()["identity"]
        rejected = evaluate_before_after(finding(), same_build)
        checks = {
            "docs/performance-grindflow.md:L9-U2":
                duration == 38 == metric["baseline"]["value"]
                and metric["baseline"]["observed_at"] == "2026-10-10T00:42:17Z",
            "docs/performance-grindflow.md:L9-U3":
                self.contract["surfaces"][0]["id"] == "ci.production_smoke"
                and metric["id"] == "job_duration" and "no TTFB" in self.grindflow,
            "docs/performance-remediation.md:L3-U1":
                safe["work_item"] == validate_work_item(safe["work_item"])
                and safe["work_item"]["producer_ref"] == "factory:performance",
            "docs/performance-remediation.md:L9-U1":
                (info["decision"], stale["decision"], escalation["decision"],
                 unsafe["decision"], safe["decision"])
                == ("NO_ACTION", "BLOCKED", "ESCALATE", "BLOCKED", "AUTO_REPAIR"),
            "docs/performance-remediation.md:L11-U1": info["decision"] == "NO_ACTION",
            "docs/performance-remediation.md:L12-U1": stale["decision"] == "BLOCKED",
            "docs/performance-remediation.md:L13-U1":
                escalation["decision"] == "ESCALATE" and escalation["human_gate_required"],
            "docs/performance-remediation.md:L14-U1": unsafe["decision"] == "BLOCKED",
            "docs/performance-remediation.md:L17-U1":
                safe["decision"] == "AUTO_REPAIR" and safe["execute_actions"] is False
                and safe["authority"] == "unchanged",
            "docs/performance-remediation.md:L21-U1":
                adopted["decision"] == "ADOPT" and adopted["delta"] == -80,
            "docs/performance-remediation.md:L23-U2":
                rejected["decision"] == "REVERT_OR_REPLAN"
                and rejected["reasons"] == ["unchanged_build_identity"],
            "docs/performance-remediation.md:L25-U1":
                finding()["observed"]["sample_count"] == 30
                and finding()["observed"]["window_seconds"] == 300,
            "docs/performance-remediation.md:L25-U2":
                finding()["observed"]["unit"] == finding()["budget"]["unit"] == "ms",
            "docs/performance-remediation.md:L25-U4":
                "esa validación corresponde al detector y al productor autorizado"
                in self.remediation and safe["execute_actions"] is False,
            "docs/performance-remediation.md:L25-U5":
                "verificar la autenticidad" in self.remediation
                and adopted["execute_actions"] is False,
            "docs/performance-remediation.md:L29-U1":
                safe["queue_required"] is True and safe["execute_actions"] is False
                and adopted["authority"] == "unchanged",
        }
        self.assertEqual(set(checks), set(UNITS))
        for key, valid in checks.items():
            with self.subTest(unit=key):
                self.assertEqual(self.rows[key][3], "NO_VERIFICABLE")
                self.assertTrue(valid, key)

    def test_falla_cerrado(self):
        """AC-02: autoridad, forma y procedencia falsas nunca autorizan adopción."""
        for condition in ("cost_change", "architecture_change", "consistency_risk",
                          "business_semantics", "destructive_migration",
                          "sensitive_data", "capacity_budget"):
            with self.subTest(condition=condition):
                decision = plan_remediation(
                    finding(), triage(), proposal(triggered_conditions=[condition])
                )
                self.assertEqual(decision["decision"], "ESCALATE")
                self.assertFalse(decision["execute_actions"])
        for changes in ({"reversible": False}, {"tests_covered": False}):
            with self.subTest(changes=changes):
                self.assertEqual(
                    plan_remediation(finding(), triage(), proposal(**changes))["decision"],
                    "BLOCKED",
                )
        self.assertEqual(
            plan_remediation(finding(), triage(), proposal(within_authority=False))["decision"],
            "ESCALATE",
        )
        for state in ("STALE", "INSUFFICIENT", "UNKNOWN"):
            with self.subTest(state=state):
                self.assertEqual(
                    plan_remediation(finding(evidence_state=state), triage(), proposal())["decision"],
                    "BLOCKED",
                )
        for field in ("project", "surface", "metric"):
            with self.subTest(identity=field), self.assertRaises(PerformanceRemediationError):
                evaluate_before_after(finding(), finding(**{field: "other"}))
        for field, value in (("sample_count", 0), ("sample_count", True),
                             ("window_seconds", -1), ("window_seconds", 31_536_001),
                             ("value", float("nan")), ("value", float("inf"))):
            wrong = improved()
            wrong["observed"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(
                PerformanceRemediationError
            ):
                evaluate_before_after(finding(), wrong)
        with self.assertRaises(PerformanceRemediationError):
            evaluate_before_after(
                finding(), improved(budget={"operator": "lte", "unit": "s", "value": 250})
            )
        before = finding()
        for wrong in (
            improved(evidence_ref=before["evidence_ref"]),
            improved(observed={**before["observed"], "value": 220}),
            improved(identity=before["identity"]),
        ):
            with self.subTest(ref=wrong["evidence_ref"]):
                self.assertEqual(
                    evaluate_before_after(before, wrong)["decision"], "REVERT_OR_REPLAN"
                )
        invalid = improved()
        invalid["observed"]["observed_at"] = "2026-02-30T00:00:00Z"
        with self.assertRaises(PerformanceRemediationError):
            evaluate_before_after(before, invalid)

    def test_sin_datos_reales(self):
        """AC-03: solo muestras falsas, no operaciones ni secretos."""
        data = {"before": finding(), "after": improved(), "proposal": proposal()}
        payload = json.dumps(data, sort_keys=True)
        self.assertNotIn("https://", payload)
        self.assertNotRegex(payload, r"(?i)(?:github_pat_|Bearer\s+\S{10,}|sk-\w{20,})")
        self.assertNotRegex(payload, r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
        self.assertTrue(finding()["evidence_ref"].startswith("run:"))
        self.assertEqual(plan_remediation(
            finding(), triage(), proposal()
        )["authority"], "unchanged")
        self.assertFalse(plan_remediation(
            finding(), triage(), proposal()
        )["execute_actions"])

    def test_estados_unknown_explicitos(self):
        """AC-04: superficies sin medición e integración mantienen UNKNOWN."""
        self.assertEqual(len(self.contract["surfaces"]), 1)
        self.assertEqual(self.grindflow.count("| UNKNOWN |"), 4)
        for surface in ("Landing pública", "Login", "Composer", "Library"):
            with self.subTest(surface=surface):
                self.assertIn(surface, self.grindflow)
        for key in UNITS:
            with self.subTest(unit=key):
                self.assertEqual(self.rows[key][3], "NO_VERIFICABLE")
                self.assertIn("#1572", self.rows[key][4])
        self.assertIn("no una tendencia", self.grindflow)
        self.assertIn("sin evidencia", self.grindflow)
        self.assertFalse(plan_remediation(
            finding(evidence_state="UNKNOWN"), triage(), proposal()
        )["execute_actions"])
        self.assertEqual(evaluate_before_after(
            finding(evidence_state="UNKNOWN"), improved()
        )["decision"], "REVERT_OR_REPLAN")


if __name__ == "__main__":
    unittest.main()
