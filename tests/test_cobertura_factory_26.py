#!/usr/bin/env python3
"""#1817. Exercise real release, readiness, Constitution, Lab and Fitness code.

A = verifiable offline subcontracts only. B = live systems or authenticated
historical runs. C = governance/documentation. No B/C becomes covered here.
"""
from __future__ import annotations

from copy import deepcopy
import unittest

from evolution.constitution import (
    ConstitutionError, PROTECTED_INVARIANTS, validate_candidate,
)
from evolution.fitness import compare_fitness
from lab.factory_lab import FactoryLabError, evaluate_shadow, promotion_contract
from scripts.issue_contract_preflight import (
    IssueContractPreflightError, evaluate_issue_body,
)
from scripts.release_auto_eligibility import (
    REQUIRED_CHECKS, evaluate as evaluate_release,
)
from scripts.reusable_permission_compat import compare_permissions

LIST = "docs/lista-salida-produccion.md:"
LIVING = "docs/living-software-operational-e2e.md:"
A = {
    LIST + "L84-U2": "green PR is not publication: release evaluator remains dry-run",
    LIVING + "L14-U1": "acceptance and factory-plan-task are preflighted together",
    LIVING + "L22-U1": "Constitution rejects mutation of protected invariants",
    LIVING + "L23-U1": "Fitness measures coordination seconds separately",
    LIVING + "L24-U1": "Fitness measures reservation attempts separately",
    LIVING + "L26-U1": "Factory Lab shadow has no external writes or mutations",
}
B = {
    LIST + "L85-U1": "real alerts, SLA, operator guard, agent load, smoke and restore need external receipts",
    LIST + "L86-U1": "real consumer HTTPS, privacy, accessibility, backups and go-live authority need external proofs",
    LIST + "L87-U1": "GitHub/ChatGPT provider outage handling needs authenticated real-world observation",
    LIST + "L9-U2": "consumer deploy identity and version must be witnessed by its actual observer",
    LIVING + "L10-U1": "historic run 36507097760 needs original GitHub timeline",
    LIVING + "L11-U1": "historic run 36507219161 needs original GitHub timeline",
    LIVING + "L12-U1": "historic run 36507269422 and its V3 lease need authentic GitHub evidence",
    LIVING + "L42-U1": "historical 35 seconds need authenticated original event durations",
    LIVING + "L43-U1": "historical 27 seconds need authenticated original event durations",
}
C = {
    LIST + "L87-U2": "SIN_COBERTURA until integration is documentary status",
    LIST + "L88-U1": "provider purchases and credentials require OWNER decision",
    LIST + "L9-U1": "list of canonical sources is documentary",
    LIST + "L90-U1": "checklist never certifies production is a policy",
    LIVING + "L28-U1": "do not rewrite coordinator/generalize is a scope limitation",
}
ALL = frozenset(A) | frozenset(B) | frozenset(C)
SHA = "a" * 40
UNKNOWN = "UNKNOWN"



def release_fixture() -> dict:
    """Fake caller-authenticated fields are NOT independently authenticated."""
    return {
        "phase": "construccion", "kill_switch_state": "RUNNING",
        "release_machinery_changed": False, "v1_tag_protected": True,
        "evidence_authenticated": True, "main_sha": SHA,
        "observed_main_sha": SHA, "published_version": "1.0.38",
        "candidate_version": "1.0.39",
        "checks": [{"name": name, "head_sha": SHA, "status": "completed",
                    "conclusion": "success", "authenticated": True}
                   for name in sorted(REQUIRED_CHECKS)],
    }


def issue_fixture() -> str:
    return """### Contexto
Preflight sintético.

### Alcance
Inspeccionar una reserva ficticia sin GitHub.

### Fuera de alcance
Sin I/O externo.

### Criterios de aceptación
- [ ] [AC-01] Contrato de prueba.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"test","target":"tests/test_cobertura_factory_26.py::CoberturaFactory26Tests::test_contrato_principal"}]} -->

### Rutas reclamadas
- tests/test_cobertura_factory_26.py

<!-- factory-plan-task {"version":1,"epic":1082,"task_key":"OFFLINE_1817_V1","order":66,"owner":"pl0n3r","roles":["qa"],"depends_on":[],"paths":["tests/test_cobertura_factory_26.py"]} -->
"""


def proposal_fixture() -> dict:
    return {
        "version": 1,
        "changes": [{
            "path": "evolution_state.heuristics.reservation_readiness_preflight",
            "operation": "add",
            "value": {
                "checks": ["acceptance_contract", "status_available",
                           "factory_plan_task"],
                "mode": "preflight", "scope": "issue_reservation",
            },
        }],
        "evidence": ["synthetic:factory-1817"],
        "rollback": {"reversible": True, "strategy": "restore_baseline"},
    }


def vectors() -> tuple[dict, dict]:
    baseline = {
        key: {"value": 1.0, "direction": "higher"}
        for key in PROTECTED_INVARIANTS
    }
    baseline.update({
        "coordination_seconds": {"value": 35, "direction": "lower"},
        "reservation_attempts": {"value": 3, "direction": "lower"},
    })
    candidate = deepcopy(baseline)
    candidate["coordination_seconds"]["value"] = 27
    candidate["reservation_attempts"]["value"] = 1
    return baseline, candidate


def operational_claim(_untrusted: object) -> str:
    """No local synthetic observation authenticates a historical/real source."""
    return UNKNOWN


class CoberturaFactory26Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: call real existing implementations for all six A subcontracts."""
        self.assertEqual((20, 6, 9, 5), (len(ALL), len(A), len(B), len(C)))
        self.assertEqual(ALL, frozenset(A) | frozenset(B) | frozenset(C))
        self.assertFalse(set(A) & set(B))
        self.assertFalse(set(A) & set(C))
        self.assertFalse(set(B) & set(C))

        # L84-U2: a wholly green PR cannot publish a release.
        original = release_fixture()
        snapshot = deepcopy(original)
        eligible = evaluate_release(snapshot)
        self.assertEqual(eligible["decision"], "DRY_RUN_ELIGIBLE")
        self.assertIs(eligible["authorizes_release"], False)
        self.assertEqual(eligible["mutations"], 0)
        self.assertEqual(snapshot, original)

        # Living L14-U1: actually parse the acceptance contract + plan marker.
        ready = evaluate_issue_body(issue_fixture())
        self.assertTrue(ready["valid"])
        self.assertEqual(ready["task_key"], "OFFLINE_1817_V1")
        self.assertEqual(ready["paths"], ["tests/test_cobertura_factory_26.py"])
        self.assertEqual([c["id"] for c in ready["criteria"]], ["AC-01"])
        self.assertRegex(ready["acceptance_sha256"], r"^[0-9a-f]{64}$")

        # Living L22-U1: protected Constitution is executed.
        self.assertEqual(set(PROTECTED_INVARIANTS), {
            "security", "privacy", "traceability", "reversibility", "authority",
        })
        candidate = proposal_fixture()
        self.assertRegex(validate_candidate(candidate), r"^[0-9a-f]{64}$")

        # Living L23/L24: time and number of attempts remain two dimensions.
        before, after = vectors()
        fitness = compare_fitness(baseline=before, candidate=after)
        self.assertEqual(fitness["claim"], "improved")
        self.assertEqual(fitness["protected_regressions"], [])
        self.assertEqual(fitness["missing_dimensions"], [])
        self.assertEqual(
            fitness["dimensions"]["coordination_seconds"]["candidate"], 27)
        self.assertEqual(
            fitness["dimensions"]["reservation_attempts"]["candidate"], 1)
        for dimension in ("coordination_seconds", "reservation_attempts"):
            self.assertEqual(fitness["dimensions"][dimension]["status"], "improved")

        # Living L26: prove the shadow evaluator does not mutate caller state.
        baseline_snapshot = deepcopy(before)
        candidate_snapshot = deepcopy(after)
        proposal_snapshot = deepcopy(candidate)
        shadow = evaluate_shadow(
            stable_sha="a" * 40, candidate_sha="b" * 40,
            stable_metrics=before, candidate_metrics=after,
            constitution_candidate=candidate,
        )
        self.assertEqual(before, baseline_snapshot)
        self.assertEqual(after, candidate_snapshot)
        self.assertEqual(candidate, proposal_snapshot)
        self.assertEqual(candidate["rollback"], proposal_snapshot["rollback"])
        self.assertEqual(shadow["mode"], "shadow")
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])
        self.assertEqual(shadow["promotion"]["execution"], "not-performed")
        contract = promotion_contract(
            shadow_result=shadow, stable_sha="a" * 40, candidate_sha="b" * 40,
            stable_metrics=before, candidate_metrics=after,
            constitution_candidate=candidate,
        )
        self.assertTrue(contract["requires_human_or_authorized_promotion"])
        self.assertEqual(contract["execution"], "not-performed")
        self.assertEqual(before, baseline_snapshot)
        self.assertEqual(after, candidate_snapshot)
        self.assertEqual(candidate, proposal_snapshot)

        # B/C are not promoted on the strength of the offline subcontracts.
        for key, explanation in {**B, **C}.items():
            with self.subTest(classified=key):
                self.assertGreater(len(explanation), 25)
                self.assertEqual(operational_claim(explanation), UNKNOWN)

    def test_falla_cerrado(self):
        """AC-02: malformed evidence, missing authority and drift fail closed."""
        # Exercise the actual release/issue/Constitution/Lab validators below.
        # Never bind this test to the coverage matrix or its future promotion.

        for change in (
            {"kill_switch_state": "PAUSED"},
            {"evidence_authenticated": False},
            {"observed_main_sha": "b" * 40},
            {"checks": []},
        ):
            sample = release_fixture()
            sample.update(change)
            blocked = evaluate_release(sample)
            self.assertEqual(blocked["decision"], "BLOCKED")
            self.assertFalse(blocked["authorizes_release"])
            self.assertEqual(blocked["mutations"], 0)
        missing_grant = compare_permissions(
            {"contents": "write", "checks": "read"},
            {"contents": "read"},
        )
        self.assertFalse(missing_grant["compatible"])
        self.assertEqual(missing_grant["reason"], "insufficient_permissions")
        self.assertEqual(missing_grant["missing"], [
            {"scope": "checks", "required": "read", "granted": "none"},
            {"scope": "contents", "required": "write", "granted": "read"},
        ])
        malformed_grants = compare_permissions({"contents": "write"}, None)
        self.assertFalse(malformed_grants["compatible"])
        self.assertEqual(malformed_grants["reason"], "invalid_contract")
        live = release_fixture()
        live["phase"] = "live"
        self.assertEqual(evaluate_release(live)["decision"],
                         "HUMAN_GATE_REQUIRED")

        for invalid in (
            issue_fixture().replace("### Contexto", "### Context"),
            issue_fixture().replace("<!-- factory-plan-task",
                                    "<!-- invalid-factory-plan"),
            issue_fixture().replace("[AC-01]", "[AC-XX]"),
        ):
            with self.assertRaises(IssueContractPreflightError):
                evaluate_issue_body(invalid)
        invalid = proposal_fixture()
        invalid["changes"][0]["path"] = "decisiones.yml"
        with self.assertRaises(ConstitutionError):
            validate_candidate(invalid)
        invalid = proposal_fixture()
        invalid["rollback"]["reversible"] = False
        with self.assertRaises(ConstitutionError):
            validate_candidate(invalid)

        before, after = vectors()
        invalid_shadow_candidate = proposal_fixture()
        with self.assertRaises(FactoryLabError):
            evaluate_shadow(
                stable_sha="a" * 40, candidate_sha="a" * 40,
                stable_metrics=before, candidate_metrics=after,
                constitution_candidate=invalid_shadow_candidate,
            )
        degraded = deepcopy(after)
        degraded["security"]["value"] = 0.5
        adverse = compare_fitness(baseline=before, candidate=degraded)
        self.assertEqual(adverse["claim"], "blocked")
        self.assertIn("security", adverse["protected_regressions"])

    def test_sin_datos_reales(self):
        """AC-03: local input only, no PII, secrets, live providers or network."""
        self.assertEqual(ALL, frozenset(A) | frozenset(B) | frozenset(C))
        for alleged in (
            {"run": 36507097760, "status": "success"},
            {"live": True, "status": "VALIDATED_IN_PRODUCTION"},
            {"owner": True, "release": True},
        ):
            self.assertEqual(operational_claim(alleged), UNKNOWN)
        self.assertEqual(proposal_fixture()["evidence"], ["synthetic:factory-1817"])
        self.assertEqual(release_fixture()["main_sha"], "a" * 40)
        self.assertEqual(release_fixture()["phase"], "construccion")
        self.assertFalse(evaluate_release(release_fixture())["authorizes_release"])
        self.assertFalse(evaluate_shadow(
            stable_sha="a" * 40, candidate_sha="b" * 40,
            stable_metrics=vectors()[0], candidate_metrics=vectors()[1],
            constitution_candidate=proposal_fixture(),
        )["mutation_allowed"])


if __name__ == "__main__":
    unittest.main()
