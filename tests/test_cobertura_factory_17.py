"""Factory #1808: pruebas ejecutables de Feedback Mesh y Fitness.

No se simulan los PR y runs históricos ni el handoff físico de macOS:
requieren evidencia externa o expresan política/arquitectura.
"""
from __future__ import annotations

import copy
import json
import socket
import subprocess
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from evolution.autonomy import AutonomyEngine, CapabilityScope
from evolution.constitution import (
    ConstitutionError, PROTECTED_INVARIANTS, validate_candidate,
)
from evolution.engine import EvolutionEngine
from evolution.fitness import FitnessError, compare_fitness
from evolution.models import EvolutionError
from lab.factory_lab import FactoryLabError, evaluate_shadow
from metricas.review_efficiency import (
    ReviewEfficiencyError, STABLE_REVIEW_ROUND_LIMIT, build_report,
    build_shadow_candidate, validate_observation,
)
from scripts.politica_kit import load_policy


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "metricas/datos/review-efficiency-baseline.jsonl"
MANIFEST = ROOT / "feedback/data/feedback-mesh-e2e.json"
STABLE_SHA = "a" * 40
CANDIDATE_SHA = "b" * 40


def _rows():
    return [json.loads(line) for line in BASELINE.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _metric(value, direction="higher"):
    return {"value": value, "direction": direction}


def _metrics(cost=None):
    return {**{name: _metric(1.0) for name in PROTECTED_INVARIANTS},
            "review_cost": _metric(cost, "lower")}


def _candidate():
    return {
        "version": 1,
        "changes": [{
            "path": "evolution_state.thresholds.review_round_limit_low_risk",
            "operation": "add",
            "value": {"stable": 3, "candidate": 2, "mode": "shadow"},
        }],
        "evidence": ["synthetic:review-rounds"],
        "rollback": {"reversible": True, "strategy": "restore_baseline"},
    }


def _report():
    return build_report(_rows(), min_samples=3)


def _factory_cohort(report):
    return next(row for row in report["cohorts"]
                if row["key"]["repo"].lower() == "pl0n3r/factory")


class CoberturaFactory17Tests(unittest.TestCase):
    """AC-01..03: interfaces de runtime, fixtures locales y casos negativos."""

    def test_contrato_principal(self):
        """Reproduce revisión real, evaluación shadow y decisión de rechazo."""
        manifest = _manifest()
        report = _report()
        factory = _factory_cohort(report)
        consumer = next(cohort for cohort in report["cohorts"]
                        if cohort["key"]["repo"] == "pl0n3r/GrindFlow")

        # L20-U1: informe real separa cohortes Factory y consumidor.
        with self.subTest(row="feedback:L20-U1"):
            self.assertTrue(report["baseline_reproducible"])
            self.assertEqual(report["records"], len(_rows()))
            self.assertNotEqual(factory["key"], consumer["key"])
            self.assertNotEqual(factory["key"]["risk"], consumer["key"]["risk"])
            self.assertTrue(all(c["policy_recommendation"] is None
                                for c in report["cohorts"]))

        # L21-U1: candidata low-risk 3 -> 2 no es cambio en stable.
        with self.subTest(row="feedback:L21-U1"):
            self.assertEqual(STABLE_REVIEW_ROUND_LIMIT, 3)
            self.assertEqual(factory["sample_status"], "insufficient_data")
            self.assertEqual(factory["paired_2_3_samples"], 0)
            self.assertEqual(manifest["decision"]["reason"], "insufficient_evidence")

        # L22-U1/L31-U1: Constitution valida la superficie reversible.
        with self.subTest(row="feedback:L22-U1,L31-U1"):
            self.assertRegex(validate_candidate(_candidate()), r"^[0-9a-f]{64}$")
            self.assertEqual(_candidate()["changes"][0]["path"].split(".")[0],
                             "evolution_state")

        # L23-U1/L24-U1: Lab shadow, sin escrituras e incertidumbre explícita.
        with self.subTest(row="feedback:L23-U1,L24-U1"):
            lab = evaluate_shadow(
                stable_sha=STABLE_SHA, candidate_sha=CANDIDATE_SHA,
                stable_metrics=_metrics(), candidate_metrics=_metrics(),
                constitution_candidate=_candidate(),
            )
            self.assertEqual(lab["mode"], "shadow")
            self.assertFalse(lab["mutation_allowed"])
            self.assertEqual(lab["external_writes"], [])
            self.assertEqual(lab["baseline"]["name"], "stable")
            self.assertEqual(lab["fitness"]["claim"], "inconclusive")
            self.assertIn("review_cost", lab["fitness"]["missing_dimensions"])
            self.assertIn("security", lab["fitness"]["protected_dimensions"])
            self.assertFalse(lab["promotion"]["ready"])
            self.assertEqual(lab["promotion"]["execution"], "not-performed")

        # L25-U1/L25-U2: faltan muestras pareadas => no promover.
        with self.subTest(row="feedback:L25-U1,L25-U2"):
            answer = build_shadow_candidate(
                report=report, cohort_key=factory["key"],
                stable_sha=STABLE_SHA, candidate_sha=CANDIDATE_SHA,
                protected_stable={name: 1.0 for name in PROTECTED_INVARIANTS},
                protected_candidate={name: 1.0 for name in PROTECTED_INVARIANTS},
            )
            self.assertEqual(answer["status"], "insufficient_evidence")
            self.assertFalse(answer["mutation_allowed"])
            self.assertEqual(answer["external_writes"], [])
            self.assertEqual(manifest["decision"], {
                "status": "reject", "reason": "insufficient_evidence",
                "promotion_executed": False,
            })

        # L26-U1: la política real mantiene el límite en tres rondas.
        with self.subTest(row="feedback:L26-U1"):
            self.assertEqual(load_policy(root=ROOT)["review_round_limit"], 3)
            self.assertEqual(manifest["stable_policy"]["review_round_limit"], 3)
            self.assertIs(manifest["stable_policy"]["changed"], False)

        # L31-U1: la autonomía no confiere autoridad externa.
        with self.subTest(row="feedback:L31-U1:authority"):
            autonomy = AutonomyEngine(
                CapabilityScope("review-efficiency", authority_class="operational"),
                reason="synthetic observation", evidence=["synthetic:review"],
            )
            snapshot = autonomy.snapshot()
            self.assertEqual(snapshot["level"], "observe")
            self.assertEqual(snapshot["authority"]["external_permissions_added"], [])
            self.assertEqual(set(snapshot["authority"]["forbidden_external_authority"]),
                             {"money", "legal", "personal_data", "irreversible_delete"})

        # L25-U2: el rejection loop reutiliza EvolutionEngine.
        with self.subTest(row="feedback:L25-U2:engine"):
            engine = EvolutionEngine(
                _candidate(), reason="synthetic rejected hypothesis",
                evidence=["synthetic:review"],
            )
            for stage in ("remember", "learn", "propose", "shadow", "experiment", "validate"):
                engine.transition(stage, reason=f"synthetic:{stage}",
                                  evidence=[f"synthetic:{stage}"])
            result = engine.transition(
                "promote_or_reject", decision="reject",
                reason="insufficient evidence", evidence=["synthetic:fitness"],
            )
            self.assertEqual(result.decision, "reject")
            self.assertEqual(engine.current.stage, "promote_or_reject")

        # Fitness L20-U1: delta menor significa mejora de latencia.
        with self.subTest(row="fitness:L20-U1"):
            good = compare_fitness(
                baseline={**{x: _metric(1.0) for x in PROTECTED_INVARIANTS},
                          "latency": _metric(10, "lower")},
                candidate={**{x: _metric(1.0) for x in PROTECTED_INVARIANTS},
                           "latency": _metric(7, "lower")},
            )
            self.assertEqual(good["dimensions"]["latency"]["status"], "improved")
            self.assertEqual(good["claim"], "improved")

    def test_falla_cerrado(self):
        """Rechaza observaciones, rutas, permisos y métricas inconsistentes."""
        original = _rows()[0]
        for key, value in (("sha", "invalid"), ("round", 4),
                           ("review_state", "UNKNOWN_STATE"),
                           ("findings", [{"id": "invalid"}])):
            with self.subTest(malformed_review=key), self.assertRaises(ReviewEfficiencyError):
                validate_observation({**original, key: value})
        with self.assertRaises(ReviewEfficiencyError):
            build_report(_rows(), min_samples=0)

        for path in ("stable_authority.review_round_limit", "constitution.security",
                     "external_permissions.money"):
            bad = _candidate()
            bad["changes"][0]["path"] = path
            with self.subTest(forbidden_path=path), self.assertRaises(ConstitutionError):
                validate_candidate(bad)
        bad = _candidate()
        bad["rollback"]["reversible"] = False
        with self.assertRaises(ConstitutionError):
            validate_candidate(bad)

        with self.assertRaises(FactoryLabError):
            evaluate_shadow(
                stable_sha=STABLE_SHA, candidate_sha=STABLE_SHA,
                stable_metrics=_metrics(), candidate_metrics=_metrics(),
                constitution_candidate=_candidate(),
            )
        with self.assertRaises(EvolutionError):
            EvolutionEngine(
                _candidate(), reason="synthetic", evidence=["synthetic:ref"],
            ).transition("promote_or_reject", decision="adopt",
                         reason="skip steps", evidence=["synthetic:ref"])

        # Fitness L20-U1: direction solo higher/lower; no cambio de sentido.
        for invalid in ("up", None, 1):
            with self.subTest(direction=invalid), self.assertRaises(FitnessError):
                compare_fitness(
                    baseline={"security": _metric(1.0, invalid)},
                    candidate={"security": _metric(1.0, invalid)},
                )
        with self.assertRaises(FitnessError):
            compare_fitness(
                baseline={"security": _metric(1.0, "higher")},
                candidate={"security": _metric(2.0, "lower")},
            )
        with self.assertRaises(FitnessError):
            compare_fitness(
                baseline={"security": _metric(1.0)},
                candidate={"security": _metric(float("nan"))},
            )
        protected_regression = compare_fitness(
            baseline={name: _metric(1.0) for name in PROTECTED_INVARIANTS},
            candidate={name: _metric(0.0 if name == "security" else 1.0)
                       for name in PROTECTED_INVARIANTS},
        )
        self.assertEqual(protected_regression["claim"], "blocked")
        self.assertIn("security", protected_regression["protected_regressions"])
        self.assertFalse(protected_regression["can_claim_improvement"])

    def test_sin_datos_reales(self):
        """Ejecuta las rutas existentes offline, sin red ni subprocesos."""
        frozen = copy.deepcopy(_rows())
        with (mock.patch.object(socket, "create_connection",
                                side_effect=AssertionError("network forbidden")),
              mock.patch.object(socket, "socket",
                                side_effect=AssertionError("network forbidden")),
              mock.patch.object(urllib.request, "urlopen",
                                side_effect=AssertionError("network forbidden")),
              mock.patch.object(subprocess, "run",
                                side_effect=AssertionError("subprocess forbidden"))):
            report = _report()
            shadow = evaluate_shadow(
                stable_sha=STABLE_SHA, candidate_sha=CANDIDATE_SHA,
                stable_metrics=_metrics(), candidate_metrics=_metrics(),
                constitution_candidate=_candidate(),
            )
            policy = load_policy(root=ROOT)
            candidate_hash = validate_candidate(_candidate())
        self.assertEqual(_rows(), frozen)
        self.assertTrue(report["baseline_reproducible"])
        self.assertEqual(shadow["external_writes"], [])
        self.assertEqual(policy["review_round_limit"], 3)
        self.assertEqual(len(candidate_hash), 64)
        self.assertTrue(all(row["result_ref"].startswith(("main:", "head:", "blocked:"))
                            for row in frozen))


if __name__ == "__main__":
    unittest.main()
