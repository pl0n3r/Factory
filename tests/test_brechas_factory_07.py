#!/usr/bin/env python3
"""Factory #1625: 16 brechas de autonomía, autoridad y contexto.

Pruebas locales sintéticas de contratos existentes. No acreditan decisiones
humanas, permisos externos, promoción live ni estado operativo: UNKNOWN.
"""
from __future__ import annotations

import ast
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
DOC_PHRASES = {
    "docs/autonomy-engine.md": {
        31: "\x60major\x60: baja dos niveles;",
        32: "\x60critical\x60: revoca hasta \x60observe\x60.",
        34: "la historia previa no se modifica.",
    },
    "docs/capability-authority.md": {
        16: "disparar menos autonomía o revocación, nunca más permisos.",
        18: "Cuando una acción recibe varios grants, \x60scopes\x60 y \x60targets\x60 agregados",
        21: "el resumen como un producto cartesiano. \x60authorize()\x60 evalúa siempre",
        22: "exacto y falla cerrado ante combinaciones no concedidas.",
        26: "Los grants y revocaciones se aceptan únicamente desde",
        39: "\x60CapabilityAuthorityRegistry.autonomy_scope()\x60 acepta únicamente los niveles",
        42: "nunca agregan permisos.",
    },
    "docs/context-compiler.md": {
        11: "\x60project_dna\x60 validado;",
        12: "una \x60task\x60 cerrada con id, título, objetivo y tags;",
        13: "\x60context\x60 relevante con categoría, fuente, texto y tags;",
        14: "límites explícitos;",
        15: "fingerprint SHA-256 determinista.",
        32: "máximo 12 piezas de contexto;",
    },
}
CLAUSES = {
    f"{doc}:L{number}-U1": (doc, number, phrase)
    for doc, lines in DOC_PHRASES.items()
    for number, phrase in lines.items()
}
IDS = tuple(CLAUSES)
WITNESSES = {
    "downgrade": ("tests/test_autonomy_engine.py", "AutonomyEngineTests",
                  "test_failures_reduce_or_revoke_autonomy"),
    "bindings": ("tests/test_capability_authority.py", "CapabilityAuthorityTests",
                 "test_matrix_preserves_exact_bindings_without_cartesian_authority"),
    "conditions": ("tests/test_capability_authority.py", "CapabilityAuthorityTests",
                   "test_capability_matrix_declares_actions_and_scope"),
    "provenance": ("tests/test_capability_authority.py", "CapabilityAuthorityTests",
                   "test_grants_and_revocations_require_trusted_provenance"),
    "levels": ("tests/test_capability_authority.py", "CapabilityAuthorityTests",
               "test_autonomy_changes_only_within_existing_scope"),
    "no_expansion": ("tests/test_capability_authority.py", "CapabilityAuthorityTests",
                     "test_performance_cannot_create_new_authority"),
    "context_schema": ("tests/test_context_compiler.py", "ContextCompilerTests",
                       "test_mission_package_contains_only_relevant_context"),
    "context_source": ("tests/test_context_compiler.py", "ContextCompilerTests",
                       "test_sources_are_traceable"),
    "context_bounds": ("tests/test_context_compiler.py", "ContextCompilerTests",
                       "test_package_is_bounded_and_deterministic"),
}
WITNESS_FOR = {
    "docs/autonomy-engine.md": {31: "downgrade", 32: "downgrade", 34: "downgrade"},
    "docs/capability-authority.md": {
        16: "conditions", 18: "bindings", 21: "bindings", 22: "bindings",
        26: "provenance", 39: "levels", 42: "no_expansion",
    },
    "docs/context-compiler.md": {
        11: "context_schema", 12: "context_schema", 13: "context_source",
        14: "context_bounds", 15: "context_bounds", 32: "context_bounds",
    },
}


def read_sources() -> dict[str, str]:
    return {
        path: (ROOT / path).read_text(encoding="utf-8")
        for path in (MATRIX, *DOC_PHRASES)
    }


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Rechaza filas ausentes, duplicadas, ambiguas y promoción artificial."""
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matriz ausente")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| \x60"):
            continue
        fields = tuple(part.strip() for part in line.strip("|").split("|"))
        key = fields[0].strip("\x60")
        if key not in CLAUSES:
            continue
        phrase = CLAUSES[key][2]
        if (key in found or len(fields) != 5
                or fields[0] != "\x60" + key + "\x60"
                or not fields[1].startswith(phrase)
                or fields[2] != "NO_VERIFICABLE"
                or "[Contraste #1569]" not in fields[3]
                or not fields[3].endswith(".")
                or fields[4] != "—"):
            raise ValueError(UNKNOWN + ": fila inválida " + key)
        found[key] = fields
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": filas incompletas")
    return found


def source_matches(key: object, sources: object) -> bool:
    """La cláusula debe seguir anclada a la línea exacta del documento."""
    if (type(key) is not str or key not in CLAUSES
            or type(sources) is not dict
            or set(sources) != {MATRIX, *DOC_PHRASES}):
        return False
    path, number, phrase = CLAUSES[key]
    source = sources.get(path)
    if type(source) is not str:
        return False
    lines = source.splitlines()
    return number <= len(lines) and phrase in lines[number - 1]


def local_evidence() -> dict[str, bool]:
    """Ejecuta testigos existentes sin red real, manteniendo el import aislado."""
    originals = sys.path[:]
    passed = {}
    try:
        for directory in (ROOT, ROOT / "tests"):
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
        for label, (path, class_name, test_name) in WITNESSES.items():
            namespace = runpy.run_path(str(ROOT / path))
            case = namespace[class_name](test_name)
            result = unittest.TestResult()
            case.run(result)
            if result.testsRun != 1 or not result.wasSuccessful():
                raise AssertionError(UNKNOWN + ": testigo fallido " + label)
            passed[label] = True
        # Historia append-only en un downgrade sintético: sin promoción live.
        namespace = runpy.run_path(str(ROOT / "tests/test_autonomy_engine.py"))
        engine = namespace["AutonomyEngine"](
            "synthetic-observer", reason="fixture", evidence=["synthetic:initial"]
        )
        initial = engine.history[0]
        outcome = engine.record_failure(
            "critical", reason="synthetic:critical", evidence=["synthetic:event"]
        )
        if not (outcome.level == "observe" and len(engine.history) == 2
                and engine.history[0] is initial and initial.sequence == 0):
            raise AssertionError(UNKNOWN + ": downgrade no append-only")
    finally:
        sys.path[:] = originals
    return {
        key: passed[WITNESS_FOR[doc][line]]
        for key, (doc, line, _) in CLAUSES.items()
    }


def assess(sources: object, evidence: object) -> dict[str, str]:
    unknown = dict.fromkeys(IDS, UNKNOWN)
    if (type(sources) is not dict or set(sources) != {MATRIX, *DOC_PHRASES}
            or type(evidence) is not dict or set(evidence) != set(IDS)
            or any(type(v) is not bool for v in evidence.values())):
        return unknown
    try:
        matrix_rows(sources[MATRIX])
    except (ValueError, KeyError):
        return unknown
    return {
        key: LOCAL if source_matches(key, sources) and evidence[key] else UNKNOWN
        for key in IDS
    }


def operational_attestation(_key: object, _claim: object = None) -> str:
    """Los testigos sintéticos nunca acreditan autoridad, release o live."""
    return UNKNOWN


class BrechasFactory07Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        sources = read_sources()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(matrix_rows(sources[MATRIX])), set(IDS))
        checked = local_evidence()
        self.assertEqual(set(checked), set(IDS))
        for key, status in assess(sources, checked).items():
            with self.subTest(clause=key):
                self.assertEqual(status, LOCAL)
                self.assertEqual(operational_attestation(key), UNKNOWN)

    def test_falla_cerrado(self) -> None:
        sources = read_sources()
        good = dict.fromkeys(IDS, True)
        for key in IDS:
            row = next(line for line in sources[MATRIX].splitlines()
                       if line.startswith("| \x60" + key + "\x60 |"))
            for corrupt in (
                sources[MATRIX].replace(row, "", 1),
                sources[MATRIX] + "\n" + row,
                sources[MATRIX].replace(
                    row, row.replace("NO_VERIFICABLE", "VERIFICADO"), 1
                ),
            ):
                with self.subTest(clause=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        matrix_rows(corrupt)
                    self.assertEqual(
                        assess({**sources, MATRIX: corrupt}, good)[key], UNKNOWN
                    )
            self.assertEqual(assess(sources, {**good, key: False})[key], UNKNOWN)
            self.assertEqual(assess(sources, {**good, key: "passed"})[key], UNKNOWN)
            doc, line, _ = CLAUSES[key]
            altered = sources[doc].splitlines(keepends=True)
            altered[line - 1] = "UNKNOWN: cláusula ausente\n"
            self.assertEqual(
                assess({**sources, doc: "".join(altered)}, good)[key], UNKNOWN
            )
        for missing in (None, {}, {MATRIX: sources[MATRIX]}, "success"):
            self.assertEqual(set(assess(missing, good).values()), {UNKNOWN})
        self.assertEqual(set(assess(sources, {}).values()), {UNKNOWN})

    def test_sin_datos_reales(self) -> None:
        """Ningún request ni comando shell; testigos usan fixtures y stubs."""
        content = (ROOT / "tests/test_brechas_factory_07.py").read_text(
            encoding="utf-8"
        )
        imported = set()
        for node in ast.walk(ast.parse(content)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(
            imported, {"__future__", "ast", "pathlib", "runpy", "sys", "unittest"}
        )
        self.assertEqual(set(WITNESS_FOR), set(DOC_PHRASES))
        self.assertTrue(all(
            (ROOT / path).is_file() for path, _, _ in WITNESSES.values()
        ))

    def test_estados_unknown_explicitos(self) -> None:
        sources = read_sources()
        for key in IDS:
            with self.subTest(clause=key):
                for claim in (
                    None, True, "success", {"ci": "success"},
                    {"permission": "granted"}, {"approved": True},
                    {"state": "VALIDATED_IN_PRODUCTION"},
                ):
                    self.assertEqual(operational_attestation(key, claim), UNKNOWN)
                self.assertEqual(assess(sources, {})[key], UNKNOWN)
        self.assertEqual(operational_attestation("unlisted", {}), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
