#!/usr/bin/env python3
"""Factory #1635: 16 offline clauses for Evolution Engine and Guardrail Compiler.

A successful local regression is not evidence of a deployed workflow,
constitution promotion, a human decision, or production readiness.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from evolution.constitution import ConstitutionError, validate_candidate
from evolution.engine import EvolutionEngine
from evolution.models import EvolutionError
from evolution.experience_guardrails import (
    ExperienceGuardrailError, compile_guardrail_candidates,
)
from lecciones.memoria import LessonValidationError, validate_lesson


ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
EVOLUTION = "docs/evolution-engine.md"
GUARDRAILS = "docs/experience-guardrails.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"

# The exact source line and matrix record must both remain intact.
CLAUSES = {
    "docs/evolution-engine.md:L22-U1": (EVOLUTION, "`parent_generation`"),
    "docs/evolution-engine.md:L25-U1": (EVOLUTION, "huella del candidato validado"),
    "docs/evolution-engine.md:L26-U1": (EVOLUTION, "`decision` cuando la etapa"),
    "docs/evolution-engine.md:L27-U1": (EVOLUTION, "`restores_generation`"),
    "docs/evolution-engine.md:L29-U1": (EVOLUTION, "El candidato se valida antes"),
    "docs/evolution-engine.md:L35-U1": (EVOLUTION, "exige una decisión explícita"),
    "docs/evolution-engine.md:L41-U1": (EVOLUTION, "Rollback solo es válido"),
    "docs/experience-guardrails.md:L11-U1": (GUARDRAILS, "`what`: qué ocurrió"),
    "docs/experience-guardrails.md:L12-U1": (GUARDRAILS, "`why`: causa"),
    "docs/experience-guardrails.md:L13-U1": (GUARDRAILS, "`prevention`: prevención"),
    "docs/experience-guardrails.md:L14-U1": (GUARDRAILS, "`source`: Issue/PR"),
    "docs/experience-guardrails.md:L15-U1": (GUARDRAILS, "además de id, proyecto"),
    "docs/experience-guardrails.md:L17-U1": (GUARDRAILS, "Las lecciones se validan"),
    "docs/experience-guardrails.md:L24-U1": (GUARDRAILS, "causa normalizada"),
    "docs/experience-guardrails.md:L25-U1": (GUARDRAILS, "prevención normalizada"),
    "docs/experience-guardrails.md:L27-U1": (GUARDRAILS, "La normalización solo elimina"),
}


def documents() -> dict[str, str]:
    """Read canonical checkout sources, not the network or real lessons."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in (MATRIX, EVOLUTION, GUARDRAILS)}


def matrix_rows(raw: object) -> dict[str, str]:
    """Require every unique NO_VERIFICABLE row and its historical provenance."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matrix missing")
    found: dict[str, str] = {}
    for line in raw.splitlines():
        normalized = line.lstrip()
        for key, (_path, phrase) in CLAUSES.items():
            if not normalized.startswith("| `" + key + "` |"):
                continue
            if key in found:
                raise ValueError("UNKNOWN: duplicated " + key)
            cells = [part.strip() for part in normalized.strip("|").split("|")]
            if (len(cells) != 5 or cells[0] != "`" + key + "`"
                    or phrase.casefold() not in cells[1].casefold()
                    or cells[2] != "NO_VERIFICABLE"
                    or "No se confirmó test + PR fusionado" not in cells[3]
                    or "[contraste #1570]" not in cells[4]):
                raise ValueError("UNKNOWN: altered " + key)
            found[key] = cells[1]
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: rows missing")
    return found


def source_matches(key: str, docs: object) -> bool:
    if key not in CLAUSES or not isinstance(docs, dict):
        return False
    path, phrase = CLAUSES[key]
    source = docs.get(path)
    if not isinstance(source, str):
        return False
    try:
        n = int(key.split(":L", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return False
    lines = source.splitlines()
    return 1 <= n <= len(lines) and phrase.casefold() in lines[n - 1].casefold()


def candidate() -> dict[str, object]:
    """Synthetic constitution-compatible edit; no stable-authority paths."""
    return {
        "version": 1,
        "changes": [{
            "path": "evolution_state.heuristics.synthetic_guardrail",
            "operation": "add",
            "value": {"status": "candidate"},
        }],
        "evidence": ["factory#1635:synthetic"],
        "rollback": {"reversible": True, "strategy": "revert"},
    }


def evolution_proof() -> dict[str, bool]:
    """Exercise validation, lineage, decisions, immutability and rollback."""
    key = "docs/evolution-engine.md:"
    data = candidate()
    fingerprint = validate_candidate(data)
    before = deepcopy(data)
    engine = EvolutionEngine(data, reason="synthetic start", evidence=["test:1635"])
    initial = engine.current
    try:
        malformed = deepcopy(data)
        malformed["changes"][0]["path"] = "stable_authority.sources"
        EvolutionEngine(malformed, reason="invalid", evidence=["test:invalid"])
    except ConstitutionError:
        rejected_invalid = True
    else:
        rejected_invalid = False

    try:
        engine.rollback(0, reason="early", evidence=["test:early"])
    except EvolutionError:
        rejected_early = True
    else:
        rejected_early = False

    for stage in engine.lifecycle[1:-1]:
        args = {"decision": "adopt"} if stage == "promote_or_reject" else {}
        engine.transition(stage, reason="stage:" + stage,
                          evidence=["test:" + stage], **args)
    before_rollback = engine.history
    promote = next(record for record in before_rollback
                   if record.stage == "promote_or_reject")
    rollback = engine.rollback(2, reason="synthetic restore",
                               evidence=["test:restore"])
    try:
        engine.rollback(0, reason="again", evidence=["test:again"])
    except EvolutionError:
        rejected_repeat = True
    else:
        rejected_repeat = False

    other = EvolutionEngine(data, reason="another", evidence=["test:another"])
    for stage in other.lifecycle[1:]:
        if stage == "promote_or_reject":
            break
        other.transition(stage, reason="advance:" + stage,
                         evidence=["test:" + stage])
    before_decision = other.history
    invalid_decisions = []
    for decision in (None, "approve", True):
        try:
            other.transition("promote_or_reject", reason="invalid decision",
                             evidence=["test:invalid"], decision=decision)
        except EvolutionError:
            invalid_decisions.append(other.history == before_decision)
        else:
            invalid_decisions.append(False)
    reject = other.transition("promote_or_reject", reason="explicit reject",
                              evidence=["test:reject"], decision="reject")

    records = engine.history
    return {
        key + "L22-U1": (initial.parent_generation is None
                        and all(records[i].parent_generation == i - 1
                                for i in range(1, len(records)))),
        key + "L25-U1": (isinstance(fingerprint, str)
                        and len(fingerprint) == 64
                        and all(record.candidate_fingerprint == fingerprint
                                for record in records)),
        key + "L26-U1": (promote.decision == "adopt"
                        and all(record.decision is None
                                for record in records if record.stage != "promote_or_reject")),
        key + "L27-U1": (rollback.restores_generation == 2
                        and all(record.restores_generation is None
                                for record in before_rollback)),
        key + "L29-U1": (rejected_invalid and initial.generation == 0
                        and data == before),
        key + "L35-U1": (all(invalid_decisions)
                        and reject.decision == "reject"),
        key + "L41-U1": (rejected_early and rejected_repeat
                        and records[:-1] == before_rollback
                        and len(records) == len(before_rollback) + 1
                        and engine.active_generation == 2),
    }


def lesson(number: int, *, source: str | None = None,
           why: str = "CI drift in shared workflow",
           prevention: str = "Use a pinned central workflow") -> dict[str, str]:
    return {
        "id": f"synthetic-{number:03d}",
        "project": "pl0n3r/factory",
        "kind": "incident",
        "occurred_at": "2026-10-10T12:00:00Z",
        "what": "Synthetic workflow drifted from the expected contract",
        "why": why,
        "prevention": prevention,
        "source": source or f"pl0n3r/factory#{400 + number}",
    }


def rejects(action: object, error_type: type[Exception]) -> bool:
    try:
        action()
    except error_type:
        return True
    return False


def guardrail_proof() -> dict[str, bool]:
    """Validate all fields before grouping; only surface normalization counts."""
    prefix = "docs/experience-guardrails.md:"
    first, second = lesson(1), lesson(2)
    original = [deepcopy(first), deepcopy(second)]
    compiled = compile_guardrail_candidates(original)
    if len(compiled) != 1:
        return {key: False for key in CLAUSES if key.startswith(prefix)}
    record = compiled[0]
    required = {"id", "project", "kind", "occurred_at",
                "what", "why", "prevention", "source"}
    base_valid = set(validate_lesson(first, "synthetic")) == required | {"_sort_at"}
    checks = {}
    for field, line in (("what", 11), ("why", 12), ("prevention", 13),
                        ("source", 14)):
        bad = deepcopy(first)
        bad.pop(field)
        checks[prefix + f"L{line}-U1"] = (
            base_valid and bool(first[field])
            and rejects(lambda bad=bad: validate_lesson(bad, "synthetic"),
                        LessonValidationError)
            and rejects(lambda bad=bad: compile_guardrail_candidates([bad, second]),
                        ExperienceGuardrailError))
    invalid_meta = []
    for field in ("id", "project", "kind", "occurred_at"):
        bad = deepcopy(first)
        bad.pop(field)
        invalid_meta.append(rejects(
            lambda bad=bad: validate_lesson(bad, "synthetic"),
            LessonValidationError))
    checks[prefix + "L15-U1"] = (base_valid and all(invalid_meta)
                                    and original == [first, second])
    checks[prefix + "L17-U1"] = (
        rejects(lambda: compile_guardrail_candidates(
            [first, {**second, "kind": "unknown"}]), ExperienceGuardrailError)
        and rejects(lambda: compile_guardrail_candidates(
            [first, {**second, "source": "not a GitHub Issue"}]),
                    ExperienceGuardrailError)
        and record["occurrences"] == 2)

    why_equivalent = compile_guardrail_candidates([
        lesson(3, why="FÁLLO, de CÓDIGO!"),
        lesson(4, why=" fallo  de codigo "),
    ])
    why_different = compile_guardrail_candidates([
        lesson(5, why="A network call timed out"),
        lesson(6, why="The worker was given no permission"),
    ])
    prevention_equivalent = compile_guardrail_candidates([
        lesson(7, prevention="Revisar, EL CÓDIGO!"),
        lesson(8, prevention="revisar el codigo"),
    ])
    prevention_different = compile_guardrail_candidates([
        lesson(9, prevention="Retry once"),
        lesson(10, prevention="Ask a human before retrying"),
    ])
    checks[prefix + "L24-U1"] = (
        len(why_equivalent) == 1
        and why_equivalent[0]["occurrences"] == 2)
    checks[prefix + "L25-U1"] = (
        len(prevention_equivalent) == 1
        and prevention_equivalent[0]["occurrences"] == 2)
    checks[prefix + "L27-U1"] = (
        not why_different and not prevention_different
        and len(why_equivalent) == 1
        and len(prevention_equivalent) == 1)
    return checks


def proof() -> dict[str, bool]:
    return {**evolution_proof(), **guardrail_proof()}


def assess(docs: object, checks: object) -> dict[str, str]:
    """Refuse all promotion on missing, ambiguous or edited source evidence."""
    result = dict.fromkeys(CLAUSES, UNKNOWN)
    if not isinstance(docs, dict) or not isinstance(checks, dict):
        return result
    if any(type(docs.get(p)) is not str or not docs[p]
           for p in (MATRIX, EVOLUTION, GUARDRAILS)):
        return result
    try:
        matrix_rows(docs[MATRIX])
    except ValueError:
        return result
    if (set(checks) != set(CLAUSES)
            or any(type(value) is not bool for value in checks.values())
            or not all(source_matches(key, docs) for key in CLAUSES)):
        return result
    for key, verified in checks.items():
        if verified:
            result[key] = LOCAL
    return result


class BrechasFactory17Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs, evidence = documents(), proof()
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(docs[MATRIX])))
        self.assertEqual(set(CLAUSES), set(evidence))
        self.assertTrue(all(evidence.values()))
        self.assertTrue(all(source_matches(key, docs) for key in CLAUSES))
        self.assertEqual({LOCAL}, set(assess(docs, evidence).values()))

    def test_falla_cerrado(self) -> None:
        docs, evidence = documents(), proof()
        for key in CLAUSES:
            line = next(x for x in docs[MATRIX].splitlines()
                        if x.startswith("| `" + key + "` |"))
            for damaged in (
                docs[MATRIX].replace(line, "", 1),
                docs[MATRIX] + "\n" + line,
                docs[MATRIX].replace(line, line.replace(
                    "NO_VERIFICABLE", "CUBIERTO", 1), 1),
            ):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(damaged)
                self.assertEqual({UNKNOWN}, set(assess(
                    {**docs, MATRIX: damaged}, evidence).values()))
            path, _phrase = CLAUSES[key]
            original = docs[path].splitlines()
            n = int(key.split(":L", 1)[1].split("-", 1)[0])
            altered = list(original)
            altered[n - 1] = "[UNKNOWN: clause deleted]"
            self.assertEqual(UNKNOWN, assess(
                {**docs, path: "\n".join(altered)}, evidence)[key])
            self.assertEqual({UNKNOWN}, set(assess(
                docs, {**evidence, key: None}).values()))
        self.assertEqual({UNKNOWN}, set(assess({}, evidence).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))

    def test_sin_datos_reales(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        syntax = ast.parse(source)
        imports = {alias.name.split(".")[0] for node in ast.walk(syntax)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(syntax)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {
            "requests", "httpx", "urllib", "socket", "subprocess", "pymysql",
            "psycopg", "playwright", "selenium",
        })
        self.assertNotIn("BEGIN " + "PRIVATE KEY", source)
        self.assertEqual({MATRIX, EVOLUTION, GUARDRAILS}, set(documents()))
        self.assertTrue(all(not Path(x).is_absolute() for x in documents()))

    def test_estados_unknown_explicitos(self) -> None:
        docs, evidence = documents(), proof()
        for key in CLAUSES:
            with self.subTest(key=key):
                line = next(x for x in docs[MATRIX].splitlines()
                            if x.startswith("| `" + key + "` |"))
                self.assertEqual("NO_VERIFICABLE", line.split(" | ")[2])
                self.assertEqual(LOCAL, assess(docs, evidence)[key])
                for fake in (None, {}, {"production": True},
                             {**evidence, "live": True}):
                    self.assertEqual(UNKNOWN, assess(docs, fake)[key])
        self.assertNotIn("PROMOTED", assess(docs, evidence).values())
        self.assertNotIn("VALIDATED_IN_PRODUCTION", assess(docs, evidence).values())


if __name__ == "__main__":
    unittest.main()
