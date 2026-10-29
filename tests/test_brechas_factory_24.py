#!/usr/bin/env python3
"""Factory #1642: 16 synthetic gaps, with independent fail-closed evidence.

A local assertion is not proof of a real execution, V3 lease, provider
contract, destructive permission, CI result, or released capability.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from evolution.constitution import PROTECTED_INVARIANTS, validate_candidate
from evolution.immune import ImmuneError, compile_immunity_candidate
from evolution.pruning import (
    PROTECTED_CAPABILITIES, PruningError, compile_pruning_candidate,
    evaluate_pruning,
)
from evolution.repair import compile_repair_plan
from scripts import issue_contract_preflight as preflight

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
TICK = chr(96)

# Each source excerpt is pinned to the original matrix unit, not to a
# speculative production capability. B-clauses are semantic (no line number).
CLAUSES = {
    "docs/growth-pruning.md:L48-U1":
        ("docs/growth-pruning.md", "La ejecución real debe atravesar Evolution Engine"),
    "docs/growth-pruning.md:L52-U1":
        ("docs/growth-pruning.md", "Nunca pueden podarse las dimensiones constitucionales"),
    "docs/growth-pruning.md:L60-U1":
        ("docs/growth-pruning.md", "Pruning falla cerrado antes de evaluar"),
    "docs/growth-pruning.md:L64-U1":
        ("docs/growth-pruning.md", "borrar historia"),
    "docs/growth-pruning.md:L65-U1":
        ("docs/growth-pruning.md", "retirar Constitution o controles protegidos"),
    "docs/growth-pruning.md:L66-U1":
        ("docs/growth-pruning.md", "mutar stable"),
    "docs/growth-pruning.md:L67-U1":
        ("docs/growth-pruning.md", "promover candidatos automáticamente"),
    "docs/immune-repair.md:B03":
        ("docs/immune-repair.md", "TrustedDecisionSource"),
    "docs/immune-repair.md:B04":
        ("docs/immune-repair.md", "TrustedIncidentRegistry"),
    "docs/inventario-tecnico-datos-productos.md:B01":
        ("docs/inventario-tecnico-datos-productos.md",
         "Si cualquiera cambia, este inventario debe considerarse histórico"),
    "docs/inventario-tecnico-datos-productos.md:B02":
        ("docs/inventario-tecnico-datos-productos.md",
         "no identificado; el gateway actual es nulo"),
    "docs/issue-contract-preflight.md:L19-U1":
        ("docs/issue-contract-preflight.md", "valida primero las secciones y criterios"),
    "docs/issue-contract-preflight.md:L20-U1":
        ("docs/issue-contract-preflight.md", "fija el fingerprint con"),
    "docs/issue-contract-preflight.md:L21-U1":
        ("docs/issue-contract-preflight.md", "valida el marker con"),
    "docs/issue-contract-preflight.md:L22-U1":
        ("docs/issue-contract-preflight.md", "fija su identidad con"),
    "docs/issue-contract-preflight.md:L24-U1":
        ("docs/issue-contract-preflight.md", "Un marker ausente o inválido"),
}

BODY = """### Contexto
Contrato local de prueba de Factory #1642.

### Alcance
Analizar cláusulas sin red.

### Fuera de alcance
Producción, secretos, reservas y datos reales.

### Criterios de aceptación
- [ ] [AC-01] Contrato verificable.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"test","target":"tests/test_brechas_factory_24.py::BrechasFactory24Tests::test_contrato_principal"}]} -->

### Rutas reclamadas
- tests/test_brechas_factory_24.py
<!-- factory-plan-task {"version":1,"epic":1082,"task_key":"BRECHAS_FACTORY_24_V1","order":30,"owner":"pl0n3r","roles":["ingenieria-software","qa"],"depends_on":[],"paths":["tests/test_brechas_factory_24.py"]} -->
"""


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Require exactly 16 unpromoted, well-formed clauses in the census."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matrix not available")
    found = {}
    for line in raw.splitlines():
        for key in CLAUSES:
            if not line.startswith("| " + TICK + key + TICK + " |"):
                continue
            if key in found:
                raise ValueError("UNKNOWN: duplicate " + key)
            cells = tuple(x.strip() for x in line.strip("|").split("|"))
            if (len(cells) != 5 or cells[0] != TICK + key + TICK
                    or cells[2] != "NO_VERIFICABLE"
                    or len(cells[1]) < 10 or len(cells[3]) < 16):
                raise ValueError("UNKNOWN: malformed or promoted " + key)
            found[key] = cells
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: missing clauses")
    return found


def source_clause(key: str, docs: dict[str, str]) -> bool:
    if key not in CLAUSES:
        return False
    path, phrase = CLAUSES[key]
    original = docs.get(path)
    if type(original) is not str or not original:
        return False
    match = re.search(r":L([0-9]+)-U[0-9]+$", key)
    if match:
        line = int(match.group(1))
        lines = original.splitlines()
        return 1 <= line <= len(lines) and phrase in lines[line - 1]
    return phrase in original


def rejected(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except (ValueError, TypeError):
        return True
    return False


def prune_args(**overrides):
    return {
        **{
            "capability": "synthetic obsolete renderer",
            "usage_count": 0,
            "age_days": 180,
            "value_score": 0.1,
            "evidence": ["synthetic:check-1", "synthetic:check-2"],
            "parent_fingerprint": "a" * 64,
        },
        **overrides,
    }


def checks() -> dict[str, bool]:
    """One concrete local behavioral or provenance-negative check per unit."""
    args = prune_args()
    evaluation = evaluate_pruning(**args)
    compiled = compile_pruning_candidate(evaluation, **args)
    candidate = compiled["candidate"]
    change = candidate["changes"][0]

    protected_dimensions = all(
        rejected(evaluate_pruning, **prune_args(capability=name))
        for name in PROTECTED_INVARIANTS
    )
    protected_controls = all(
        rejected(evaluate_pruning, **prune_args(capability=name))
        for name in ("constitution", "human-gates", "rollback", "audit-trail")
    )
    # The protected check must run before bad usage/age/value is read.
    protected_first = False
    try:
        evaluate_pruning(**prune_args(
            capability="constitution", usage_count="invalid", age_days=-2,
            value_score="invalid",
        ))
    except PruningError as exc:
        protected_first = "protegida" in str(exc)

    destructive = compile_repair_plan(
        diagnosis="synthetic damage", actions=["synthetic reversible repair"],
        verification=["synthetic check"],
        rollback={"strategy": "revert", "steps": ["synthetic undo"]},
        destructive=True,
        human_authority={"approved": True, "decision_ref": "synthetic-owner-ref"},
        decision_evidence={"author_association": "OWNER", "status": "resolved"},
        # No authenticated decision_source: a caller dict has no authority.
    )
    no_registry = rejected(
        compile_immunity_candidate,
        failure_signature="synthetic repeated incident",
        incident_ids=["synthetic-incident-1", "synthetic-incident-2"],
        expected_prevention="synthetic prevention", incident_registry=None,
    )
    self_signed = rejected(
        compile_immunity_candidate,
        failure_signature="synthetic repeated incident",
        expected_prevention="synthetic prevention",
        incident_snapshots=[{"incident_id": "fake"}, {"incident_id": "fake2"}],
    )

    inventory = (ROOT / "docs/inventario-tecnico-datos-productos.md").read_text(
        encoding="utf-8"
    )
    recorded_shas = (
        "02be616b1bb8f33f7da601a0cca33e5c0e4dcc79",
        "8c59ea017b5cb8f90985cf9aae8e32d59f93c65c",
        "138b1babac0ff6797ad9e0f3ccb0fbda0f793452",
    )

    with (patch.object(preflight, "parse_contract",
                       wraps=preflight.parse_contract) as parse_a,
          patch.object(preflight, "contract_fingerprint",
                       wraps=preflight.contract_fingerprint) as hash_a,
          patch.object(preflight, "parse_task_marker",
                       wraps=preflight.parse_task_marker) as parse_t,
          patch.object(preflight, "task_marker_fingerprint",
                       wraps=preflight.task_marker_fingerprint) as hash_t):
        contract = preflight.evaluate_issue_body(BODY)
        calls = (parse_a.call_count, hash_a.call_count,
                 parse_t.call_count, hash_t.call_count)

    malformed = BODY.replace("<!-- factory-plan-task ", "<!-- removed-task ", 1)
    fail_closed = False
    try:
        preflight.evaluate_issue_body(malformed)
    except preflight.IssueContractPreflightError as exc:
        fail_closed = exc.code == "task_missing"
    missing_acceptance = BODY.replace("### Criterios de aceptación",
                                      "### Unrecognized", 1)
    fail_closed &= rejected(preflight.evaluate_issue_body, missing_acceptance)

    result = {
        "docs/growth-pruning.md:L48-U1":
            evaluation["eligible"] and validate_candidate(candidate)
            == compiled["candidate_fingerprint"]
            and change["operation"] == "add"
            and candidate["rollback"]["reversible"] is True,
        "docs/growth-pruning.md:L52-U1":
            protected_dimensions
            and set(PROTECTED_INVARIANTS).issubset(PROTECTED_CAPABILITIES),
        "docs/growth-pruning.md:L60-U1": protected_first,
        "docs/growth-pruning.md:L64-U1":
            compiled["lineage"]["history_preserved"] is True
            and candidate["rollback"]["strategy"] == "restore_baseline",
        "docs/growth-pruning.md:L65-U1": protected_controls,
        "docs/growth-pruning.md:L66-U1":
            change["path"].startswith("evolution_state.heuristics.")
            and "stable" not in change["path"],
        "docs/growth-pruning.md:L67-U1":
            change["value"]["status"] == "prune-candidate"
            and compiled["candidate"] == candidate,
        "docs/immune-repair.md:B03":
            destructive["authority"]["required"] == "human"
            and destructive["authority"]["approved"] is False
            and destructive["authorized_execution_ready"] is False
            and destructive["automatic_execution_allowed"] is False,
        "docs/immune-repair.md:B04":
            no_registry and self_signed,
        "docs/inventario-tecnico-datos-productos.md:B01":
            all(sha in inventory for sha in recorded_shas)
            and "histórico hasta revalidarlo" in inventory
            and "read-only" in inventory,
        "docs/inventario-tecnico-datos-productos.md:B02":
            "gateway actual es nulo" in inventory
            and "Google Tag Manager" in inventory
            and "GA4" in inventory
            and "no decide si una entidad actúa como responsable" in inventory,
        "docs/issue-contract-preflight.md:L19-U1":
            calls[0] == 1 and contract["valid"] is True,
        "docs/issue-contract-preflight.md:L20-U1":
            calls[1] == 1
            and re.fullmatch("[a-f0-9]{64}", contract["acceptance_sha256"])
            is not None,
        "docs/issue-contract-preflight.md:L21-U1":
            calls[2] == 1
            and contract["paths"] == ["tests/test_brechas_factory_24.py"],
        "docs/issue-contract-preflight.md:L22-U1":
            calls[3] == 1
            and re.fullmatch("[a-f0-9]{64}", contract["task_marker_sha256"])
            is not None,
        "docs/issue-contract-preflight.md:L24-U1": fail_closed,
    }
    return result


def verdict(matrix: object, docs: object, tests: object) -> dict[str, dict[str, str]]:
    """Missing, malformed or caller-provided evidence cannot claim success."""
    result = {
        key: {"local": UNKNOWN, "operational": UNKNOWN, "release": UNKNOWN}
        for key in CLAUSES
    }
    try:
        matrix_rows(matrix)
    except ValueError:
        return result
    if (type(docs) is not dict or set(docs) != {v[0] for v in CLAUSES.values()}
            or type(tests) is not dict or set(tests) != set(CLAUSES)
            or any(type(value) is not bool for value in tests.values())):
        return result
    for key, passed in tests.items():
        if passed and source_clause(key, docs):
            result[key]["local"] = LOCAL
    return result


class BrechasFactory24Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: each of 16 gaps has a direct assertion or explicit UNKNOWN."""
        matrix = (ROOT / MATRIX).read_text(encoding="utf-8")
        docs = {path: (ROOT / path).read_text(encoding="utf-8")
                for path, _ in CLAUSES.values()}
        verified = checks()
        self.assertEqual(len(CLAUSES), 16)
        self.assertEqual(set(matrix_rows(matrix)), set(CLAUSES))
        self.assertEqual(set(verified), set(CLAUSES))
        result = verdict(matrix, docs, verified)
        for key in CLAUSES:
            with self.subTest(unit=key):
                self.assertTrue(source_clause(key, docs), "UNKNOWN: source drift")
                self.assertTrue(verified[key], "UNKNOWN: probe did not prove contract")
                self.assertEqual(result[key]["local"], LOCAL)
                self.assertEqual(result[key]["operational"], UNKNOWN)

    def test_falla_cerrado(self):
        """AC-02: duplicates, missing, promotions and forged proof are rejected."""
        matrix = (ROOT / MATRIX).read_text(encoding="utf-8")
        docs = {path: (ROOT / path).read_text(encoding="utf-8")
                for path, _ in CLAUSES.values()}
        verified = checks()
        for key in CLAUSES:
            prefix = "| " + TICK + key + TICK + " |"
            line = next(line for line in matrix.splitlines()
                        if line.startswith(prefix))
            for invalid in (
                matrix.replace(line, "", 1),
                matrix + "\n" + line,
                matrix.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
                matrix.replace(line, "| " + TICK + key + TICK + " | broken", 1),
            ):
                with self.subTest(unit=key):
                    with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                        matrix_rows(invalid)
            path = CLAUSES[key][0]
            damaged = dict(docs)
            damaged[path] = ""
            self.assertEqual(verdict(matrix, damaged, verified)[key]["local"], UNKNOWN)
        self.assertTrue(all(
            v["local"] == UNKNOWN
            for v in verdict(matrix, docs, {"ci": True}).values()
        ))
        damaged_tests = dict(verified)
        damaged_tests[next(iter(CLAUSES))] = None
        self.assertTrue(all(
            v["local"] == UNKNOWN
            for v in verdict(matrix, docs, damaged_tests).values()
        ))

    def test_sin_datos_reales(self):
        """AC-03: all probes are synthetic, deterministic and network-free."""
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {alias.name.split(".")[0]
                    for node in ast.walk(tree) if isinstance(node, ast.Import)
                    for alias in node.names}
        imported |= {node.module.split(".")[0]
                     for node in ast.walk(tree)
                     if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imported & {
            "requests", "urllib", "socket", "httpx", "subprocess",
            "sqlite3", "playwright", "selenium",
        })
        self.assertNotIn("https://api.github.com", source)
        self.assertEqual(set(checks()), set(CLAUSES))
        self.assertEqual(BODY.count("factory-acceptance"), 1)

    def test_estados_unknown_explicitos(self):
        """AC-04: local tests cannot certify coordination or real services."""
        matrix = (ROOT / MATRIX).read_text(encoding="utf-8")
        docs = {path: (ROOT / path).read_text(encoding="utf-8")
                for path, _ in CLAUSES.values()}
        confirmed = verdict(matrix, docs, checks())
        for key in CLAUSES:
            with self.subTest(unit=key):
                self.assertEqual(confirmed[key]["operational"], UNKNOWN)
                self.assertEqual(confirmed[key]["release"], UNKNOWN)
                self.assertEqual(verdict("", docs, checks())[key]["local"], UNKNOWN)
                self.assertEqual(verdict(matrix, {}, checks())[key]["local"], UNKNOWN)
        self.assertTrue(all(value["operational"] == UNKNOWN
                            for value in confirmed.values()))


if __name__ == "__main__":
    unittest.main()
