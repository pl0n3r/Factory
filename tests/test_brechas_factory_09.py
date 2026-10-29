"""Factory #1627: 16 brechas de conversación y coordinación, sin evidencia inventada.

Los contratos documentales y sus fixtures se pueden validar localmente. El
comportamiento de todas las sesiones, la telemetría y CI/prod no se infieren de
un prompt ni de estas pruebas; esas afirmaciones permanecen UNKNOWN.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
CONTRAST = "docs/contraste-factory_resto_1.md"
CONVERSATION = "docs/conversacion-agentes.md"
COORDINATION = "docs/coordinacion-pr-validation.md"
NUCLEO = "agentes/NUCLEO.md"
CONVERSATION_TEST = "tests/test_conversacion_agentes.py"
COORDINATION_TEST = "tests/test_coordinacion_reusable_contract.py"
CALLER = ".github/workflows/coordinacion-trabajo.yml"
FIXTURE = "tests/fixtures/estado_compacto.md"
UNKNOWN = "UNKNOWN"
LOCAL = "CONTRATO_LOCAL"
STATE_FIELDS = ("objetivo", "repo", "issue", "pr", "head", "decisiones",
                "confirmado", "no repetir", "pendiente", "siguiente")

# Cláusula exacta -> (línea histórica, testigo del texto, familia).
# Un localizador no es evidencia de cumplimiento en sesiones ajenas.
RULES = {
    CONVERSATION + ":L45-U1": (45, "Agrupar lecturas independientes en paralelo.", "sesion"),
    CONVERSATION + ":L46-U1": (46, "Sin polling: una lectura terminal de CI", "sesion"),
    CONVERSATION + ":L47-U1": (47, "Resultado primero, detalle después", "sesion"),
    CONVERSATION + ":L47-U2": (47, "hitos en 3–7 líneas salvo petición.", "sesion"),
    CONVERSATION + ":L48-U1": (48, "No duplicar en el chat lo registrado en GitHub.", "sesion"),
    CONVERSATION + ":L57-U1": (57, "Lo de la segunda fila no se resuelve solo con instrucciones", "integracion"),
    CONVERSATION + ":L65-U1": (65, "No es un fallo:", "plataforma"),
    CONVERSATION + ":L65-U2": (65, "una sola espera, luego continuar.", "plataforma"),
    CONVERSATION + ":L66-U1": (66, "Reducir disparadores:", "plataforma"),
    CONVERSATION + ":L66-U2": (66, "no pegar secretos, tokens ni volcados grandes", "plataforma"),
    CONVERSATION + ":L66-U3": (66, "no encadenar ejecuciones de código innecesarias", "plataforma"),
    CONVERSATION + ":L66-U4": (66, "describir la finalidad defensiva/operativa", "plataforma"),
    CONVERSATION + ":L67-U1": (67, "Si se repite en el mismo chat:", "plataforma"),
    CONVERSATION + ":L69-U1": (69, "Requiere Issue propio.", "integracion"),
    CONVERSATION + ":L73-U1": (73, "comprueba que trae todos los campos", "fixture"),
    COORDINATION + ":L16-U1": (16, "El caller canónico conserva", "coordinacion"),
}
PATHS = (MATRIX, CONTRAST, CONVERSATION, COORDINATION, NUCLEO,
         CONVERSATION_TEST, COORDINATION_TEST, CALLER, FIXTURE)


def parse_rows(source: str, columns: int) -> dict[str, tuple[str, ...]]:
    """Un ID duplicado, una fila incompleta o una omisión no son cobertura."""
    rows = {}
    for line in source.splitlines():
        if not line.startswith("|"):
            continue
        cells = tuple(cell.strip().strip(chr(96)) for cell in line.strip("|").split("|"))
        if not cells or cells[0] not in RULES:
            continue
        if len(cells) != columns or cells[0] in rows:
            raise ValueError("UNKNOWN: fila ambigua o duplicada")
        rows[cells[0]] = cells
    if set(rows) != set(RULES):
        raise ValueError("UNKNOWN: faltan cláusulas")
    return rows


def parse_state(text: str) -> dict[str, list[str]]:
    """Parseador de fixture, sin acceso a conversaciones ni datos reales."""
    lines = text.strip().splitlines()
    if not lines or lines[0] != "STATE":
        raise ValueError("UNKNOWN: encabezado STATE ausente")
    state = {}
    key = None
    for line in lines[1:]:
        if line.startswith("- "):
            if key is None:
                raise ValueError("UNKNOWN: entrada sin clave")
            state[key].append(line[2:].strip())
        elif ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if not key or key in state:
                raise ValueError("UNKNOWN: campo duplicado o vacío")
            state[key] = [value.strip()] if value.strip() else []
        else:
            raise ValueError("UNKNOWN: línea no estructurada")
    if set(state) != set(STATE_FIELDS):
        raise ValueError("UNKNOWN: campos requeridos")
    if any(not values or any(not value for value in values) for values in state.values()):
        raise ValueError("UNKNOWN: campos sin valor")
    if not re.fullmatch(r"\S+@[0-9a-f]{40}", state["head"][0]):
        raise ValueError("UNKNOWN: SHA no verificable")
    return state


def contract_evidence(identifier: str, sources: dict, matrix: dict,
                      contrast: dict) -> dict[str, str]:
    """Contrato local constatado no equivale a sesión, CI o producción reales."""
    result = {"documento": UNKNOWN, "sesion": UNKNOWN, "ci": UNKNOWN,
              "produccion": UNKNOWN}
    if identifier not in RULES:
        return result
    row = matrix.get(identifier)
    candidate = contrast.get(identifier)
    if (not isinstance(row, tuple) or not isinstance(candidate, tuple)
            or len(row) != 5 or len(candidate) != 6
            or row[0] != identifier or candidate[0] != identifier
            or row[2] != "NO_VERIFICABLE"
            or candidate[2] != "NO_VERIFICABLE"
            or "Contraste #1569" not in row[3]
            or "[fuente]" not in candidate[5]):
        return result
    path, _, _ = identifier.partition(":L")
    line_number, snippet, kind = RULES[identifier]
    lines = sources.get(path, "").splitlines()
    if len(lines) < line_number or snippet.casefold() not in lines[line_number - 1].casefold():
        return result
    if kind == "coordinacion":
        if (not all(token in sources.get(CALLER, "") for token in
                    ("pull_request:", "closed", "pr-event", "github.event.action == 'closed'"))
                or "test_merged_pr_validation_is_neutral" not in
                sources.get(COORDINATION_TEST, "")
                or "test_coordinacion_reusable_contract.py" not in candidate[4]):
            return result
    else:
        nucleus = sources.get(NUCLEO, "")
        tests = sources.get(CONVERSATION_TEST, "")
        if ("transiciones significativas" not in nucleus
                or "test_fixture_permite_continuar_sin_historial" not in tests
                or "test_conversacion_agentes.py" not in candidate[4]):
            return result
        if kind == "fixture":
            try:
                parse_state(sources.get(FIXTURE, ""))
            except ValueError:
                return result
    result["documento"] = LOCAL
    return result


def classify_behavior(observation: object) -> str:
    """Ni una declaración sintética ni un prompt prueban todas las sesiones."""
    if not isinstance(observation, dict):
        return UNKNOWN
    if observation.get("source") in ("prompt", "fixture", "synthetic", None):
        return UNKNOWN
    # Sin adaptador autenticado de telemetría en esta hoja no afirmar éxito.
    return UNKNOWN


class BrechasFactory09Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {path: (ROOT / path).read_text(encoding="utf-8") for path in PATHS}
        cls.matrix = parse_rows(cls.sources[MATRIX], 5)
        cls.contrast = parse_rows(cls.sources[CONTRAST], 6)

    def test_contrato_principal(self):
        """AC-01: las dieciséis cláusulas se anclan a evidencia local exacta."""
        self.assertEqual(len(RULES), 16)
        self.assertEqual(set(self.matrix), set(RULES))
        self.assertEqual(set(self.contrast), set(RULES))
        for identifier in RULES:
            with self.subTest(clause=identifier):
                result = contract_evidence(identifier, self.sources,
                                           self.matrix, self.contrast)
                self.assertEqual(result["documento"], LOCAL, identifier)
                self.assertEqual(result["sesion"], UNKNOWN)
        state = parse_state(self.sources[FIXTURE])
        self.assertEqual(set(state), set(STATE_FIELDS))
        self.assertIn("Playwright", state["pendiente"][0])

    def test_falla_cerrado(self):
        """AC-02: ninguna evidencia ausente o alterada se promociona a éxito."""
        for identifier in RULES:
            with self.subTest(clause=identifier):
                missing = dict(self.matrix)
                del missing[identifier]
                self.assertEqual(contract_evidence(identifier, self.sources,
                    missing, self.contrast)["documento"], UNKNOWN)
                wrong = dict(self.matrix)
                wrong[identifier] = (identifier, "", "CUBIERTO", "", "")
                self.assertEqual(contract_evidence(identifier, self.sources,
                    wrong, self.contrast)["documento"], UNKNOWN)
                path = identifier.split(":L", 1)[0]
                deleted_source = {**self.sources, path: ""}
                self.assertEqual(contract_evidence(identifier, deleted_source,
                    self.matrix, self.contrast)["documento"], UNKNOWN)
        for sample in ("", "state\nfoo: bar", "STATE\nobjetivo: a",
                       self.sources[FIXTURE].replace("siguiente:", "siguiente_a:"),
                       self.sources[FIXTURE] + "\nobjetivo: duplicado"):
            with self.subTest(sample=sample[:35]):
                with self.assertRaises(ValueError):
                    parse_state(sample)
        first = next(iter(RULES))
        row = next(line for line in self.sources[MATRIX].splitlines()
                   if line.startswith("| " + chr(96) + first + chr(96) + " |"))
        with self.assertRaises(ValueError):
            parse_rows(self.sources[MATRIX] + "\n" + row, 5)

    def test_sin_datos_reales(self):
        """AC-03: sólo lectura local, fixtures falsos y biblioteca estándar."""
        body = Path(__file__).read_text(encoding="utf-8")
        self.assertNotRegex(body, r"(?m)^(?:import|from)\s+(?:requests|httpx|urllib|socket|subprocess)\b")
        self.assertNotIn("-----BEGIN " + "PRIVATE KEY-----", body)
        self.assertNotRegex(body, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
        for path in PATHS:
            with self.subTest(path=path):
                self.assertFalse(Path(path).is_absolute())
                self.assertTrue((ROOT / path).is_file())

    def test_estados_unknown_explicitos(self):
        """AC-04: sin runtime/CI observado, los resultados siguen UNKNOWN."""
        for identifier in RULES:
            with self.subTest(clause=identifier):
                observed = contract_evidence(identifier, self.sources,
                                             self.matrix, self.contrast)
                self.assertEqual((observed["sesion"], observed["ci"],
                                  observed["produccion"]),
                                 (UNKNOWN, UNKNOWN, UNKNOWN))
                self.assertEqual(self.matrix[identifier][2], "NO_VERIFICABLE")
                self.assertEqual(self.contrast[identifier][2], "NO_VERIFICABLE")
        for observation in (None, {}, {"source": "prompt", "success": True},
                            {"source": "synthetic", "success": True},
                            {"source": "real", "success": True}):
            self.assertEqual(classify_behavior(observation), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
