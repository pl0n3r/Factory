#!/usr/bin/env python3
"""Factory #2021: contraste de 70 unidades, sin inferir estado productivo."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from evolution.fitness import FitnessError, compare_fitness, validate_fitness_evidence
from evolution.growth import GrowthError, compile_growth_candidate, detect_capability_gap
from evolution.pruning import PruningError, compile_pruning_candidate, evaluate_pruning
from evolution.knowledge_lifecycle import (
    KnowledgeLifecycleError, can_increase_autonomy, create_knowledge_record,
    effective_state, revalidate_knowledge, transition_knowledge,
)
from evolution.pruning import propose_knowledge_pruning
from scripts.issue_contract_preflight import (
    IssueContractPreflightError, evaluate_issue_body,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "verificacion" / "verificacion-05.md"
INVENTORY = ROOT / "docs" / "inventario-tecnico-datos-productos.md"

# IDs copiados del contrato canónico #2021; no leer Issues/PRs externos en CI.
EXPECTED_IDS = (
    "docs/fitness-engine.md:L30-U1",
    "docs/fitness-engine.md:L37-U1",
    "docs/fitness-engine.md:L38-U1",
    "docs/fitness-engine.md:L39-U1",
    "docs/fitness-engine.md:L40-U1",
    "docs/fitness-engine.md:L50-U1",
    "docs/fitness-engine.md:L51-U1",
    "docs/fitness-engine.md:L52-U1",
    "docs/fitness-engine.md:L53-U1",
    "docs/fitness-engine.md:L54-U1",
    "docs/fitness-engine.md:L56-U1",
    "docs/fitness-engine.md:L62-U1",
    "docs/fitness-engine.md:L69-U1",
    "docs/fitness-engine.md:L75-U1",
    "docs/growth-pruning.md:L10-U1",
    "docs/growth-pruning.md:L20-U1",
    "docs/growth-pruning.md:L21-U1",
    "docs/growth-pruning.md:L22-U1",
    "docs/growth-pruning.md:L23-U1",
    "docs/growth-pruning.md:L24-U1",
    "docs/growth-pruning.md:L30-U1",
    "docs/growth-pruning.md:L33-U1",
    "docs/growth-pruning.md:L34-U1",
    "docs/growth-pruning.md:L35-U1",
    "docs/growth-pruning.md:L37-U1",
    "docs/growth-pruning.md:L43-U1",
    "docs/growth-pruning.md:L44-U1",
    "docs/growth-pruning.md:L46-U1",
    "docs/growth-pruning.md:L48-U1",
    "docs/growth-pruning.md:L52-U1",
    "docs/growth-pruning.md:L60-U1",
    "docs/growth-pruning.md:L64-U1",
    "docs/growth-pruning.md:L65-U1",
    "docs/growth-pruning.md:L66-U1",
    "docs/growth-pruning.md:L67-U1",
    "docs/inventario-tecnico-datos-productos.md:B01",
    "docs/inventario-tecnico-datos-productos.md:B02",
    "docs/inventario-tecnico-datos-productos.md:B03",
    "docs/issue-contract-preflight.md:L3-U1",
    "docs/issue-contract-preflight.md:L19-U1",
    "docs/issue-contract-preflight.md:L20-U1",
    "docs/issue-contract-preflight.md:L21-U1",
    "docs/issue-contract-preflight.md:L22-U1",
    "docs/issue-contract-preflight.md:L24-U1",
    "docs/issue-contract-preflight.md:L28-U1",
    "docs/issue-contract-preflight.md:L28-U2",
    "docs/knowledge-lifecycle.md:L9-U1",
    "docs/knowledge-lifecycle.md:L10-U1",
    "docs/knowledge-lifecycle.md:L11-U1",
    "docs/knowledge-lifecycle.md:L11-U2",
    "docs/knowledge-lifecycle.md:L12-U1",
    "docs/knowledge-lifecycle.md:L13-U1",
    "docs/knowledge-lifecycle.md:L13-U2",
    "docs/knowledge-lifecycle.md:L19-U1",
    "docs/knowledge-lifecycle.md:L20-U1",
    "docs/knowledge-lifecycle.md:L21-U1",
    "docs/knowledge-lifecycle.md:L22-U1",
    "docs/knowledge-lifecycle.md:L23-U1",
    "docs/knowledge-lifecycle.md:L24-U1",
    "docs/knowledge-lifecycle.md:L26-U1",
    "docs/knowledge-lifecycle.md:L30-U1",
    "docs/knowledge-lifecycle.md:L30-U2",
    "docs/knowledge-lifecycle.md:L30-U3",
    "docs/knowledge-lifecycle.md:L30-U4",
    "docs/knowledge-lifecycle.md:L30-U5",
    "docs/knowledge-lifecycle.md:L30-U6",
    "docs/knowledge-lifecycle.md:L30-U7",
    "docs/knowledge-lifecycle.md:L36-U1",
    "docs/knowledge-lifecycle.md:L37-U1",
    "docs/knowledge-lifecycle.md:L38-U1",
)


def metric(value, direction="higher"):
    return {"value": value, "direction": direction}


def base_fitness():
    return {
        **{name: metric(1) for name in
           ("security", "privacy", "traceability", "reversibility", "authority")},
        "cost": metric(10, "lower"),
        "performance": metric(100),
    }


def knowledge(knowledge_id="rule-alpha", fingerprint=None, *,
              state="active", date="2026-01-01T00:00:00Z"):
    return create_knowledge_record(
        knowledge_id=knowledge_id,
        knowledge_type="guardrail",
        content_fingerprint=fingerprint or "a" * 64,
        provenance=["pl0n3r/Factory#2021"],
        scope={"project": "pl0n3r/Factory", "domain": "living-software"},
        created_at="2026-01-01T00:00:00Z",
        last_validated_at=date,
        last_useful_at=date,
        confidence=0.91,
        evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


class VerificacionFactory05Tests(unittest.TestCase):
    def test_report_lists_all_70_units_once(self):
        raw = REPORT.read_text(encoding="utf-8")
        rows = re.findall(r"^\| \x60([^\x60]+)\x60 \|", raw, flags=re.M)
        self.assertEqual(len(rows), 70)
        self.assertEqual(len(set(rows)), 70)
        self.assertEqual(set(rows), set(EXPECTED_IDS))
        for row in raw.splitlines():
            if row.startswith("| " + chr(96)):
                cells = [cell.strip() for cell in row.split("|")[1:-1]]
                self.assertEqual(len(cells), 5, row)
                self.assertTrue(cells[2], row)
                self.assertIn("test_", cells[3], row)
                self.assertTrue(cells[4].startswith(("A:", "B:")), row)
        self.assertIn("NO_VERIFICABLE", raw)
        self.assertIn("No se transforma", raw)

    def test_fitness_states_and_claims(self):
        baseline = base_fitness()
        better = {**baseline, "cost": metric(8, "lower")}
        improvement = compare_fitness(baseline=baseline, candidate=better)
        self.assertEqual(improvement["dimensions"]["cost"]["status"], "improved")
        self.assertEqual(improvement["claim"], "improved")
        self.assertTrue(improvement["can_claim_improvement"])
        self.assertEqual(compare_fitness(baseline=baseline, candidate=baseline)["claim"], "equal")
        worse = {**baseline, "cost": metric(12, "lower"), "performance": metric(101)}
        mixed = compare_fitness(baseline=baseline, candidate=worse)
        self.assertEqual(mixed["dimensions"]["cost"]["status"], "regressed")
        self.assertEqual(mixed["claim"], "mixed")
        blocked = compare_fitness(
            baseline=baseline,
            candidate={**better, "security": metric(0.8)},
        )
        self.assertEqual(blocked["claim"], "blocked")
        self.assertIn("security", blocked["protected_regressions"])
        self.assertFalse(blocked["can_claim_improvement"])
        missing = compare_fitness(baseline=baseline, candidate={
            key: value for key, value in better.items() if key != "cost"
        })
        self.assertEqual(missing["dimensions"]["cost"]["status"], "unknown")
        self.assertIn("cost", missing["missing_dimensions"])
        self.assertEqual(missing["claim"], "inconclusive")
        self.assertFalse(missing["can_claim_improvement"])

    def test_fitness_source_and_guards(self):
        original = base_fitness()
        result = compare_fitness(baseline=original, candidate=original)
        self.assertEqual(validate_fitness_evidence(
            baseline=original, candidate=original, result=result,
        ), result)
        forged = {**result, "can_claim_improvement": True}
        with self.assertRaises(FitnessError):
            validate_fitness_evidence(
                baseline=original, candidate=original, result=forged,
            )
        self.assertRegex(result["fingerprint"], r"^[0-9a-f]{64}$")
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=repr(value)):
                with self.assertRaises(FitnessError):
                    compare_fitness(
                        baseline=original,
                        candidate={**original, "cost": metric(value, "lower")},
                    )
        with self.assertRaises(FitnessError):
            compare_fitness(
                baseline=original, candidate=original,
                protected_dimensions=["security"],
            )

    def test_growth_reuse_and_candidate(self):
        reused = detect_capability_gap(
            required_capability="Métrica Ágil",
            available_capabilities=["metrica-agil"],
        )
        self.assertFalse(reused["gap"])
        self.assertEqual(reused["reuse"], "metrica-agil")
        absent = detect_capability_gap(
            required_capability="Métrica Ágil",
            available_capabilities=["otro módulo"],
        )
        self.assertTrue(absent["gap"])
        candidate = compile_growth_candidate(
            gap=absent, required_capability="Métrica Ágil",
            available_capabilities=["otro módulo"],
            evidence=["pl0n3r/Factory#2021"],
            expected_value="Verificación de capacidad sintética",
        )
        self.assertEqual(candidate["capability"], "metrica-agil")
        self.assertEqual(candidate["lineage"]["gap_fingerprint"], absent["fingerprint"])
        self.assertEqual(candidate["candidate"]["changes"][0]["operation"], "add")
        self.assertTrue(candidate["candidate"]["rollback"]["reversible"])
        self.assertEqual(candidate["expected_value"], "Verificación de capacidad sintética")
        self.assertIsNone(compile_growth_candidate(
            gap=absent, required_capability="Métrica Ágil",
            available_capabilities=["metrica-agil"],
            evidence=["pl0n3r/Factory#2021"], expected_value="No duplicar",
        ))
        with self.assertRaises(GrowthError):
            compile_growth_candidate(
                gap={**absent, "required": "fraud"},
                required_capability="Métrica Ágil",
                available_capabilities=["otro módulo"],
                evidence=["pl0n3r/Factory#2021"], expected_value="Incorrecto",
            )

    def test_pruning_thresholds_and_safety(self):
        args = dict(capability="legacy formatter", usage_count=1, age_days=90,
                    value_score=0.25,
                    evidence=["pl0n3r/Factory#2021", "pl0n3r/Factory#304"],
                    parent_fingerprint="a" * 64)
        good = evaluate_pruning(**args)
        self.assertTrue(good["eligible"])
        self.assertTrue(all(good["criteria"].values()))
        self.assertRegex(good["fingerprint"], r"^[0-9a-f]{64}$")
        for altered in (
            {"usage_count": 2}, {"age_days": 89},
            {"value_score": 0.26}, {"evidence": ["pl0n3r/Factory#2021"]},
        ):
            with self.subTest(altered=altered):
                self.assertFalse(evaluate_pruning(**{**args, **altered})["eligible"])
        for protected in ("security", "privacy", "traceability",
                          "reversibility", "authority", "constitution",
                          "human-gates", "rollback", "audit-trail"):
            with self.subTest(protected=protected):
                with self.assertRaises(PruningError):
                    evaluate_pruning(**{**args, "capability": protected})
        with self.assertRaises(PruningError):
            evaluate_pruning(**{**args, "protected": True})
        with self.assertRaises(PruningError):
            evaluate_pruning(**{**args, "age_days": -1})

    def test_pruning_lineage_and_no_direct_mutation(self):
        args = dict(capability="legacy formatter", usage_count=0, age_days=180,
                    value_score=0.1,
                    evidence=["pl0n3r/Factory#2021", "pl0n3r/Factory#304"],
                    parent_fingerprint="a" * 64)
        evaluation = evaluate_pruning(**args)
        candidate = compile_pruning_candidate(evaluation, **args)
        self.assertEqual(candidate["lineage"]["parent_fingerprint"], "a" * 64)
        self.assertEqual(candidate["lineage"]["evaluation_fingerprint"],
                         evaluation["fingerprint"])
        self.assertTrue(candidate["lineage"]["history_preserved"])
        change = candidate["candidate"]["changes"][0]
        self.assertEqual(change["operation"], "add")
        self.assertTrue(change["path"].startswith("evolution_state.heuristics."))
        self.assertEqual(change["value"]["status"], "prune-candidate")
        self.assertEqual(candidate["candidate"]["rollback"]["strategy"],
                         "restore_baseline")
        self.assertNotIn("delete", str(candidate["candidate"]).lower())
        with self.assertRaises(PruningError):
            compile_pruning_candidate({**evaluation, "eligible": False}, **args)

    def test_inventory_is_historical_not_legal_approval(self):
        text = INVENTORY.read_text(encoding="utf-8")
        block = text.split("## Snapshot auditado", 1)[1].split(
            "## Cómo leer este mapa", 1
        )[0]
        for product in ("Condor", "GrindFlow", "BRVTAL"):
            self.assertRegex(block, rf"(?m)^- {product}: \x60[0-9a-f]{{40}}\x60$")
        for example in ("NullTransactionalEmailGateway", "Supabase",
                        "24 horas", "30 días", "15 minutos"):
            self.assertIn(example, text)
        self.assertIn("no es aprobación jurídica", text)
        self.assertIn("retención", text.lower())

    def test_issue_preflight_accepts_and_rejects_offline(self):
        acceptance = {"version": 1, "criteria": [
            {"id": "AC-01", "kind": "test",
             "target": ("tests/test_verificacion_factory_05.py::"
                        "VerificacionFactory05Tests::"
                        "test_issue_preflight_accepts_and_rejects_offline")},
        ]}
        task = {"version": 1, "epic": 304, "task_key": "FACTORY_VERIFY_05",
                "order": 905, "owner": "pl0n3r", "roles": ["qa"],
                "depends_on": [], "paths": ["tests/test_verificacion_factory_05.py"]}
        body = (
            "### Contexto\nPrueba sintética.\n\n"
            "### Alcance\nValidación local.\n\n"
            "### Fuera de alcance\nSin red.\n\n"
            "### Criterios de aceptación\n- [ ] [AC-01] Prueba causal.\n\n"
            "### Contrato ejecutable\n<!-- factory-acceptance "
            + json.dumps(acceptance) + " -->\n\n"
            "### Rutas reclamadas\n- tests/test_verificacion_factory_05.py\n"
            "<!-- factory-plan-task " + json.dumps(task) + " -->\n"
        )
        result = evaluate_issue_body(body)
        self.assertTrue(result["valid"])
        self.assertEqual(result["task_key"], "FACTORY_VERIFY_05")
        self.assertEqual(result["paths"], task["paths"])
        for field in ("acceptance_sha256", "task_marker_sha256"):
            self.assertRegex(result[field], r"^[0-9a-f]{64}$")
        for tampered in (
            body.replace("### Contexto", "### Wrong"),
            body.split("<!-- factory-plan-task", 1)[0],
            body.replace('"task_key": "FACTORY_VERIFY_05"',
                         '"task_key": "invalid"'),
        ):
            with self.subTest(kind=tampered[:30]):
                with self.assertRaises(IssueContractPreflightError):
                    evaluate_issue_body(tampered)
        # Preflight solo devuelve identidad del texto: ninguna reserva, branch o PR.
        self.assertNotIn("reservation_id", result)

    def test_knowledge_states_autonomy_and_history(self):
        active = knowledge(date="2026-09-01T00:00:00Z")
        self.assertEqual(effective_state(active, "2026-09-20T00:00:00Z"), "active")
        self.assertTrue(can_increase_autonomy(active, "2026-09-20T00:00:00Z"))
        self.assertEqual(effective_state(active, "2026-10-20T00:00:00Z"),
                         "needs_review")
        self.assertFalse(can_increase_autonomy(active, "2026-10-20T00:00:00Z"))
        for state in ("candidate", "deprecated", "archived"):
            with self.subTest(state=state):
                self.assertFalse(can_increase_autonomy(
                    knowledge(state=state), "2026-09-20T00:00:00Z"))
        deprecated = transition_knowledge(
            active, target_state="deprecated", at="2026-10-20T00:00:00Z",
            evidence=["pl0n3r/Factory#304"], reason="superseded",
        )
        archived = transition_knowledge(
            deprecated, target_state="archived", at="2026-10-21T00:00:00Z",
            evidence=["pl0n3r/Factory#305"], reason="retained-for-audit",
        )
        self.assertEqual(archived["state"], "archived")
        self.assertEqual(archived["provenance"], active["provenance"])
        self.assertEqual(archived["history"][-1]["to"], "archived")
        self.assertFalse(can_increase_autonomy(archived, "2026-10-22T00:00:00Z"))

    def test_knowledge_revalidation_rejects_replay(self):
        stale = knowledge()
        refreshed = revalidate_knowledge(
            stale, validated_at="2026-09-28T00:00:00Z",
            evidence=["pl0n3r/Factory#304"],
            confidence=0.96, evidence_class="verified",
        )
        self.assertEqual(refreshed["state"], "active")
        self.assertIn("pl0n3r/Factory#304", refreshed["provenance"])
        self.assertEqual(refreshed["history"][-1]["to"], "active")
        self.assertTrue(can_increase_autonomy(refreshed, "2026-09-28T00:00:00Z"))
        with self.assertRaises(KnowledgeLifecycleError):
            revalidate_knowledge(
                refreshed, validated_at="2026-09-29T00:00:00Z",
                evidence=["pl0n3r/Factory#304"],
                confidence=0.96, evidence_class="verified",
            )
        archived = transition_knowledge(
            stale, target_state="deprecated", at="2026-09-28T00:00:00Z",
            evidence=["pl0n3r/Factory#305"], reason="retired",
        )
        with self.assertRaises(KnowledgeLifecycleError):
            revalidate_knowledge(
                archived, validated_at="2026-09-29T00:00:00Z",
                evidence=["pl0n3r/Factory#306"],
                confidence=0.96, evidence_class="verified",
            )

    def test_knowledge_pruning_is_review_only(self):
        old = "2026-01-01T00:00:00Z"
        a = knowledge("rule-alpha", fingerprint="b" * 64, date=old)
        b = knowledge("rule-beta", fingerprint="b" * 64, date=old)
        proposals = propose_knowledge_pruning(
            [a, b], now_at="2026-09-28T00:00:00Z",
        )
        self.assertEqual(len(proposals), 1)
        p = proposals[0]
        self.assertEqual(p["action"], "review-consolidation")
        self.assertEqual(p["knowledge_ids"], ["rule-alpha", "rule-beta"])
        self.assertFalse(p["delete"])
        self.assertTrue(p["history_preserved"])
        self.assertEqual(
            proposals,
            propose_knowledge_pruning([b, a], now_at="2026-09-28T00:00:00Z"),
        )


if __name__ == "__main__":
    unittest.main()
