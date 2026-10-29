#!/usr/bin/env python3
"""Factory #1792: contratos conductuales offline con límites explícitos.

Invoca motores/guardas reales del kit; NO lee la matriz de cobertura.
Las publicaciones, observaciones autenticadas y activaciones de Fase B
no se atribuyen a los fixtures locales. Sin red, secretos ni datos reales.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import unittest
import urllib.request
from unittest import mock

from scripts.aceptacion_kit import AcceptanceError, parse_contract
from scripts.coordinar_trabajo import closing_issues, issue_from_branch
from scripts.lease_auto_release import Evidence, decide
from scripts.lease_auto_release_run import (
    evaluate_phase_a_candidate, observe_recent_activity, run_cycle,
)
from scripts.orquestador_kit import PlanError, claims_overlap, parse_task_marker
from scripts.release_bootstrap import (
    ReleaseBootstrapError, _latest_owner_approval, _is_release_machinery_path,
)
from scripts.unattended_kill_switch import (
    CANONICAL_SOURCE_URL, CANONICAL_REPOSITORY_URL,
    evaluate_unattended_kill_switch,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc)
SHA = "a" * 40
UUID = "123e4567-e89b-42d3-a456-426614174000"

# A: comportamiento local del código existente; B/C/D no acreditan runtime.
A = frozenset({
    "AGENTES.md:B01", "AGENTES.md:B02",
    "ISSUE-1080:AC-02", "ISSUE-1080:AC-03",
    "ISSUE-1382:AC-01", "ISSUE-1382:AC-02",
    "ISSUE-1382:AC-03", "ISSUE-1382:AC-04",
})
B = {
    "AGENTES.md:B03": "publicar y mover v1 requieren autorización owner y GitHub real",
    "ISSUE-1082:AC-02": "propagación real a seis consumidores es externa",
    "ISSUE-1082:AC-03": "crear un incidente real requiere GitHub y permiso de escritura",
    "ISSUE-1382:AC-05": "24 horas y 100 ejecuciones exigen recibos auténticos por repo",
    "ISSUE-1382:AC-06": "activar Fase B exige autorización, lock/CAS y recibos reales",
}
C = {
    "AGENTES.md:B04": "carga de roles y disciplina de uso remoto son política de agentes",
    "ISSUE-1082:AC-01": "ocho reglas y lecciones describen documentación normativa",
    "ISSUE-1382:AC-07": "estado del README es declaración, no observación de Fase B",
}
D = {
    "ISSUE-1080:AC-01": "publicación autónoma de v1 sin puerta humana no implementada/autorizada",
    "ISSUE-1080:AC-04": "no hay rollback ejecutor dry-run completo certificado en esta hoja",
    "ISSUE-1082:AC-04": "el validador admite claims de directorio: veto total no implementado",
    "ISSUE-304:AC-01": "contratos de rendimiento arbitrarios no tienen ciclo ejecutable general",
}


def acceptance_body() -> str:
    machine = {"version": 1, "criteria": [
        {"id": "AC-01", "kind": "test",
         "target": "tests/test_cobertura_factory_01.py::CoberturaFactory01Tests::test_contrato_principal"},
        {"id": "AC-02", "kind": "check", "target": "Tests de scripts"},
    ]}
    return (
        "### Contexto\nEntrada ficticia\n"
        "### Alcance\nSin red\n"
        "### Fuera de alcance\nProducción\n"
        "### Criterios de aceptación\n"
        "- [ ] [AC-01] Validar un test sintético\n"
        "- [ ] [AC-02] Exigir check independiente\n"
        "### Contrato ejecutable\n"
        "<!-- factory-acceptance " + json.dumps(machine) + " -->\n"
    )


def switch_payload(state: str = "RUNNING") -> dict:
    return {
        "number": 767, "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL,
        "state": "closed", "user": {"login": "pl0n3r"},
        "body": ('<!-- factory-unattended-kill-switch '
                 + json.dumps({"version": 1, "state": state, "owner": "pl0n3r"})
                 + ' -->'),
    }


def evidence(**change) -> Evidence:
    record = {
        "now": NOW, "last_activity_at": NOW - timedelta(minutes=42),
        "recovery_since": NOW - timedelta(minutes=11),
        "status": "estado: requiere recuperación",
        "phase": "construccion", "issue_open": True, "v3_active": True,
        "lease_id": UUID, "owner": "pl0n3r", "branch_sha": SHA,
        "branch_present": True, "evidence_complete": True,
        "trusted_phase": True, "kill_switch_running": True,
        "ci_running": False, "changes_requested": False,
        "owner_recovered": False, "rate_remaining": 80, "rate_limit": 100,
    }
    record.update(change)
    return Evidence(**record)


def event_guard(event: str) -> subprocess.CompletedProcess:
    """Ejecutar el Bash real del workflow, no verificar solo su texto."""
    workflow = (ROOT / ".github/workflows/aceptacion.yml").read_text(encoding="utf-8")
    piece = workflow.split(
        "      - name: Rechazar eventos privilegiados\n", 1
    )[1].split("      - name: Validar contexto PR\n", 1)[0]
    script = piece.split("        run: |\n", 1)[1]
    code = "\n".join(line.removeprefix("          ") for line in script.splitlines())
    return subprocess.run(
        ["bash", "-c", code], cwd=ROOT, text=True, capture_output=True,
        timeout=8, check=False,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "EVENT_NAME": event},
    )


class CoberturaFactory01Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: 8 rutas A ejecutan implementaciones reales y fallan cerrado."""
        self.assertEqual((len(A), len(B), len(C), len(D)), (8, 5, 3, 4))
        self.assertEqual(len(A | B.keys() | C.keys() | D.keys()), 20)
        self.assertTrue(all(x.isdisjoint(A) for x in (B.keys(), C.keys(), D.keys())))

        # AGENTES B01: rama y relación de cierre, no reserva GitHub simulada.
        with self.subTest(row="AGENTES.md:B01"):
            self.assertEqual(issue_from_branch("trabajo/issue-42"), 42)
            self.assertEqual(closing_issues("Closes #42"), {42})
            self.assertIsNone(issue_from_branch("main"))
            self.assertEqual(closing_issues("sin relación de cierre"), set())

        # AGENTES B02: control real de eventos antes de checkout.
        with self.subTest(row="AGENTES.md:B02"):
            valid = event_guard("pull_request")
            self.assertEqual(valid.returncode, 0, valid.stderr)
            for event in ("issue_comment", "workflow_run", "pull_request_target"):
                denied = event_guard(event)
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn("solo acepta pull_request", denied.stdout)

        # ISSUE-1080 AC02: protector de maquinaria de release.
        with self.subTest(row="ISSUE-1080:AC-02"):
            self.assertTrue(_is_release_machinery_path(
                ".github/workflows/release.yml"))
            self.assertFalse(_is_release_machinery_path(
                "tests/test_cobertura_factory_01.py"))
            owner = {"user": {"login": "pl0n3r"},
                     "author_association": "OWNER",
                     "body": '<!-- factory-release-approval {"sha":"' + SHA + '"} -->'}
            self.assertEqual(_latest_owner_approval([owner], "pl0n3r"), SHA)

        # ISSUE-1080 AC03: kill switch validado por fuente y firma exacta.
        with self.subTest(row="ISSUE-1080:AC-03"):
            allowed = evaluate_unattended_kill_switch(switch_payload())
            self.assertEqual(allowed.state, "RUNNING")
            self.assertFalse(allowed.global_pause)
            blocked = evaluate_unattended_kill_switch(switch_payload("PAUSED"))
            self.assertTrue(blocked.global_pause)
            self.assertEqual(blocked.state, "PAUSED")

        # ISSUE-1382 AC01: informe de observación no otorga autoridad.
        with self.subTest(row="ISSUE-1382:AC-01"):
            report = observe_recent_activity([17], object(), now=NOW)
            self.assertEqual(report.state, "invalid_input")
            self.assertFalse(report.release_authorized)

        # ISSUE-1382 AC02: fase B deshabilitada por defecto.
        with self.subTest(row="ISSUE-1382:AC-02"):
            disabled = run_cycle([17], object())
            self.assertEqual(disabled.state, "feature_disabled")
            self.assertFalse(disabled.results[0][1].wrote)

        # ISSUE-1382 AC03: no aceptar flags, lote o evidencia inválidos.
        with self.subTest(row="ISSUE-1382:AC-03"):
            self.assertEqual(run_cycle([17, 17], object()).state, "invalid_batch")
            self.assertEqual(run_cycle([17], object(), feature_enabled=1).state,
                             "invalid_flags")
            self.assertEqual(decide(evidence(evidence_complete=False)).action,
                             "unknown")

        # ISSUE-1382 AC04: sin autoridad explícita, cero escrituras.
        with self.subTest(row="ISSUE-1382:AC-04"):
            gate = run_cycle([17], object(), feature_enabled=True,
                             dry_run=False, mutations_authorized=False)
            self.assertEqual(gate.state, "mutation_gate_off")
            self.assertFalse(gate.results[0][1].wrote)
            self.assertEqual(decide(evidence()).action, "release")
            self.assertEqual(decide(evidence(kill_switch_running=False)).action,
                             "wait")

        # Contratos offline adyacentes, sin promocionar las filas B/C/D:
        contract = parse_contract(acceptance_body())
        self.assertEqual([(x.id, x.kind) for x in contract],
                         [("AC-01", "test"), ("AC-02", "check")])
        self.assertTrue(claims_overlap("tests/", "tests/fake.py"))
        self.assertFalse(claims_overlap("tests/one.py", "docs/two.md"))

    def test_falla_cerrado(self) -> None:
        """AC-02: falta de autoridad, datos ambiguos y eventos prohibidos."""
        # El parser extrae 0; no lo confundimos con una reserva autorizada.
        self.assertEqual(issue_from_branch("trabajo/issue-0"), 0)
        self.assertIsNone(issue_from_branch("feature/issue-0"))
        self.assertEqual(event_guard("issues").returncode != 0, True)
        with self.assertRaises(ReleaseBootstrapError):
            _latest_owner_approval([], "pl0n3r")
        with self.assertRaises(ReleaseBootstrapError):
            _latest_owner_approval([{
                "user": {"login": "intruso"}, "author_association": "OWNER",
                "body": '<!-- factory-release-approval {"sha":"' + SHA + '"} -->',
            }], "pl0n3r")
        issue = switch_payload()
        issue["user"] = {"login": "intruso"}
        self.assertTrue(evaluate_unattended_kill_switch(issue).global_pause)
        issue = switch_payload()
        issue["body"] += issue["body"]
        self.assertTrue(evaluate_unattended_kill_switch(issue).global_pause)
        with self.assertRaises(AcceptanceError):
            parse_contract(acceptance_body().replace(
                '"target": "Tests de scripts"', '"target": "Validar"'))
        with self.assertRaises(PlanError):
            parse_task_marker('<!-- factory-plan-task {"version":1,"paths":["../"]} -->')
        self.assertEqual(decide(evidence(rate_remaining=2)).action, "unknown")
        self.assertEqual(decide(evidence(changes_requested=True)).action, "wait")
        self.assertEqual(
            evaluate_phase_a_candidate([], [], [], repository="pl0n3r/Factory").status,
            "invalid_evidence",
        )

    def test_sin_datos_reales(self) -> None:
        """AC-03: entradas locales sintéticas, sin red/PII/cuentas reales."""
        with (
            mock.patch.object(socket, "create_connection",
                              side_effect=AssertionError("red prohibida")),
            mock.patch.object(urllib.request, "urlopen",
                              side_effect=AssertionError("red prohibida")),
        ):
            self.assertEqual(decide(evidence()).reason,
                             "inactive_after_recovery_grace")
            self.assertEqual(
                run_cycle([17], object(), feature_enabled=False).state,
                "feature_disabled",
            )
            self.assertEqual(parse_contract(acceptance_body())[0].id, "AC-01")
        self.assertTrue(all(str(s).strip() for s in (*B.values(), *C.values(),
                                                      *D.values())))
        self.assertEqual(UUID, "123e4567-e89b-42d3-a456-426614174000")


if __name__ == "__main__":
    unittest.main()
