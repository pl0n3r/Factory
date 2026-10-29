"""#1805: pruebas offline de Evolution Engine y Experience Guardrail Compiler.

Llama a los módulos reales sin leer el estado de la matriz ni consultar la red.
Los candidatos se mantienen en estado candidate: no otorgan autoridad estable.
"""
from __future__ import annotations

from copy import deepcopy
import re
import unittest

from evolution.constitution import ConstitutionError, EXPECTED_LIFECYCLE, validate_candidate
from evolution.engine import EvolutionEngine
from evolution.experience_guardrails import (
    ExperienceGuardrailError,
    compile_guardrail_candidates,
)
from evolution.models import EvolutionError
from lecciones.memoria import validate_lesson


def _candidate():
    return {
        "version": 1,
        "changes": [{
            "path": "evolution_state.heuristics.probe",
            "operation": "add",
            "value": {"status": "candidate", "prevention": "Review offline only"},
        }],
        "evidence": ["pl0n3r/factory#1805"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


def _lesson(n: int, source: int | None = None, *,
            why: str = "Falla repetida en CI.",
            prevention: str = "Validar siempre.",
            what: str = "Falló el workflow en un ejemplo sintético.") -> dict:
    return {
        "id": f"synthetic-{n:03d}",
        "project": "pl0n3r/factory",
        "kind": "process",
        "occurred_at": "2026-09-20T12:00:00Z",
        "what": what,
        "why": why,
        "prevention": prevention,
        "source": f"pl0n3r/factory#{source if source is not None else 200 + n}",
    }


def _repeated():
    return [
        _lesson(1, 201),
        _lesson(2, 202, why=" FALLA, repetida en ci!! ",
                prevention=" VALIDAR SIEMPRE! "),
        _lesson(3, 203, why="Fállá repetida en CÍ",
                prevention="Validar... siempre"),
    ]


class CoberturaFactory14Tests(unittest.TestCase):
    """AC-01/02/03: cobertura conductual de las 20 filas documentadas."""

    def test_contrato_principal(self):
        # evolution:L29 — la primera generación usa el fingerprint real
        # validado por Constitution, no una etiqueta sin efecto.
        candidate = _candidate()
        engine = EvolutionEngine(candidate, reason="start",
                                 evidence=["pl0n3r/factory#1805"])
        fingerprint = validate_candidate(candidate)
        self.assertEqual(len(engine.history), 1)
        self.assertEqual(engine.history[0].generation, 0)
        self.assertEqual(engine.history[0].candidate_fingerprint, fingerprint)
        self.assertEqual(engine.lifecycle, EXPECTED_LIFECYCLE)

        # evolution:L35 — solo adopt/reject en promote_or_reject.
        for stage in EXPECTED_LIFECYCLE[1:-1]:
            record = engine.transition(
                stage, reason=f"offline:{stage}", evidence=["synthetic:evidence"],
                **({"decision": "adopt"} if stage == "promote_or_reject" else {}),
            )
            if stage == "promote_or_reject":
                self.assertEqual(record.decision, "adopt")
            self.assertEqual(record.candidate_fingerprint, fingerprint)

        # evolution:L41 — append-only rollback al final constitucional.
        before = engine.history
        self.assertEqual(before[-1].stage, "prune")
        rolled = engine.rollback(
            0, reason="revert synthetic experiment", evidence=["synthetic:revert"],
        )
        self.assertEqual(rolled.stage, "rollback")
        self.assertEqual(rolled.parent_generation, before[-1].generation)
        self.assertEqual(rolled.restores_generation, 0)
        self.assertEqual(engine.history[:-1], before)
        self.assertEqual(engine.active_generation, 0)
        self.assertEqual(len(engine.history), len(EXPECTED_LIFECYCLE))

        lessons = _repeated()
        # experience:L11..15/L17 — valida campos reales antes de agrupar;
        # what/why/prevention/source y atributos canónicos se preservan.
        for item in lessons:
            with self.subTest(lesson=item["id"]):
                validated = validate_lesson(item, "synthetic")
                for key in ("what", "why", "prevention", "source", "id",
                            "project", "kind", "occurred_at"):
                    self.assertEqual(validated[key], item[key].strip())
        output = compile_guardrail_candidates(lessons)
        self.assertEqual(len(output), 1)
        item = output[0]
        value = item["candidate"]["changes"][0]["value"]

        # experience:L24/L25/L27 — causa y prevención plegadas sin inferir
        # significado; mayúsculas, acentos, puntuación y espacios equivalentes.
        self.assertEqual(item["occurrences"], 3)
        self.assertEqual(item["lesson_ids"],
                         ["synthetic-001", "synthetic-002", "synthetic-003"])
        self.assertEqual(item["sources"],
                         ["pl0n3r/factory#201", "pl0n3r/factory#202",
                          "pl0n3r/factory#203"])
        self.assertEqual(item["candidate_fingerprint"],
                         compile_guardrail_candidates(list(reversed(lessons)))[0]
                         ["candidate_fingerprint"])

        # experience:L4/L43 — huellas estables; candidato no es regla stable.
        self.assertRegex(item["pattern_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertRegex(item["candidate_fingerprint"], r"^[0-9a-f]{64}$")
        self.assertEqual(value["status"], "candidate")
        self.assertEqual(item["candidate"]["changes"][0]["operation"], "add")

        # experience:L44 — identidad, fuentes, tipo y timestamp de cada
        # lección de origen sin perder entradas.
        origins = value["origins"]
        self.assertEqual(len(origins), 3)
        self.assertEqual({o["lesson_id"] for o in origins}, set(item["lesson_ids"]))
        self.assertEqual({o["source"] for o in origins}, set(item["sources"]))
        self.assertEqual({o["kind"] for o in origins}, {"process"})
        self.assertTrue(all(o["occurred_at"] == "2026-09-20T12:00:00Z"
                            for o in origins))

        # experience:L45/L46 — prevención y ocurrencias verificables.
        self.assertEqual(item["expected_prevention"], "Validar siempre.")
        self.assertEqual(value["expected_prevention"], item["expected_prevention"])
        self.assertEqual(value["occurrences"], 3)

        # experience:L47 — candidato constitucional reversible, único
        # namespace autorizado, nunca stable_authority.
        self.assertEqual(item["candidate"]["changes"][0]["path"],
                         f"evolution_state.heuristics.{item['guardrail_id']}")
        self.assertEqual(value["guardrail_id"], item["guardrail_id"])
        self.assertEqual(value["pattern_fingerprint"], item["pattern_fingerprint"])
        self.assertEqual(item["candidate"]["rollback"],
                         {"reversible": True, "strategy": "revert"})
        self.assertEqual(validate_candidate(item["candidate"]),
                         item["candidate_fingerprint"])

    def test_falla_cerrado(self):
        # evolution:L29 — rechazo previo a toda generación si la
        # Constitución no permite el cambio (o el candidato está incompleto).
        for changes in ([], [{
            "path": "stable_authority.policy", "operation": "replace",
            "value": "override",
        }]):
            bad = _candidate()
            bad["changes"] = changes
            with self.subTest(changes=changes):
                with self.assertRaises(ConstitutionError):
                    EvolutionEngine(bad, reason="bad", evidence=["synthetic"])

        engine = EvolutionEngine(_candidate(), reason="init",
                                 evidence=["synthetic"])
        with self.assertRaises(EvolutionError):
            engine.transition("experiment", reason="skip",
                              evidence=["synthetic"])
        with self.assertRaises(EvolutionError):
            engine.rollback(0, reason="early", evidence=["synthetic"])
        for stage in EXPECTED_LIFECYCLE[1:-1]:
            if stage == "promote_or_reject":
                # evolution:L35 — decisiones inexistentes o ambiguas
                # nunca se tratan como autorización implícita.
                for invalid in (None, "maybe", "approved", True):
                    with self.subTest(invalid_decision=invalid):
                        with self.assertRaises(EvolutionError):
                            engine.transition(stage, reason="bad",
                                              evidence=["synthetic"],
                                              decision=invalid)
            engine.transition(
                stage, reason="valid", evidence=["synthetic"],
                **({"decision": "reject"} if stage == "promote_or_reject" else {}),
            )
        self.assertEqual(next(row.decision for row in engine.history
                              if row.stage == "promote_or_reject"), "reject")
        # evolution:L41 — bool no es generación ni se permite rollback
        # sobre un target futuro o no existente.
        for invalid in (True, -1, 999, "0"):
            with self.subTest(rollback_target=invalid):
                with self.assertRaises(EvolutionError):
                    engine.rollback(invalid, reason="invalid",
                                    evidence=["synthetic"])

        # experience:L17: sin schema válido no hay agrupación.
        for field in ("what", "why", "prevention", "source", "id",
                      "project", "kind", "occurred_at"):
            invalid = _lesson(91)
            del invalid[field]
            with self.subTest(missing_field=field):
                with self.assertRaises(ExperienceGuardrailError):
                    compile_guardrail_candidates([invalid, _lesson(92)])
        malformed = _lesson(93)
        malformed["source"] = "https://example.invalid/no-issue"
        with self.assertRaises(ExperienceGuardrailError):
            compile_guardrail_candidates([malformed, _lesson(94)])
        with self.assertRaises(ExperienceGuardrailError):
            compile_guardrail_candidates([_lesson(1), _lesson(1)])

        # experience:L32 — una lección y la misma fuente no promueven.
        self.assertEqual(compile_guardrail_candidates([_lesson(1)]), [])
        self.assertEqual(compile_guardrail_candidates([
            _lesson(1, 220), _lesson(2, 220)]), [])

        # experience:L24/25/27: cambios semánticos no se colapsan.
        self.assertEqual(compile_guardrail_candidates([
            _lesson(1, 221), _lesson(2, 222, why="Otra causa")]), [])
        self.assertEqual(compile_guardrail_candidates([
            _lesson(1, 221),
            _lesson(2, 222, prevention="Prevención diferente")]), [])
        self.assertEqual(compile_guardrail_candidates([
            _lesson(1, 221),
            {**_lesson(2, 222), "project": "another/project"}]), [])

        # experience:L36 — hard cap de 32 y umbral mínimo de dos.
        for minimum in (1, 0, -1, 33, 2.0, True):
            with self.subTest(min_occurrences=minimum):
                with self.assertRaises(ExperienceGuardrailError):
                    compile_guardrail_candidates([_lesson(1)], min_occurrences=minimum)
        with self.assertRaises(ExperienceGuardrailError):
            compile_guardrail_candidates([_lesson(n) for n in range(1, 34)])
        self.assertEqual(compile_guardrail_candidates(
            [_lesson(1), _lesson(2)], min_occurrences=3), [])

    def test_sin_datos_reales(self):
        # experience:L4/L47: la compilación es pura; metadata sintética
        # no habilita guardrails, red, políticas ni datos de usuarios.
        lessons = _repeated()
        original = deepcopy(lessons)
        first = compile_guardrail_candidates(lessons)
        second = compile_guardrail_candidates(deepcopy(lessons))
        self.assertEqual(lessons, original)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 1)
        row = first[0]
        change = row["candidate"]["changes"][0]
        self.assertTrue(change["path"].startswith("evolution_state.heuristics."))
        self.assertNotIn("stable_authority", str(row))
        self.assertNotIn("provider_credentials", str(row))
        self.assertEqual(change["value"]["status"], "candidate")
        self.assertEqual(row["candidate"]["rollback"]["strategy"], "revert")
        self.assertTrue(all(re.fullmatch(r"pl0n3r/factory#\d+", s)
                            for s in row["sources"]))
        self.assertEqual(row["candidate"]["evidence"], row["sources"])

    def test_gate_validar_presente(self):
        # AC-04: la rama protegida exige el Validar de GitHub sobre HEAD exacto;
        # no se lee ni se simula el estado de un check en una prueba local.
        engine = EvolutionEngine(_candidate(), reason="offline",
                                 evidence=["synthetic"])
        self.assertEqual(engine.current.stage, "observe")
        candidate = compile_guardrail_candidates([_lesson(1), _lesson(2)])[0]
        self.assertEqual(validate_candidate(candidate["candidate"]),
                         candidate["candidate_fingerprint"])


if __name__ == "__main__":
    unittest.main()
