"""Factory #1654: 16 brechas de observación V3 y complejidad organizacional.

Los tests son OFFLINE: no acreditan ciclos reales, CAS armado, release ni live.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS
from metricas.costos import load_budgets
from metricas.organizational_complexity import (
    OrganizationalComplexityError, build_complexity_report,
    compare_simplification, evaluate_workitem_complexity,
    normalize_observation,
)
from scripts.lease_github_port import LeaseGithubPort, PortNotArmed
from scripts.lease_auto_release_integration import _GhReadOnlyAPI

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
OBSERVER = "docs/observador-reservas-consumidor.md:"
COMPLEXITY = "docs/organizational-complexity.md:"
OBS_LINES = (7, 68, 71, 77, 78, 80)
FIELDS = {
    10: ("active_roles", "reviewers"),
    11: ("checks",), 13: ("engines_consulted",),
    14: ("context_tokens",), 15: ("coordination_minutes",),
    16: ("wait_minutes",), 17: ("review_minutes",),
    18: ("useful_execution_minutes",),
    19: ("protected_controls",),
    20: ("evidence_refs", "comparison_scope"),
}
IDS = tuple([f"{OBSERVER}L{i}-U1" for i in OBS_LINES]
            + [f"{COMPLEXITY}L{i}-U1" for i in FIELDS])


def read(path: str) -> str:
    """Read committed sources without credentials or external access."""
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(document: str) -> dict[str, tuple[str, ...]]:
    """Reject absent, duplicate and truncated exact coverage units."""
    found = {}
    for raw in document.splitlines():
        cells = tuple(x.strip() for x in raw.strip().strip("|").split("|"))
        if not cells or cells[0].strip(chr(96)) not in IDS:
            continue
        key = cells[0].strip(chr(96))
        if key in found or len(cells) != 5 or not all(cells[:4]):
            raise ValueError("unidad de matriz ambigua: " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError("faltan filas obligatorias de #1654")
    return found


def synthetic_item() -> dict:
    """Only fake IDs, categories and deterministic metrics."""
    return {
        "version": 1, "work_id": "factory-synthetic-1654-before",
        "comparison_scope": "synthetic-comparable-1654",
        "task_type": "infraestructura", "task_size": "small", "risk": "medium",
        "rules_consulted": ["rule:constitution", "rule:factory-plan"],
        "active_roles": ["role:engineering", "role:qa"],
        "reviewers": ["reviewer:qa"],
        "checks": ["check:ci", "check:security", "check:quality"],
        "handoffs": [],
        "engines_consulted": ["engine:fitness", "engine:constitution"],
        "context_tokens": 4000, "coordination_minutes": 12,
        "wait_minutes": 8, "review_minutes": 5,
        "useful_execution_minutes": 45,
        "protected_metrics": {k: 1.0 for k in PROTECTED_INVARIANTS},
        "evidence_refs": ["synthetic:issue-1654-event-1"],
        "observed_at": "2026-10-28T12:00:00Z",
    }


def operational_status(_: object) -> str:
    """Local evidence is never proof of operational release."""
    return UNKNOWN


class BrechasFactory36Tests(unittest.TestCase):
    """AC-01 through AC-04, fail closed and without real data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = read("docs/matriz-cobertura.md")
        cls.units = matrix_rows(cls.matrix)
        cls.budgets = load_budgets(
            ROOT / "metricas/presupuestos.json", root=ROOT,
        )

    def test_contrato_principal(self) -> None:
        """AC-01: each of 16 IDs plus actual code behavior and limits."""
        self.assertEqual(len(self.units), 16)
        for uid in IDS:
            with self.subTest(unit=uid):
                entry = self.units[uid]
                self.assertEqual(entry[0].strip(chr(96)), uid)
                self.assertEqual(entry[2], "NO_VERIFICABLE")
                self.assertIn("Contraste #157", entry[3])
                self.assertEqual(operational_status(entry), UNKNOWN)

        docs = read("docs/observador-reservas-consumidor.md")
        reusable = read(".github/workflows/observador-reservas-consumidor.yml")
        caller = read("template/.github/workflows/observador-reservas-consumidor.yml")
        # L7: feature disabled, release and mutations never armed by source.
        self.assertIn("FACTORY_LEASE_AUTO_RELEASE_ENABLED: 'false'", reusable)
        self.assertIn("release_authorized:false", docs)
        self.assertIn("mutations:0", docs)
        port = LeaseGithubPort(object(), armed=False)
        for action in (
            lambda: port.read(123), lambda: port.lock("factory-coordination-1"),
            lambda: port.append(123, "synthetic", None),
            lambda: port.status(123, "estado: disponible", None),
        ):
            with self.assertRaises(PortNotArmed):
                action()
        # L68: no real CAS is proven. L71: an artifact is never authority.
        self.assertIn("protocolo de bloqueo/CAS compartido real", docs)
        self.assertIn("PortNotArmed", read("scripts/lease_github_port.py"))
        self.assertIn("terminal_certified:false", docs)
        self.assertIn("release_authorized:false", reusable)
        self.assertIn("mutations:0", reusable)
        # L77/L78: caller PR rollback differs from a protected Factory release.
        key = chr(36) + "{{ github.repository_id }}"
        self.assertIn("lease-consumer-caller-" + key, caller)
        self.assertIn("factory-coordination-" + key, reusable)
        self.assertIn("observador-reservas-consumidor.yml@v1", caller)
        # L80: artifact source does not authenticate a real redaction event.
        self.assertIn("GITHUB_TOKEN", docs)
        self.assertIn("name: lease-consumer-evidence-" + chr(36)
                      + "{{ github.run_id }}", reusable)
        self.assertIn("permissions:\n  contents: read", reusable)

        item = synthetic_item()
        result = evaluate_workitem_complexity(item, self.budgets)
        measures = result["measurements"]
        # L10/11/13..18: real measurement values, not textual presence.
        for field, value in (
            ("active_roles", 2), ("reviewers", 1), ("checks", 3),
            ("engines_consulted", 2), ("context_tokens", 4000),
            ("coordination_minutes", 12), ("wait_minutes", 8),
            ("review_minutes", 5), ("useful_execution_minutes", 45),
        ):
            with self.subTest(measure=field):
                self.assertEqual(measures[field], value)
        self.assertEqual(measures["organizational_overhead_minutes"], 25)
        self.assertEqual(measures["total_minutes"], 70)
        # L19: all constitutional invariants remain protected; no score.
        self.assertEqual(set(result["protected_controls"]), set(PROTECTED_INVARIANTS))
        self.assertEqual(set(PROTECTED_INVARIANTS), {
            "security", "privacy", "traceability", "reversibility", "authority",
        })
        self.assertNotIn("score", result)
        # L20: preserved provenance and comparison cohort.
        self.assertEqual(result["comparison_scope"], item["comparison_scope"])
        self.assertEqual(result["evidence_refs"], item["evidence_refs"])
        self.assertRegex(result["fingerprint"], r"^[0-9a-f]{64}$")
        report = build_complexity_report([item], self.budgets)
        self.assertEqual(report["useful_execution_minutes"], 45)
        self.assertEqual(report["organizational_overhead_minutes"], 25)
        for line, fields in FIELDS.items():
            with self.subTest(unit=f"{COMPLEXITY}L{line}-U1"):
                self.assertIn(f"{COMPLEXITY}L{line}-U1", self.units)
                for field in fields:
                    self.assertIn(field, result if field in result else measures)

    def test_falla_cerrado(self) -> None:
        """AC-02: missing rows/metrics, unknown budgets and cohorts reject."""
        for uid in IDS:
            original = next(
                s for s in self.matrix.splitlines()
                if s.startswith("| " + chr(96) + uid + chr(96) + " |")
            )
            with self.subTest(unit=uid):
                with self.assertRaises(ValueError):
                    matrix_rows(self.matrix.replace(original, ""))
                with self.assertRaises(ValueError):
                    matrix_rows(self.matrix + "\n " + original)
                with self.assertRaises(ValueError):
                    matrix_rows(self.matrix.replace(
                        original, "| " + chr(96) + uid + chr(96) + " | corta |"))
        item = synthetic_item()
        for field in (
            "active_roles", "reviewers", "checks", "engines_consulted",
            "context_tokens", "coordination_minutes", "wait_minutes",
            "review_minutes", "useful_execution_minutes", "protected_metrics",
            "evidence_refs", "comparison_scope",
        ):
            with self.subTest(field=field):
                absent = copy.deepcopy(item)
                absent.pop(field)
                with self.assertRaises(OrganizationalComplexityError):
                    normalize_observation(absent)
        ambiguous = copy.deepcopy(item)
        ambiguous["context_tokens"] = None
        with self.assertRaises(OrganizationalComplexityError):
            evaluate_workitem_complexity(ambiguous, self.budgets)
        unprotected = copy.deepcopy(item)
        unprotected["protected_metrics"].pop("authority")
        with self.assertRaises(OrganizationalComplexityError):
            evaluate_workitem_complexity(unprotected, self.budgets)
        different = copy.deepcopy(item)
        different["comparison_scope"] = "different-synthetic-cohort"
        with self.assertRaises(OrganizationalComplexityError):
            compare_simplification(item, different)
        self.assertEqual(UNKNOWN, operational_status({"release_authorized": True}))

    def test_sin_datos_reales(self) -> None:
        """AC-03: anonymous fixture and no API access, tokens or PII."""
        item = synthetic_item()
        self.assertEqual(
            normalize_observation(item)["work_id"],
            "factory-synthetic-1654-before",
        )
        payload = json.dumps(item, sort_keys=True)
        for forbidden in ("@", "http://", "https://", "Bearer ", "ghp_", "password"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(UNKNOWN, operational_status(item))
        api = _GhReadOnlyAPI("pl0n3r/Factory")
        self.assertFalse(LeaseGithubPort(api, armed=False)._armed)

    def test_estados_unknown_explicitos(self) -> None:
        """AC-04: no 100 real cycles, release adoption or protected CAS."""
        docs = read("docs/observador-reservas-consumidor.md")
        reusable = read(".github/workflows/observador-reservas-consumidor.yml")
        self.assertEqual(set(self.units), set(IDS))
        self.assertIn("100 ciclos terminales válidos", docs)
        self.assertIn("24 horas reales", docs)
        self.assertIn("PortNotArmed", docs)
        self.assertIn("terminal_certified:false", reusable)
        for uid in IDS:
            with self.subTest(unit=uid):
                self.assertEqual("NO_VERIFICABLE", self.units[uid][2])
                self.assertEqual(UNKNOWN, operational_status(self.units[uid]))
        self.assertEqual(UNKNOWN, operational_status("candidate_terminal"))
        # Existing discrepancy: docs say 7 days and reusable retains 30.
        # Do not change either outside this issue's claim or mark it green.
        self.assertIn("retienen 7 días", docs)
        self.assertIn("retention-days: 30", reusable)
        self.assertEqual(UNKNOWN, operational_status({"retention_match": False}))


if __name__ == "__main__":
    unittest.main()
