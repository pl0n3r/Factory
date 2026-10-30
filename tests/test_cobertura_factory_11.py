#!/usr/bin/env python3
"""Factory #1802: pruebas reales offline de vistas derivadas y DoD.

Las filas que requieren preflight externo, un simulacro real o son política
se clasifican en el PR, nunca se sustituyen por afirmaciones de cobertura.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request

from intelligence.derived_views import (
    DerivedViewDriftError, DerivedViewError, DerivedViewSpec,
    check_drift, render_markdown_table,
)
from intelligence.dod_compiler import (
    DodCompilerError, FACTORY_INVARIANTS, SAFE_FALLBACK,
    compile_done_contract,
)
from intelligence.project_dna import discover_project_dna

ROOT = Path(__file__).resolve().parents[1]
VIEWS = "docs/derived-views.md:"
DIET = "docs/dieta-factory.md:"
DOD = "docs/dod-compiler.md:"
OFFLINE = frozenset({
    VIEWS + "L3-U2", VIEWS + "L34-U1", VIEWS + "L38-U1",
    VIEWS + "L39-U1", VIEWS + "L40-U1", VIEWS + "L40-U2",
    VIEWS + "L41-U1", VIEWS + "L9-U1",
    DOD + "L12-U1", DOD + "L14-U1", DOD + "L16-U1",
    DOD + "L18-U1", DOD + "L24-U1", DOD + "L25-U1",
    DOD + "L26-U1", DOD + "L3-U1",
})
POLICY = {
    VIEWS + "L42-U1": "La decisión de documentar reversión es normativa.",
    DIET + "B01": "Ledger y baseline histórica, no comportamiento en runtime.",
}
WORLD = {
    DIET + "B04": "Preflight vigente de consumidores requiere inspección actual externa.",
    DIET + "B05": "Reversión acumulada requiere simulacro real con estado persistente.",
}


def dna():
    return discover_project_dna(
        paths=[
            "package.json", ".github/workflows/ci.yml", "vercel.json",
            "database/schema.sql", ".sentryclirc",
        ],
        manifests={"package.json": {"dependencies": {
            "fastify": "^5", "@sentry/node": "^9",
        }}},
        capabilities=["api", "web"],
    )


def done(change_type="code", surfaces=None, risk="low", *, source=None):
    return compile_done_contract(
        project_dna=dna() if source is None else source,
        task={
            "id": "synthetic-1802", "title": "synthetic evidence",
            "change_type": change_type,
            "surfaces": ["api"] if surfaces is None else surfaces,
            "risk": risk,
        },
    )


def evidence(contract):
    return {(row["kind"], row["target"]) for row in contract["evidence"]}


class CoberturaFactory11Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: prueba contratos ejecutables, no la matriz de cobertura."""
        self.assertEqual((len(OFFLINE), len(POLICY), len(WORLD)), (16, 2, 2))
        self.assertEqual(len(OFFLINE | POLICY.keys() | WORLD.keys()), 20)
        exercised = set()

        # L3: una vista materializa la fuente normalizada sin mutarla.
        records = [{"id": "b", "state": "pending"},
                   {"id": "a", "state": "ready"}]
        original = [dict(record) for record in records]
        generated = render_markdown_table(records, ("id", "state"), sort_by="id")
        self.assertEqual(records, original)
        self.assertEqual(
            generated,
            render_markdown_table(reversed(records), ("id", "state"), sort_by="id"),
        )
        check_drift(generated, generated)
        exercised.add(VIEWS + "L3-U2")

        # L34: README es derivado de PLAN/Issues, no fuente de sí mismo.
        readme = DerivedViewSpec(
            "factory.readme.tandas", "PLAN-AGENTES.md + estado canónico",
            "README.md#estado-de-las-tandas", "regression", None,
            "tests/test_readme_tandas.py",
        )
        readme.validate()
        self.assertNotEqual(readme.source, readme.view)
        exercised.add(VIEWS + "L34-U1")

        # L38, L39, L9: fuente, registro e identidad estable de cada vista.
        registry = json.loads((ROOT / "config/derived_views.json").read_text(
            encoding="utf-8"))
        self.assertEqual(registry["version"], 1)
        specs = [DerivedViewSpec(**item) for item in registry["views"]]
        self.assertTrue(specs)
        for spec in specs:
            spec.validate()
            self.assertNotEqual(spec.source, spec.view)
        self.assertTrue(all(spec.source.strip() for spec in specs))
        exercised.add(VIEWS + "L38-U1")
        self.assertTrue(all(spec.drift_check for spec in specs))
        self.assertEqual(len({spec.view_id for spec in specs}), len(specs))
        exercised.add(VIEWS + "L39-U1")
        ids = tuple(spec.view_id for spec in specs)
        self.assertIn("factory.readme.tandas", ids)
        self.assertEqual(ids, tuple(DerivedViewSpec(**v).view_id
                                   for v in registry["views"]))
        with self.assertRaises(FrozenInstanceError):
            specs[0].view_id = "changed"
        exercised.add(VIEWS + "L9-U1")

        # L40: generación segura, sin reloj, azar ni red; regression sin generator.
        with patch("socket.create_connection",
                   side_effect=AssertionError("network")), \
             patch("time.time", side_effect=AssertionError("clock")), \
             patch("random.random", side_effect=AssertionError("random")):
            repeated = render_markdown_table(
                records, ("id", "state"), sort_by="id")
        self.assertEqual(repeated.encode(), generated.encode())
        exercised.add(VIEWS + "L40-U1")
        regression = DerivedViewSpec(
            "reg", "canonical", "derived", "regression", None,
            "tests/test_derived_views.py",
        )
        regression.validate()
        self.assertIsNone(regression.generator)
        exercised.add(VIEWS + "L40-U2")

        # L41: un drift de un carácter falla cerrado.
        with self.assertRaises(DerivedViewDriftError):
            check_drift(generated, generated.replace("ready", "blocked"))
        exercised.add(VIEWS + "L41-U1")

        # L3: compilar evidencia a partir de tarea y DNA reales, sin ejecutarla.
        compiled = done()
        self.assertEqual(compiled["profile"], "derived")
        self.assertEqual(compiled["task_id"], "synthetic-1802")
        self.assertTrue(compiled["context_complete"])
        self.assertRegex(compiled["fingerprint"], r"^[0-9a-f]{64}$")
        exercised.add(DOD + "L3-U1")

        # L12: perfiles de cambio distintos producen evidencia específica.
        for change, required in {
            "code": ("test", "tests:changed-scope"),
            "database": ("check", "backup:evidence"),
            "ci": ("check", "workflow:validation"),
            "docs": ("check", "docs:lint"),
            "security": ("test", "security:negative-cases"),
        }.items():
            with self.subTest(change=change):
                self.assertIn(required, evidence(done(change_type=change)))
        exercised.add(DOD + "L12-U1")

        # L14: superficies declaradas y orden normalizado, no inferencias.
        by_surface = done(surfaces=["release", "web", "api", "ci"])
        self.assertTrue({
            ("check", "release:exact-sha"), ("test", "web:smoke"),
            ("test", "api:contract"), ("check", "workflow:representative-run"),
        } <= evidence(by_surface))
        self.assertEqual(by_surface["surfaces"], ["api", "ci", "release", "web"])
        exercised.add(DOD + "L14-U1")

        # L16: risk alto no reduce evidencia y unknown exige safe fallback.
        self.assertNotIn(("check", "rollback:plan"), evidence(done(risk="low")))
        self.assertIn(("check", "rollback:plan"), evidence(done(risk="medium")))
        self.assertIn(("check", "smoke:exact-sha"), evidence(done(risk="high")))
        fallback = done(risk="unknown")
        self.assertEqual(fallback["profile"], "safe-fallback")
        self.assertTrue({(r["kind"], r["target"]) for r in SAFE_FALLBACK}
                        <= evidence(fallback))
        exercised.add(DOD + "L16-U1")

        # L18: DNA aporta fingerprint estable independiente del orden de inputs.
        reordered = discover_project_dna(
            paths=list(reversed([
                "package.json", ".github/workflows/ci.yml", "vercel.json",
                "database/schema.sql", ".sentryclirc",
            ])),
            manifests={"package.json": {"dependencies": {
                "@sentry/node": "^9", "fastify": "^5",
            }}},
            capabilities=["web", "api"],
        )
        self.assertEqual(dna()["fingerprint"], reordered["fingerprint"])
        self.assertEqual(compiled["project_dna_fingerprint"], dna()["fingerprint"])
        self.assertEqual(done(source=reordered)["fingerprint"],
                         compiled["fingerprint"])
        exercised.add(DOD + "L18-U1")

        # L24, L25, L26: CI, reviews y claims se conservan incondicionalmente.
        inv = {(row["kind"], row["target"]) for row in FACTORY_INVARIANTS}
        self.assertEqual(compiled["invariants"], list(FACTORY_INVARIANTS))
        self.assertIn(("check", "ci:required"), inv & evidence(compiled))
        exercised.add(DOD + "L24-U1")
        self.assertIn(("check", "reviews:no-open-findings"),
                      inv & evidence(done("security", risk="high")))
        exercised.add(DOD + "L25-U1")
        self.assertIn(("check", "scope:claimed-paths-only"),
                      inv & evidence(done("docs", risk="medium")))
        exercised.add(DOD + "L26-U1")
        self.assertEqual(exercised, OFFLINE)

    def test_falla_cerrado(self):
        """AC-02: datos, contexto y autoridad ambiguos se rechazan."""
        spec = DerivedViewSpec("id", "canonical", "view", "generated",
                               "module:generator", "tests/test_drift.py")
        for corrupt in (
            {"source": "view"}, {"view_id": ""}, {"mode": "unsupported"},
            {"generator": None}, {"drift_check": ""},
        ):
            with self.subTest(spec=corrupt):
                with self.assertRaises(DerivedViewError):
                    DerivedViewSpec(**{**vars(spec), **corrupt}).validate()
        with self.assertRaises(DerivedViewError):
            DerivedViewSpec("reg", "a", "b", "regression",
                            "generator", "guard").validate()
        for columns, order in (((), "id"), (("name",), "id")):
            with self.subTest(columns=columns):
                with self.assertRaises(DerivedViewError):
                    render_markdown_table([{"id": "one"}], columns, sort_by=order)
        with self.assertRaises(DerivedViewDriftError):
            check_drift("canonical\n", "tampered\n")
        for changed in (
            {"change_type": "garbage"}, {"risk": "garbage"},
            {"surfaces": "api"}, {"surfaces": ["api", ""]},
        ):
            with self.subTest(task=changed):
                with self.assertRaises(DodCompilerError):
                    done(**changed)
        incomplete = done(
            change_type="unknown", surfaces=[], risk="unknown",
            source=discover_project_dna(paths=[]),
        )
        self.assertEqual(incomplete["profile"], "safe-fallback")
        self.assertFalse(incomplete["context_complete"])
        self.assertIn(("check", "context:complete-before-promotion"),
                      evidence(incomplete))
        self.assertIn(("check", "ci:required"), evidence(incomplete))

    def test_sin_datos_reales(self):
        """AC-03: funciones puras con datos sintéticos, sin efectos externos."""
        def forbidden(*_args, **_kwargs):
            raise AssertionError("I/O externo prohibido")

        with patch.object(socket, "create_connection", forbidden), \
             patch.object(request, "urlopen", forbidden), \
             patch.object(subprocess, "run", forbidden):
            self.assertEqual(done()["profile"], "derived")
            high = done("security", ["api"], "high")
            self.assertTrue(high["context_complete"])
            self.assertIn(("check", "security:scan"), evidence(high))
            self.assertEqual(len(OFFLINE | POLICY.keys() | WORLD.keys()), 20)
            self.assertEqual(render_markdown_table(
                [{"id": "fixture", "status": "synthetic"}],
                ("id", "status"), sort_by="id",
            ), "| id | status |\n| --- | --- |\n| fixture | synthetic |\n")


if __name__ == "__main__":
    unittest.main()
