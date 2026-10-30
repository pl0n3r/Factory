#!/usr/bin/env python3
"""#1804: cobertura conductual de métricas y Evolution Engine.

No consulta la matriz: ejercita funciones reales con datos ficticios.
Las filas que dependen de un workflow no existente o de consumidores externos
se clasifican D fuera del test, no se dan por cubiertas artificialmente.
"""
from __future__ import annotations

import contextlib
import io
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request

from metricas import evaluar_agentes as metrics
from metricas.evaluar_agentes import ValidationError, aggregate, load_records, validate_record
from evolution.constitution import ConstitutionError, EXPECTED_LIFECYCLE, validate_candidate
from evolution.engine import EvolutionEngine
from evolution.models import EvolutionError


def record(n: int, model: str = "alpha", **overrides):
    """Registro mínimo verificable: identidades sin PII, red ni secretos."""
    value = {
        "task_id": f"factory#{n}",
        "task_type": "backend",
        "agent": "synthetic-agent",
        "model": model,
        "prompt_id": "synthetic-prompt",
        "roles": ["qa"],
        "success": True,
        "merged_first_try": True,
        "commits": 2,
        "review_rounds": 1,
        "rework_commits": 0,
        "incidents_after": 0,
        "completed_at": "2026-09-20T12:00:00Z",
        "tokens_input": 20,
        "tokens_output": 10,
    }
    value.update(overrides)
    return validate_record(value, "synthetic")


def pair(**inferior):
    """Dos grupos de tamaño suficiente, idénticos salvo la métrica aislada."""
    rows = [record(n) for n in range(1, 4)]
    rows.extend(record(n + 10, "beta", **inferior) for n in range(1, 4))
    return aggregate(rows, min_samples=3)["task_types"]["backend"]


def candidate():
    return {
        "version": 1,
        "changes": [{
            "path": "evolution_state.heuristics.synthetic",
            "operation": "add",
            "value": {"status": "candidate", "prevention": "offline test"},
        }],
        "evidence": ["pl0n3r/factory#1804"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


def evolve_to_prune(engine):
    """Ejecuta transiciones reales, sin escribir autoridad estable."""
    for stage in EXPECTED_LIFECYCLE[1:-1]:
        engine.transition(
            stage, reason=f"synthetic:{stage}", evidence=["synthetic:evidence"],
            **({"decision": "adopt"} if stage == "promote_or_reject" else {}),
        )
    return engine


class CoberturaFactory13Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # evaluacion-agentes:L21/L22/L23: jerarquía observada en aggregate,
        # no búsqueda del texto del documento ni de estados de matriz.
        comparisons = (
            ("merged_first_try", {"merged_first_try": False}, "first_merge_rate"),
            ("rework_commits", {"rework_commits": 2}, "rework_commits_avg"),
            ("review_rounds", {"review_rounds": 2}, "review_rounds_avg"),
            ("tokens", {"tokens_input": 200}, "tokens_avg"),
        )
        for label, change, metric in comparisons:
            with self.subTest(metric=label):
                report = pair(**change)
                best, worse = report["configurations"]
                self.assertEqual(best["configuration"]["model"], "alpha")
                self.assertEqual(worse["configuration"]["model"], "beta")
                self.assertEqual(best["rank"], 1)
                self.assertEqual(worse["rank"], 2)
                self.assertEqual(report["recommendation"]["model"], "alpha")
                self.assertEqual(report["recommendation_status"], "data-backed")
                if metric in ("first_merge_rate",):
                    self.assertGreater(best[metric], worse[metric])
                else:
                    self.assertLess(best[metric], worse[metric])

        # L26-U1: sin dos opciones comparables y diferencia real no hay ganador.
        one = aggregate([record(n) for n in range(1, 4)], min_samples=3)
        self.assertIsNone(one["task_types"]["backend"]["recommendation"])
        few = aggregate(
            [record(1), record(2, "beta", success=False)], min_samples=3,
        )["task_types"]["backend"]
        self.assertIsNone(few["recommendation"])
        self.assertTrue(all(
            row["sample_status"] == "insufficient_data"
            for row in few["configurations"]
        ))
        tied = pair()
        self.assertIsNone(tied["recommendation"])
        self.assertEqual(tied["recommendation_status"], "tie-or-incomplete-cost")
        self.assertEqual(
            {x["rank"] for x in tied["configurations"]}, {1},
        )

        # L26-U2/U3 y L24: tokens solo desempatan con telemetría completa.
        partial = [record(n) for n in range(1, 4)]
        partial += [
            record(11, "beta", tokens_output=None),
            record(12, "beta"),
            record(13, "beta"),
        ]
        incomplete = aggregate(partial, min_samples=3)["task_types"]["backend"]
        configs = {
            row["configuration"]["model"]: row
            for row in incomplete["configurations"]
        }
        self.assertIsNone(configs["beta"]["tokens_avg"])
        self.assertEqual(configs["beta"]["tokens_complete_samples"], 2)
        self.assertIsNone(incomplete["recommendation"])
        self.assertEqual(incomplete["recommendation_status"], "tie-or-incomplete-cost")
        self.assertNotEqual(configs["beta"]["tokens_avg"], 0)

        # L32-U3: un periodo sin registros es éxito vacío, NO recomendación.
        empty = aggregate([], min_samples=3)
        self.assertEqual(empty["records"], 0)
        self.assertEqual(empty["task_types"], {})
        self.assertIn("No se emite recomendación", metrics.render_markdown(empty))

        # L7: el validador procesa los 13 campos obligatorios, sin defaults
        # silenciosos; una muestra sintética válida los preserva.
        validated = record(99)
        self.assertTrue(metrics.REQUIRED <= validated.keys())
        self.assertEqual(len(metrics.REQUIRED), 13)
        self.assertEqual(validated["task_id"], "factory#99")

        # evolution-engine:L10/L12/L20/L22/L25/L26/L27: lifecycle real,
        # contador de generaciones, linaje y huella constitucional.
        spec = candidate()
        fingerprint = validate_candidate(spec)
        engine = EvolutionEngine(
            spec, reason="synthetic:observe", evidence=["synthetic:initial"],
        )
        self.assertEqual(engine.lifecycle, EXPECTED_LIFECYCLE)
        self.assertEqual(
            engine.lifecycle,
            ("observe", "remember", "learn", "propose", "shadow",
             "experiment", "validate", "promote_or_reject", "measure",
             "prune", "rollback"),
        )
        initial = engine.current
        self.assertEqual(initial.generation, 0)
        self.assertIsNone(initial.parent_generation)
        self.assertEqual(initial.candidate_fingerprint, fingerprint)
        evolve_to_prune(engine)
        before = engine.history
        self.assertEqual(len(before), len(EXPECTED_LIFECYCLE) - 1)
        for generation, item in enumerate(before):
            self.assertEqual(item.generation, generation)
            self.assertEqual(item.stage, EXPECTED_LIFECYCLE[generation])
            self.assertEqual(
                item.parent_generation,
                None if generation == 0 else generation - 1,
            )
            self.assertEqual(item.candidate_fingerprint, fingerprint)
            self.assertEqual(
                item.decision,
                "adopt" if item.stage == "promote_or_reject" else None,
            )
            self.assertIsNone(item.restores_generation)
        restored = engine.rollback(
            0, reason="synthetic:restore", evidence=["synthetic:rollback"],
        )
        self.assertEqual(restored.stage, "rollback")
        self.assertEqual(restored.generation, len(before))
        self.assertEqual(restored.parent_generation, before[-1].generation)
        self.assertEqual(restored.restores_generation, initial.generation)
        self.assertEqual(restored.candidate_fingerprint, fingerprint)
        self.assertEqual(engine.history[:len(before)], before)
        self.assertEqual(engine.active_generation, initial.generation)

    def test_falla_cerrado(self):
        # L7: ausencia de campos obligatorios, números o tipos ambiguos
        # se rechaza por el código de validación, no por buscar una matriz.
        for field in sorted(metrics.REQUIRED):
            with self.subTest(missing=field):
                invalid = {
                    "task_id": "factory#1", "task_type": "backend",
                    "agent": "synthetic-agent", "model": "alpha",
                    "prompt_id": "synthetic-prompt", "roles": ["qa"],
                    "success": True, "merged_first_try": True, "commits": 2,
                    "review_rounds": 1, "rework_commits": 0,
                    "incidents_after": 0,
                    "completed_at": "2026-09-20T12:00:00Z",
                }
                invalid.pop(field)
                with self.assertRaises(ValidationError):
                    validate_record(invalid, "synthetic")
        for changes in (
            {"commits": -1}, {"review_rounds": 4},
            {"tokens_input": -1}, {"success": "true"},
            {"completed_at": "2026-09-20T12:00:00"},
            {"unknown": "untrusted"},
        ):
            with self.subTest(bad=changes):
                raw = {
                    "task_id": "factory#1", "task_type": "backend",
                    "agent": "synthetic-agent", "model": "alpha",
                    "prompt_id": "synthetic-prompt", "roles": ["qa"],
                    "success": True, "merged_first_try": True, "commits": 2,
                    "review_rounds": 1, "rework_commits": 0,
                    "incidents_after": 0,
                    "completed_at": "2026-09-20T12:00:00Z",
                }
                raw.update(changes)
                with self.assertRaises(ValidationError):
                    validate_record(raw, "synthetic")
        with self.assertRaises(ValidationError):
            aggregate([], min_samples=0)

        # evolution-engine:L12/L26/L27: saltos, decisiones sin etapa y
        # rollback anticipado o a generaciones no previas fallan cerrado.
        engine = EvolutionEngine(
            candidate(), reason="synthetic:observe", evidence=["synthetic:init"],
        )
        for stage, decision in (
            ("learn", None), ("not-a-stage", None),
            ("remember", "adopt"), ("rollback", None),
        ):
            with self.subTest(stage=stage, decision=decision):
                with self.assertRaises(EvolutionError):
                    engine.transition(
                        stage, reason="synthetic:bad",
                        evidence=["synthetic:bad"], decision=decision,
                    )
        with self.assertRaises(EvolutionError):
            engine.rollback(
                0, reason="synthetic:early", evidence=["synthetic:early"],
            )
        for stage in EXPECTED_LIFECYCLE[1:-1]:
            if stage == "promote_or_reject":
                with self.assertRaises(EvolutionError):
                    engine.transition(
                        stage, reason="synthetic:missing",
                        evidence=["synthetic:missing"],
                    )
            engine.transition(
                stage, reason="synthetic:advance",
                evidence=["synthetic:advance"],
                **({"decision": "reject"} if stage == "promote_or_reject" else {}),
            )
        for target in (-1, True, engine.current.generation):
            with self.subTest(target=target):
                with self.assertRaises(EvolutionError):
                    engine.rollback(
                        target, reason="synthetic:invalid",
                        evidence=["synthetic:invalid"],
                    )
        # El fingerprint solo puede provenir de Constitution v1.
        bad_candidate = candidate()
        bad_candidate["changes"][0]["path"] = "stable_authority.bypass"
        with self.assertRaises(ConstitutionError):
            EvolutionEngine(
                bad_candidate, reason="synthetic:bad",
                evidence=["synthetic:bad"],
            )

    def test_sin_datos_reales(self):
        # L32-U1/U2/U3: ejecutar CLI genuino en un sandbox temporal; sus
        # rutas son fijas y --input/--output no existen. Sin red ni subprocess.
        def denied(*_args, **_kwargs):
            raise AssertionError("I/O externo no permitido")
        with tempfile.TemporaryDirectory(prefix="factory-1804-") as folder:
            root = Path(folder)
            data = root / "metricas" / "datos"
            data.mkdir(parents=True)
            artifacts = root / "artifacts"
            with patch.object(socket, "create_connection", denied), \
                 patch.object(request, "urlopen", denied), \
                 patch.object(subprocess, "run", denied), \
                 patch.object(metrics, "DEFAULT_DATA_DIR", data), \
                 patch.object(metrics, "DEFAULT_OUTPUT_DIR", artifacts), \
                 patch.object(sys, "argv", ["evaluar_agentes.py", "--allow-empty",
                                            "--month", "2026-09"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(metrics.main(), 0)
                self.assertEqual(
                    {p.name for p in artifacts.iterdir()},
                    {"dashboard.md", "recomendaciones.json"},
                )
                report = json.loads((artifacts / "recomendaciones.json").read_text())
                self.assertEqual(report["period"], "2026-09")
                self.assertEqual(report["records"], 0)
                self.assertEqual(report["task_types"], {})
                self.assertIn(
                    "No se emite recomendación",
                    (artifacts / "dashboard.md").read_text(),
                )
                self.assertEqual(load_records([data], allow_empty=True,
                                              month="2026-09"), [])
                result = aggregate(
                    [record(1), record(2, "beta", rework_commits=2)],
                    min_samples=1,
                )
                self.assertEqual(result["records"], 2)
                evolve_to_prune(EvolutionEngine(
                    candidate(), reason="synthetic:start",
                    evidence=["synthetic:only"],
                ))
            for extra in ("--input", "--output"):
                with self.subTest(flag=extra), \
                     patch.object(sys, "argv",
                                  ["evaluar_agentes.py", extra, str(root)]), \
                     contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        metrics.main()
                    self.assertEqual(raised.exception.code, 2)
            self.assertFalse((root / "outside").exists())

    def test_gate_validar_presente(self):
        # AC-04: solo check auténtico Validar del HEAD autoriza merge.
        # Este caso protege el contrato de evidencia; NO fabrica un check.
        # La evidencia terminal la aporta GitHub Actions, no esta prueba.
        engine = EvolutionEngine(
            candidate(), reason="synthetic:check", evidence=["synthetic:check"],
        )
        self.assertEqual(engine.current.stage, "observe")
        with self.assertRaises(EvolutionError):
            engine.transition(
                "promote_or_reject", reason="synthetic:skip",
                evidence=["synthetic:skip"], decision="adopt",
            )
        self.assertEqual(engine.current.generation, 0)


if __name__ == "__main__":
    unittest.main()
