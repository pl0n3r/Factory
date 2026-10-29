#!/usr/bin/env python3
"""Factory #1636: 16 clauses on guardrail candidates and the F2 read-only sweep.

Evidence for a local contract does not authorize promotion, tag movement,
workflow deletion, publication, external migration or production readiness.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evolution.constitution import validate_candidate
from evolution.experience_guardrails import (
    ExperienceGuardrailError, MAX_LESSONS, MIN_OCCURRENCES,
    compile_guardrail_candidates,
)
from scripts import f2_caller_preflight as f2

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
GUARDRAILS = "docs/experience-guardrails.md"
MIGRATION = "docs/f2-caller-migration.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"

# Each matrix row is linked to its original exact source line. These three
# external/adoption clauses remain UNKNOWN even if local code works.
CLAUSES = {
    "docs/experience-guardrails.md:L32-U1": (GUARDRAILS, "Por defecto se requieren al menos"),
    "docs/experience-guardrails.md:L36-U1": (GUARDRAILS, "El compilador acepta hasta 32"),
    "docs/experience-guardrails.md:L4-U1": (GUARDRAILS, "Nunca promueve una regla directamente a"),
    "docs/experience-guardrails.md:L43-U1": (GUARDRAILS, "fingerprint determinista del patrón"),
    "docs/experience-guardrails.md:L44-U1": (GUARDRAILS, "ids y fuentes de todas las lecciones origen"),
    "docs/experience-guardrails.md:L45-U1": (GUARDRAILS, "prevención esperada"),
    "docs/experience-guardrails.md:L46-U1": (GUARDRAILS, "ocurrencias"),
    "docs/experience-guardrails.md:L47-U1": (GUARDRAILS, "candidato constitucional bajo"),
    "docs/experience-guardrails.md:L49-U1": (GUARDRAILS, "rollback `revert`"),
    "docs/experience-guardrails.md:L5-U1": (GUARDRAILS, "stable y nunca modifica las lecciones históricas"),
    "docs/experience-guardrails.md:L50-U1": (GUARDRAILS, "fingerprint validado por Constitution"),
    "docs/experience-guardrails.md:L53-U1": (GUARDRAILS, "promoción posterior debe recorrer Evolution Engine / Factory Lab"),
    "docs/experience-guardrails.md:L54-U1": (GUARDRAILS, "no puede convertir el candidato en autoridad estable"),
    "docs/f2-caller-migration.md:L11-U1": (MIGRATION, "El código `0` (`SAFE`) significa"),
    "docs/f2-caller-migration.md:L15-U1": (MIGRATION, "Este inventario no representa otros forks"),
    "docs/f2-caller-migration.md:L15-U2": (MIGRATION, "Para publicar un reemplazo o retirar un reusable"),
}
LOCAL_KEYS = set(CLAUSES) - {
    "docs/experience-guardrails.md:L53-U1",
    "docs/f2-caller-migration.md:L15-U1",
    "docs/f2-caller-migration.md:L15-U2",
}


def original_sources() -> dict[str, str]:
    """Read only the three original checkout documents, never remote state."""
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in (MATRIX, GUARDRAILS, MIGRATION)}


def matrix_rows(raw: object) -> dict[str, str]:
    """Reject duplicates, missing provenance, altered states and malformed rows."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matrix missing")
    found: dict[str, str] = {}
    for line in raw.splitlines():
        normalized = line.lstrip()
        for key, (_, phrase) in CLAUSES.items():
            if not normalized.startswith("| `" + key + "` |"):
                continue
            if key in found:
                raise ValueError("UNKNOWN: duplicate row " + key)
            parts = [piece.strip() for piece in normalized.strip().strip("|").split("|")]
            if (len(parts) < 5 or parts[0] != "`" + key + "`"
                    or parts[2] != "NO_VERIFICABLE"
                    or phrase.casefold() not in parts[1].casefold()
                    or not parts[3] or not parts[4]
                    or "No se confirmó test + PR fusionado" not in parts[3]):
                raise ValueError("UNKNOWN: changed or ambiguous row " + key)
            found[key] = parts[1]
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: missing coverage IDs")
    return found


def source_matches(key: str, docs: dict[str, str]) -> bool:
    """Cross-check the original line: a matrix-only assertion is insufficient."""
    if key not in CLAUSES or not isinstance(docs, dict):
        return False
    path, phrase = CLAUSES[key]
    original = docs.get(path)
    if not isinstance(original, str):
        return False
    try:
        line_no = int(key.split(":L", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return False
    lines = original.splitlines()
    return 1 <= line_no <= len(lines) and phrase.casefold() in lines[line_no - 1].casefold()


def synthetic_lesson(number: int, *, source: str | None = None) -> dict[str, str]:
    """Valid lesson fixture, with no customer data or remote APIs."""
    return {
        "id": f"synthetic-lesson-{number:02d}",
        "project": "pl0n3r/factory",
        "kind": "incident",
        "occurred_at": "2026-09-20T12:00:00Z",
        "what": "A synthetic CI workflow drifted from its contract.",
        "why": "A shared workflow was copied locally.",
        "prevention": "Reuse the central workflow with a pinned reference.",
        "source": source or f"pl0n3r/factory#{200 + number}",
    }


def guardrail_proof() -> dict[str, bool]:
    """Exercise compiler invariants with positive, negative and boundary cases."""
    first, second = synthetic_lesson(1), synthetic_lesson(2)
    inputs = [deepcopy(first), deepcopy(second)]
    snapshot = deepcopy(inputs)
    produced = compile_guardrail_candidates(inputs)
    reversed_output = compile_guardrail_candidates(list(reversed(inputs)))
    if len(produced) != 1 or len(reversed_output) != 1:
        return dict.fromkeys(CLAUSES, False)
    candidate = produced[0]
    proposal = candidate["candidate"]
    change = proposal["changes"][0]
    value = change["value"]
    origins = value["origins"]
    try:
        compile_guardrail_candidates(inputs, min_occurrences=1)
    except ExperienceGuardrailError:
        rejects_small_threshold = True
    else:
        rejects_small_threshold = False
    try:
        compile_guardrail_candidates([synthetic_lesson(i) for i in range(33)])
    except ExperienceGuardrailError:
        rejects_too_many = True
    else:
        rejects_too_many = False
    thirty_two = compile_guardrail_candidates([synthetic_lesson(i) for i in range(32)])
    two_same_source = compile_guardrail_candidates([
        first, synthetic_lesson(2, source=first["source"]),
    ])
    checks = {
        "docs/experience-guardrails.md:L32-U1": (
            MIN_OCCURRENCES == 2 and not compile_guardrail_candidates([first])
            and not two_same_source and len(produced) == 1),
        "docs/experience-guardrails.md:L36-U1": (
            MAX_LESSONS == 32 and len(thirty_two) == 1
            and thirty_two[0]["occurrences"] == 32
            and rejects_small_threshold and rejects_too_many),
        "docs/experience-guardrails.md:L4-U1": (
            change["operation"] == "add" and value["status"] == "candidate"
            and value["lifecycle"]["state"] == "candidate"),
        "docs/experience-guardrails.md:L43-U1": (
            candidate["pattern_fingerprint"] == reversed_output[0]["pattern_fingerprint"]
            and len(candidate["pattern_fingerprint"]) == 64),
        "docs/experience-guardrails.md:L44-U1": (
            candidate["lesson_ids"] == [first["id"], second["id"]]
            and candidate["sources"] == sorted([first["source"], second["source"]])
            and {(x["lesson_id"], x["source"]) for x in origins}
            == {(first["id"], first["source"]), (second["id"], second["source"])}),
        "docs/experience-guardrails.md:L45-U1": (
            candidate["expected_prevention"] == first["prevention"]
            and value["expected_prevention"] == first["prevention"]),
        "docs/experience-guardrails.md:L46-U1": (
            candidate["occurrences"] == value["occurrences"] == len(origins) == 2),
        "docs/experience-guardrails.md:L47-U1": (
            change["path"] == "evolution_state.heuristics." + candidate["guardrail_id"]
            and value["guardrail_id"] == candidate["guardrail_id"]),
        "docs/experience-guardrails.md:L49-U1": (
            proposal["rollback"] == {"reversible": True, "strategy": "revert"}),
        "docs/experience-guardrails.md:L5-U1": inputs == snapshot,
        "docs/experience-guardrails.md:L50-U1": (
            validate_candidate(proposal) == candidate["candidate_fingerprint"]
            == reversed_output[0]["candidate_fingerprint"]),
        "docs/experience-guardrails.md:L54-U1": (
            value["status"] == "candidate" and change["operation"] == "add"
            and change["path"].startswith("evolution_state.heuristics.")),
    }
    return checks


def f2_proof() -> bool:
    """A SAFE inventory is scoped to six checkouts; missing and used fail closed."""
    with TemporaryDirectory(prefix="factory-1636-") as directory:
        root = Path(directory)
        for name in f2.CONSUMERS:
            (root / name / ".github/workflows").mkdir(parents=True)
        safe = f2.audit(root, ["readme.yml"])
        workflow = root / f2.CONSUMERS[0] / ".github/workflows" / "caller.yml"
        workflow.write_text("jobs:\n  audit:\n    uses: pl0n3r/factory/.github/workflows/readme.yml@v1\n", encoding="utf-8")
        called = f2.audit(root, ["readme.yml"])
        workflow.unlink()
        missing = root / f2.CONSUMERS[-1] / ".github/workflows"
        missing.rmdir()
        incomplete = f2.audit(root, ["readme.yml"])
    return (safe["status"] == "SAFE" and safe["references"] == []
            and safe["scanned_consumers"] == list(f2.CONSUMERS)
            and "no autoriza" in safe["scope"]
            and called["status"] == "BLOCKED" and len(called["references"]) == 1
            and incomplete["status"] == "BLOCKED"
            and f2.CONSUMERS[-1] in incomplete["missing_consumers"])


def proof() -> dict[str, bool]:
    """Only these 13 pure, checkout-local invariants can earn LOCAL_CONTRACT."""
    checks = guardrail_proof()
    checks["docs/f2-caller-migration.md:L11-U1"] = f2_proof()
    return checks


def assess(docs: object, checks: object) -> dict[str, str]:
    """Missing, ambiguous or altered documents invalidate all verdicts."""
    result = dict.fromkeys(CLAUSES, UNKNOWN)
    if not isinstance(docs, dict) or not isinstance(checks, dict):
        return result
    if any(not isinstance(docs.get(path), str) or not docs[path]
           for path in (MATRIX, GUARDRAILS, MIGRATION)):
        return result
    try:
        matrix_rows(docs[MATRIX])
    except ValueError:
        return result
    if (set(checks) != LOCAL_KEYS
            or any(type(value) is not bool for value in checks.values())
            or not all(source_matches(key, docs) for key in CLAUSES)):
        return result
    for key in LOCAL_KEYS:
        if checks[key]:
            result[key] = LOCAL
    return result


class BrechasFactory18Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        docs, checks = original_sources(), proof()
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(matrix_rows(docs[MATRIX])))
        self.assertEqual(LOCAL_KEYS, set(checks))
        self.assertTrue(all(checks.values()))
        self.assertTrue(all(source_matches(key, docs) for key in CLAUSES))
        verdicts = assess(docs, checks)
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertEqual(LOCAL if key in LOCAL_KEYS else UNKNOWN, verdicts[key])

    def test_falla_cerrado(self) -> None:
        docs, checks = original_sources(), proof()
        for key in CLAUSES:
            original = next(line for line in docs[MATRIX].splitlines()
                            if line.startswith("| `" + key + "` |"))
            for invalid in (docs[MATRIX].replace(original, "", 1),
                            docs[MATRIX] + "\n  " + original,
                            docs[MATRIX].replace(original, original.replace(
                                "NO_VERIFICABLE", "CUBIERTO", 1), 1)):
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, UNKNOWN):
                    matrix_rows(invalid)
                self.assertEqual({UNKNOWN}, set(assess({**docs, MATRIX: invalid}, checks).values()))
        self.assertEqual({UNKNOWN}, set(assess({}, checks).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, {}).values()))
        for key in LOCAL_KEYS:
            self.assertEqual(UNKNOWN, assess(docs, {**checks, key: None})[key])
        for key in CLAUSES:
            path, _ = CLAUSES[key]
            self.assertEqual(UNKNOWN, assess({**docs, path: ""}, checks)[key])

    def test_sin_datos_reales(self) -> None:
        text = Path(__file__).read_text(encoding="utf-8")
        syntax = ast.parse(text)
        imports = {alias.name.split(".")[0] for node in ast.walk(syntax)
                   if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module.split(".")[0] for node in ast.walk(syntax)
                    if isinstance(node, ast.ImportFrom) and node.module}
        self.assertFalse(imports & {"requests", "httpx", "socket", "subprocess", "urllib"})
        self.assertNotIn("BEGIN PRIVATE KEY", text)
        self.assertEqual({MATRIX, GUARDRAILS, MIGRATION}, set(original_sources()))
        self.assertTrue(all(not Path(path).is_absolute() for path in original_sources()))

    def test_estados_unknown_explicitos(self) -> None:
        docs, checks = original_sources(), proof()
        result = assess(docs, checks)
        for key in CLAUSES:
            with self.subTest(key=key):
                row = next(line for line in docs[MATRIX].splitlines()
                           if line.startswith("| `" + key + "` |"))
                self.assertEqual("NO_VERIFICABLE", row.split(" | ")[2])
                self.assertIn(result[key], (LOCAL, UNKNOWN))
        for key in set(CLAUSES) - LOCAL_KEYS:
            self.assertEqual(UNKNOWN, result[key])
        # A green local test never decides external callers, a release, or promotion.
        self.assertNotIn("PROMOTED", result.values())
        self.assertNotIn("SAFE_TO_PUBLISH", result.values())


if __name__ == "__main__":
    unittest.main()
