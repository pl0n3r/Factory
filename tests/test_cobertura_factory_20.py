#!/usr/bin/env python3
"""#1811: real offline preflight and knowledge lifecycle regression contracts.

No reservations, external services, real data, live changes or matrix promotion.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest import mock
import urllib.request

from scripts import aceptacion_kit, issue_contract_preflight as preflight, orquestador_kit
from evolution import knowledge_lifecycle as knowledge

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
PRE = "docs/issue-contract-preflight.md:"
LIFE = "docs/knowledge-lifecycle.md:"
PRE_UNITS = ("L19-U1", "L20-U1", "L21-U1", "L22-U1",
             "L24-U1", "L28-U1", "L28-U2", "L3-U1")
LIFE_UNITS = ("L10-U1", "L11-U1", "L11-U2", "L12-U1", "L13-U1",
              "L13-U2", "L19-U1", "L20-U1", "L21-U1", "L22-U1",
              "L23-U1", "L24-U1")
IDS = frozenset(PRE + x for x in PRE_UNITS) | frozenset(LIFE + x for x in LIFE_UNITS)
NOW = "2026-10-29T00:00:00Z"
BODY = '''### Contexto
Caso sintético de preflight.

### Alcance
Validar funciones puras sin reservar.

### Fuera de alcance
Red, datos reales y publicaciones.

### Criterios de aceptación
- [ ] [AC-01] Fingerprints deterministas.
- [ ] [AC-02] Entradas inválidas denegadas.
- [ ] [AC-03] Solo datos sintéticos.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"test","target":"tests/test_cobertura_factory_20.py::CoberturaFactory20Tests::test_contrato_principal"},{"id":"AC-02","kind":"test","target":"tests/test_cobertura_factory_20.py::CoberturaFactory20Tests::test_falla_cerrado"},{"id":"AC-03","kind":"test","target":"tests/test_cobertura_factory_20.py::CoberturaFactory20Tests::test_sin_datos_reales"}]} -->

### Rutas reclamadas
- tests/test_cobertura_factory_20.py
<!-- factory-plan-task {"version":1,"epic":1082,"task_key":"OFFLINE_PREFLIGHT_FIXTURE","order":1,"owner":"pl0n3r","roles":["ingenieria-software","qa"],"depends_on":[],"paths":["tests/test_cobertura_factory_20.py"]} -->
'''


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Do not confuse a missing, duplicated or promoted row with coverage."""
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: missing matrix")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| `"):
            continue
        cells = tuple(value.strip() for value in line.strip().strip("|").split("|"))
        if len(cells) != 5:
            continue
        key = cells[0].strip("`")
        if key not in IDS:
            continue
        if (key in found or cells[0] != "`" + key + "`"
                or cells[2] != "NO_VERIFICABLE"
                or "Contraste #1571" not in cells[3]):
            raise ValueError("UNKNOWN: corrupted unit " + key)
        found[key] = cells
    if set(found) != IDS or len(found) != 20:
        raise ValueError("UNKNOWN: incomplete 20-row inventory")
    return found


def fixture(*, state: str = "active",
            validated: str = "2026-10-20T00:00:00Z") -> dict:
    """Synthetic refs, dates and checksums exercise the production model."""
    return knowledge.create_knowledge_record(
        knowledge_id="fixture-rule-001",
        knowledge_type="guardrail",
        content_fingerprint=hashlib.sha256(b"synthetic learned rule").hexdigest(),
        provenance=["pl0n3r/Factory#1082"],
        scope={"project": "pl0n3r/Factory", "domain": "synthetic-lifecycle"},
        created_at="2026-01-01T00:00:00Z",
        last_validated_at=validated, last_useful_at=validated,
        confidence=0.95, evidence_class="verified",
        review_policy={"review_after_days": 30, "expires_after_days": 90},
        state=state,
    )


class CoberturaFactory20Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: eight preflight and twelve knowledge subcontracts exercised."""
        rows = matrix_rows(MATRIX.read_text(encoding="utf-8"))
        self.assertEqual((20, 8, 12), (len(rows), len(PRE_UNITS), len(LIFE_UNITS)))
        for key in IDS:
            with self.subTest(row=key):
                self.assertEqual("NO_VERIFICABLE", rows[key][2])

        # Preflight L3/L19/L21: execute both production parsers in their order.
        with (mock.patch.object(preflight, "parse_contract",
                                wraps=preflight.parse_contract) as acceptance,
              mock.patch.object(preflight, "parse_task_marker",
                                wraps=preflight.parse_task_marker) as task):
            observed = preflight.evaluate_issue_body(BODY)
        acceptance.assert_called_once_with(BODY)
        task.assert_called_once_with(BODY)
        self.assertTrue(observed["valid"])
        self.assertEqual(["AC-01", "AC-02", "AC-03"],
                         [x["id"] for x in observed["criteria"]])
        # Preflight L20/L22: compare to canonical fingerprints.
        self.assertEqual(aceptacion_kit.contract_fingerprint(BODY),
                         observed["acceptance_sha256"])
        parsed = orquestador_kit.parse_task_marker(BODY)
        self.assertEqual(orquestador_kit.task_marker_fingerprint(parsed),
                         observed["task_marker_sha256"])
        self.assertEqual("OFFLINE_PREFLIGHT_FIXTURE", observed["task_key"])
        self.assertEqual(["tests/test_cobertura_factory_20.py"], observed["paths"])
        self.assertEqual([], observed["depends_on"])
        # Preflight L28: real CLI only emits local verdict, no grant or lease.
        sink = io.StringIO()
        self.assertEqual(0, preflight.main([], stdin=io.StringIO(BODY), stdout=sink))
        self.assertEqual(observed, json.loads(sink.getvalue()))
        self.assertEqual({
            "version", "valid", "acceptance_sha256", "task_marker_sha256",
            "task_key", "paths", "depends_on", "criteria",
        }, set(observed))
        self.assertNotIn("reservation", sink.getvalue().lower())

        # Lifecycle L19-L23: real constructor enforces required metadata.
        current = fixture()
        self.assertEqual(current, knowledge.validate_knowledge_record(current))
        self.assertEqual(["pl0n3r/Factory#1082"], current["provenance"])
        self.assertEqual({"project": "pl0n3r/Factory", "domain": "synthetic-lifecycle"},
                         current["scope"])
        self.assertEqual("2026-01-01T00:00:00Z", current["created_at"])
        self.assertEqual("2026-10-20T00:00:00Z", current["last_validated_at"])
        self.assertEqual(current["last_validated_at"], current["last_useful_at"])
        self.assertEqual(hashlib.sha256(b"synthetic learned rule").hexdigest(),
                         current["content_fingerprint"])
        self.assertEqual((0.95, "verified"),
                         (current["confidence"], current["evidence_class"]))
        self.assertEqual({"review_after_days": 30, "expires_after_days": 90},
                         current["review_policy"])
        # L10: only recently revalidated active evidence enables autonomy.
        self.assertEqual("active", knowledge.effective_state(current, NOW))
        self.assertTrue(knowledge.can_increase_autonomy(current, NOW))
        # L11 U1/U2: stale active evidence cannot increase autonomy.
        stale = fixture(validated="2026-06-01T00:00:00Z")
        self.assertEqual("needs_review", knowledge.effective_state(stale, NOW))
        self.assertFalse(knowledge.can_increase_autonomy(stale, NOW))
        # L12/L13: deprecated and archived states preserve all history.
        retired = knowledge.transition_knowledge(
            current, target_state="deprecated", at=NOW,
            evidence=["pl0n3r/Factory#1811"], reason="superseded")
        archived = knowledge.transition_knowledge(
            retired, target_state="archived", at="2026-10-30T00:00:00Z",
            evidence=["pl0n3r/Factory#1812"], reason="retained-for-audit")
        self.assertEqual("deprecated", retired["state"])
        self.assertEqual("archived", archived["state"])
        self.assertEqual(["deprecated", "archived"],
                         [event["to"] for event in archived["history"]])
        self.assertEqual(2, len(archived["history"]))
        self.assertEqual(current["provenance"], archived["provenance"])
        self.assertEqual([], current["history"])
        self.assertFalse(knowledge.can_increase_autonomy(
            archived, "2026-10-31T00:00:00Z"))
        # L24: revalidation appends traceable states, never overwrites history.
        renewed = knowledge.revalidate_knowledge(
            stale, validated_at=NOW, evidence=["pl0n3r/Factory#1813"],
            confidence=0.96, evidence_class="reproduced")
        self.assertEqual("active", renewed["state"])
        self.assertEqual(["needs_review", "active"],
                         [entry["to"] for entry in renewed["history"]])
        self.assertEqual(["pl0n3r/Factory#1813"], renewed["history"][-1]["evidence"])
        self.assertEqual([], stale["history"])
        self.assertTrue(knowledge.can_increase_autonomy(renewed, NOW))

    def test_falla_cerrado(self) -> None:
        """AC-02: malformed acceptance, unauthorized claims and metadata fail."""
        raw = MATRIX.read_text(encoding="utf-8")
        row = next(line for line in raw.splitlines()
                   if line.startswith("| `docs/issue-contract-preflight.md:L19-U1` |"))
        for damaged in (None, "", raw.replace(row + "\n", "", 1),
                        raw + "\n" + row,
                        raw.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1)):
            with self.subTest(inventory=str(damaged)[:20]):
                with self.assertRaisesRegex(ValueError, "UNKNOWN"):
                    matrix_rows(damaged)
        # Acceptance must fail before attempting to parse any task claim.
        for bad in ("", BODY.replace("### Contexto", "### Other", 1),
                    BODY.replace("[AC-01]", "[AC-X]", 1)):
            with mock.patch.object(preflight, "parse_task_marker") as task:
                with self.assertRaises(preflight.IssueContractPreflightError) as caught:
                    preflight.evaluate_issue_body(bad)
                self.assertEqual("acceptance_invalid", caught.exception.code)
                task.assert_not_called()
        for body, expected in (
            (BODY.split("<!-- factory-plan-task", 1)[0], "task_missing"),
            (BODY.replace("OFFLINE_PREFLIGHT_FIXTURE", "not-valid-key"), "task_invalid"),
        ):
            with self.assertRaises(preflight.IssueContractPreflightError) as caught:
                preflight.evaluate_issue_body(body)
            self.assertEqual(expected, caught.exception.code)
        stream = io.StringIO()
        self.assertEqual(2, preflight.main([], stdin=io.StringIO("invalid"), stdout=stream))
        self.assertFalse(json.loads(stream.getvalue())["valid"])

        good = fixture()
        for field, value in (
            ("provenance", []),
            ("scope", {"project": "fixture"}),
            ("content_fingerprint", "invalid"),
            ("confidence", float("nan")),
            ("evidence_class", "unverified"),
            ("review_policy", {"review_after_days": 90, "expires_after_days": 30}),
            ("last_validated_at", "not-a-date"),
        ):
            damaged = deepcopy(good)
            damaged[field] = value
            with self.subTest(field=field):
                with self.assertRaises(knowledge.KnowledgeLifecycleError):
                    knowledge.validate_knowledge_record(damaged)
        stale = fixture(validated="2026-06-01T00:00:00Z")
        with self.assertRaisesRegex(knowledge.KnowledgeLifecycleError,
                                    "identidad de evidencia nueva"):
            knowledge.revalidate_knowledge(
                stale, validated_at=NOW, evidence=stale["provenance"],
                confidence=0.95, evidence_class="verified")
        retired = knowledge.transition_knowledge(
            good, target_state="deprecated", at=NOW,
            evidence=["pl0n3r/Factory#1811"], reason="superseded")
        with self.assertRaises(knowledge.KnowledgeLifecycleError):
            knowledge.revalidate_knowledge(
                retired, validated_at=NOW,
                evidence=["pl0n3r/Factory#1813"],
                confidence=0.99, evidence_class="verified")
        corrupted = deepcopy(retired)
        corrupted["history"][0]["to"] = "archived"
        with self.assertRaises(knowledge.KnowledgeLifecycleError):
            knowledge.validate_knowledge_record(corrupted)
        self.assertFalse(knowledge.can_increase_autonomy(retired, NOW))

    def test_sin_datos_reales(self) -> None:
        """AC-03: no network or subprocess and no mutation of synthetic evidence."""
        item = fixture()
        before = deepcopy(item)
        with (mock.patch.object(socket, "create_connection",
                                side_effect=AssertionError("network")),
              mock.patch.object(urllib.request, "urlopen",
                                side_effect=AssertionError("network")),
              mock.patch.object(subprocess, "run",
                                side_effect=AssertionError("process"))):
            sink = io.StringIO()
            self.assertEqual(0, preflight.main([], stdin=io.StringIO(BODY), stdout=sink))
            self.assertTrue(json.loads(sink.getvalue())["valid"])
            self.assertEqual("active", knowledge.effective_state(item, NOW))
            self.assertTrue(knowledge.can_increase_autonomy(item, NOW))
            self.assertEqual(before, item)
        self.assertEqual(IDS, set(matrix_rows(MATRIX.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    unittest.main()
