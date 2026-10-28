#!/usr/bin/env python3
"""Factory #1643: 16 synthetic, fail-closed preflight/lifecycle regressions.

Offline contract evidence never certifies a V3 lease, consumers, release or merge.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from evolution.knowledge_lifecycle import (
    KnowledgeLifecycleError, can_increase_autonomy, create_knowledge_record,
    effective_state, propose_pruning_candidates, transition_knowledge,
    validate_knowledge_record,
)
from scripts import issue_contract_preflight as preflight

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "docs/matriz-cobertura.md"
CONTRAST = "docs/contraste-factory_resto_3.md"
PREFLIGHT_DOC = "docs/issue-contract-preflight.md"
KNOWLEDGE_DOC = "docs/knowledge-lifecycle.md"
UNKNOWN = "UNKNOWN"
NOW = "2026-09-15T00:00:00Z"
NEW = "2026-09-01T00:00:00Z"
OLD = "2026-01-01T00:00:00Z"

# Stable identities from the original census (do not promote the matrix).
CLAUSES = {
    "docs/issue-contract-preflight.md:L28-U1": ("Este comando **no reserva trabajo**", PREFLIGHT_DOC),
    "docs/issue-contract-preflight.md:L28-U2": ("Solo valida texto local", PREFLIGHT_DOC),
    "docs/issue-contract-preflight.md:L3-U1": ("Antes de publicar ", PREFLIGHT_DOC),
    "docs/knowledge-lifecycle.md:L10-U1": ("**active**:", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L11-U1": ("**needs_review**:", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L11-U2": ("deja de aumentar autonomía", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L12-U1": ("**deprecated**:", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L13-U1": ("**archived**:", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L13-U2": ("nunca implica borrado", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L19-U1": ("provenance verificable", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L20-U1": ("last_validated_at", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L21-U1": ("content_fingerprint", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L22-U1": ("evidence class", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L23-U1": ("review_after_days", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L24-U1": ("history append-only", KNOWLEDGE_DOC),
    "docs/knowledge-lifecycle.md:L26-U1": ("no puede aumentar autonomía", KNOWLEDGE_DOC),
}
BODY = """### Contexto
Regresión sintética de contrato.

### Alcance
Validar acceptance y task marker localmente.

### Fuera de alcance
Sin GitHub, red, secretos ni datos de clientes.

### Criterios de aceptación
- [ ] [AC-01] contrato ejecutable.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"test","target":"tests/test_brechas_factory_25.py::BrechasFactory25Tests::test_contrato_principal"}]} -->

### Rutas reclamadas
- tests/test_brechas_factory_25.py
<!-- factory-plan-task {"version":1,"epic":1082,"task_key":"BRECHAS_FACTORY_25_V1","order":30,"owner":"pl0n3r","roles":["ingenieria-software","qa"],"depends_on":[],"paths":["tests/test_brechas_factory_25.py"]} -->
"""


def record(*, state: str = "active", validated: str = NEW) -> dict:
    return create_knowledge_record(
        knowledge_id="factory-rule-1643", knowledge_type="guardrail",
        content_fingerprint="a" * 64,
        provenance=["pl0n3r/Factory#1643@rev:fixture-a"],
        scope={"project": "pl0n3r/Factory", "domain": "knowledge"},
        created_at=OLD, last_validated_at=validated, last_useful_at=validated,
        confidence=0.9, evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


def rows(text: str, kind: str) -> dict[str, tuple[str, ...]]:
    """One complete, unpromoted row for each requirement in both references."""
    if type(text) is not str or kind not in ("matrix", "contrast"):
        raise ValueError("UNKNOWN: source invalid")
    result = {}
    for key, (phrase, doc) in CLAUSES.items():
        prefix = "| " + chr(96) + key + chr(96) + " |"
        matches = [line for line in text.splitlines() if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError("UNKNOWN: missing/duplicate " + key)
        cells = tuple(c.strip() for c in matches[0].strip("|").split("|"))
        if (len(cells) != (5 if kind == "matrix" else 6)
                or cells[0] != chr(96) + key + chr(96)
                or phrase not in cells[1]
                or cells[2] != "NO_VERIFICABLE"):
            raise ValueError("UNKNOWN: malformed/promoted " + key)
        if kind == "matrix":
            valid = ("Contraste #1571" in cells[3]
                     and "PR MERGED" in cells[3] and cells[4] == "—")
        else:
            valid = ("Sin aserción exacta + PR MERGED" in cells[5]
                     and ("issue_contract_preflight.py" in cells[3]
                          if doc == PREFLIGHT_DOC else
                          "knowledge_lifecycle.py" in cells[3]))
        if not valid:
            raise ValueError("UNKNOWN: uncertain provenance " + key)
        result[key] = cells
    return result


def original_line(docs: dict[str, str], key: str) -> bool:
    if key not in CLAUSES:
        return False
    phrase, path = CLAUSES[key]
    m = re.fullmatch(r".+:L([0-9]+)-U[0-9]+", key)
    lines = docs.get(path, "").splitlines()
    line = int(m.group(1)) if m else 0
    return 1 <= line <= len(lines) and phrase in lines[line - 1]


def operational(_key: object, _claim: object = None) -> str:
    return UNKNOWN


def evidence() -> dict[str, bool]:
    """Independent checks for all 16 IDs, without credentials or remote calls."""
    fresh, stale = record(), record(validated=OLD)
    retired = transition_knowledge(
        fresh, target_state="deprecated", at=NOW,
        evidence=["pl0n3r/Factory#1643@rev:fixture-b"], reason="superseded",
    )
    archived = transition_knowledge(
        retired, target_state="archived", at="2026-09-16T00:00:00Z",
        evidence=["pl0n3r/Factory#1643@rev:fixture-c"], reason="audit",
    )
    result = preflight.evaluate_issue_body(BODY)
    with (patch.object(preflight, "parse_contract", wraps=preflight.parse_contract) as a,
          patch.object(preflight, "contract_fingerprint", wraps=preflight.contract_fingerprint) as f,
          patch.object(preflight, "parse_task_marker", wraps=preflight.parse_task_marker) as t,
          patch.object(preflight, "task_marker_fingerprint", wraps=preflight.task_marker_fingerprint) as tf):
        reused = preflight.evaluate_issue_body(BODY)
        uses_parsers = (reused == result and a.call_count == 2
                        and f.call_count == t.call_count == tf.call_count == 1)
    sink = io.StringIO()
    exit_code = preflight.main([], stdin=io.StringIO(BODY), stdout=sink)
    data = json.loads(sink.getvalue())

    def invalid(changes: dict) -> bool:
        try:
            validate_knowledge_record(changes)
            return False
        except KnowledgeLifecycleError:
            return True

    without_scope = deepcopy(fresh)
    without_scope["scope"].pop("domain")
    invalid_time = deepcopy(fresh)
    invalid_time["last_useful_at"] = "2025-12-31T00:00:00Z"
    invalid_sha = deepcopy(fresh)
    invalid_sha["content_fingerprint"] = "a" * 63
    bad_policy = deepcopy(fresh)
    bad_policy["review_policy"]["expires_after_days"] = 20
    low_confidence = deepcopy(fresh)
    low_confidence["confidence"] = 0.5
    bad_history = deepcopy(archived)
    bad_history["history"].reverse()
    pruning = propose_pruning_candidates(
        [archived], now_at="2026-12-31T00:00:00Z",
    )
    history_preserved = (
        archived["history"][:len(retired["history"])] == retired["history"]
        and len(archived["history"]) == len(retired["history"]) + 1
    )
    return {
        "docs/issue-contract-preflight.md:L28-U1":
            exit_code == 0 and data["valid"] is True
            and not (set(data) & {"reservation_id", "lease", "branch", "merge"}),
        "docs/issue-contract-preflight.md:L28-U2": uses_parsers,
        "docs/issue-contract-preflight.md:L3-U1":
            result["valid"] and
            bool(re.fullmatch(r"[a-f0-9]{64}", result["acceptance_sha256"])) and
            bool(re.fullmatch(r"[a-f0-9]{64}", result["task_marker_sha256"])) and
            result["paths"] == ["tests/test_brechas_factory_25.py"],
        "docs/knowledge-lifecycle.md:L10-U1":
            effective_state(fresh, NOW) == "active"
            and can_increase_autonomy(fresh, NOW),
        "docs/knowledge-lifecycle.md:L11-U1":
            effective_state(stale, NOW) == "needs_review",
        "docs/knowledge-lifecycle.md:L11-U2":
            not can_increase_autonomy(stale, NOW),
        "docs/knowledge-lifecycle.md:L12-U1":
            retired["state"] == "deprecated"
            and not can_increase_autonomy(retired, NOW),
        "docs/knowledge-lifecycle.md:L13-U1":
            archived["state"] == "archived" and history_preserved,
        "docs/knowledge-lifecycle.md:L13-U2":
            bool(pruning) and all(
                p.get("delete") is False and p.get("history_preserved") is True
                for p in pruning),
        "docs/knowledge-lifecycle.md:L19-U1":
            fresh["provenance"] == ["pl0n3r/Factory#1643@rev:fixture-a"]
            and fresh["scope"]["domain"] == "knowledge" and invalid(without_scope),
        "docs/knowledge-lifecycle.md:L20-U1":
            all(k in fresh for k in ("created_at", "last_validated_at", "last_useful_at"))
            and invalid(invalid_time),
        "docs/knowledge-lifecycle.md:L21-U1":
            len(fresh["content_fingerprint"]) == 64 and invalid(invalid_sha),
        "docs/knowledge-lifecycle.md:L22-U1":
            fresh["evidence_class"] == "verified"
            and not can_increase_autonomy(low_confidence, NOW),
        "docs/knowledge-lifecycle.md:L23-U1":
            fresh["review_policy"] == {"review_after_days": 30, "expires_after_days": 90}
            and invalid(bad_policy),
        "docs/knowledge-lifecycle.md:L24-U1":
            history_preserved and invalid(bad_history),
        "docs/knowledge-lifecycle.md:L26-U1":
            not can_increase_autonomy(stale, NOW)
            and all(not can_increase_autonomy(record(state=s), NOW)
                    for s in ("candidate", "deprecated", "archived")),
    }


class BrechasFactory25Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: each of the 16 rows has its own executable regression."""
        matrix = (ROOT / MATRIX).read_text(encoding="utf-8")
        contrast = (ROOT / CONTRAST).read_text(encoding="utf-8")
        docs = {p: (ROOT / p).read_text(encoding="utf-8")
                for p in (PREFLIGHT_DOC, KNOWLEDGE_DOC)}
        self.assertEqual(set(rows(matrix, "matrix")), set(CLAUSES))
        self.assertEqual(set(rows(contrast, "contrast")), set(CLAUSES))
        checks = evidence()
        self.assertEqual(set(checks), set(CLAUSES))
        for key, result in checks.items():
            with self.subTest(unit=key):
                self.assertTrue(original_line(docs, key), "UNKNOWN: source drift")
                self.assertTrue(result, "UNKNOWN: behavior unverified")
                self.assertEqual(operational(key, result), UNKNOWN)

    def test_falla_cerrado(self) -> None:
        """AC-02: absent/duplicate/promoted/ambiguous rows fail closed."""
        docs = {p: (ROOT / p).read_text(encoding="utf-8")
                for p in (PREFLIGHT_DOC, KNOWLEDGE_DOC)}
        for path, kind in ((MATRIX, "matrix"), (CONTRAST, "contrast")):
            raw = (ROOT / path).read_text(encoding="utf-8")
            for key in CLAUSES:
                row = next(line for line in raw.splitlines()
                           if line.startswith("| " + chr(96) + key + chr(96) + " |"))
                for candidate in (
                    raw.replace(row, "", 1),
                    raw + "\n" + row,
                    raw.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
                    raw.replace(row, "| " + chr(96) + key + chr(96) + " | invalid", 1),
                ):
                    with self.subTest(unit=key, kind=kind):
                        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                            rows(candidate, kind)
                changed = dict(docs)
                path_doc = CLAUSES[key][1]
                changed[path_doc] = changed[path_doc].replace(CLAUSES[key][0], "", 1)
                self.assertFalse(original_line(changed, key))
        invalid_body = BODY.replace("### Contexto", "### Context", 1)
        with self.assertRaises(preflight.IssueContractPreflightError):
            preflight.evaluate_issue_body(invalid_body)

    def test_sin_datos_reales(self) -> None:
        """AC-03: in-memory, deterministic inputs; no HTTP, DB or credentials."""
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {a.name.split(".")[0] for n in ast.walk(tree)
                   if isinstance(n, ast.Import) for a in n.names}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(imports & {
            "requests", "httpx", "urllib", "socket", "subprocess",
            "sqlite3", "sqlalchemy", "selenium", "playwright",
        })
        self.assertEqual(len(CLAUSES), 16)
        self.assertNotIn("api_key", BODY.lower())
        self.assertTrue(all(evidence().values()))

    def test_estados_unknown_explicitos(self) -> None:
        """AC-04: a fixture cannot certify reservation, release or production."""
        for key in CLAUSES:
            with self.subTest(unit=key):
                for claim in (None, {}, True, {"ci": "success"},
                              {"reservation_id": "synthetic-v3"},
                              {"autonomy": "enabled"},
                              {"deploy": "VALIDATED_IN_PRODUCTION"},
                              {"pr": "merged", "test": "passed"}):
                    self.assertEqual(operational(key, claim), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
