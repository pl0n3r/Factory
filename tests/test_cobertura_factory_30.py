"""Regresión offline Factory #1821; solo fixtures sintéticos y módulos reales.
B: performance-brvtal L20-U1 (artifact remoto). C: L20-U3 (provenance documental).
"""

import copy
import json
import unittest
from unittest.mock import patch
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS
from performance.contract import validate_performance_contract
from performance.detector import detect_performance
from scripts.orquestador_kit import (
    PlanError, claims_overlap, parse_plan, parse_task_marker,
    reservation_blockers, verified_changed_file_overlap,
)
from metricas.costos import load_budgets
from metricas.organizational_complexity import (
    build_complexity_report,
    compare_simplification,
    contextual_budget,
    evaluate_workitem_complexity,
)


ROOT = Path(__file__).resolve().parents[1]
BUDGETS = load_budgets(Path("metricas/presupuestos.json"), root=ROOT)


def observation(
    work_id="pl0n3r/Factory#245-before",
    *,
    comparison_scope="factory-245-comparable",
    task_type="infraestructura",
    task_size="small",
    risk="medium",
    rules=None,
    roles=None,
    reviewers=None,
    checks=None,
    handoffs=None,
    engines=None,
    context_tokens=8_000,
    coordination=10,
    wait=8,
    review=10,
    useful=40,
    protected=None,
):
    return {
        "version": 1,
        "work_id": work_id,
        "comparison_scope": comparison_scope,
        "task_type": task_type,
        "task_size": task_size,
        "risk": risk,
        "rules_consulted": rules or ["rule:constitution", "rule:factory-plan"],
        "active_roles": roles or ["role:architecture", "role:engineering"],
        "reviewers": reviewers or ["reviewer:qa"],
        "checks": checks or ["check:ci", "check:sonar"],
        "handoffs": handoffs or [],
        "engines_consulted": engines or ["engine:fitness"],
        "context_tokens": context_tokens,
        "coordination_minutes": coordination,
        "wait_minutes": wait,
        "review_minutes": review,
        "useful_execution_minutes": useful,
        "protected_metrics": protected or {
            key: 1.0 for key in PROTECTED_INVARIANTS
        },
        "evidence_refs": ["pl0n3r/Factory#245@event:measurement"],
        "observed_at": "2026-09-29T00:55:00Z",
    }


class CoberturaFactory30Tests(unittest.TestCase):
    def test_contrato_principal(self):
        first = observation()
        second = copy.deepcopy(first)
        second["rules_consulted"].reverse()
        second["checks"].reverse()
        left = evaluate_workitem_complexity(first, BUDGETS)
        right = evaluate_workitem_complexity(second, BUDGETS)
        self.assertEqual(left, right)
        self.assertRegex(left["fingerprint"], r"^[0-9a-f]{64}$")
        self.assertNotIn("score", left)
        self.assertEqual(
            left["measurements"]["organizational_overhead_minutes"],
            28,
        )
        self.assertEqual(left["measurements"]["useful_execution_minutes"], 40)

        # Orquestador B01: contratos DAG y exclusividad, código puro real.
        def task(key, paths, depends_on=()):
            return {"key": key, "title": "Synthetic " + key, "owner": "pl0n3r",
                    "paths": list(paths), "depends_on": list(depends_on)}
        def plan(tasks):
            return "<!-- factory-plan " + json.dumps(
                {"version": 1, "tasks": tasks}, separators=(",", ":")
            ) + " -->"
        planned = parse_plan(plan([
            task("FIRST", ("docs/synthetic.txt",)),
            task("SECOND", ("docs/synthetic.txt",), ("FIRST",)),
        ]))
        self.assertEqual([item.key for item in planned], ["FIRST", "SECOND"])

        # Orquestador B02: identidad, completitud de dependencias y owner.
        def issue(number, dependencies=()):
            payload = {"version": 1, "epic": 1082, "task_key": "SYNTHETIC",
                       "order": 1, "owner": "pl0n3r", "roles": ["qa"],
                       "depends_on": list(dependencies), "paths": ["tests/synthetic.py"]}
            return {"number": number, "state": "open", "labels": [],
                    "body": "<!-- factory-plan-task " + json.dumps(payload) + " -->"}
        current = issue(101, (99,))
        complete = {99: {"state": "closed", "state_reason": "completed"}}
        self.assertEqual(reservation_blockers(current, [current], "pl0n3r", complete), [])
        self.assertEqual(parse_task_marker(current["body"])["owner"], "pl0n3r")

        # Orquestador B04: aliases Unicode y SHAs exactos rechazan colisiones.
        self.assertTrue(claims_overlap("Docs/Caf\u00e9.md", "docs/Cafe\u0301.md"))
        self.assertFalse(claims_overlap("docs/a.py", "docs/b.py"))
        result = verified_changed_file_overlap(
            ("docs/",), ("docs/",),
            left_files=["docs/Caf\u00e9.md"], right_files=["docs/cafe\u0301.md"],
            left_head="a" * 40, right_head="b" * 40,
            left_evidence_head="a" * 40, right_evidence_head="b" * 40,
            left_complete=True, right_complete=True,
            other_issue=102, other_lease="synthetic-lease",
        )
        self.assertFalse(result["safe"])
        self.assertEqual(result["reason"], "shared_changed_files")

        # Performance L17/L18/L20-U2: validar contrato y clasificar probes sintéticos.
        contract = validate_performance_contract(json.loads(
            (ROOT / "performance/contracts/brvtal.json").read_text(encoding="utf-8")
        ))
        baseline = {
            "public.home.mobile": {"fcp": 380, "lcp": 1624, "cls": 0},
            "public.home.desktop": {"fcp": 456, "lcp": 1772, "cls": 0.005},
        }
        self.assertEqual({row["id"] for row in contract["surfaces"]}, set(baseline))
        for surface in contract["surfaces"]:
            for metric in surface["metrics"]:
                with self.subTest(surface=surface["id"], metric=metric["id"]):
                    metric_id = metric["id"]
                    expected = baseline[surface["id"]][metric_id]
                    self.assertEqual(metric["baseline"]["value"], expected)
                    self.assertEqual(metric["baseline"]["observed_at"], "2026-10-01T11:47:49Z")
                    self.assertEqual(metric["evidence"]["observed_at"],
                                     metric["baseline"]["observed_at"])
                    sample = {
                        "version": 1, "project": "brvtal", "surface": surface["id"],
                        "metric": metric_id, "value": expected,
                        "unit": "ratio" if metric_id == "cls" else "ms",
                        "observed_at": "2026-10-01T11:47:49Z",
                        "window_seconds": 1, "sample_count": 1,
                        "severity": "info", "operational_impact": False,
                        "bottleneck": "frontend",
                        "evidence_ref": "synthetic:offline:probe",
                        "sha": "a" * 40, "release": "synthetic-0.0.0",
                    }
                    verdict = detect_performance(
                        contract, sample, evaluated_at="2026-10-01T12:00:00Z"
                    )
                    self.assertEqual(verdict["classification"], "PERF_INFO")
                    self.assertEqual(verdict["evidence_state"], "CURRENT")
                    self.assertFalse(verdict["breach"])

    def test_budget_is_contextual_and_preserves_constitution(self):
        documentation = observation(
            task_type="documentacion",
            task_size="small",
            risk="low",
        )
        security = observation(
            task_type="seguridad",
            task_size="small",
            risk="high",
        )
        doc_budget = contextual_budget(documentation, BUDGETS)
        security_budget = contextual_budget(security, BUDGETS)

        self.assertNotEqual(
            doc_budget["limits"]["coordination_minutes"],
            security_budget["limits"]["coordination_minutes"],
        )
        self.assertNotEqual(
            doc_budget["limits"]["context_tokens"],
            security_budget["limits"]["context_tokens"],
        )
        self.assertEqual(
            set(doc_budget["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        self.assertEqual(
            set(security_budget["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        for protected in PROTECTED_INVARIANTS:
            self.assertNotIn(protected, doc_budget["limits"])
            self.assertNotIn(protected, security_budget["limits"])

    def test_excess_overhead_generates_simplification_candidate(self):
        item = observation(
            rules=[f"rule:{index}" for index in range(20)],
            roles=[f"role:{index}" for index in range(10)],
            reviewers=[f"reviewer:{index}" for index in range(6)],
            checks=[f"check:{index}" for index in range(16)],
            handoffs=[f"handoff:{index}" for index in range(5)],
            engines=[f"engine:{index}" for index in range(10)],
            context_tokens=40_000,
            coordination=80,
            wait=90,
            review=70,
            useful=30,
        )
        result = evaluate_workitem_complexity(item, BUDGETS)
        candidate = result["simplification_candidate"]

        self.assertTrue(result["over_budget_dimensions"])
        self.assertIsNotNone(candidate)
        self.assertEqual(
            candidate["target_dimensions"],
            result["over_budget_dimensions"],
        )
        self.assertEqual(
            candidate["evidence_refs"],
            item["evidence_refs"],
        )
        self.assertEqual(
            set(candidate["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        self.assertEqual(candidate["authority"], "unchanged")
        self.assertFalse(candidate["execute"])

    def test_falla_cerrado(self):
        before = observation(
            context_tokens=20_000,
            coordination=40,
            wait=30,
            review=30,
            useful=40,
        )
        after = observation(
            "pl0n3r/Factory#245-after",
            context_tokens=10_000,
            coordination=20,
            wait=15,
            review=15,
            useful=40,
        )
        regressed = copy.deepcopy(after)
        regressed["protected_metrics"]["security"] = 0.9

        blocked = compare_simplification(before, regressed)
        self.assertEqual(blocked["fitness"]["claim"], "blocked")
        self.assertIn(
            "security",
            blocked["fitness"]["protected_regressions"],
        )
        self.assertFalse(blocked["can_claim_simplification"])

        improved = compare_simplification(before, after)
        self.assertEqual(improved["fitness"]["claim"], "improved")
        self.assertFalse(improved["fitness"]["protected_regressions"])
        self.assertTrue(improved["can_claim_simplification"])
        self.assertEqual(improved["authority"], "unchanged")
        self.assertFalse(improved["execute"])

        # Organizational L48: una cohorte diferente prohíbe reclamar mejora.
        for field, val in (("comparison_scope", "another"), ("task_type", "seguridad"),
                           ("task_size", "large"), ("risk", "critical")):
            changed = copy.deepcopy(after)
            changed[field] = val
            with self.subTest(cohort=field):
                with self.assertRaises(ValueError):
                    compare_simplification(before, changed)

        # B01: ciclos, referencias faltantes y colisión paralela fallan cerrado.
        def tk(key, paths, dependencies=()):
            return {"key": key, "title": "Synthetic", "owner": "pl0n3r",
                    "paths": list(paths), "depends_on": list(dependencies)}
        for tasks in (
            [tk("ONE", ["docs/a"], ["MISSING"])],
            [tk("ONE", ["docs/a"], ["TWO"]), tk("TWO", ["docs/b"], ["ONE"])],
            [tk("ONE", ["docs/a"]), tk("TWO", ["docs/a"])],
        ):
            body = "<!-- factory-plan " + json.dumps(
                {"version": 1, "tasks": tasks}
            ) + " -->"
            with self.subTest(tasks=tasks):
                with self.assertRaises(PlanError):
                    parse_plan(body)

        # B02: owner incorrecto, dependencia abierta y lease solapada bloquean.
        marker = {"version": 1, "epic": 1082, "task_key": "SYNTHETIC",
                  "order": 1, "owner": "pl0n3r", "roles": ["qa"],
                  "depends_on": [99], "paths": ["tests/synthetic.py"]}
        current = {"number": 101, "state": "open", "labels": [],
                   "body": "<!-- factory-plan-task " + json.dumps(marker) + " -->"}
        denied = reservation_blockers(current, [current], "wrong-owner",
                                      {99: {"state": "open"}})
        self.assertTrue(any("planificada" in msg for msg in denied))
        self.assertTrue(any("dependencias" in msg for msg in denied))
        rival = {"number": 102, "state": "open",
                 "labels": [{"name": "estado: reservado"}],
                 "body": current["body"]}
        conflicts = reservation_blockers(
            current, [current, rival], "pl0n3r",
            {99: {"state": "closed", "state_reason": "completed"}},
        )
        self.assertTrue(any("colisión" in msg for msg in conflicts))

        # B04: evidencia stale/incompleta no concede compatibilidad por diff.
        stale = verified_changed_file_overlap(
            ("docs/",), ("docs/",),
            left_files=["docs/a"], right_files=["docs/b"],
            left_head="a" * 40, right_head="b" * 40,
            left_evidence_head="c" * 40, right_evidence_head="b" * 40,
            left_complete=True, right_complete=True,
            other_issue=102, other_lease="synthetic-lease",
        )
        self.assertFalse(stale["safe"])
        self.assertEqual(stale["reason"], "diff_stale_or_incomplete")

        # Performance: métrica fuera del budget no obtiene permiso ni umbral.
        contract = json.loads((ROOT / "performance/contracts/brvtal.json").read_text())
        sample = {
            "version": 1, "project": "brvtal", "surface": "public.home.mobile",
            "metric": "metric_unknown", "value": 1, "unit": "ms",
            "observed_at": "2026-10-01T11:47:49Z",
            "window_seconds": 1, "sample_count": 1, "severity": "info",
            "operational_impact": False, "bottleneck": "frontend",
            "evidence_ref": "synthetic:offline:unknown", "sha": "a" * 40,
            "release": "synthetic",
        }
        unknown = detect_performance(
            contract, sample, evaluated_at="2026-10-01T12:00:00Z"
        )
        self.assertEqual(unknown["classification"], "PERF_REVIEW")
        self.assertEqual(unknown["evidence_state"], "UNKNOWN")
        self.assertIsNone(unknown["breach"])

    def test_sin_datos_reales(self):
        first = observation(
            "pl0n3r/Factory#245-a",
            coordination=10,
            wait=5,
            review=5,
            useful=40,
        )
        second = observation(
            "pl0n3r/Factory#245-b",
            coordination=20,
            wait=10,
            review=10,
            useful=60,
        )
        report = build_complexity_report([second, first], BUDGETS)

        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["useful_execution_minutes"], 100)
        self.assertEqual(report["organizational_overhead_minutes"], 60)
        self.assertEqual(report["total_minutes"], 160)
        self.assertEqual(report["overhead_ratio"], 0.375)
        self.assertEqual(
            set(report["protected_controls"]),
            set(PROTECTED_INVARIANTS),
        )
        self.assertRegex(report["fingerprint"], r"^[0-9a-f]{64}$")

        # Este WorkItem es un fixture, no dato real ni acceso a red.
        sample = observation("synthetic:offline:work", useful=30)
        # Sustituir la referencia histórica heredada; no es evidencia sintética.
        sample["evidence_refs"] = ["synthetic:offline:evidence"]
        encoded = json.dumps(sample)
        self.assertNotIn("@", encoded)
        self.assertNotIn("https://", encoded)
        with patch("urllib.request.urlopen", side_effect=AssertionError("No red")):
            evaluated = evaluate_workitem_complexity(sample, BUDGETS)
            self.assertEqual(evaluated["work_id"], "synthetic:offline:work")

    def test_validar_exact_head(self):
        """Valida el contrato real de CI sin crear una dependencia circular."""
        from scripts.aceptacion_kit import FORBIDDEN_CHECKS
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("Validar", FORBIDDEN_CHECKS)
        self.assertIn("name: Validar", workflow)
        self.assertIn("github.event.pull_request.head.sha", workflow)
        self.assertIn("needs: [event_guard, preflight, php, node]", workflow)


if __name__ == "__main__":
    unittest.main()
