#!/usr/bin/env python3
"""Factory #1803: regresiones funcionales de DoD y evaluación de agentes.

Solo ejecuta contratos puros sobre datos sintéticos, sin leer matrices de
cobertura, emitir releases ni conceder autoridad de deploy.
"""
from __future__ import annotations

import copy
import json
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request

from intelligence.dod_compiler import (
    DodCompilerError,
    FACTORY_INVARIANTS,
    SAFE_FALLBACK,
    compile_done_contract,
)
from intelligence.project_dna import discover_project_dna
from metricas.evaluar_agentes import (
    ValidationError,
    aggregate,
    load_records,
    validate_record,
)

PATHS = [
    "package.json",
    ".github/workflows/ci.yml",
    "vercel.json",
    "database/schema.sql",
    ".sentryclirc",
]
MANIFEST = {
    "package.json": {
        "dependencies": {"fastify": "^5", "@sentry/node": "^9"},
    },
}
INVARIANTS = {
    ("check", "ci:required"),
    ("check", "reviews:no-open-findings"),
    ("check", "scope:claimed-paths-only"),
}
FALLBACK = {
    ("test", "tests:full-suite"),
    ("check", "static:analysis"),
    ("check", "security:scan"),
    ("check", "rollback:plan"),
    ("check", "context:complete-before-promotion"),
}


def dna():
    return discover_project_dna(
        paths=PATHS, manifests=MANIFEST, capabilities=["api", "web"],
    )


def compile_for(change_type="code", risk="low", surfaces=None, *, source=None):
    return compile_done_contract(
        project_dna=dna() if source is None else source,
        task={
            "id": "Factory#1803",
            "title": "synthetic contract",
            "change_type": change_type,
            "surfaces": ["api"] if surfaces is None else surfaces,
            "risk": risk,
        },
    )


def targets(contract):
    return {(item["kind"], item["target"]) for item in contract["evidence"]}


def metric(number, model="alpha", **changes):
    row = {
        "task_id": f"Factory#{number}",
        "task_type": "backend",
        "agent": "synthetic-agent",
        "model": model,
        "prompt_id": "fixture-v1",
        "roles": ["qa"],
        "success": True,
        "merged_first_try": True,
        "commits": 2,
        "review_rounds": 1,
        "rework_commits": 0,
        "incidents_after": 0,
        "completed_at": "2026-09-20T12:00:00Z",
        "tokens_input": 100,
        "tokens_output": 20,
    }
    row.update(changes)
    return row


class CoberturaFactory12Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # L34-U1 a L38-U1: cada cambio requiere pruebas/checks
        # adicionales reales, nunca meras descripciones del documento.
        profiles = {
            "code": {("test", "tests:changed-scope"), ("check", "static:analysis")},
            "database": {
                ("check", "migration:verify-plan"),
                ("check", "backup:evidence"),
                ("test", "schema:compatibility"),
            },
            "ci": {
                ("check", "workflow:validation"),
                ("check", "workflow:representative-run"),
            },
            "docs": {("check", "docs:lint"), ("check", "docs:links")},
            "security": {
                ("check", "security:scan"),
                ("test", "security:negative-cases"),
            },
        }
        for change_type, required in profiles.items():
            with self.subTest(change_type=change_type):
                result = compile_for(change_type, surfaces=["api"])
                self.assertEqual(result["profile"], "derived")
                self.assertTrue(result["context_complete"])
                self.assertTrue(required <= targets(result))
                self.assertTrue(INVARIANTS <= targets(result))
                self.assertEqual(result["invariants"], list(FACTORY_INVARIANTS))
                self.assertTrue(all(
                    row["kind"] in {"test", "check"}
                    and ":" in row["target"]
                    and not row["target"].endswith(":")
                    for row in result["evidence"]
                ))
                self.assertRegex(result["fingerprint"], r"^[0-9a-f]{64}$")
                self.assertEqual(result["project_dna_fingerprint"], dna()["fingerprint"])

        # L39-U1/U2: rollback en medium/high y smoke exact-SHA solo high.
        for risk in ("medium", "high"):
            with self.subTest(risk=risk):
                evidence = targets(compile_for("code", risk))
                self.assertIn(("check", "rollback:plan"), evidence)
                self.assertEqual(
                    ("check", "smoke:exact-sha") in evidence, risk == "high",
                )
        self.assertNotIn(
            ("check", "rollback:plan"), targets(compile_for("code", "low")),
        )

        # L48, L50-L54, L56, L5, L6: Project DNA incompleto
        # produce una lista de obligaciones MÁS estricta, no ALLOW.
        unknown_cases = [
            ("unknown", "low", ["api"], dna()),
            ("code", "unknown", ["api"], dna()),
            ("code", "low", [], dna()),
            ("code", "low", ["api"], discover_project_dna(paths=["README.md"])),
        ]
        for change, risk, surfaces, source in unknown_cases:
            with self.subTest(change=change, risk=risk, surfaces=surfaces):
                result = compile_for(change, risk, surfaces, source=source)
                self.assertEqual(result["profile"], "safe-fallback")
                self.assertFalse(result["context_complete"])
                self.assertTrue(FALLBACK | INVARIANTS <= targets(result))
                self.assertTrue({(x["kind"], x["target"]) for x in SAFE_FALLBACK}
                                <= targets(result))
        equivalent_dna = discover_project_dna(
            paths=list(reversed(PATHS)),
            manifests=MANIFEST,
            capabilities=["web", "api"],
        )
        self.assertEqual(
            compile_for()["fingerprint"],
            compile_for(source=equivalent_dna)["fingerprint"],
        )

        # L13: el validador opera sobre registros verdaderos, no el doc.
        observed = validate_record(metric(1), "fixture")
        self.assertEqual(observed["task_id"], "Factory#1")
        self.assertEqual(observed["incidents_after"], 0)

        # L17: muestra insuficiente no se considera elegible.
        insufficient = aggregate(
            [validate_record(metric(1), "fixture")], min_samples=2,
        )["task_types"]["backend"]
        self.assertIsNone(insufficient["recommendation"])
        self.assertEqual(
            insufficient["configurations"][0]["sample_status"],
            "insufficient_data",
        )
        self.assertIsNone(insufficient["configurations"][0]["rank"])

        # L19: el éxito prevalece sobre incidentes o el nombre del modelo.
        successful = [validate_record(metric(i), "fixture") for i in range(1, 4)]
        less_successful = [
            validate_record(
                metric(i + 10, model="beta", success=(i != 3)),
                "fixture",
            ) for i in range(1, 4)
        ]
        ranked = aggregate(successful + less_successful, min_samples=3)
        rows = ranked["task_types"]["backend"]["configurations"]
        self.assertEqual(rows[0]["configuration"]["model"], "alpha")
        self.assertEqual(rows[0]["success_rate"], 1.0)
        self.assertEqual(rows[1]["success_rate"], 0.6667)
        self.assertEqual(
            ranked["task_types"]["backend"]["recommendation"]["model"],
            "alpha",
        )

        # L20: con éxito igual, MENOS incidentes por tarea gana.
        no_incidents = [validate_record(metric(i), "fixture") for i in range(1, 4)]
        incident_prone = [
            validate_record(metric(i + 10, model="beta", incidents_after=2), "fixture")
            for i in range(1, 4)
        ]
        report = aggregate(no_incidents + incident_prone, min_samples=3)
        best, other = report["task_types"]["backend"]["configurations"]
        self.assertEqual(best["configuration"]["model"], "alpha")
        self.assertEqual(best["incidents_per_task"], 0)
        self.assertEqual(other["incidents_per_task"], 2)
        self.assertEqual(best["rank"], 1)

    def test_falla_cerrado(self):
        # DoD: no se admiten tareas incompletas o Project DNA fabricado.
        with self.assertRaises(DodCompilerError):
            compile_for("invented", "low")
        with self.assertRaises(DodCompilerError):
            compile_for("code", "invalid")
        for invalid in ("", "not-a-list"):
            with self.subTest(surfaces=invalid):
                with self.assertRaises(DodCompilerError):
                    compile_for("code", surfaces=invalid)
        corrupted = copy.deepcopy(dna())
        corrupted["stack"] = ["invented"]
        with self.assertRaises(ValueError):
            compile_for(source=corrupted)

        # L13: campos desconocidos, negativos, tiempos sin zona
        # y más de tres rondas se rechazan, no se cuentan en ranking.
        invalid_rows = [
            metric(1, extra="unexpected"),
            metric(1, commits=-1),
            metric(1, incidents_after=-1),
            metric(1, review_rounds=4),
            metric(1, completed_at="2026-09-20T12:00:00"),
            metric(1, tokens_input=-1),
            metric(1, success="true"),
        ]
        for index, row in enumerate(invalid_rows):
            with self.subTest(index=index):
                with self.assertRaises(ValidationError):
                    validate_record(row, "fixture")

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.jsonl"
            path.write_text(
                "\n".join(json.dumps(metric(1)) for _ in range(2)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValidationError, "duplicado"):
                load_records([path])
        with self.assertRaises(ValidationError):
            aggregate([], min_samples=0)

    def test_sin_datos_reales(self):
        # Las pruebas no consultan red ni corren comandos de sistema.
        def reject(*_args, **_kwargs):
            raise AssertionError("I/O real prohibido")

        with patch.object(socket, "create_connection", reject), \
             patch.object(request, "urlopen", reject), \
             patch.object(subprocess, "run", reject):
            first = compile_for("security", "high")
            self.assertIn(("check", "smoke:exact-sha"), targets(first))
            rows = [validate_record(metric(i), "fixture") for i in range(1, 4)]
            summary = aggregate(rows, min_samples=3)
            self.assertEqual(summary["records"], 3)
            self.assertIsNone(summary["task_types"]["backend"]["recommendation"])
            equivalent_dna = discover_project_dna(
                paths=list(reversed(PATHS)),
                manifests=MANIFEST,
                capabilities=["web", "api"],
            )
            self.assertEqual(
                first["fingerprint"],
                compile_for("security", "high", source=equivalent_dna)["fingerprint"],
            )

    def test_gate_validar_presente(self):
        # El status 'Validar' success NO se inventa en Python:
        # se exige el check de GitHub sobre HEAD exacto antes del merge.
        # Esta regresión impide que el compilador conceda autoridad
        # por falta de identidad o de contexto.
        fallback = compile_for(
            "unknown", "unknown", [], source=discover_project_dna(paths=[]),
        )
        self.assertEqual(fallback["profile"], "safe-fallback")
        self.assertFalse(fallback["context_complete"])
        self.assertIn(("check", "ci:required"), targets(fallback))
        self.assertIn(
            ("check", "context:complete-before-promotion"), targets(fallback),
        )


if __name__ == "__main__":
    unittest.main()
