"""16 brechas de vistas derivadas, Dieta Factory y DoD Compiler (#1632).

Un test sintético verifica el contrato local, pero nunca acredita por sí solo
snapshots históricos, preflight en consumidores ni rollback integrado.
La matriz canónica sigue NO_VERIFICABLE hasta reconciliación posterior.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from intelligence.derived_views import (
    DerivedViewDriftError, DerivedViewError, DerivedViewSpec,
    check_drift, render_markdown_table,
)
from intelligence.dod_compiler import (
    CHANGE_PROFILES, FACTORY_INVARIANTS, SAFE_FALLBACK, DodCompilerError,
    compile_done_contract,
)
from intelligence.project_dna import (
    ProjectDnaError, discover_project_dna, validate_project_dna,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
LOCAL = "CONTRATO_SINTETICO"
DERIVED = "docs/derived-views.md:L9-U1"
DIET = tuple("docs/dieta-factory.md:" + name for name in ("B01", "B04", "B05"))
DOD = tuple("docs/dod-compiler.md:" + name for name in (
    "L12-U1", "L14-U1", "L16-U1", "L18-U1", "L24-U1", "L25-U1",
    "L26-U1", "L3-U1", "L34-U1", "L35-U1", "L36-U1", "L37-U1",
))
IDS = (DERIVED,) + DIET + DOD


def synthetic_dna(*, incomplete=False):
    if incomplete:
        return discover_project_dna(paths=["README.md"])
    return discover_project_dna(
        paths=["package.json", ".github/workflows/ci.yml", "vercel.json",
               "database/schema.sql", ".sentryclirc"],
        manifests={"package.json": {"dependencies": {
            "fastify": "^5", "@sentry/node": "^9",
        }}},
        capabilities=["api", "web"],
    )


def task(kind="code", risk="low", surfaces=("api",)):
    return {"id": "synthetic/factory#1632", "title": "Synthetic task",
            "change_type": kind, "risk": risk, "surfaces": list(surfaces)}


def compile_task(kind="code", risk="low", surfaces=("api",), *, dna=None):
    return compile_done_contract(
        project_dna=synthetic_dna() if dna is None else dna,
        task=task(kind, risk, surfaces),
    )


def evidence(contract):
    return {(row["kind"], row["target"]) for row in contract["evidence"]}


def matrix_rows(raw):
    """NO_VERIFICABLE es indispensable: nunca inferir promoción desde este test."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matriz ilegible")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("|"):
            continue
        cells = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if not cells:
            continue
        name = cells[0].strip(chr(96))
        if name not in IDS:
            continue
        if name in found or len(cells) != 5 or not all(cells[:4]):
            raise ValueError("UNKNOWN: fila incompleta o duplicada: " + name)
        if cells[2] != "NO_VERIFICABLE":
            raise ValueError("UNKNOWN: promoción sin PR fusionado: " + name)
        found[name] = cells
    if set(found) != set(IDS):
        raise ValueError("UNKNOWN: faltan IDs en matriz")
    return found


def derived_stable_id():
    manifest = json.loads((ROOT / "config/derived_views.json").read_text(
        encoding="utf-8"))
    if type(manifest) is not dict or manifest.get("version") != 1:
        return False
    items = manifest.get("views")
    if not isinstance(items, list) or not items:
        return False
    specs = []
    for item in items:
        try:
            spec = DerivedViewSpec(**item)
            spec.validate()
        except (TypeError, DerivedViewError):
            return False
        specs.append(spec)
    names = [spec.view_id for spec in specs]
    if len(names) != len(set(names)) or "factory.readme.tandas" not in names:
        return False
    rows = [{"id": name, "mode": spec.mode}
            for name, spec in zip(names, specs)]
    original = render_markdown_table(rows, ("id", "mode"), sort_by="id")
    reversed_rows = render_markdown_table(
        list(reversed(rows)), ("id", "mode"), sort_by="id")
    if original != reversed_rows:
        return False
    try:
        check_drift(original, original + "alterado")
    except DerivedViewDriftError:
        return True
    return False


def diet_status(row_id, *, supplied=None):
    """Tres pruebas de despliegue histórico NO existen en fixtures locales.

    B01: los snapshots de todas las fases no están acreditados.
    B04: no hay preflight autenticado exact-main de *todos* los consumidores.
    B05: no hay simulacro de reversión acumulada sobre todos los gates.
    Un dict sintético no suple esos hechos, aunque incluya valores True.
    """
    if row_id not in DIET:
        return UNKNOWN
    return UNKNOWN


def proof():
    project = synthetic_dna()
    source_fingerprint = project["fingerprint"]
    standard = {
        kind: compile_task(kind) for kind in ("code", "database", "ci", "docs")
    }
    fallback = compile_task(
        "unknown", "unknown", (), dna=synthetic_dna(incomplete=True))
    low = compile_task("code", "low")
    medium = compile_task("code", "medium")
    high = compile_task("code", "high")
    unknown_risk = compile_task("code", "unknown")
    many = compile_task("code", "low", ("release", "api", "api"))
    source_valid = validate_project_dna(project)
    keys = set(CHANGE_PROFILES)
    invariants = set((v["kind"], v["target"]) for v in FACTORY_INVARIANTS)
    all_contracts = tuple(standard.values()) + (low, medium, high, fallback)
    results = {
        DERIVED: derived_stable_id(),
        DOD[0]: keys == {"code", "database", "ci", "docs", "security"}
                and fallback["profile"] == "safe-fallback",
        DOD[1]: many["surfaces"] == ["api", "release"]
                and ("check", "release:exact-sha") in evidence(many)
                and compile_task("docs", "low", ())["profile"] == "safe-fallback",
        DOD[2]: all(c["risk"] == r for c, r in
                    ((low, "low"), (medium, "medium"), (high, "high")))
                and evidence(low) < evidence(medium) < evidence(high)
                and unknown_risk["profile"] == "safe-fallback",
        DOD[3]: low["project_dna_fingerprint"] == source_fingerprint
                and source_valid["fingerprint"] == source_fingerprint,
        DOD[4]: ("check", "ci:required") in invariants
                and all(invariants <= evidence(c) for c in all_contracts),
        DOD[5]: ("check", "reviews:no-open-findings") in invariants
                and all(invariants <= evidence(c) for c in all_contracts),
        DOD[6]: ("check", "scope:claimed-paths-only") in invariants
                and all(invariants <= evidence(c) for c in all_contracts),
        DOD[7]: low["profile"] == "derived"
                and standard["code"]["evidence"] != standard["database"]["evidence"]
                and len(low["fingerprint"]) == 64,
        DOD[8]: {("test", "tests:changed-scope"),
                 ("check", "static:analysis")} <= evidence(standard["code"]),
        DOD[9]: {("check", "migration:verify-plan"),
                 ("check", "backup:evidence"),
                 ("test", "schema:compatibility")} <= evidence(standard["database"]),
        DOD[10]: {("check", "workflow:validation"),
                  ("check", "workflow:representative-run")} <= evidence(standard["ci"]),
        DOD[11]: {("check", "docs:lint"),
                  ("check", "docs:links")} <= evidence(standard["docs"]),
    }
    for row_id in DIET:
        results[row_id] = diet_status(row_id)
    return {key: (LOCAL if result is True else UNKNOWN) for key, result in results.items()}


class BrechasFactory14Tests(unittest.TestCase):
    def test_contrato_principal(self):
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        outcomes = proof()
        self.assertEqual(set(outcomes), set(IDS))
        for row_id in IDS:
            with self.subTest(row=row_id):
                expected = UNKNOWN if row_id in DIET else LOCAL
                self.assertEqual(outcomes[row_id], expected)

    def test_falla_cerrado(self):
        for invalid in (
            DerivedViewSpec("", "src", "view", "regression", None, "guard"),
            DerivedViewSpec("id", "view", "view", "regression", None, "guard"),
            DerivedViewSpec("id", "src", "view", "generated", None, "guard"),
        ):
            with self.subTest(view=invalid.view_id):
                with self.assertRaises(DerivedViewError):
                    invalid.validate()
        for bad in (
            {**task(), "risk": "critical"},
            {**task(), "change_type": "run-command"},
            {**task(), "extra": "injected"},
            {**task(), "surfaces": ["api", ""]},
        ):
            with self.subTest(task=bad):
                with self.assertRaises(DodCompilerError):
                    compile_done_contract(project_dna=synthetic_dna(), task=bad)
        bad_dna = deepcopy(synthetic_dna())
        bad_dna["fingerprint"] = "0" * 64
        with self.assertRaises(ProjectDnaError):
            validate_project_dna(bad_dna)
        self.assertEqual(diet_status("sin-evidencia", supplied={"trusted": True}), UNKNOWN)
        with self.assertRaises(ValueError):
            matrix_rows(None)
        # Mutación causal: quitar una invariante debe romper una fila.
        import intelligence.dod_compiler as engine
        with patch.object(engine, "FACTORY_INVARIANTS",
                          tuple(v for v in FACTORY_INVARIANTS
                                if v["target"] != "ci:required")):
            changed = compile_task("code")
            self.assertNotIn(("check", "ci:required"), evidence(changed))
        self.assertIn(("check", "ci:required"), evidence(compile_task("code")))

    def test_sin_datos_reales(self):
        with patch("socket.socket", side_effect=AssertionError("sin red")):
            results = proof()
            text = render_markdown_table(
                [{"id": "fake-a", "state": "unknown"}],
                ("id", "state"), sort_by="id")
        self.assertEqual(set(results), set(IDS))
        self.assertIn("fake-a", text)
        self.assertTrue(all(k.startswith("docs/") for k in IDS))
        self.assertEqual(len(DIET), 3)

    def test_estados_unknown_explicitos(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        found = matrix_rows(matrix)
        self.assertEqual(set(found), set(IDS))
        outcomes = proof()
        for row_id in DIET:
            with self.subTest(row=row_id):
                self.assertEqual(outcomes[row_id], UNKNOWN)
                self.assertIn("Contrastado:", found[row_id][3])
                self.assertEqual(found[row_id][2], "NO_VERIFICABLE")
        for row_id in DOD + (DERIVED,):
            with self.subTest(row=row_id):
                self.assertEqual(found[row_id][2], "NO_VERIFICABLE")
                self.assertIn("No se confirmó test + PR fusionado", found[row_id][3])
        # La mutación debe afectar específicamente una fila reclamada.
        line = next(s for s in matrix.splitlines()
                    if s.startswith("| " + chr(96) + DERIVED + chr(96) + " |"))
        corrupt = matrix.replace(line, line.replace("NO_VERIFICABLE", "VERIFICADO"))
        with self.assertRaises(ValueError):
            matrix_rows(corrupt)


if __name__ == "__main__":
    unittest.main()
