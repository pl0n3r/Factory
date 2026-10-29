"""Factory #1684: 16 brechas de permisos, feedback y rollback.

Los contratos puros se prueban con fixtures sintéticos; las operaciones
reales de producto, procedencia de callers y rollback siguen UNKNOWN.
Esta hoja no modifica ni promueve la matriz de cobertura.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import reusable_permission_compat as compat

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"

CLAUSES = {
    "docs/retroalimentacion-producto.md:L9-U1": [
        "docs/retroalimentacion-producto.md",
        9,
        "`project`: `owner/repo`;"
    ],
    "docs/reusable-permission-compat.md:L10-U1": [
        "docs/reusable-permission-compat.md",
        10,
        "un reusable es compatible solo si, para cada scope requerido, el caller concede un nivel igual o mayor;"
    ],
    "docs/reusable-permission-compat.md:L11-U1": [
        "docs/reusable-permission-compat.md",
        11,
        "un conjunto de consumidores es compatible solo si **todos** sus callers lo son."
    ],
    "docs/reusable-permission-compat.md:L11-U2": [
        "docs/reusable-permission-compat.md",
        11,
        "No existe mayoría, promedio ni excepción implícita."
    ],
    "docs/reusable-permission-compat.md:L17-U1": [
        "docs/reusable-permission-compat.md",
        17,
        "Su único trabajo es validar mapas ya extraídos por un adaptador confiable."
    ],
    "docs/reusable-permission-compat.md:L19-U1": [
        "docs/reusable-permission-compat.md",
        19,
        "La integración posterior con la puerta de release debe obtener los envelopes de callers reales o fixtures con provenance y alimentar este contrato"
    ],
    "docs/reusable-permission-compat.md:L19-U2": [
        "docs/reusable-permission-compat.md",
        19,
        "cualquier evidencia ausente o inválida debe conservar el bloqueo."
    ],
    "docs/reusable-permission-compat.md:L3-U1": [
        "docs/reusable-permission-compat.md",
        3,
        "`reusable_permission_compat.py` define un contrato **puro y fail-closed** para comparar el permission envelope máximo que requiere un workflow reusable con"
    ],
    "docs/reusable-permission-compat.md:L7-U1": [
        "docs/reusable-permission-compat.md",
        7,
        "niveles: `none < read < write`;"
    ],
    "docs/reusable-permission-compat.md:L8-U1": [
        "docs/reusable-permission-compat.md",
        8,
        "scopes omitidos por el caller equivalen a `none`;"
    ],
    "docs/reusable-permission-compat.md:L9-U1": [
        "docs/reusable-permission-compat.md",
        9,
        "scopes o niveles desconocidos invalidan el contrato;"
    ],
    "docs/reusable-release-rollback.md:L10-U1": [
        "docs/reusable-release-rollback.md",
        10,
        "tag/release semántica asociada al incidente;"
    ],
    "docs/reusable-release-rollback.md:L11-U1": [
        "docs/reusable-release-rollback.md",
        11,
        "repositorios y workflows consumidores afectados;"
    ],
    "docs/reusable-release-rollback.md:L12-U1": [
        "docs/reusable-release-rollback.md",
        12,
        "run IDs cuyo resultado sea `startup_failure`;"
    ],
    "docs/reusable-release-rollback.md:L13-U1": [
        "docs/reusable-release-rollback.md",
        13,
        "SHA/tag estable previo conocido que sí materializaba jobs en consumidores."
    ],
    "docs/reusable-release-rollback.md:L19-U1": [
        "docs/reusable-release-rollback.md",
        19,
        "El objetivo debe ser un SHA/tag Factory previamente conocido como estable para los consumidores afectados."
    ]
}

EXPECTED_SOURCE_LINES = {
    "docs/retroalimentacion-producto.md:L9-U1": "- `project`: `owner/repo`;",
    "docs/reusable-permission-compat.md:L10-U1": "- un reusable es compatible solo si, para cada scope requerido, el caller concede un nivel igual o mayor;",
    "docs/reusable-permission-compat.md:L11-U1": "- un conjunto de consumidores es compatible solo si **todos** sus callers lo son. No existe mayoría, promedio ni excepción implícita.",
    "docs/reusable-permission-compat.md:L11-U2": "- un conjunto de consumidores es compatible solo si **todos** sus callers lo son. No existe mayoría, promedio ni excepción implícita.",
    "docs/reusable-permission-compat.md:L17-U1": "El módulo no lee YAML, GitHub, red, archivos, variables de entorno, secretos ni credenciales. Tampoco modifica permisos. Su único trabajo es validar mapas ya extraídos por un adaptador confiable.",
    "docs/reusable-permission-compat.md:L19-U1": "La integración posterior con la puerta de release debe obtener los envelopes de callers reales o fixtures con provenance y alimentar este contrato; cualquier evidencia ausente o inválida debe conservar el bloqueo.",
    "docs/reusable-permission-compat.md:L19-U2": "La integración posterior con la puerta de release debe obtener los envelopes de callers reales o fixtures con provenance y alimentar este contrato; cualquier evidencia ausente o inválida debe conservar el bloqueo.",
    "docs/reusable-permission-compat.md:L3-U1": "`reusable_permission_compat.py` define un contrato **puro y fail-closed** para comparar el permission envelope máximo que requiere un workflow reusable con el envelope que concede cada caller.",
    "docs/reusable-permission-compat.md:L7-U1": "- niveles: `none < read < write`;",
    "docs/reusable-permission-compat.md:L8-U1": "- scopes omitidos por el caller equivalen a `none`;",
    "docs/reusable-permission-compat.md:L9-U1": "- scopes o niveles desconocidos invalidan el contrato;",
    "docs/reusable-release-rollback.md:L10-U1": "- tag/release semántica asociada al incidente;",
    "docs/reusable-release-rollback.md:L11-U1": "- repositorios y workflows consumidores afectados;",
    "docs/reusable-release-rollback.md:L12-U1": "- run IDs cuyo resultado sea `startup_failure`;",
    "docs/reusable-release-rollback.md:L13-U1": "- SHA/tag estable previo conocido que sí materializaba jobs en consumidores.",
    "docs/reusable-release-rollback.md:L19-U1": "El objetivo debe ser un SHA/tag Factory previamente conocido como estable para los consumidores afectados. No se elige por inferencia ni por “último release verde” si no existe evidencia de consumidor."
}

IDS = tuple(CLAUSES)
PERMISSION_DOC = "docs/reusable-permission-compat.md:"
EXTERNAL_IDS = frozenset(key for key in IDS if (
    key.startswith("docs/retroalimentacion-producto.md:")
    or key.startswith("docs/reusable-release-rollback.md:")
    or key == PERMISSION_DOC + "L19-U1"))
LOCAL_IDS = frozenset(IDS) - EXTERNAL_IDS
SOURCES = frozenset([MATRIX] + [item[0] for item in CLAUSES.values()])


def sources() -> dict[str, str]:
    """Leer solo textos versionados; nunca invocar APIs externas."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in sorted(SOURCES)}


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Detectar IDs antes de validar forma, incluidos duplicados disimulados."""
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matrix missing")
    found: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        normalized = line.lstrip()
        if not normalized.startswith("|"):
            continue
        row_text = normalized.rstrip()
        # Drop precisely one outer delimiter so extra columns remain visible.
        body = row_text[1:-1] if row_text.endswith("|") else row_text[1:]
        parts = tuple(piece.strip() for piece in body.split("|"))
        if not parts or not (parts[0].startswith(chr(96)) and
                            parts[0].endswith(chr(96))):
            continue
        key = parts[0][1:-1]
        if key not in CLAUSES:
            continue
        if (key in found or not row_text.endswith("|")
                or not row_text.startswith("| " + chr(96) + key + chr(96) + " |")
                or len(parts) != 5 or parts[0] != chr(96) + key + chr(96)
                or parts[1] != CLAUSES[key][2]
                or parts[2] != "NO_VERIFICABLE"
                or "[contraste #1574]" not in parts[3]
                or parts[4] != "—"):
            raise ValueError(UNKNOWN + ": altered row " + key)
        found[key] = parts
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": missing coverage IDs")
    return found


def source_matches(key: str, docs: dict[str, str], row: tuple[str, ...]) -> bool:
    if key not in CLAUSES:
        return False
    path, line, fragment = CLAUSES[key]
    original = docs.get(path)
    if type(original) is not str:
        return False
    lines = original.splitlines()
    return (1 <= line <= len(lines) and fragment == row[1]
            and lines[line - 1] == EXPECTED_SOURCE_LINES[key])


def permission_evidence() -> dict[str, bool]:
    """Demostrar semántica real de código puro, nunca de permisos en producción."""
    prefix = PERMISSION_DOC
    required = {"contents": "read"}
    good = {"contents": "write"}
    weak = {"contents": "none"}
    missing = compat.compare_permissions(required, {})
    low = compat.compare_permissions({"contents": "write"}, {"contents": "read"})
    ok = compat.compare_permissions(required, good)
    invalid_scope = compat.compare_permissions({"invalid": "read"}, good)
    invalid_level = compat.compare_permissions(required, {"contents": "admin"})
    all_good = compat.compare_callers(required, {"a": good, "b": {"contents": "read"}})
    one_bad = compat.compare_callers(required, {
        "a": good, "b": {"contents": "read"}, "c": weak})
    absent = compat.compare_callers(required, {})
    source = inspect.getsource(compat)
    tree = ast.parse(source)
    import_roots = set()
    forbidden_calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            import_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"open", "eval", "exec"}:
                forbidden_calls.add(node.func.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "io"
                    and node.func.attr == "open"):
                forbidden_calls.add("io.open")
    pure = (not import_roots.intersection({"os", "socket", "requests", "urllib",
                                          "subprocess", "pathlib"})
            and not forbidden_calls)
    deterministic = (ok == compat.compare_permissions(required, good)
                     and one_bad == compat.compare_callers(required, {
                         "c": weak, "a": good, "b": {"contents": "read"}}))
    return {
        prefix + "L3-U1": pure and deterministic
            and not compat.compare_permissions(None, good)["compatible"],
        prefix + "L7-U1": compat.LEVEL_RANK == {"none": 0, "read": 1, "write": 2},
        prefix + "L8-U1": (not missing["compatible"]
                            and missing["missing"] == [{
                                "scope": "contents", "required": "read", "granted": "none"}]),
        prefix + "L9-U1": (not invalid_scope["compatible"]
                            and invalid_scope["reason"] == "invalid_contract"
                            and not invalid_level["compatible"]
                            and invalid_level["reason"] == "invalid_contract"),
        prefix + "L10-U1": (ok["compatible"] and not low["compatible"]
                             and low["reason"] == "insufficient_permissions"),
        prefix + "L11-U1": (all_good["compatible"] and not one_bad["compatible"]
                              and one_bad["reason"] == "caller_incompatible"),
        prefix + "L11-U2": (not one_bad["compatible"]
                              and sum(v["compatible"] for v in one_bad["callers"]) == 2
                              and len(one_bad["callers"]) == 3),
        prefix + "L17-U1": (pure and deterministic
                              and "yaml" not in import_roots),
        prefix + "L19-U2": (not absent["compatible"] and
                              absent["reason"] == "invalid_contract"
                              and not invalid_level["compatible"]),
    }


def assess(docs: object, checks: object) -> dict[str, str]:
    """Ninguna prueba local autoriza un rollback o una observación externa."""
    unknown = dict.fromkeys(IDS, UNKNOWN)
    if (type(docs) is not dict or set(docs) != SOURCES
            or type(checks) is not dict or set(checks) != LOCAL_IDS
            or any(type(value) is not bool for value in checks.values())):
        return unknown
    try:
        rows = matrix_rows(docs[MATRIX])
    except (KeyError, ValueError):
        return unknown
    return {key: (LOCAL if key in LOCAL_IDS and checks[key]
                   and source_matches(key, docs, rows[key]) else UNKNOWN)
            for key in IDS}


def external_evidence(_key: object, _claim: object = None) -> str:
    """La evidencia de consumidor/OWNER debe validarse fuera de esta prueba."""
    return UNKNOWN


class BrechasFactory66Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs = sources()
        self.assertEqual(16, len(IDS))
        self.assertEqual(9, len(LOCAL_IDS))
        self.assertEqual(7, len(EXTERNAL_IDS))
        self.assertEqual(set(IDS), set(matrix_rows(docs[MATRIX])))
        checks = permission_evidence()
        self.assertEqual(LOCAL_IDS, set(checks))
        self.assertTrue(all(checks.values()))
        actual = assess(docs, checks)
        for key in IDS:
            with self.subTest(id=key):
                self.assertTrue(source_matches(key, docs, matrix_rows(docs[MATRIX])[key]))
                self.assertEqual(LOCAL if key in LOCAL_IDS else UNKNOWN, actual[key])
                self.assertEqual(UNKNOWN, external_evidence(key))

    def test_falla_cerrado(self) -> None:
        docs = sources()
        checks = dict.fromkeys(LOCAL_IDS, True)
        for key in IDS:
            original = next(line for line in docs[MATRIX].splitlines()
                            if line.startswith("| " + chr(96) + key + chr(96) + " |"))
            corruptions = (
                docs[MATRIX].replace(original, "", 1),
                docs[MATRIX] + "\n" + original,
                docs[MATRIX] + "\n" + original.replace("| " + chr(96),
                    "|  " + chr(96), 1),
                docs[MATRIX].replace(original, original + "|", 1),
                docs[MATRIX].replace(original, original[:-1], 1),
                docs[MATRIX].replace(original, original.replace(
                    "NO_VERIFICABLE", "VERIFICADO", 1), 1),
                docs[MATRIX].replace(original, original.replace(
                    CLAUSES[key][2], "UNKNOWN: fuente inválida", 1), 1),
            )
            for corrupted in corruptions:
                with self.subTest(id=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(corrupted)
                self.assertEqual({UNKNOWN}, set(assess(
                    {**docs, MATRIX: corrupted}, checks).values()))
            path, line, _ = CLAUSES[key]
            changed = docs[path].splitlines(keepends=True)
            changed[line - 1] = "UNKNOWN: doc source modified\n"
            self.assertEqual(UNKNOWN, assess(
                {**docs, path: "".join(changed)}, checks)[key])
            changed = docs[path].splitlines(keepends=True)
            changed[line - 1] = changed[line - 1].rstrip("\n") + (
                " esta regla queda retirada\n")
            self.assertEqual(UNKNOWN, assess(
                {**docs, path: "".join(changed)}, checks)[key])

    def test_sin_datos_reales(self) -> None:
        """No importar redes, credenciales ni ejecución de despliegue."""
        raw = (ROOT / "tests/test_brechas_factory_66.py").read_text(encoding="utf-8")
        roots = set()
        for node in ast.walk(ast.parse(raw)):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertEqual({"__future__", "ast", "inspect", "pathlib",
                          "unittest", "scripts"}, roots)
        self.assertEqual(LOCAL_IDS, set(permission_evidence()))
        self.assertFalse(roots.intersection({"subprocess", "requests", "os",
                                              "socket", "urllib"}))

    def test_estados_unknown_explicitos(self) -> None:
        docs = sources()
        complete = dict.fromkeys(LOCAL_IDS, True)
        self.assertEqual({UNKNOWN}, set(assess({}, complete).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))
        for bad in (None, {}, dict.fromkeys(LOCAL_IDS, "success"),
                    {**complete, "extra": True},
                    {**complete, next(iter(LOCAL_IDS)): None}):
            with self.subTest(invalid=str(bad)[:30]):
                self.assertEqual({UNKNOWN}, set(assess(docs, bad).values()))
        actual = assess(docs, complete)
        with patch.object(inspect, "getsource", return_value=(
                "import io\nio.open('synthetic-fixture')\n")):
            tainted = permission_evidence()
        self.assertFalse(tainted[PERMISSION_DOC + "L3-U1"])
        self.assertFalse(tainted[PERMISSION_DOC + "L17-U1"])
        for key in EXTERNAL_IDS:
            with self.subTest(external=key):
                self.assertEqual(UNKNOWN, actual[key])
                self.assertEqual(UNKNOWN, external_evidence(
                    key, {"approved": True, "stable_factory_sha": "f" * 40}))
                self.assertEqual(UNKNOWN, external_evidence(key, "CI success"))


if __name__ == "__main__":
    unittest.main()
