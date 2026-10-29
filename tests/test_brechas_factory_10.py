#!/usr/bin/env python3
"""Factory #1628: 16 cláusulas de validación post-merge con evidencia sintética.

Las pruebas locales no son recibos de merge, CI, reserva ni HEALTH: UNKNOWN.
"""
from __future__ import annotations

import ast
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
DOC = "docs/coordinacion-pr-validation.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
LINES = (17, 18, 19, 21, 22, 24, 27, 29, 33, 34, 35, 36, 40, 47, 48, 49)
PHRASES = {
    17: "debe reconciliar la reserva y el estado.",
    18: "El caller usa \x60validar-pr-evento\x60 como precondición: ese job solo completa",
    19: "cuando \x60github.event.pull_request.merged != true\x60. \x60validar-pr\x60 conserva",
    21: "llega a invocar \x60operation: validate\x60.",
    22: "El reusable aplica la misma defensa: una llamada \x60validate\x60 originada por un",
    24: "Un cierre **sin merge** tiene \x60merged == false\x60 y no recibe esta excepción.",
    27: "Mantener la forma legacy de \x60validar-pr\x60",
    29: "\x60closed\x60 por sí solo nunca se convierte en autoridad para saltarse validaciones.",
    33: "La neutralidad post-merge no cambia \x60validate_pull()\x60.",
    34: "siga abierto, el coordinador conserva el comportamiento fail-closed existente:",
    35: "el Issue debe estar abierto, la branch debe ser \x60trabajo/issue-N\x60, la reserva y",
    36: "su identidad deben ser válidas, la relación de cierre debe corresponder y no",
    40: "\x60Issue #N debe estar abierto durante el PR\x60.",
    47: "\x60tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral\x60;",
    48: "\x60tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate\x60;",
    49: "\x60tests/test_coordinar_trabajo.py::CoordinacionTests::test_open_pr_with_closed_issue_still_fails_closed\x60.",
}
IDS = tuple(f"{DOC}:L{n}-U1" for n in LINES)
WITNESSES = {
    "reusable": (
        "tests/test_coordinacion_reusable_contract.py",
        "T", "test_merged_pr_validation_is_neutral",
    ),
    "consumer": (
        "tests/test_consumer_coordination_template.py",
        "ConsumerCoordinationTemplateTests", "test_merged_pr_does_not_revalidate",
    ),
    "coordinar": (
        "tests/test_coordinar_trabajo.py",
        "CoordinacionTests", "test_open_pr_with_closed_issue_still_fails_closed",
    ),
}
WITNESS_FOR = {
    17: "consumer", 18: "consumer", 19: "consumer", 21: "consumer",
    22: "reusable", 24: "consumer", 27: "consumer", 29: "consumer",
    33: "coordinar", 34: "coordinar", 35: "coordinar", 36: "coordinar",
    40: "coordinar", 47: "reusable", 48: "consumer", 49: "coordinar",
}


def read_sources() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in (MATRIX, DOC)}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Rechazar filas ausentes, duplicadas, ambiguas o promovidas sin evidencia."""
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matriz ausente")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| \x60"):
            continue
        cells = tuple(v.strip() for v in line.strip("|").split("|"))
        key = cells[0].strip("\x60")
        if key not in IDS:
            continue
        number = int(key.rsplit(":L", 1)[1].split("-", 1)[0])
        if (key in found or len(cells) != 5
                or cells[0] != f"\x60{key}\x60"
                or PHRASES[number] not in cells[1]
                or cells[2] != "NO_VERIFICABLE"
                or "La prueba candidata necesita vincularse a la cláusula exacta."
                not in cells[3] or not cells[4]):
            raise ValueError(UNKNOWN + ": fila inválida " + key)
        found[key] = cells
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": faltan cláusulas")
    return found


def source_matches(key: object, sources: object) -> bool:
    if (type(key) is not str or key not in IDS or
            type(sources) is not dict or set(sources) != {MATRIX, DOC} or
            type(sources[DOC]) is not str):
        return False
    number = int(key.rsplit(":L", 1)[1].split("-", 1)[0])
    lines = sources[DOC].splitlines()
    return number <= len(lines) and PHRASES[number] in lines[number - 1]


def local_proof() -> dict[str, bool]:
    """Ejercita las regresiones existentes usando solo fixtures offline."""
    passed = {}
    initial_path = sys.path[:]
    try:
        for import_root in (ROOT, ROOT / "tests"):
            if str(import_root) not in sys.path:
                sys.path.insert(0, str(import_root))
        for name, (path, cls_name, method) in WITNESSES.items():
            module = runpy.run_path(str(ROOT / path))
            case = module[cls_name](method)
            case.setUp()
            try:
                getattr(case, method)()
            finally:
                case.tearDown()
            passed[name] = True
    finally:
        sys.path[:] = initial_path
    return {
        f"{DOC}:L{line}-U1": passed[WITNESS_FOR[line]] for line in LINES
    }


def assess(sources: object, proof: object) -> dict[str, str]:
    unknown = dict.fromkeys(IDS, UNKNOWN)
    if (type(sources) is not dict or set(sources) != {MATRIX, DOC}
            or type(proof) is not dict or set(proof) != set(IDS)
            or any(type(v) is not bool for v in proof.values())):
        return unknown
    try:
        matrix_rows(sources[MATRIX])
    except ValueError:
        return unknown
    return {
        key: LOCAL if source_matches(key, sources) and proof[key] else UNKNOWN
        for key in IDS
    }


def operational_attestation(_key: object, _claim: object = None) -> str:
    """No inferir garantías operativas a partir de regresiones locales."""
    return UNKNOWN


class BrechasFactory10Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        sources = read_sources()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(matrix_rows(sources[MATRIX])), set(IDS))
        proof = local_proof()
        self.assertEqual(set(proof), set(IDS))
        for key, status in assess(sources, proof).items():
            with self.subTest(row=key):
                self.assertEqual(status, LOCAL)
                self.assertEqual(operational_attestation(key), UNKNOWN)

    def test_falla_cerrado(self) -> None:
        sources = read_sources()
        good = dict.fromkeys(IDS, True)
        for key in IDS:
            row = next(line for line in sources[MATRIX].splitlines()
                       if line.startswith(f"| \x60{key}\x60 |"))
            for malformed in (
                sources[MATRIX].replace(row, "", 1),
                sources[MATRIX] + "\n" + row,
                sources[MATRIX].replace(
                    row, row.replace("NO_VERIFICABLE", "VERIFICADO"), 1),
            ):
                with self.subTest(row=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        matrix_rows(malformed)
                    self.assertEqual(
                        assess({**sources, MATRIX: malformed}, good)[key], UNKNOWN)
            self.assertEqual(assess(sources, {**good, key: False})[key], UNKNOWN)
            self.assertEqual(assess(sources, {**good, key: "success"})[key], UNKNOWN)
            n = int(key.rsplit(":L", 1)[1].split("-", 1)[0])
            changed = sources[DOC].splitlines(keepends=True)
            changed[n - 1] = "UNKNOWN: sin fuente.\n"
            self.assertEqual(
                assess({**sources, DOC: "".join(changed)}, good)[key], UNKNOWN)
        for invalid in (None, {}, {MATRIX: sources[MATRIX]}, "success"):
            self.assertEqual(set(assess(invalid, good).values()), {UNKNOWN})
        self.assertEqual(set(assess(sources, None).values()), {UNKNOWN})

    def test_sin_datos_reales(self) -> None:
        code = (ROOT / "tests/test_brechas_factory_10.py").read_text(encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertEqual(imports, {"__future__", "ast", "pathlib", "runpy", "sys", "unittest"})
        self.assertTrue(all((ROOT / path).is_file()
                            for path, _, _ in WITNESSES.values()))
        self.assertEqual(set(WITNESS_FOR), set(LINES))

    def test_estados_unknown_explicitos(self) -> None:
        sources = read_sources()
        for key in IDS:
            with self.subTest(row=key):
                for claim in (None, True, "success", {"ci": "success"},
                              {"merged": True}, {"approved": True},
                              {"status": "VALIDATED_IN_PRODUCTION"}):
                    self.assertEqual(operational_attestation(key, claim), UNKNOWN)
                self.assertEqual(assess(sources, {})[key], UNKNOWN)
        self.assertEqual(operational_attestation("desconocido", {}), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
