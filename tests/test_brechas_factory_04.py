#!/usr/bin/env python3
"""Factory #1622: sixteen offline acceptance-contract witnesses.

Pure local parser/check contracts may be verified. Historical CI, owner
approval, external state and production evidence remain UNKNOWN.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from scripts.aceptacion_kit import (
    AcceptanceError, CheckPending, Criterion, parse_contract, verify_check,
    verify_checks_only,
)

ROOT = Path(__file__).resolve().parents[1]
DOC = "docs/aceptacion-ejecutable.md"
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "CONTRATO_LOCAL_SINTETICO"
CLAUSES = {
    "L22-U1": "- [ ] [AC-01] descripción verificable",
    "L37-U1": "Los IDs del marker deben coincidir exactamente",
    "L41-U1": "Solo acepta un target con forma:",
    "L45-U1": "La ruta debe vivir en un directorio de tests permitido",
    "L49-U2": "nunca cuenta como éxito",
    "L49-U3": "solo satisface el criterio con",
    "L5-U1": "gates genéricos",
    "L51-U1": "no pueden referenciarse como evidencia",
    "L57-U1": "Lint + Tests + Coordinación",
    "L59-U1": "La espera solo vuelve a leer check-runs",
    "L59-U2": "Un fallo terminal distinto de evidencia pendiente",
    "L6-U1": "criterios específicos del Issue",
    "L61-U1": "no se ejecutan durante ese preflight",
    "L67-U1": ".github/ISSUE_TEMPLATE/trabajo.yml",
    "L71-U1": "Los PR históricos abiertos deberán migrar",
    "L71-U2": "No se fabrican criterios retrospectivos",
}
IDS = tuple(DOC + ":" + k for k in CLAUSES)
LOCAL_IDS = frozenset(DOC + ":" + k for k in (
    "L22-U1", "L37-U1", "L41-U1", "L45-U1",
    "L49-U2", "L49-U3", "L51-U1", "L59-U2",
))
EXTERNAL_IDS = frozenset(IDS) - LOCAL_IDS
GAPS = {
    k: "UNKNOWN: falta prueba externa autenticada de workflows, historial y "
       "checks reales; un fixture local no certifica GitHub ni producción"
    for k in EXTERNAL_IDS
}


def example_body(*, human="AC-01", machine="AC-01",
                 kind="check", target="Tests de scripts"):
    marker = json.dumps({
        "version": 1,
        "criteria": [{"id": machine, "kind": kind, "target": target}],
    }, ensure_ascii=False, separators=(",", ":"))
    return "\n\n".join((
        "### Contexto\n\nEjemplo sintético sin red.",
        "### Alcance\n\nContrato local.",
        "### Fuera de alcance\n\nProducción y datos reales.",
        "### Criterios de aceptación\n\n- [ ] [" + human + "] Prueba válida.",
        "### Contrato ejecutable\n\n<!-- factory-acceptance " + marker + " -->",
    ))


def checks(status="completed", conclusion="success"):
    return {"check_runs": [{
        "id": 7, "name": "Tests de scripts",
        "status": status, "conclusion": conclusion,
    }]}


def matrix_rows(raw):
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matriz faltante")
    out = {}
    tick = chr(96)
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        if not cells or not cells[0].startswith(tick):
            continue
        key = cells[0].strip(tick)
        if key not in IDS:
            continue
        if (key in out or len(cells) != 5 or cells[2] != "NO_VERIFICABLE"
                or not all(cells[1:])):
            raise ValueError(UNKNOWN + ": duplicada, promovida o ambigua " + key)
        out[key] = cells
    if set(out) != set(IDS):
        raise ValueError(UNKNOWN + ": fila faltante")
    return out


def source_contract(key, document):
    if key not in IDS or type(document) is not str:
        return False
    unit = key.rsplit(":", 1)[1]
    lineno = unit[1:].split("-", 1)[0]
    lines = document.splitlines()
    return (lineno.isdecimal() and 0 < int(lineno) <= len(lines)
            and CLAUSES[unit] in lines[int(lineno) - 1])


def behavior_evidence():
    def rejected(body):
        try:
            parse_contract(body)
        except AcceptanceError:
            return True
        return False

    def invalid_check(payload, error):
        try:
            verify_check(Criterion("AC-01", "check", "Tests de scripts"),
                         payload)
        except error:
            return True
        return False

    good = example_body()
    criterion = Criterion("AC-01", "check", "Tests de scripts")
    valid = parse_contract(good)
    successful = (
        verify_check(criterion, checks()) is None
        and verify_checks_only([criterion], checks()) == ["AC-01"]
    )
    return {
        DOC + ":L22-U1": (len(valid) == 1 and valid[0] == criterion
                          and rejected(good.replace("- [ ] [AC-01]",
                                                    "- [ ] AC-01"))),
        DOC + ":L37-U1": rejected(example_body(human="AC-02")),
        DOC + ":L41-U1": (
            len(parse_contract(example_body(
                kind="test", target="tests/test_x.py::Clase::test_abc"))) == 1
            and rejected(example_body(
                kind="test", target="tests/test_x.txt::Clase::test_abc"))
        ),
        DOC + ":L45-U1": (
            rejected(example_body(
                kind="test", target="tests/../test_x.py::Clase::test_abc"))
            and rejected(example_body(
                kind="test", target="/tmp/test_x.py::Clase::test_abc"))
        ),
        DOC + ":L49-U2": (
            invalid_check(checks("queued", None), CheckPending)
            and invalid_check({"check_runs": []}, CheckPending)
        ),
        DOC + ":L49-U3": (successful
                           and invalid_check(checks("completed", "failure"),
                                             AcceptanceError)),
        DOC + ":L51-U1": (
            rejected(example_body(target="Validar"))
            and rejected(example_body(target="Criterios de aceptación"))
        ),
        DOC + ":L59-U2": (
            invalid_check(checks("completed", "failure"), AcceptanceError)
            and invalid_check(checks("completed", "timed_out"), AcceptanceError)
        ),
    }


def assess(matrix, source, evidence):
    out = dict.fromkeys(IDS, UNKNOWN)
    try:
        rows = matrix_rows(matrix)
    except ValueError:
        return out
    if (type(evidence) is not dict or set(evidence) != LOCAL_IDS
            or any(type(v) is not bool for v in evidence.values())):
        return out
    for key in LOCAL_IDS:
        if (evidence[key] and source_contract(key, source)
                and CLAUSES[key.rsplit(":", 1)[1]] in rows[key][1]):
            out[key] = LOCAL
    return out


def external_status(key, untrusted_claim):
    return UNKNOWN


class BrechasFactory04Tests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / DOC).read_text(encoding="utf-8")
        self.matrix = (ROOT / MATRIX).read_text(encoding="utf-8")
        self.proof = behavior_evidence()

    def test_contrato_principal(self):
        rows = matrix_rows(self.matrix)
        self.assertEqual(len(rows), 16)
        self.assertEqual(len(IDS), len(set(IDS)))
        self.assertEqual(set(self.proof), LOCAL_IDS)
        self.assertTrue(all(self.proof.values()))
        results = assess(self.matrix, self.source, self.proof)
        for key in IDS:
            with self.subTest(key=key):
                self.assertTrue(source_contract(key, self.source))
                self.assertIn(CLAUSES[key.rsplit(":", 1)[1]], rows[key][1])
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertEqual(results[key],
                                 LOCAL if key in LOCAL_IDS else UNKNOWN)

    def test_falla_cerrado(self):
        line = next(x for x in self.matrix.splitlines() if
                    x.startswith("| " + chr(96) + IDS[0] + chr(96) + " |"))
        invalid = (
            None, "", self.matrix.replace(line, "", 1),
            self.matrix + "\n" + line,
            self.matrix.replace(
                line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
        )
        for altered in invalid:
            with self.subTest(case=type(altered).__name__):
                with self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(altered)
                self.assertEqual(set(assess(altered, self.source,
                                             self.proof).values()), {UNKNOWN})
        tampered = self.source.replace(
            CLAUSES["L37-U1"], "Permitir IDs incoherentes", 1)
        self.assertEqual(
            assess(self.matrix, tampered, self.proof)[DOC + ":L37-U1"], UNKNOWN)
        for body in (
            example_body(human="AC-02"),
            example_body(target="Validar"),
            example_body(kind="test",
                         target="tests/../test_x.py::Clase::test_abc"),
        ):
            with self.assertRaises(AcceptanceError):
                parse_contract(body)

    def test_sin_datos_reales(self):
        own = (ROOT / "tests/test_brechas_factory_04.py").read_text(
            encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(own)):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports, {
            "__future__", "ast", "json", "pathlib", "unittest", "scripts",
        })
        self.assertEqual(set(GAPS), EXTERNAL_IDS)
        self.assertTrue(all("UNKNOWN" in msg for msg in GAPS.values()))

    def test_estados_unknown_explicitos(self):
        for key in IDS:
            with self.subTest(key=key):
                for claim in (None, True, "success", {"ci": "success"},
                              {"owner": "APPROVED"},
                              {"production": "VALIDATED_IN_PRODUCTION"}):
                    self.assertEqual(external_status(key, claim), UNKNOWN)
                self.assertEqual(
                    assess(self.matrix, self.source, {})[key], UNKNOWN)
                if key in EXTERNAL_IDS:
                    self.assertEqual(assess(self.matrix, self.source,
                                            self.proof)[key], UNKNOWN)
                    self.assertTrue(GAPS[key].startswith("UNKNOWN:"))
                else:
                    weakened = {**self.proof, key: False}
                    self.assertEqual(assess(self.matrix, self.source,
                                            weakened)[key], UNKNOWN)
        claims = {k: "success" for k in LOCAL_IDS}
        self.assertEqual(set(assess(self.matrix, self.source, claims).values()),
                         {UNKNOWN})


if __name__ == "__main__":
    unittest.main()
