"""Factory #1685: 16 fail-closed contracts for reusable-release rollback.

These tests execute the existing pure rollback planner against synthetic
consumer evidence. They never move v1, invoke GitHub, deploy, use real SHA
identities or infer consumer recovery from an internal green check. Actual
administrative approval and post-rollback consumer evidence remain UNKNOWN.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import re
import unittest

from scripts.release_auto_rollback_plan import plan_rollback

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
RUNBOOK = ROOT / "docs/reusable-release-rollback.md"
PREFIX = "docs/reusable-release-rollback.md:"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_SYNTHETIC"
GAP = "BRECHA_DOCUMENTADA"
AFFECTED = "a" * 40
STABLE = "b" * 40

# Every ID is mapped to the original source line, not a fabricated row index.
CLAUSES = {
    "L19-U2": (19, "No se elige por inferencia ni por"),
    "L23-U1": (23, "affected_factory_sha=<SHA afectado>"),
    "L24-U1": (24, "stable_factory_sha=<SHA estable objetivo>"),
    "L25-U1": (25, "consumidores que justifican el rollback"),
    "L26-U1": (26, "evidencia que demuestra que el SHA estable"),
    "L30-U1": (30, "Detectar o recomendar rollback"),
    "L32-U1": (32, "El OWNER debe ejecutar conscientemente"),
    "L34-U1": (34, "La acción administrativa debe equivaler exactamente a mover"),
    "L38-U1": (38, "No se autoriza mover tags semánticos"),
    "L42-U1": (42, "Después de restablecer"),
    "L44-U1": (44, "materializar jobs"),
    "L45-U1": (45, "startup_failure"),
    "L46-U1": (46, "Factory@v1"),
    "L48-U1": (48, "Solo pueden reintentarse o regenerarse"),
    "L50-U1": (50, "Si no existe evidencia nueva de consumidor"),
    "L56-U1": (56, "SHA afectado"),
}
IDS = tuple(PREFIX + part for part in CLAUSES)
POSTCHECKS = (
    "new_consumer_run_materializes_jobs",
    "new_consumer_run_is_not_startup_failure",
    "published_v1_ref_matches_stable_sha",
)
# These involve real post-rollback consumer evidence and a human-authorized
# tag update: impossible to certify from a unit test with no external inputs.
GAPS = {
    "L42-U1": "no actual OWNER-authorized tag movement or fresh consumer event",
    "L44-U1": "no fresh authenticated consumer job materialization after restore",
    "L45-U1": "no fresh consumer run proving startup_failure was resolved",
    "L46-U1": "no live verification that Factory@v1 resolves to target SHA",
    "L48-U1": "no real failed-run retry or regenerated event after restore",
    "L50-U1": "no persisted incident status or fresh consumer recovery evidence",
}


def fixture() -> dict:
    """All identifiers are synthetic; stable run predates failing run."""
    return {
        "phase": "construccion",
        "kill_switch_state": "RUNNING",
        "tag_protected": True,
        "evidence_authenticated": True,  # Synthetic caller assertion, not auth.
        "incident_type": "startup_failure",
        "affected_factory_sha": AFFECTED,
        "current_v1_sha": AFFECTED,
        "stable_factory_sha": STABLE,
        "affected_consumer_runs": [{
            "repository": "synthetic/consumer",
            "workflow": "synthetic-validate",
            "run_id": 200,
            "factory_sha": AFFECTED,
            "conclusion": "startup_failure",
            "authenticated": True,
            "materialized_jobs": False,
        }],
        "stable_consumer_runs": [{
            "repository": "synthetic/consumer",
            "workflow": "synthetic-validate",
            "run_id": 100,
            "factory_sha": STABLE,
            "conclusion": "success",
            "authenticated": True,
            "materialized_jobs": True,
        }],
    }


def rows(raw: object) -> dict[str, tuple[str, ...]]:
    """Reject missing, duplicated or promoted matrix rows, even if unrelated."""
    if type(raw) is not str or not raw:
        raise ValueError(UNKNOWN + ": matrix absent")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| " + chr(96) + PREFIX):
            continue
        body = line.strip()
        pieces = tuple(part.strip() for part in body.strip("|").split("|"))
        if not pieces or not pieces[0].startswith(chr(96)):
            continue
        name = pieces[0].strip(chr(96))
        if name not in IDS:
            continue
        if (name in found or len(pieces) != 5 or
                pieces[0] != chr(96) + name + chr(96) or
                pieces[2] != "NO_VERIFICABLE" or
                "No se confirmó test + PR fusionado" not in pieces[3] or
                "[contraste #1574]" not in pieces[3] or
                pieces[4] != "—"):
            raise ValueError(UNKNOWN + ": invalid coverage " + name)
        found[name] = pieces
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": missing rollback clauses " +
                         str(sorted(set(IDS) - set(found))))
    return found


def source_clause(key: object, doc: object, cell: object) -> bool:
    if type(key) is not str or key not in IDS or type(doc) is not str or type(cell) is not str:
        return False
    line_no, fragment = CLAUSES[key[len(PREFIX):]]
    lines = doc.splitlines()
    return (len(lines) >= line_no and fragment in lines[line_no - 1]
            and cell in lines[line_no - 1])


def blocked_variant(field: str, value: object) -> bool:
    sample = fixture()
    sample[field] = value
    result = plan_rollback(sample)
    return (result["decision"] == "BLOCKED"
            and result["authorizes_tag_move"] is False
            and result["mutations"] == 0
            and result["proposed_stable_sha"] is None)


def evidence(key: object, matrix: object, doc: object,
             snapshot: object, result: object) -> str:
    """All conclusions are local; gaps are deliberately not promoted."""
    if type(key) is not str or key not in IDS or type(snapshot) is not dict or type(result) is not dict:
        return UNKNOWN
    try:
        found = rows(matrix)
    except ValueError:
        return UNKNOWN
    if not source_clause(key, doc, found[key][1]):
        return UNKNOWN
    baseline = fixture()
    expected = plan_rollback(baseline)
    if (snapshot != baseline or result != expected
            or expected["decision"] != "HUMAN_GATE_REQUIRED"
            or expected["reason"] != "owner_must_authorize_v1_rollback"
            or expected["authorizes_tag_move"] is not False
            or expected["mutations"] != 0
            or expected["proposed_stable_sha"] != STABLE
            or expected["postrollback_verification_required"] != list(POSTCHECKS)):
        return UNKNOWN
    suffix = key[len(PREFIX):]
    if suffix in GAPS:
        return GAP
    # Every local row has a separate behavioral witness against actual code.
    tests = {
        "L19-U2": lambda: blocked_variant("stable_consumer_runs", []),
        "L23-U1": lambda: blocked_variant("affected_factory_sha", "latest-green"),
        "L24-U1": lambda: blocked_variant("stable_factory_sha", AFFECTED),
        "L25-U1": lambda: blocked_variant("affected_consumer_runs", []),
        "L26-U1": lambda: blocked_variant("stable_consumer_runs", [{
            **baseline["stable_consumer_runs"][0], "materialized_jobs": False
        }]),
        "L30-U1": lambda: expected["authorizes_tag_move"] is False
                          and expected["mutations"] == 0,
        "L32-U1": lambda: expected["decision"] == "HUMAN_GATE_REQUIRED",
        "L34-U1": lambda: expected["proposed_stable_sha"] == STABLE
                          and expected["proposed_stable_sha"] != AFFECTED,
        "L38-U1": lambda: blocked_variant("stable_factory_sha", AFFECTED)
                          and expected["mutations"] == 0,
        "L56-U1": lambda: baseline["affected_factory_sha"] == AFFECTED
                          and snapshot["affected_factory_sha"] == AFFECTED,
    }
    try:
        return LOCAL if tests[suffix]() is True else UNKNOWN
    except (KeyError, TypeError, ValueError):
        return UNKNOWN


def gap_description(key: object, matrix: object, doc: object,
                    snapshot: object, result: object) -> str:
    if type(key) is not str or not key.startswith(PREFIX):
        return UNKNOWN
    suffix = key[len(PREFIX):]
    if suffix not in GAPS or evidence(key, matrix, doc, snapshot, result) != GAP:
        return UNKNOWN
    return key + ": " + GAP + " — " + GAPS[suffix] + "; operational " + UNKNOWN


def operational(_key: object, _claims: object = None) -> str:
    """Synthetic flags or green checks are never production evidence."""
    return UNKNOWN


class BrechasFactory67Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.doc = RUNBOOK.read_text(encoding="utf-8")
        cls.data = fixture()
        cls.before = deepcopy(cls.data)
        cls.result = plan_rollback(cls.data)

    def test_contrato_principal(self):
        self.assertEqual(16, len(IDS))
        self.assertEqual(set(IDS), set(rows(self.matrix)))
        self.assertEqual(self.before, self.data)
        for key in IDS:
            with self.subTest(row=key):
                self.assertTrue(source_clause(key, self.doc, rows(self.matrix)[key][1]))
                verdict = evidence(key, self.matrix, self.doc, self.data, self.result)
                if key[len(PREFIX):] in GAPS:
                    self.assertEqual(GAP, verdict)
                    self.assertIn("operational UNKNOWN",
                                  gap_description(key, self.matrix, self.doc,
                                                  self.data, self.result))
                else:
                    self.assertEqual(LOCAL, verdict)
                self.assertEqual(UNKNOWN, operational(key, verdict))
        self.assertEqual(list(POSTCHECKS),
                         self.result["postrollback_verification_required"])

    def test_falla_cerrado(self):
        for key in IDS:
            line = next(row for row in self.matrix.splitlines()
                        if row.startswith("| " + chr(96) + key + chr(96) + " |"))
            for damaged in (self.matrix.replace(line, "", 1),
                            self.matrix + "\n" + line,
                            self.matrix.replace(line, line.replace(
                                "NO_VERIFICABLE", "VERIFICADO"), 1)):
                with self.subTest(row=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        rows(damaged)
                    self.assertEqual(UNKNOWN, evidence(key, damaged, self.doc,
                                                       self.data, self.result))
            self.assertEqual(UNKNOWN, evidence(
                key, self.matrix, "", self.data, self.result))
        for changes in (
            {"phase": "unknown"}, {"kill_switch_state": "PAUSED"},
            {"evidence_authenticated": False},
            {"current_v1_sha": "c" * 40},
            {"affected_consumer_runs": []},
            {"stable_consumer_runs": []},
        ):
            with self.subTest(change=changes):
                self.assertTrue(blocked_variant(*next(iter(changes.items()))))
        self.assertEqual(UNKNOWN, evidence(
            IDS[0], self.matrix, self.doc, {"green": True}, self.result))
        self.assertEqual(UNKNOWN, evidence(
            IDS[0], self.matrix, self.doc, self.data, {"decision": "success"}))
        self.assertEqual(UNKNOWN, gap_description(
            PREFIX + "L99-U1", self.matrix, self.doc, self.data, self.result))

    def test_sin_datos_reales(self):
        module = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = {name.name.split(".")[0] for node in ast.walk(module)
                    if isinstance(node, ast.Import) for name in node.names}
        imported.update(node.module.split(".")[0] for node in ast.walk(module)
                        if isinstance(node, ast.ImportFrom) and node.module)
        self.assertFalse(imported & {
            "requests", "httpx", "socket", "urllib", "subprocess", "os",
            "playwright", "boto3", "github",
        })
        self.assertEqual("synthetic/consumer",
                         self.data["affected_consumer_runs"][0]["repository"])
        self.assertEqual("synthetic/consumer",
                         self.data["stable_consumer_runs"][0]["repository"])
        self.assertEqual(self.before, self.data)
        self.assertEqual(0, self.result["mutations"])
        self.assertIs(self.result["authorizes_tag_move"], False)

    def test_estados_unknown_explicitos(self):
        for key in IDS:
            with self.subTest(row=key):
                self.assertEqual("NO_VERIFICABLE", rows(self.matrix)[key][2])
                for claim in (
                    None, True, {"ci": "success"}, {"new_consumer_run": 101},
                    {"v1": STABLE}, {"owner_approval": True},
                    {"production": "recovered"},
                ):
                    self.assertEqual(UNKNOWN, operational(key, claim))
        self.assertEqual(UNKNOWN, operational(PREFIX + "L46-U1", self.result))
        for suffix in GAPS:
            self.assertEqual(GAP, evidence(
                PREFIX + suffix, self.matrix, self.doc, self.data, self.result))


if __name__ == "__main__":
    unittest.main()
