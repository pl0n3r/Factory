"""Contratos sintéticos para las 16 brechas de Factory #1655.

Solo ejercita código local y fixtures estáticos; no acredita operación live ni
reconcilia docs/matriz-cobertura.md (esa modificación pertenece a otra hoja).
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS
from metricas.organizational_complexity import (
    OrganizationalComplexityError,
    build_complexity_report,
    compare_simplification,
    contextual_budget,
    evaluate_workitem_complexity,
    normalize_observation,
)
from scripts.orquestador_kit import PlanError, parse_plan, topological_order


ROOT = Path(__file__).resolve().parents[1]
BUDGETS = json.loads(
    (ROOT / "metricas/presupuestos.json").read_text(encoding="utf-8")
)
UNITS = (
    "docs/organizational-complexity.md:L29-U1",
    "docs/organizational-complexity.md:L40-U1",
    "docs/organizational-complexity.md:L41-U1",
    "docs/organizational-complexity.md:L42-U1",
    "docs/organizational-complexity.md:L48-U1",
    "docs/organizational-complexity.md:L52-U1",
    "docs/organizational-complexity.md:L53-U1",
    "docs/organizational-complexity.md:L61-U1",
    "docs/organizational-complexity.md:L62-U1",
    "docs/organizational-complexity.md:L63-U1",
    "docs/organizational-complexity.md:L64-U1",
    "docs/organizational-complexity.md:L65-U1",
    "docs/organizational-complexity.md:L66-U1",
    "docs/organizational-complexity.md:L68-U1",
    "docs/organizational-complexity.md:L9-U1",
    "docs/orquestador.md:B01",
)


def observation(work_id="synthetic-before", **changes):
    """Observación artificial completa con valores verificables y sin PII."""
    item = {
        "version": 1,
        "work_id": work_id,
        "comparison_scope": "synthetic-factory-cohort",
        "task_type": "infraestructura",
        "task_size": "small",
        "risk": "medium",
        "rules_consulted": ["rule:constitution", "rule:planning"],
        "active_roles": ["role:engineering", "role:qa"],
        "reviewers": ["reviewer:qa"],
        "checks": ["check:ci"],
        "handoffs": [],
        "engines_consulted": ["engine:fitness"],
        "context_tokens": 4000,
        "coordination_minutes": 12,
        "wait_minutes": 6,
        "review_minutes": 2,
        "useful_execution_minutes": 40,
        "protected_metrics": {key: 1.0 for key in PROTECTED_INVARIANTS},
        "evidence_refs": ["synthetic:factory-1655"],
        "observed_at": "2026-10-01T00:00:00Z",
    }
    item.update(changes)
    return item


def plan(*tasks):
    """Marker de /planificar con tareas sintéticas sin mutar Issues reales."""
    return "<!-- factory-plan " + json.dumps(
        {"version": 1, "tasks": list(tasks)}, separators=(",", ":")
    ) + " -->"


def task(key, path, dependencies=()):
    return {
        "key": key,
        "title": "Prueba sintética " + key,
        "owner": "pl0n3r",
        "paths": [path],
        "depends_on": list(dependencies),
    }


class BrechasFactory37Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: correspondencia exacta de cada unidad con aserción funcional."""
        before = observation()
        after = observation(
            "synthetic-after",
            rules_consulted=["rule:constitution"],
            context_tokens=2000,
            coordination_minutes=6,
            wait_minutes=3,
            review_minutes=1,
        )
        excessive = observation(
            "synthetic-over",
            rules_consulted=[f"rule:{i}" for i in range(18)],
            context_tokens=40000,
            coordination_minutes=80,
            wait_minutes=40,
            review_minutes=20,
        )
        baseline = evaluate_workitem_complexity(before, BUDGETS)
        exceeded = evaluate_workitem_complexity(excessive, BUDGETS)
        budget = contextual_budget(before, BUDGETS)
        documentation_budget = contextual_budget(
            observation("synthetic-doc", task_type="documentacion"), BUDGETS
        )
        comparison = compare_simplification(before, after)
        report = build_complexity_report([excessive, before], BUDGETS)
        dims = baseline["dimensions"]
        high = exceeded["dimensions"]
        fitness_dims = comparison["fitness"]["dimensions"]

        # Validación del contrato B01 ANTES de materializar hojas.
        parsed = parse_plan(plan(
            task("A", "tests/synthetic-a.py"),
            task("B", "tests/synthetic-b.py", ("A",)),
        ))
        ordered = topological_order(parsed)
        checks = {
            "docs/organizational-complexity.md:L29-U1": (
                budget["task_multiplier"] == BUDGETS["task_type_multipliers"]["infraestructura"]
                and documentation_budget["task_multiplier"]
                == BUDGETS["task_type_multipliers"]["documentacion"]
                and budget["limits"]["context_tokens"]
                != documentation_budget["limits"]["context_tokens"]
            ),
            "docs/organizational-complexity.md:L40-U1": (
                dims["rules_consulted"]["observed"] == 2
                and high["rules_consulted"]["observed"] == 18
            ),
            "docs/organizational-complexity.md:L41-U1": (
                dims["rules_consulted"]["budget"] == budget["limits"]["rules_consulted"]
                and dims["context_tokens"]["budget"] == budget["limits"]["context_tokens"]
            ),
            "docs/organizational-complexity.md:L42-U1": (
                dims["rules_consulted"]["status"] == "within"
                and high["rules_consulted"]["status"] == "over"
                and high["rules_consulted"]["observed"] > high["rules_consulted"]["budget"]
            ),
            "docs/organizational-complexity.md:L48-U1": (
                comparison["comparison_scope"] == before["comparison_scope"]
                and comparison["before_work_id"] == before["work_id"]
                and comparison["after_work_id"] == after["work_id"]
            ),
            "docs/organizational-complexity.md:L52-U1": (
                set(budget["protected_controls"]) == set(PROTECTED_INVARIANTS)
                and all(
                    fitness_dims[key]["direction"] == "higher"
                    and fitness_dims[key]["protected"]
                    for key in PROTECTED_INVARIANTS
                )
                and all(key not in budget["limits"] for key in PROTECTED_INVARIANTS)
            ),
            "docs/organizational-complexity.md:L53-U1": all(
                fitness_dims[key]["direction"] == "lower"
                and fitness_dims[key]["status"] == "improved"
                for key in (
                    "organizational_overhead_minutes", "context_tokens", "governance_items"
                )
            ),
            "docs/organizational-complexity.md:L61-U1": (
                report["useful_execution_minutes"] == 80
            ),
            "docs/organizational-complexity.md:L62-U1": (
                report["organizational_overhead_minutes"] == 160
            ),
            "docs/organizational-complexity.md:L63-U1": (
                report["total_minutes"] == 240
            ),
            "docs/organizational-complexity.md:L64-U1": (
                report["overhead_ratio"] == round(160 / 240, 6)
            ),
            "docs/organizational-complexity.md:L65-U1": (
                report["simplification_candidates"] == 1
                and exceeded["simplification_candidate"] is not None
                and exceeded["simplification_candidate"]["target_dimensions"]
                == exceeded["over_budget_dimensions"]
                and exceeded["simplification_candidate"]["execute"] is False
            ),
            "docs/organizational-complexity.md:L66-U1": (
                report["over_budget_counts"]["rules_consulted"] == 1
                and all(v == 1 for v in report["over_budget_counts"].values())
            ),
            "docs/organizational-complexity.md:L68-U1": (
                report["total_minutes"]
                == report["useful_execution_minutes"] + report["organizational_overhead_minutes"]
                and "score" not in report
                and "score" not in baseline
                and comparison["can_claim_simplification"]
                and comparison["execute"] is False
            ),
            "docs/organizational-complexity.md:L9-U1": (
                baseline["measurements"]["rules_consulted"]
                == len(before["rules_consulted"])
                and exceeded["measurements"]["rules_consulted"]
                == len(excessive["rules_consulted"])
            ),
            "docs/orquestador.md:B01": (
                [t.key for t in ordered] == ["A", "B"]
                and ordered[1].depends_on == ("A",)
                and all(t.owner == "pl0n3r" for t in ordered)
                and all(t.paths for t in ordered)
            ),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(checks), set(UNITS))
        for unit in UNITS:
            with self.subTest(unit=unit):
                self.assertTrue(checks[unit], f"{unit}: brecha NO_VERIFICABLE")

    def test_falla_cerrado(self):
        """AC-02: inputs incompletos, cohortes, ciclos y claims fallan cerrado."""
        missing = observation()
        del missing["context_tokens"]
        invalid_budget = copy.deepcopy(BUDGETS)
        del invalid_budget["task_type_multipliers"]["default"]
        other_cohort = observation(
            "synthetic-other", comparison_scope="unrelated-synthetic-scope"
        )
        for data in (missing, observation(context_tokens=-1),
                     observation(protected_metrics={"security": 1})):
            with self.subTest(observation=data):
                with self.assertRaises(OrganizationalComplexityError):
                    normalize_observation(data)
        with self.assertRaises(OrganizationalComplexityError):
            contextual_budget(observation(), invalid_budget)
        with self.assertRaises(OrganizationalComplexityError):
            compare_simplification(observation(), other_cohort)
        bad_plans = (
            plan(task("A", "src/a.py", ("B",)), task("B", "src/b.py", ("A",))),
            plan(task("A", "src/a.py", ("MISSING",))),
            plan(task("A", "src/shared.py"), task("B", "src/shared.py")),
        )
        for body in bad_plans:
            with self.subTest(plan=body):
                with self.assertRaises(PlanError):
                    parse_plan(body)
        with self.assertRaises(PlanError):
            parse_plan("No existe marker HTML de plan.")

    def test_sin_datos_reales(self):
        """AC-03: fixtures estáticas sin credenciales ni uso de red/producción."""
        synthetic = observation()
        normalized = normalize_observation(synthetic)
        self.assertEqual(normalized["work_id"], "synthetic-before")
        self.assertEqual(normalized["evidence_refs"], ["synthetic:factory-1655"])
        self.assertEqual(set(normalized), set(synthetic))
        self.assertEqual(
            set(normalized["protected_metrics"]), set(PROTECTED_INVARIANTS)
        )
        extra = observation(customer_email="synthetic@example.invalid")
        with self.assertRaises(OrganizationalComplexityError):
            normalize_observation(extra)
        result = evaluate_workitem_complexity(synthetic, BUDGETS)
        self.assertNotIn("customer_email", repr(result))
        self.assertNotIn("synthetic@example.invalid", repr(result))
        self.assertFalse(result["simplification_candidate"])

    def test_estados_unknown_explicitos(self):
        """AC-04: no inferir simplificación cuando falta evidencia protegida."""
        before = observation()
        after = observation(
            "synthetic-after",
            context_tokens=2000,
            coordination_minutes=6,
            wait_minutes=3,
            review_minutes=1,
        )
        after["protected_metrics"]["security"] = None
        unknown = compare_simplification(before, after)
        self.assertEqual(unknown["fitness"]["claim"], "inconclusive")
        self.assertIn("security", unknown["fitness"]["missing_dimensions"])
        self.assertEqual(
            unknown["fitness"]["dimensions"]["security"]["status"], "unknown"
        )
        self.assertFalse(unknown["can_claim_simplification"])
        self.assertFalse(unknown["execute"])
        missing = observation()
        missing["context_tokens"] = None
        with self.assertRaises(OrganizationalComplexityError):
            build_complexity_report([missing], BUDGETS)


if __name__ == "__main__":
    unittest.main()
