"""Factory #1818: cobertura conductual offline de Living Software y memoria.

Sólo se atribuyen al código los contratos ejercitables; la veracidad de runs
históricos, la política institucional y las prohibiciones globales requieren
otras fuentes/gates (clasificación B/C/D documentada en PR e Issue).
Todos los registros de entrada creados por esta prueba son sintéticos.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from lab.factory_lab import FactoryLabError, evaluate_shadow
from lecciones.memoria import (
    LessonValidationError,
    load_lessons,
    summarize,
    token_comparison,
    validate_lesson,
)
from metricas.organizational_complexity import compare_simplification


CUTOFF = "2026-09-15T00:00:00Z"
FACTORY = "pl0n3r/Factory"
CONDOR = "pl0n3r/Condor"


def synthetic_scenario():
    """Ficción determinista; no leer runs, SHA ni manifests históricos."""
    return {
        "complexity": {
            "comparison_scope": "fixture-1818-readiness",
            "before_coordination_seconds": 35,
            "after_coordination_seconds": 27,
            "useful_execution_seconds": 29,
        },
        "shadow_candidate": {
            "stable_sha": "a" * 40,
            "candidate_sha": "b" * 40,
            "rollback": "restore_baseline",
        },
        "decision": {"authority_expanded": False},
    }


def complexity_observation(data, *, before):
    """Observación local íntegramente sintética para el comparador real."""
    seconds = data["complexity"][
        "before_coordination_seconds" if before
        else "after_coordination_seconds"
    ]
    label = "before" if before else "after"
    return {
        "version": 1,
        "work_id": f"fixture-1818-readiness-{label}",
        "comparison_scope": data["complexity"]["comparison_scope"],
        "task_type": "coordination",
        "task_size": "small",
        "risk": "medium",
        "rules_consulted": [
            "acceptance-contract", "factory-plan-task", "status-available",
        ],
        "active_roles": [],
        "reviewers": [],
        "checks": ["acceptance", "availability", "parallel-claims"],
        "handoffs": ["issue-comment"],
        "engines_consulted": ["coordination"],
        "context_tokens": 0,
        "coordination_minutes": seconds / 60,
        "wait_minutes": 0,
        "review_minutes": 0,
        "useful_execution_minutes": (
            data["complexity"]["useful_execution_seconds"] / 60
        ),
        "protected_metrics": {
            name: 1.0 for name in PROTECTED_INVARIANTS
        },
        "evidence_refs": [f"fixture:1818-{label}"],
        "observed_at": (
            "2026-09-01T00:00:00Z" if before
            else "2026-09-02T00:00:00Z"
        ),
    }


def constitution_candidate(data):
    """Propuesta ficticia solo en el namespace evolutivo permitido."""
    return {
        "version": 1,
        "changes": [
            {
                "path": "evolution_state.heuristics.reservation_readiness_preflight",
                "operation": "add",
                "value": {
                    "checks": [
                        "acceptance_contract", "status_available",
                        "factory_plan_task",
                    ],
                    "mode": "preflight",
                    "scope": "issue_reservation",
                },
            },
        ],
        "evidence": ["fixture:1818-readiness"],
        "rollback": {
            "reversible": True,
            "strategy": data["shadow_candidate"]["rollback"],
        },
    }


def lab_vectors(data):
    """Fitness: invariantes idénticos y dos mejoras no agregadas."""
    baseline = {
        name: {"value": 1.0, "direction": "higher"}
        for name in PROTECTED_INVARIANTS
    }
    candidate = {
        name: {"value": 1.0, "direction": "higher"}
        for name in PROTECTED_INVARIANTS
    }
    baseline.update({
        "coordination_seconds": {
            "value": data["complexity"]["before_coordination_seconds"],
            "direction": "lower",
        },
        "reservation_attempts": {"value": 3, "direction": "lower"},
    })
    candidate.update({
        "coordination_seconds": {
            "value": data["complexity"]["after_coordination_seconds"],
            "direction": "lower",
        },
        "reservation_attempts": {"value": 1, "direction": "lower"},
    })
    return baseline, candidate


def lesson(identifier="factory-short", project=FACTORY, **changes):
    item = {
        "id": identifier,
        "project": project,
        "kind": "rework",
        "occurred_at": "2026-09-01T00:00:00Z",
        "what": "Contrato sintético de coordinación falló.",
        "why": "Faltaba una precondición confirmada en la prueba.",
        "prevention": "Verificar el contrato antes de reservar.",
        "source": "pl0n3r/Factory#1818",
    }
    item.update(changes)
    return item


def sample(task_id, date, tokens, task_type="agent-bootstrap"):
    return {
        "task_type": task_type,
        "task_id": task_id,
        "tokens_input": tokens,
        "completed_at": date,
    }


def metrics_file(tmp: str, rows: list[dict]) -> Path:
    path = Path(tmp) / "tokens.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows),
        encoding="utf-8",
    )
    return path


class CoberturaFactory27Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """L45/L60, memoria L11-U2/L12-U1/U2/L16/L18: código real."""
        data = synthetic_scenario()
        protected = {name: 1.0 for name in PROTECTED_INVARIANTS}
        self.assertTrue(protected)

        # living:L45-U1: comparar la misma cohorte contra el código #245.
        before = complexity_observation(data, before=True)
        after = complexity_observation(data, before=False)
        comparison = compare_simplification(before, after)
        self.assertEqual(before["protected_metrics"], protected)
        self.assertEqual(after["protected_metrics"], protected)
        self.assertEqual(comparison["fitness"]["claim"], "improved")
        self.assertEqual(comparison["fitness"]["protected_regressions"], [])
        self.assertEqual(comparison["fitness"]["missing_dimensions"], [])
        self.assertTrue(comparison["can_claim_simplification"])
        self.assertEqual(comparison["authority"], "unchanged")
        self.assertFalse(comparison["execute"])

        # living:L60-U1: Constitution + Lab sobre la misma propuesta.
        proposal = constitution_candidate(data)
        self.assertRegex(validate_candidate(proposal), r"^[0-9a-f]{64}$")
        baseline, candidate = lab_vectors(data)
        shadow = evaluate_shadow(
            stable_sha=data["shadow_candidate"]["stable_sha"],
            candidate_sha=data["shadow_candidate"]["candidate_sha"],
            stable_metrics=baseline,
            candidate_metrics=candidate,
            constitution_candidate=proposal,
        )
        self.assertEqual(shadow["mode"], "shadow")
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])
        self.assertEqual(shadow["promotion"]["execution"], "not-performed")
        self.assertEqual(shadow["fitness"]["protected_regressions"], [])
        self.assertFalse(data["decision"]["authority_expanded"])

        # memoria:L16-U1, L11-U2: validar lecciones; si una reciente no
        # cabe en el presupuesto, rescatar otra más antigua sin vaciar contexto.
        big = validate_lesson(
            lesson(
                "factory-large", occurred_at="2026-09-02T00:00:00Z",
                what="w" * 260, why="r" * 260, prevention="p" * 260,
            ),
            "synthetic-big",
        )
        small = validate_lesson(lesson(), "synthetic-small")
        foreign = validate_lesson(
            lesson("condor-small", project=CONDOR), "synthetic-condor",
        )
        summary = summarize(
            [big, small, foreign], FACTORY, max_lessons=3, max_chars=400,
        )
        self.assertIn("factory-short", summary)
        self.assertIn("pl0n3r/Factory#1818", summary)
        self.assertNotIn("factory-large", summary)
        self.assertNotIn("condor-small", summary)
        self.assertLessEqual(len(summary), 400)

        # memoria:L12-U1/U2: telemetría agent-bootstrap, corte temporal y
        # task_id owner/repo#N; jamás mezclar la cohorte de otro repositorio.
        rows = [
            sample("pl0n3r/Factory#101", "2026-09-01T00:00:00Z", 100),
            sample("pl0n3r/Factory#102", "2026-09-02T00:00:00Z", 120),
            sample("pl0n3r/Factory#103", "2026-09-16T00:00:00Z", 60),
            sample("pl0n3r/Factory#104", "2026-09-17T00:00:00Z", 50),
            sample("pl0n3r/Condor#201", "2026-09-01T00:00:00Z", 1),
            sample("pl0n3r/Condor#202", "2026-09-02T00:00:00Z", 1),
            sample("pl0n3r/Condor#203", "2026-09-16T00:00:00Z", 900),
            sample("pl0n3r/Condor#204", "2026-09-17T00:00:00Z", 900),
            sample("pl0n3r/Factory#105", "2026-09-18T00:00:00Z", 999,
                   "other-task"),
        ]
        with tempfile.TemporaryDirectory() as temp:
            result = token_comparison(
                metrics_file(temp, rows), CUTOFF, FACTORY,
            )
            self.assertEqual(result["task_type"], "agent-bootstrap")
            self.assertEqual(result["change_at"], "2026-09-15T00:00:00+00:00")
            self.assertEqual(result["project"], FACTORY)
            self.assertEqual(result["before_samples"], 2)
            self.assertEqual(result["after_samples"], 2)
            self.assertEqual(result["before_avg_tokens"], 110)
            self.assertEqual(result["after_avg_tokens"], 55)
            self.assertEqual(result["reduction_pct"], 50.0)
            self.assertEqual(result["status"], "measured")

            # memoria:L18-U1: dos muestras before sin after -> NO inferir ROI.
            insufficient = token_comparison(
                metrics_file(temp, rows[:2]), CUTOFF, FACTORY,
            )
            self.assertEqual(insufficient["status"], "insufficient-data")
            self.assertIsNone(insufficient["reduction_pct"])
            self.assertEqual(insufficient["after_samples"], 0)

        # memoria:L16-U1: el lector real sólo acepta schema y conserva
        # project, causa declarada, prevención y fuente auditable.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.jsonl"
            path.write_text(
                json.dumps(lesson("factory-loaded")) + "\n",
                encoding="utf-8",
            )
            parsed = load_lessons([path])
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0]["project"], FACTORY)
            self.assertEqual(parsed[0]["source"], "pl0n3r/Factory#1818")
            self.assertEqual(parsed[0]["prevention"], lesson()["prevention"])

    def test_falla_cerrado(self):
        """Negativos reales: evidencia, scopes, authority y datos inválidos."""
        # Living L45/L60: protected regression impide reclamar mejora;
        # no acepta SHA igual para el baseline y el candidato.
        data = synthetic_scenario()
        before = complexity_observation(data, before=True)
        unsafe = complexity_observation(data, before=False)
        unsafe["protected_metrics"]["authority"] = 0.0
        guarded = compare_simplification(before, unsafe)
        self.assertFalse(guarded["can_claim_simplification"])
        self.assertTrue(guarded["fitness"]["protected_regressions"])
        stable, candidate = lab_vectors(data)
        with self.assertRaises(FactoryLabError):
            evaluate_shadow(
                stable_sha=data["shadow_candidate"]["stable_sha"],
                candidate_sha=data["shadow_candidate"]["stable_sha"],
                stable_metrics=stable,
                candidate_metrics=candidate,
                constitution_candidate=constitution_candidate(data),
            )

        # Memoria: sin identificación de origen y causa/prevention no
        # se almacena evidencia, ni se aceptan campos arbitrarios.
        for mutation in (
            {"source": "example.invalid/claim"},
            {"why": ""},
            {"prevention": "una\nlinea"},
            {"project": "unknown"},
            {"arbitrary_payload": "synthetic"},
        ):
            with self.subTest(lesson_mutation=mutation):
                with self.assertRaises(LessonValidationError):
                    validate_lesson(lesson(**mutation), "bad-synthetic")

        with self.assertRaises(LessonValidationError):
            summarize(
                [validate_lesson(lesson(), "valid")],
                "project-without-owner",
            )
        with self.assertRaises(LessonValidationError):
            summarize(
                [validate_lesson(lesson(), "valid")], FACTORY,
                max_chars=399,
            )

        # La muestra de otro repositorio no puede atribuirse a Factory:
        # con identidad inválida del task_id falla cerrado.
        with tempfile.TemporaryDirectory() as temp:
            bad = [sample("factory#201", "2026-09-01T00:00:00Z", 10)]
            with self.assertRaises(LessonValidationError):
                token_comparison(metrics_file(temp, bad), CUTOFF, FACTORY)

            # Telemetría parcial no puede convertirse en mejora.
            missing = token_comparison(
                Path(temp) / "not-present.jsonl", CUTOFF, FACTORY,
            )
            self.assertEqual(missing["status"], "insufficient-data")
            self.assertIsNone(missing["reduction_pct"])

            duplicate = metrics_file(temp, [sample(
                "pl0n3r/Factory#101", "2026-09-01T00:00:00Z", True,
            )])
            with self.assertRaises(LessonValidationError):
                token_comparison(duplicate, CUTOFF, FACTORY)

    def test_sin_datos_reales(self):
        """Ejercita validadores con fixtures locales, sin credenciales ni red."""
        payload = lesson()
        normalized = validate_lesson(payload, "synthetic")
        self.assertEqual(normalized["source"], "pl0n3r/Factory#1818")
        self.assertEqual(normalized["project"], FACTORY)
        self.assertEqual(
            set(payload),
            {"id", "project", "kind", "occurred_at", "what", "why",
             "prevention", "source"},
        )
        serialized = json.dumps(payload).lower()
        for prohibited in ("password", "bearer ", "api_key", "private_key", "@"):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, serialized)
        # El Lab devuelve un resultado, no ejecuta mutación ni acciones remotas.
        data = synthetic_scenario()
        baseline, candidate = lab_vectors(data)
        shadow = evaluate_shadow(
            stable_sha=data["shadow_candidate"]["stable_sha"],
            candidate_sha=data["shadow_candidate"]["candidate_sha"],
            stable_metrics=baseline,
            candidate_metrics=candidate,
            constitution_candidate=constitution_candidate(data),
        )
        self.assertFalse(shadow["mutation_allowed"])
        self.assertEqual(shadow["external_writes"], [])
        self.assertEqual(shadow["promotion"]["execution"], "not-performed")


if __name__ == "__main__":
    unittest.main()
