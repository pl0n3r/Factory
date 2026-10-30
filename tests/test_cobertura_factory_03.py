#!/usr/bin/env python3
"""Factory #1794: behavioral proof for acceptance and Recovery Health.

17 offline behaviors invoke the real Python validators and recovery projection.
The real offsite backup/restore operation is B (not asserted by synthetic data);
two workflow-descriptive claims are C. No coverage matrix access, external I/O,
production evidence, credentials or personal data.
"""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock
import urllib.request

from recovery.status import RecoveryStatusError, project_recovery_readiness
from scripts.aceptacion_kit import (
    AcceptanceError, CheckPending, Criterion, contract_fingerprint,
    parse_contract, run_named_test, validate_payload, verify_check,
    verify_checks_only,
)

A = frozenset({
    "ISSUE-305:AC-11",
    "docs/aceptacion-ejecutable.md:L12-U1",
    "docs/aceptacion-ejecutable.md:L14-U1",
    "docs/aceptacion-ejecutable.md:L15-U1",
    "docs/aceptacion-ejecutable.md:L16-U1",
    "docs/aceptacion-ejecutable.md:L17-U1",
    "docs/aceptacion-ejecutable.md:L18-U1",
    "docs/aceptacion-ejecutable.md:L22-U1",
    "docs/aceptacion-ejecutable.md:L37-U1",
    "docs/aceptacion-ejecutable.md:L41-U1",
    "docs/aceptacion-ejecutable.md:L45-U1",
    "docs/aceptacion-ejecutable.md:L49-U2",
    "docs/aceptacion-ejecutable.md:L49-U3",
    "docs/aceptacion-ejecutable.md:L5-U1",
    "docs/aceptacion-ejecutable.md:L51-U1",
    "docs/aceptacion-ejecutable.md:L59-U2",
    "docs/aceptacion-ejecutable.md:L6-U1",
})
B = {
    "ISSUE-305:AC-12": (
        "Un backup/offsite/restore E2E REAL exige almacenamiento, "
        "fuente y evidencia autenticados; fixtures offline no certifican RPO/RTO."
    ),
}
C = {
    "docs/aceptacion-ejecutable.md:L57-U1": (
        "Diagrama de orden de jobs; no es un comportamiento ejecutable "
        "independiente de los motores/gates probados."
    ),
    "docs/aceptacion-ejecutable.md:L59-U1": (
        "La prohibición de reejecutar workflows durante la espera es "
        "una restricción del workflow, no una función Python invocable."
    ),
}
TARGET = "tests/test_synthetic_acceptance.py::SyntheticAcceptance::test_specific"
CHECK = "Tests de scripts"
HEADINGS = (
    "### Contexto", "### Alcance", "### Fuera de alcance",
    "### Criterios de aceptación", "### Contrato ejecutable",
)


def make_body(*, target: str = TARGET, kind: str = "test") -> str:
    criteria = [{"id": "AC-01", "kind": kind, "target": target}]
    marker = json.dumps(
        {"version": 1, "criteria": criteria},
        separators=(",", ":"), sort_keys=True,
    )
    return "\n".join((
        "### Contexto", "Caso ficticio, sin red.",
        "### Alcance", "Contrato offline verificable.",
        "### Fuera de alcance", "Producción y secretos.",
        "### Criterios de aceptación",
        "- [ ] [AC-01] Comportamiento específico del issue.",
        "### Contrato ejecutable",
        "<!-- factory-acceptance " + marker + " -->",
    ))


def check_run(*, status="completed", conclusion="success", identifier=7):
    return {"check_runs": [{
        "id": identifier, "name": CHECK,
        "status": status, "conclusion": conclusion,
    }]}


def rejects(body: str) -> bool:
    try:
        parse_contract(body)
    except AcceptanceError:
        return True
    return False


def synthetic_case(root: Path, *, passing: bool = True) -> None:
    directory = root / "tests"
    directory.mkdir()
    (directory / "test_synthetic_acceptance.py").write_text(
        "import unittest\n"
        "class SyntheticAcceptance(unittest.TestCase):\n"
        "    def test_specific(self):\n"
        + ("        self.assertEqual(2 + 2, 4)\n" if passing else
           "        self.fail('synthetic failure')\n")
        + "    def test_not_selected(self):\n"
        + "        self.fail('must not execute')\n",
        encoding="utf-8",
    )


class CoberturaFactory03Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: 17 independent predicates, one per offline-coverable row."""
        self.assertEqual((len(A), len(B), len(C)), (17, 1, 2))
        self.assertEqual(len(A | B.keys() | C.keys()), 20)
        self.assertFalse(A & B.keys())
        self.assertFalse(A & C.keys())
        self.assertFalse(B.keys() & C.keys())

        valid = make_body()
        criteria = parse_contract(valid)
        self.assertEqual(len(criteria), 1)
        self.assertEqual(criteria[0], Criterion("AC-01", "test", TARGET))
        check = Criterion("AC-02", "check", CHECK)
        checks = check_run()

        # Exercise the real recovery readiness projection, never a mock status.
        for state in ("UNKNOWN", "BLOCKED"):
            with self.subTest(row="ISSUE-305:AC-11", state=state):
                source = {
                    "version": 1, "state": state, "authority": "unchanged",
                    "execute": False, "reasons": ["NO_VERIFIED_BACKUP"],
                    "work_item_classes": ["backup_missing"],
                }
                result = project_recovery_readiness(source, critical=True)
                self.assertEqual(result["recovery_health"], source["state"])
                self.assertFalse(result["ready"])
                self.assertTrue(result["critical_blocker"])
                self.assertFalse(result["recalculated"])
                self.assertEqual(result["work_item_classes"], source["work_item_classes"])

        # Each named mandatory section is enforced by _section -> parse_contract.
        with self.subTest(row="docs/aceptacion-ejecutable.md:L12-U1"):
            self.assertTrue(all(rejects(valid.replace(h, "### OMITIDA", 1))
                                for h in HEADINGS))
        for heading, row in (
            ("### Contexto", "docs/aceptacion-ejecutable.md:L14-U1"),
            ("### Alcance", "docs/aceptacion-ejecutable.md:L15-U1"),
            ("### Fuera de alcance", "docs/aceptacion-ejecutable.md:L16-U1"),
            ("### Criterios de aceptación",
             "docs/aceptacion-ejecutable.md:L17-U1"),
            ("### Contrato ejecutable",
             "docs/aceptacion-ejecutable.md:L18-U1"),
        ):
            with self.subTest(row=row):
                self.assertTrue(rejects(valid.replace(heading, "### OMITIDA", 1)))
                self.assertTrue(rejects(valid.replace(
                    heading, heading + "\n\n" + heading, 1
                )))

        with self.subTest(row="docs/aceptacion-ejecutable.md:L22-U1"):
            self.assertEqual(parse_contract(valid)[0].id, "AC-01")
            self.assertTrue(rejects(valid.replace("- [ ] [AC-01]",
                                                  "- [ ] AC-01")))
            self.assertTrue(rejects(valid.replace("- [ ] [AC-01]",
                                                  "- [ ] [AC-XX]")))

        with self.subTest(row="docs/aceptacion-ejecutable.md:L37-U1"):
            altered = valid.replace('"id":"AC-01"', '"id":"AC-02"')
            self.assertTrue(rejects(altered))
            self.assertTrue(rejects(valid + "\n<!-- factory-acceptance {} -->"))

        with self.subTest(row="docs/aceptacion-ejecutable.md:L41-U1"):
            self.assertEqual(parse_contract(valid)[0].target, TARGET)
            self.assertTrue(rejects(make_body(target="tests/test_synthetic.py")))
            self.assertTrue(rejects(make_body(
                target="tests/test_synthetic.py::NotClass::not_a_test"
            )))

        with self.subTest(row="docs/aceptacion-ejecutable.md:L45-U1"):
            self.assertTrue(rejects(make_body(
                target="../tests/test_bad.py::Bad::test_one"
            )))
            self.assertTrue(rejects(make_body(
                target="/tmp/test_bad.py::Bad::test_one"
            )))
            self.assertTrue(rejects(make_body(
                target="docs/test_bad.py::Bad::test_one"
            )))
            self.assertEqual(parse_contract(make_body(
                target="seguridad/test_sample.py::Spec::test_ok"
            ))[0].kind, "test")

        with self.subTest(row="docs/aceptacion-ejecutable.md:L49-U2"):
            for outcome in ("failure", "cancelled", "skipped", "neutral"):
                with self.subTest(outcome=outcome):
                    with self.assertRaises(AcceptanceError):
                        verify_check(check, check_run(conclusion=outcome))

        with self.subTest(row="docs/aceptacion-ejecutable.md:L49-U3"):
            self.assertIsNone(verify_check(check, checks))
            with self.assertRaises(CheckPending):
                verify_check(check, check_run(status="in_progress",
                                              conclusion=None))
            with self.assertRaises(AcceptanceError):
                verify_check(check, check_run(status="completed",
                                              conclusion=None))

        with self.subTest(row="docs/aceptacion-ejecutable.md:L5-U1"):
            # A passing global gate does NOT make a failing issue criterion pass.
            self.assertIsNone(verify_check(check, checks))
            with tempfile.TemporaryDirectory(prefix="factory-1794-") as tmp:
                root = Path(tmp)
                synthetic_case(root, passing=False)
                with self.assertRaises(AcceptanceError):
                    validate_payload({
                        "issue": {"body": valid}, "checks": checks,
                        "acceptance_sha256": contract_fingerprint(valid),
                        "require_pin": True,
                    }, root=root)

        with self.subTest(row="docs/aceptacion-ejecutable.md:L51-U1"):
            for forbidden in ("Validar", "Criterios de aceptación"):
                self.assertTrue(rejects(make_body(target=forbidden,
                                                   kind="check")))
            self.assertEqual(parse_contract(make_body(
                target=CHECK, kind="check"
            ))[0].kind, "check")

        with self.subTest(row="docs/aceptacion-ejecutable.md:L59-U2"):
            with self.assertRaises(CheckPending):
                verify_checks_only([check], {"check_runs": []})
            with self.assertRaises(CheckPending):
                verify_checks_only([check], check_run(
                    status="queued", conclusion=None
                ))
            with self.assertRaises(AcceptanceError):
                verify_checks_only([check], check_run(conclusion="failure"))
            self.assertEqual(verify_checks_only([check], checks), ["AC-02"])

        with self.subTest(row="docs/aceptacion-ejecutable.md:L6-U1"):
            with tempfile.TemporaryDirectory(prefix="factory-1794-") as tmp:
                root = Path(tmp)
                synthetic_case(root)
                self.assertIsNone(run_named_test(criteria[0], root))
                verified = validate_payload({
                    "issue": {"body": valid}, "checks": check_run(),
                    "acceptance_sha256": contract_fingerprint(valid),
                    "require_pin": True,
                }, root=root)
                self.assertEqual(verified["verified"], ["AC-01"])

    def test_falla_cerrado(self):
        """AC-02: no accepted evidence for unsafe/missing/ambiguous input."""
        with self.assertRaises(RecoveryStatusError):
            project_recovery_readiness({"state": "NOT_REAL"}, critical=True)
        with self.assertRaises(RecoveryStatusError):
            project_recovery_readiness({"state": "UNKNOWN"}, critical="yes")
        with self.assertRaises(RecoveryStatusError):
            project_recovery_readiness({
                "state": "UNKNOWN", "work_item_classes": ["forged_class"]
            }, critical=True)
        for malformed in (
            "", "### Contexto\n\n", make_body().replace('"version":1',
                                                      '"version":true'),
            make_body().replace('"id":"AC-01"', '"id":"AC-99"'),
        ):
            with self.subTest(malformed=malformed[:30]):
                self.assertTrue(rejects(malformed))
        with self.assertRaises(CheckPending):
            verify_check(Criterion("AC-01", "check", CHECK),
                         {"check_runs": []})
        with self.assertRaises(AcceptanceError):
            verify_check(Criterion("AC-01", "check", CHECK),
                         check_run(status="completed", conclusion="failure"))
        with tempfile.TemporaryDirectory(prefix="factory-1794-") as tmp:
            root = Path(tmp)
            synthetic_case(root, passing=False)
            with self.assertRaises(AcceptanceError):
                run_named_test(Criterion("AC-01", "test", TARGET), root)

    def test_sin_datos_reales(self):
        """AC-03: no credentials, PII, network, or live backup are accessed."""
        with (
            mock.patch.object(socket, "create_connection",
                              side_effect=AssertionError("network forbidden")),
            mock.patch.object(urllib.request, "urlopen",
                              side_effect=AssertionError("network forbidden")),
        ):
            body = make_body()
            self.assertEqual(parse_contract(body)[0].target, TARGET)
            health = project_recovery_readiness({
                "version": 1, "state": "BLOCKED", "authority": "unchanged",
                "execute": False, "reasons": ["MISSING_EVIDENCE"],
                "work_item_classes": ["backup_missing"],
            }, critical=True)
            self.assertFalse(health["ready"])
            self.assertFalse(health["recalculated"])
            with tempfile.TemporaryDirectory(prefix="factory-1794-") as tmp:
                root = Path(tmp)
                synthetic_case(root)
                run_named_test(Criterion("AC-01", "test", TARGET), root)
            for forbidden in (
                "ghp_", "github_pat_", "bearer ", "password=",
                "person@", "secret=", "snapshot_ref", "encrypted_ref",
            ):
                with self.subTest(forbidden=forbidden):
                    self.assertNotIn(forbidden, json.dumps({
                        "issue": body, "health": health,
                    }).lower())
            self.assertEqual((len(A), len(B), len(C)), (17, 1, 2))


if __name__ == "__main__":
    unittest.main()
