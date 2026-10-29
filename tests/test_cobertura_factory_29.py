#!/usr/bin/env python3
"""Factory #1820: cobertura conductual de 16 unidades, sin autoridad live.

Las otras cuatro unidades quedan C/D hasta que sus contratos operativos
existan o se autorice una corrección. Nunca se promueven por este test.
"""
from __future__ import annotations

import copy
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.constitution import PROTECTED_INVARIANTS
from metricas.costos import load_budgets
from metricas.organizational_complexity import (
    OrganizationalComplexityError, build_complexity_report,
    compare_simplification, contextual_budget, evaluate_workitem_complexity,
    normalize_observation,
)
from scripts.lease_auto_release_integration import (
    IntegrationPreview, _GhReadOnlyAPI, local_active_issue_ids,
    preview_integrated_activity,
)
from scripts.lease_github_port import LeaseGithubPort, PortNotArmed

BUDGETS = load_budgets(Path("metricas/presupuestos.json"), root=ROOT)
OBSERVER = "docs/observador-reservas-consumidor.md"
COMPLEXITY = "docs/organizational-complexity.md"
OBS_A = (63, 7, 71)
ORG_A = (10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 29, 40, 41)
A = tuple(f"{OBSERVER}:L{n}-U1" for n in OBS_A) + tuple(
    f"{COMPLEXITY}:L{n}-U1" for n in ORG_A
)
C = {
    f"{OBSERVER}:L77-U1": "Rollback del caller requiere PR del consumidor.",
    f"{OBSERVER}:L78-U1": "Rollback del reusable requiere release protegida.",
}
D = {
    f"{OBSERVER}:L68-U1": "CAS distribuido real todavía no implementado.",
    f"{OBSERVER}:L80-U1": "Retención documentada 7 días; workflow declara 30.",
}
ALL = set(A) | set(C) | set(D)


def observation(*, work_id: str = "Factory#1820-synthetic") -> dict:
    """Identidades ficticias; ni usuarios ni métricas de operaciones reales."""
    return {
        "version": 1,
        "work_id": work_id,
        "comparison_scope": "fixture-same-cohort",
        "task_type": "infraestructura",
        "task_size": "small",
        "risk": "medium",
        "rules_consulted": ["rule:constitution", "rule:factory"],
        "active_roles": ["role:engineering", "role:qa"],
        "reviewers": ["reviewer:qa"],
        "checks": ["check:ci", "check:policy"],
        "handoffs": [],
        "engines_consulted": ["engine:fitness"],
        "context_tokens": 8000,
        "coordination_minutes": 10,
        "wait_minutes": 8,
        "review_minutes": 10,
        "useful_execution_minutes": 40,
        "protected_metrics": {
            invariant: 1.0 for invariant in PROTECTED_INVARIANTS
        },
        "evidence_refs": ["fixture:synthetic"],
        "observed_at": "2026-10-29T00:00:00Z",
    }


class CoberturaFactory29Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: cada unidad A comprueba el comportamiento del código real."""
        self.assertEqual(16, len(A))
        # L63: el censo acepta ambos idiomas, pero no concede autoridad.
        es = {"number": 7, "state": "open",
              "labels": [{"name": "estado: reservado"}]}
        en = {"number": 9, "state": "open",
              "labels": [{"name": "status: in review"}]}
        self.assertEqual([7, 9], local_active_issue_ids(
            [[en, es]], "pl0n3r/Factory"))
        api = _GhReadOnlyAPI("pl0n3r/Factory")
        port = LeaseGithubPort(api)
        with self.assertRaises(PortNotArmed):
            port.read(7)

        # L7: la superficie operativa sigue desarmada (sin llamadas de red).
        with self.assertRaises(PortNotArmed):
            port.lock("factory-coordination-7")
        with self.assertRaises(PortNotArmed):
            port.append(7, "<!-- synthetic -->", None)
        with self.assertRaises(PortNotArmed):
            port.status(7, "closed", None)

        # L71: un candidato no eleva permisos ni prueba CAS / lock.
        candidate = IntegrationPreview(
            7, "read_only", "release", "inactive_after_recovery_grace",
            41, "reservation_marker"
        )
        self.assertFalse(candidate.release_authorized)
        self.assertFalse(candidate.lock_verified)
        self.assertFalse(candidate.cas_verified)
        self.assertIn("autoridad=NO", candidate.summary_line)

        # L10/L11/L13..20: cada dimensión observada se mide separadamente.
        raw = observation()
        item = normalize_observation(raw)
        evaluated = evaluate_workitem_complexity(item, BUDGETS)
        measures = evaluated["measurements"]
        expected = {
            "active_roles": 2,            # L10 roles
            "reviewers": 1,               # L10 revisores
            "checks": 2,                  # L11 gates
            "engines_consulted": 1,       # L13 engines
            "context_tokens": 8000,       # L14 tokens
            "coordination_minutes": 10,   # L15 coordinación
            "wait_minutes": 8,            # L16 espera
            "review_minutes": 10,         # L17 revisión
            "useful_execution_minutes": 40, # L18 trabajo útil
        }
        for dimension, value in expected.items():
            with self.subTest(dimension=dimension):
                self.assertEqual(value, measures[dimension])
        self.assertEqual(set(PROTECTED_INVARIANTS),
                         set(evaluated["protected_controls"]))  # L19
        self.assertEqual(raw["evidence_refs"], evaluated["evidence_refs"])
        self.assertEqual(raw["comparison_scope"], evaluated["comparison_scope"]) # L20

        # L29: el multiplicador proviene de presupuestos.json, no de otro motor.
        budget = contextual_budget(item, BUDGETS)
        self.assertEqual(
            BUDGETS["task_type_multipliers"][raw["task_type"]],
            budget["task_multiplier"],
        )
        self.assertEqual(set(PROTECTED_INVARIANTS),
                         set(budget["protected_controls"]))
        for key in PROTECTED_INVARIANTS:
            self.assertNotIn(key, budget["limits"])

        # L40/L41: vector observado/budget separado, sin score ni ejecución.
        for key in ("active_roles", "checks", "context_tokens",
                    "coordination_minutes", "review_minutes"):
            with self.subTest(observation_and_budget=key):
                self.assertEqual(measures[key],
                                 evaluated["dimensions"][key]["observed"])
                self.assertEqual(budget["limits"][key],
                                 evaluated["dimensions"][key]["budget"])
                self.assertIn(evaluated["dimensions"][key]["status"],
                              ("within", "over"))
        self.assertNotIn("score", evaluated)
        self.assertEqual(evaluated["observed_at"], item["observed_at"])

        # Validar el contrato de comparación; nunca activar simplificación.
        better = copy.deepcopy(raw)
        better["work_id"] = "Factory#1820-synthetic-after"
        better["context_tokens"] = 4000
        better["coordination_minutes"] = 5
        better["wait_minutes"] = 4
        better["review_minutes"] = 5
        comparison = compare_simplification(raw, better)
        self.assertEqual("unchanged", comparison["authority"])
        self.assertFalse(comparison["execute"])
        report = build_complexity_report([raw, better], BUDGETS)
        self.assertEqual(2, report["samples"])
        self.assertEqual(80, report["useful_execution_minutes"])
        self.assertGreater(report["organizational_overhead_minutes"], 0)

    def test_falla_cerrado(self):
        """AC-02: censo, permisos, presupuesto y métricas inválidos se vetan."""
        a = {"number": 7, "state": "open",
             "labels": [{"name": "status: reserved"}]}
        self.assertIsNone(local_active_issue_ids(
            [[a, a]], "pl0n3r/Factory"))
        self.assertIsNone(local_active_issue_ids(
            [[a]], "attacker/Factory"))
        self.assertIsNone(local_active_issue_ids([], "pl0n3r/Factory"))

        with patch("subprocess.run") as run:
            api = _GhReadOnlyAPI("pl0n3r/Factory")
            for method, path in [
                ("POST", "/repos/pl0n3r/Factory/issues/7"),
                ("PATCH", "/repos/pl0n3r/Factory/issues/7"),
                ("GET", "/repos/pl0n3r/Condor/issues/7"),
                ("GET", "/repos/pl0n3r/Factory/../secrets"),
            ]:
                with self.subTest(method=method, path=path):
                    with self.assertRaises(PermissionError):
                        api.request(method, path)
            run.assert_not_called()

        unknown = preview_integrated_activity(None, None, 0, now=None)
        self.assertEqual("UNKNOWN", unknown.state)
        self.assertFalse(unknown.release_authorized)

        raw = observation()
        for key, value in (
            ("context_tokens", -1),
            ("risk", "untrusted"),
            ("active_roles", ["role:qa", "role:qa"]),
            ("protected_metrics", {}),
        ):
            with self.subTest(invalid=key):
                item = copy.deepcopy(raw)
                item[key] = value
                with self.assertRaises(OrganizationalComplexityError):
                    normalize_observation(item)
        with self.assertRaises(OrganizationalComplexityError):
            contextual_budget(raw, {})
        after = observation(work_id="Factory#1820-other")
        after["comparison_scope"] = "unrelated"
        with self.assertRaises(OrganizationalComplexityError):
            compare_simplification(raw, after)

        regressed = observation(work_id="Factory#1820-regressed")
        regressed["context_tokens"] = 4000
        regressed["protected_metrics"]["security"] = 0.1
        comparison = compare_simplification(raw, regressed)
        self.assertFalse(comparison["can_claim_simplification"])
        self.assertFalse(comparison["execute"])

    def test_sin_datos_reales(self):
        """AC-03: entradas exclusivamente sintéticas; cero red o credenciales."""
        self.assertEqual(set(A) | set(C) | set(D), ALL)
        self.assertEqual((16, 2, 2), (len(A), len(C), len(D)))
        self.assertEqual("fixture:synthetic", observation()["evidence_refs"][0])
        self.assertTrue(all(reason for reason in (*C.values(), *D.values())))
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^import\s+(?:requests|httpx|socket)\b")
        self.assertNotRegex(source, r"(?m)^from\s+(?:requests|httpx|socket)\b")
        self.assertNotRegex(source, r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----")

    def test_gate_validar_presente(self):
        """AC-04: comprobar contrato de gate; success exact-HEAD corresponde a CI."""
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertEqual(1, len(re.findall(r"(?m)^  validar:$", ci)))
        gate = ci.split("\n  validar:\n", 1)[1]
        self.assertIn("name: Validar", gate)
        self.assertIn("if: always()", gate)
        self.assertIn("needs:", gate)


if __name__ == "__main__":
    unittest.main()
