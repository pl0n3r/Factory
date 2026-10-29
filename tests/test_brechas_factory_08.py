#!/usr/bin/env python3
"""Factory #1626: pruebas de 16 brechas de Context Compiler y conversación.

El compilador se comprueba con datos sintéticos; una regla de conversación
no es evidencia de comportamiento universal de la plataforma: UNKNOWN.
Solo pruebas locales, sin credenciales, conexiones o decisiones externas.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from intelligence.context_compiler import (
    ContextCompilerError, MAX_CONTEXT_ITEMS, MAX_ITEM_CHARS, MAX_PACKAGE_CHARS,
    compile_mission_context,
)
from intelligence.project_dna import discover_project_dna

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
CLAUSES = {
    "docs/context-compiler.md:L33-U1": [
        "docs/context-compiler.md",
        33,
        "máximo 1200 caracteres por texto;"
    ],
    "docs/context-compiler.md:L34-U1": [
        "docs/context-compiler.md",
        34,
        "máximo 12000 caracteres para el paquete serializado;"
    ],
    "docs/context-compiler.md:L35-U1": [
        "docs/context-compiler.md",
        35,
        "sin I/O, sin mutación del proyecto y sin decisión de riesgo."
    ],
    "docs/context-compiler.md:L4-U1": [
        "docs/context-compiler.md",
        4,
        "Project DNA ya validado, la tarea actual y decisiones/lecciones previa"
    ],
    "docs/conversacion-agentes.md:L11-U1": [
        "docs/conversacion-agentes.md",
        11,
        "`Encontré que el fallo viene del wiring de test, no del transporte pro"
    ],
    "docs/conversacion-agentes.md:L11-U2": [
        "docs/conversacion-agentes.md",
        11,
        "Ahora valido el contenedor en APP_ENV=test.`"
    ],
    "docs/conversacion-agentes.md:L12-U1": [
        "docs/conversacion-agentes.md",
        12,
        "`Backend y Validar ya están verdes"
    ],
    "docs/conversacion-agentes.md:L12-U2": [
        "docs/conversacion-agentes.md",
        12,
        "solo falta Playwright."
    ],
    "docs/conversacion-agentes.md:L12-U3": [
        "docs/conversacion-agentes.md",
        12,
        "Mientras corre, reviso el flujo nuevo para detectar fallos lógicos.`"
    ],
    "docs/conversacion-agentes.md:L13-U1": [
        "docs/conversacion-agentes.md",
        13,
        "`El enfoque A falló por X."
    ],
    "docs/conversacion-agentes.md:L13-U2": [
        "docs/conversacion-agentes.md",
        13,
        "Cambio al enfoque B porque evita Y.`"
    ],
    "docs/conversacion-agentes.md:L15-U1": [
        "docs/conversacion-agentes.md",
        15,
        "Prohibidas: `Sigo revisando.`, `Déjame pensar.`, `Estoy trabajando en "
    ],
    "docs/conversacion-agentes.md:L39-U1": [
        "docs/conversacion-agentes.md",
        39,
        "Debe conservar: objetivo, repo/Issue/PR, branch y SHA, decisiones toma"
    ],
    "docs/conversacion-agentes.md:L43-U1": [
        "docs/conversacion-agentes.md",
        43,
        "No reexplicar lo ya presente en Issue/PR/`lecciones/`."
    ],
    "docs/conversacion-agentes.md:L44-U1": [
        "docs/conversacion-agentes.md",
        44,
        "Buscar primero"
    ],
    "docs/conversacion-agentes.md:L44-U2": [
        "docs/conversacion-agentes.md",
        44,
        "abrir solo fragmentos relevantes."
    ]
}
IDS = tuple(CLAUSES)
LOCAL_IDS = frozenset(key for key in IDS if key.startswith("docs/context-compiler.md:"))
CONVERSATION_IDS = frozenset(IDS) - LOCAL_IDS


def sources() -> dict[str, str]:
    """Archivos originales locales; nunca inferir evidencia desde el issue."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in (MATRIX, "docs/context-compiler.md",
                         "docs/conversacion-agentes.md")}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Descubre IDs antes de validar forma; falla cerrado también con duplicados."""
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matriz ausente")
    found: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        clean = line.lstrip()
        if not clean.startswith("|"):
            continue
        fields = tuple(part.strip() for part in clean.strip().strip("|").split("|"))
        if not fields or not (fields[0].startswith("`") and fields[0].endswith("`")):
            continue
        key = fields[0][1:-1]
        if key not in CLAUSES:
            continue
        if (key in found or not clean.startswith("| `" + key + "` |")
                or len(fields) != 5 or fields[0] != "`" + key + "`"
                or not fields[1].startswith(CLAUSES[key][2])
                or fields[2] != "NO_VERIFICABLE"
                or "[Contraste #1569]" not in fields[3]
                or fields[4] != "—"):
            raise ValueError(UNKNOWN + ": fila inválida " + key)
        found[key] = fields
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": faltan identificadores")
    return found


def source_matches(key: str, docs: dict[str, str], row: tuple[str, ...]) -> bool:
    """Proteger el anclaje preciso, incluyendo la descripción de matriz."""
    if key not in CLAUSES:
        return False
    path, line, fragment = CLAUSES[key]
    raw = docs.get(path)
    if type(raw) is not str:
        return False
    lines = raw.splitlines()
    return (1 <= line <= len(lines) and fragment in lines[line - 1]
            and row[1] in lines[line - 1])


def _dna() -> dict:
    return discover_project_dna(
        paths=["package.json"],
        manifests={"package.json": {"dependencies": {"fastify": "^5"}}},
        capabilities=["api"],
    )


def _task() -> dict:
    return {"id": "factory#synthetic", "title": "Fixture",
            "goal": "Comprobar contrato de contexto", "tags": ["context"]}


def _item(text: str, source: str = "fixture#1") -> dict:
    return {"category": "evidence", "source": source,
            "text": text, "tags": ["context"]}


def local_evidence() -> dict[str, bool]:
    """Pruebas positivas/negativas reales del compilador, sin I/O externo."""
    dna, task = _dna(), _task()
    package = compile_mission_context(
        project_dna=dna, task=task, context_items=[_item("X" * 1300)])
    length_ok = (
        len(package["context"]) == 1
        and len(package["context"][0]["text"]) == MAX_ITEM_CHARS == 1200
        and package["limits"]["max_item_chars"] == 1200
    )
    many = [_item("X" * 1180, f"fixture#{n}") for n in range(12)]
    try:
        compile_mission_context(project_dna=dna, task=task, context_items=many)
    except ContextCompilerError as exc:
        package_bound = "excede el límite" in str(exc)
    else:
        package_bound = False
    # Un package compacto permite 12 items y descarta el 13 de forma
    # determinista sin usar reloj, HTTP, filesystem ni mutar el proyecto.
    sample = [_item("context fixture", f"fixture#{n:03d}") for n in range(13)]
    with patch("builtins.open", side_effect=AssertionError("unexpected I/O")), (
            patch.object(Path, "write_text", side_effect=AssertionError("mutation"))):
        first = compile_mission_context(
            project_dna=dna, task=task, context_items=sample)
        second = compile_mission_context(
            project_dna=dna, task=task, context_items=list(reversed(sample)))
    no_io = (first == second and len(first["context"]) == MAX_CONTEXT_ITEMS
             and package["limits"]["max_package_chars"] == MAX_PACKAGE_CHARS
             and len(json.dumps(first, ensure_ascii=False)) <= MAX_PACKAGE_CHARS)
    invalid_dna = dict(dna)
    invalid_dna["fingerprint"] = "0" * 64
    try:
        compile_mission_context(
            project_dna=invalid_dna, task=task, context_items=[])
    except ValueError:
        validated_dna = True
    else:
        validated_dna = False
    return {
        "docs/context-compiler.md:L33-U1": length_ok,
        "docs/context-compiler.md:L34-U1": package_bound,
        "docs/context-compiler.md:L35-U1": no_io,
        "docs/context-compiler.md:L4-U1": validated_dna,
    }


def assess(docs: object, proof: object) -> dict[str, str]:
    """UNKNOWN sin prueba o con matriz/fuentes alteradas; prompt nunca equivale a SLA."""
    unknown = dict.fromkeys(IDS, UNKNOWN)
    if (type(docs) is not dict or set(docs) != {MATRIX,
            "docs/context-compiler.md", "docs/conversacion-agentes.md"}
            or type(proof) is not dict or set(proof) != LOCAL_IDS
            or any(type(v) is not bool for v in proof.values())):
        return unknown
    try:
        rows = matrix_rows(docs[MATRIX])
    except (ValueError, KeyError):
        return unknown
    return {key: (LOCAL if key in LOCAL_IDS and proof[key]
                   and source_matches(key, docs, rows[key]) else UNKNOWN)
            for key in IDS}


def operational_attestation(_key: object, _claim: object = None) -> str:
    """Sin observación de plataforma ni decisiones externas, siempre UNKNOWN."""
    return UNKNOWN


class BrechasFactory08Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs = sources()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(LOCAL_IDS), 4)
        self.assertEqual(len(CONVERSATION_IDS), 12)
        self.assertEqual(set(matrix_rows(docs[MATRIX])), set(IDS))
        proof = local_evidence()
        self.assertEqual(set(proof), LOCAL_IDS)
        self.assertTrue(all(proof.values()))
        actual = assess(docs, proof)
        for key in IDS:
            with self.subTest(key=key):
                self.assertTrue(source_matches(key, docs, matrix_rows(docs[MATRIX])[key]))
                self.assertEqual(actual[key], LOCAL if key in LOCAL_IDS else UNKNOWN)
                self.assertEqual(operational_attestation(key), UNKNOWN)

    def test_falla_cerrado(self) -> None:
        docs = sources()
        proof = dict.fromkeys(LOCAL_IDS, True)
        for key in IDS:
            original = next(line for line in docs[MATRIX].splitlines()
                            if line.startswith("| `" + key + "` |"))
            invalids = (
                docs[MATRIX].replace(original, "", 1),
                docs[MATRIX] + "\n" + original,
                docs[MATRIX] + "\n" + original.replace("| `", "|  `", 1),
                docs[MATRIX].replace(original, original.replace(
                    "NO_VERIFICABLE", "CUBIERTO"), 1),
                docs[MATRIX].replace(original, original.replace(
                    CLAUSES[key][2], "UNKNOWN: fragmento alterado", 1), 1),
            )
            for corrupt in invalids:
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(corrupt)
                self.assertEqual(set(assess({**docs, MATRIX: corrupt}, proof).values()),
                                 {UNKNOWN})
            path, line, _ = CLAUSES[key]
            changed = docs[path].splitlines(keepends=True)
            changed[line - 1] = "UNKNOWN: source mismatch\n"
            self.assertEqual(assess({**docs, path: "".join(changed)}, proof)[key],
                             UNKNOWN)

    def test_sin_datos_reales(self) -> None:
        """Fixtures sintéticos, sin bibliotecas de red, subprocess o secretos."""
        source = (ROOT / "tests/test_brechas_factory_08.py").read_text(
            encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported, {"__future__", "ast", "json", "pathlib",
                                    "unittest", "intelligence"})
        self.assertEqual(set(local_evidence()), LOCAL_IDS)
        self.assertNotIn("requests", imported)
        self.assertNotIn("subprocess", imported)

    def test_estados_unknown_explicitos(self) -> None:
        docs = sources()
        true_proof = dict.fromkeys(LOCAL_IDS, True)
        self.assertEqual({UNKNOWN}, set(assess({}, true_proof).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))
        for value in (False, "success", None, {"ci": "success"}):
            self.assertEqual({UNKNOWN}, set(assess(
                docs, {**true_proof, next(iter(LOCAL_IDS)): value}).values())
                             if type(value) is not bool else
                             {assess(docs, {**true_proof,
                                next(iter(LOCAL_IDS)): value})[
                                    next(iter(LOCAL_IDS))]})
        for key in CONVERSATION_IDS:
            self.assertEqual(assess(docs, true_proof)[key], UNKNOWN)
            for external in ("CI green", {"approved": True},
                             {"state": "VALIDATED_IN_PRODUCTION"}):
                self.assertEqual(operational_attestation(key, external), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
