#!/usr/bin/env python3
"""Factory #1623: 16 offline witnesses for adaptive orchestration and routing.

A passing synthetic unit test is local evidence only. External staff adapters,
cross-repo permissions, production and historical GitHub decisions stay UNKNOWN.
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
LOCAL = "LOCAL_SYNTHETIC_PARTIAL"
CLAUSES = {
    "docs/aceptacion-ejecutable.md:L71-U3": "al retomar cada Issue se documenta el comportamiento",
    "docs/aceptacion-ejecutable.md:L8-U1": "Un PR no está “hecho” si solo pasa la primera capa.",
    "docs/adaptive-orchestration.md:L12-U1": "Una Session solo cuenta como",
    "docs/adaptive-orchestration.md:L33-U1": "pura entre",
    "docs/adaptive-orchestration.md:L41-U1": "El fence exige coincidencia exacta",
    "docs/adaptive-orchestration.md:L47-U1": "Solo retiene replans no críticos",
    "docs/adaptive-orchestration.md:L49-U1": "no equivale a preemption",
    "docs/adaptive-orchestration.md:L56-U1": "siguiente E2E del épico #260 debe componer Presence",
    "docs/adaptive-orchestration.md:L6-U1": "puede continuar, paralelizar o debe fallar cerrado",
    "docs/adaptive-orchestration.md:L63-U1": "Presence y Fencing únicamente aportan razones",
    "docs/adaptive-orchestration.md:L67-U1": "Una Presence unknown o stale",
    "docs/admin-staff-api.md:B04": "Los adapters de producto deben hacer cumplir",
    "docs/ai-gateway.md:L13-U1": "Cada éxito registra provider/model/executor",
    "docs/ai-gateway.md:L15-U2": "nunca un canal paralelo",
    "docs/ai-gateway.md:L17-U1": "credenciales deberán entrar únicamente",
    "docs/arquitectura-tecnica.md:B02": "Reusable workflows deben rechazar eventos privilegiados",
}
IDS = tuple(CLAUSES)
DOCS = frozenset(x.rsplit(":", 1)[0] for x in IDS)
# A witness is an existing unittest case that exercises actual pure code.
WITNESSES = {
    "docs/adaptive-orchestration.md:L12-U1":
        ("test_presence_contract.py", "PresenceContractTests",
         "test_one_fresh_working_session_classifies_solo"),
    "docs/adaptive-orchestration.md:L33-U1":
        ("test_adaptive_replan.py", "AdaptiveReplanTests",
         "test_presence_join_leave_stale_and_recovery_trigger_deterministic_replan"),
    "docs/adaptive-orchestration.md:L41-U1":
        ("test_adaptive_fencing.py", "AdaptiveFencingTests",
         "test_stale_generation_fails_closed"),
    "docs/adaptive-orchestration.md:L47-U1":
        ("test_adaptive_fencing.py", "AdaptiveFencingTests",
         "test_noncritical_rebalance_respects_cooldown"),
    "docs/adaptive-orchestration.md:L49-U1":
        ("test_adaptive_fencing.py", "AdaptiveFencingTests",
         "test_global_idle_proof_produces_keep_without_pause_or_authority_expansion"),
    "docs/adaptive-orchestration.md:L6-U1":
        ("test_presence_contract.py", "PresenceContractTests",
         "test_stale_or_unknown_freshness_fails_closed"),
    "docs/ai-gateway.md:L13-U1":
        ("test_ai_gateway.py", "AIGatewayTests",
         "test_execution_evidence_is_attributable"),
    "docs/ai-gateway.md:L15-U2":
        ("test_ai_gateway.py", "AIGatewayTests",
         "test_coding_adapter_is_governed_not_parallel"),
}
LOCAL_IDS = frozenset(WITNESSES)
EXTERNAL_IDS = frozenset(IDS) - LOCAL_IDS
GAPS = {
    key: "UNKNOWN: falta test E2E autentico, pruebas cross-repo o decisiones "
         "historicas verificables; los contratos sintéticos no acreditan "
         "operacion ni autorizacion real"
    for key in EXTERNAL_IDS
}


def load_sources():
    return {p: (ROOT / p).read_text(encoding="utf-8")
            for p in (MATRIX, *sorted(DOCS))}


def matrix_rows(raw):
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matriz ausente")
    result = {}
    tick = chr(96)
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        parts = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        if not parts or not parts[0].startswith(tick):
            continue
        key = parts[0].strip(tick)
        if key not in IDS:
            continue
        if (key in result or len(parts) != 5 or parts[2] != "NO_VERIFICABLE"
                or not all(parts[1:])):
            raise ValueError(UNKNOWN + ": duplicada, alterada o incompleta " + key)
        if CLAUSES[key] not in parts[1]:
            raise ValueError(UNKNOWN + ": requisito no coincide " + key)
        result[key] = parts
    if set(result) != set(IDS):
        raise ValueError(UNKNOWN + ": falta requisito")
    return result


def source_contract(key, sources):
    if key not in IDS or type(sources) is not dict:
        return False
    doc, marker = key.rsplit(":", 1)
    raw = sources.get(doc)
    if type(raw) is not str or not raw:
        return False
    if marker.startswith("B"):
        # Historical aggregate B rows are not stable physical line numbers.
        return doc in DOCS and len(raw) > 1000
    number = marker[1:].split("-", 1)[0]
    lines = raw.splitlines()
    return (number.isdecimal() and 0 < int(number) <= len(lines)
            and CLAUSES[key] in lines[int(number) - 1])


def synthetic_witnesses():
    """Run allowlisted pre-existing unit methods once, without network."""
    old_path = sys.path[:]
    result = {}
    try:
        for directory in (str(ROOT), str(ROOT / "tests")):
            if directory not in sys.path:
                sys.path.insert(0, directory)
        modules = {}
        for key, (name, klass, method) in WITNESSES.items():
            if name not in modules:
                modules[name] = runpy.run_path(str(ROOT / "tests" / name))
            case = modules[name][klass](method)
            outcome = unittest.TestResult()
            case.run(outcome)
            result[key] = (outcome.testsRun == 1 and outcome.wasSuccessful())
    finally:
        sys.path[:] = old_path
    return result


def assess(sources, evidence):
    answer = dict.fromkeys(IDS, UNKNOWN)
    if type(sources) is not dict or MATRIX not in sources:
        return answer
    try:
        matrix_rows(sources[MATRIX])
    except ValueError:
        return answer
    if (type(evidence) is not dict or set(evidence) != LOCAL_IDS
            or any(type(v) is not bool for v in evidence.values())):
        return answer
    for key in LOCAL_IDS:
        if evidence[key] and source_contract(key, sources):
            answer[key] = LOCAL
    return answer


def operational_attestation(key, claim):
    # Untrusted assertions cannot prove human consent or deployed behavior.
    return UNKNOWN


class BrechasFactory05Tests(unittest.TestCase):
    def setUp(self):
        self.sources = load_sources()
        self.evidence = synthetic_witnesses()

    def test_contrato_principal(self):
        rows = matrix_rows(self.sources[MATRIX])
        self.assertEqual(len(rows), 16)
        self.assertEqual(set(IDS), set(rows))
        self.assertEqual(set(self.evidence), LOCAL_IDS)
        self.assertTrue(all(self.evidence.values()))
        result = assess(self.sources, self.evidence)
        for key in IDS:
            with self.subTest(key=key):
                self.assertTrue(source_contract(key, self.sources))
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertEqual(result[key],
                                 LOCAL if key in LOCAL_IDS else UNKNOWN)

    def test_falla_cerrado(self):
        matrix = self.sources[MATRIX]
        first = IDS[0]
        line = next(row for row in matrix.splitlines()
                    if row.startswith("| " + chr(96) + first + chr(96) + " |"))
        for bad in (None, "", matrix.replace(line, "", 1),
                    matrix + "\n" + line,
                    matrix.replace(line, line.replace(
                        "NO_VERIFICABLE", "CUBIERTO"), 1)):
            with self.assertRaisesRegex(ValueError, UNKNOWN):
                matrix_rows(bad)
            self.assertEqual(
                set(assess({**self.sources, MATRIX: bad},
                           self.evidence).values()), {UNKNOWN})
        for key in LOCAL_IDS:
            source = key.rsplit(":", 1)[0]
            invalid = {**self.sources, source: ""}
            self.assertEqual(assess(invalid, self.evidence)[key], UNKNOWN)
        self.assertEqual(set(assess(self.sources, {}).values()), {UNKNOWN})

    def test_sin_datos_reales(self):
        own = (ROOT / "tests/test_brechas_factory_05.py").read_text(
            encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(own)):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports,
                             {"__future__", "ast", "pathlib", "runpy",
                              "sys", "unittest"})
        self.assertEqual(set(WITNESSES), LOCAL_IDS)
        self.assertTrue(all((ROOT / "tests" / item[0]).is_file()
                            for item in WITNESSES.values()))
        self.assertEqual(set(GAPS), EXTERNAL_IDS)

    def test_estados_unknown_explicitos(self):
        for key in IDS:
            with self.subTest(key=key):
                for forged in (None, True, "success",
                               {"ci": "success", "merged": True},
                               {"owner": "APPROVED"},
                               {"production": "VALIDATED_IN_PRODUCTION"}):
                    self.assertEqual(operational_attestation(key, forged),
                                     UNKNOWN)
                if key in EXTERNAL_IDS:
                    self.assertEqual(assess(self.sources,
                                            self.evidence)[key], UNKNOWN)
                    self.assertTrue(GAPS[key].startswith("UNKNOWN:"))
                else:
                    less = {**self.evidence, key: False}
                    self.assertEqual(assess(self.sources, less)[key], UNKNOWN)
        self.assertEqual(set(assess(
            self.sources,
            {key: "success" for key in LOCAL_IDS}).values()), {UNKNOWN})


if __name__ == "__main__":
    unittest.main()
