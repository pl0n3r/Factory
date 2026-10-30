"""Factory #1840: verificación conductual offline de Recovery y gates de release.

Ejercita funciones reales con fixtures sintéticos y negativos. No inspecciona
docs/matriz-cobertura*.md, no publica tags/releases, no accede a red ni a datos.
Las condiciones operativas externas siguen clasificadas B y las guías C.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import socket
import unittest
from unittest.mock import patch

from recovery.status import (
    derive_recovery_health, project_recovery_readiness,
    recovery_work_item_classes,
)
from scripts.release_bootstrap import ReleaseBootstrapError, validate_payload
from scripts import release_window as rw
from test_recovery_status import manifest, backup, drill
from test_release_bootstrap_runtime import (
    SHA, valid_v2_payload, valid_latest_payload, valid_rearmed_v2_payload,
)

NOW = "2026-09-29T01:34:00Z"
DRILL_AT = "2026-09-29T01:32:00Z"
WINDOW_NOW = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)
WINDOW_SHA = "4" * 40

RELEASE_REQUIRED = (
    "CI factory",
    "Sonar CI-based",
    "Evidencia CodeQL",
    "Vigilar startup_failure de reusables publicados",
    "Compatibilidad de consumidores",
)


def health(*, evidence=True, retention_drift=False):
    return derive_recovery_health(
        manifest(), backup() if evidence else None,
        drill() if evidence else None,
        observed_at=NOW,
        drill_observed_at=DRILL_AT if evidence else None,
        retention_drift=retention_drift,
    )


def workflow_snapshot(*, missing=None, state="success", head=WINDOW_SHA):
    return [
        {"name": name, "status": "completed" if state == "success" else "in_progress",
         "conclusion": state, "head_sha": head}
        for name in RELEASE_REQUIRED if name != missing
    ]


def request(**overrides):
    payload = {
        "now": "2026-10-03T10:00:00Z",
        "main_sha": WINDOW_SHA,
        "version": "1.0.23",
        "candidate_version": "1.0.23",
        "actor": "pl0n3r",
        "owner": "pl0n3r",
        "owner_requested": True,
        "gates": [],
        "workflows": workflow_snapshot(),
    }
    payload.update(overrides)
    return rw.plan_request(payload)


def gate_rows():
    rendered = rw._render_gate("1.0.23", WINDOW_SHA, WINDOW_NOW, source_issue=900)
    return [{
        "issue": {
            "number": 922, "state": "open",
            "title": "factory-release fixture",
            "body": rendered["body"],
            "updated_at": "2026-10-03T10:00:00Z",
        },
        "comments": [],
    }]


def merge_window(*, now="2026-10-03T10:10:00Z", body="",
                 priority="prioridad: alta"):
    return rw.check_pull_request({
        "now": now, "gates": gate_rows(),
        "pr": {"number": 1840, "body": body},
        "work_issue": {
            "number": 1840, "state": "open", "labels": [{"name": priority}],
        },
    })


class CoberturaFactory49Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # recovery-status L7: retention drift fresco = DEGRADED, no healthy.
        degraded = health(retention_drift=True)
        self.assertEqual(degraded["state"], "DEGRADED")
        self.assertIn("retention_drift", recovery_work_item_classes(degraded))
        self.assertEqual(degraded["authority"], "unchanged")
        self.assertIs(degraded["execute"], False)

        # L8-U1/U2: backup ausente = UNKNOWN y recovery crítico no ready.
        unknown = health(evidence=False)
        self.assertEqual(unknown["state"], "UNKNOWN")
        projected = project_recovery_readiness(unknown, critical=True)
        self.assertEqual(projected["recovery_health"], "UNKNOWN")
        self.assertFalse(projected["ready"])
        self.assertTrue(projected["critical_blocker"])
        self.assertIs(projected["recalculated"], False)

        # Salud positiva es puramente declarativa (nunca acredita backup real).
        fresh = health()
        self.assertEqual(fresh["state"], "HEALTHY")
        self.assertTrue(project_recovery_readiness(fresh)["ready"])

        # release-bootstrap B02: decisión A v2 válida ligada a gate/OWNER.
        self.assertEqual(validate_payload(valid_v2_payload()),
                         {"status": "ready", "sha": SHA})
        # B04: latest permite cambios inocuos pero invalida maquinaria de release.
        safe = valid_latest_payload(changed_files=["docs/README.md"])
        self.assertEqual(validate_payload(safe), {"status": "ready", "sha": SHA})

        # B05 / runbook L33: freeze real en evaluador, sin crear puerta.
        frozen = merge_window()
        self.assertFalse(frozen["allowed"])
        self.assertEqual(frozen["reason"], "factory_release_window_active")
        self.assertEqual(frozen["gate_issue"], 922)
        expired = merge_window(now="2026-10-03T11:01:00Z")
        self.assertTrue(expired["allowed"])
        self.assertEqual(expired["reason"], "no_active_release_window")

        # B05: cadena de procedencia bot->OWNER pasa solo en fixture autorizada.
        self.assertEqual(validate_payload(valid_rearmed_v2_payload()),
                         {"status": "ready", "sha": SHA})

        # runbook L31-U1: checks exact-main son entradas obligatorias,
        # incluso si la invocación del dueño fue legítima.
        missing = request(workflows=workflow_snapshot(missing="Evidencia CodeQL"))
        self.assertEqual(missing["action"], "rejected")
        self.assertEqual(missing["reason"], "revalidation_required")
        self.assertIn("Evidencia CodeQL", missing["missing_checks"])

        # L31-U2: evidencia completa no crea puerta sin historial autorizado.
        no_history = request()
        self.assertEqual(no_history["action"], "rejected")
        self.assertEqual(no_history["reason"], "no_trusted_release_history")

        # L24-U1: la solicitud explícita OWNER es exigida antes del checkout.
        only_owner = request(actor="collaborator")
        self.assertEqual(only_owner["reason"], "owner_request_required")

    def test_falla_cerrado(self):
        # recovery-status L9: offsite, checksum o causalidad inválidos bloquean.
        original = backup()
        no_offsite = deepcopy(original)
        no_offsite["destinations"] = []
        blocked = derive_recovery_health(
            manifest(), no_offsite, drill(), observed_at=NOW,
            drill_observed_at=DRILL_AT,
        )
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertIn("offsite_missing", recovery_work_item_classes(blocked))
        self.assertFalse(project_recovery_readiness(blocked)["ready"])

        checksum_mismatch = deepcopy(drill())
        checksum_mismatch["checksum_sha256"] = "b" * 64
        invalid_checksum = derive_recovery_health(
            manifest(), original, checksum_mismatch,
            observed_at=NOW, drill_observed_at=DRILL_AT,
        )
        self.assertEqual(invalid_checksum["state"], "BLOCKED")
        self.assertIn("checksum_failed",
                      recovery_work_item_classes(invalid_checksum))

        causal = derive_recovery_health(
            manifest(), original, drill(), observed_at=NOW,
            drill_observed_at="2026-09-29T01:00:00Z",
        )
        self.assertEqual(causal["state"], "BLOCKED")
        self.assertIn("DRILL_BEFORE_BACKUP", causal["reasons"])

        # L8-U1: un backup vencido tampoco produce HEALTHY.
        stale = derive_recovery_health(
            manifest(), original, drill(),
            observed_at="2026-09-29T02:00:01Z",
            drill_observed_at="2026-09-29T01:59:00Z",
        )
        self.assertEqual(stale["state"], "UNKNOWN")

        # Release B02/B04: sin OWNER o con maquinaria derivada nunca publica.
        bad_actor = valid_v2_payload()
        bad_actor["actor"] = "untrusted-user"
        with self.assertRaisesRegex(ReleaseBootstrapError, "propietario"):
            validate_payload(bad_actor)
        drift = valid_latest_payload(
            changed_files=[".github/workflows/release-bootstrap.yml"]
        )
        with self.assertRaisesRegex(ReleaseBootstrapError, "maquinaria de release"):
            validate_payload(drift)

        # B05: provenance inválida o autorización no demostrada bloquean.
        bad_provenance = valid_rearmed_v2_payload(sources=[])
        with self.assertRaises(ReleaseBootstrapError):
            validate_payload(bad_provenance)

        # L31-U2: también rechaza checks pendientes o sobre un SHA distinto.
        pending = request(workflows=workflow_snapshot(state="pending"))
        self.assertEqual(pending["reason"], "revalidation_required")
        wrong_sha = request(workflows=workflow_snapshot(head="5" * 40))
        self.assertEqual(wrong_sha["reason"], "revalidation_required")

        # L33: sin prioridad crítica y marker canónico no hay excepción.
        self.assertFalse(merge_window(body="/decidir A")["allowed"])

        # L43: texto libre no sustituye un /decidir A de OWNER.
        no_decision = valid_v2_payload()
        no_decision["gate"]["comments"][0]["body"] = "sigue"
        with self.assertRaises(ReleaseBootstrapError):
            validate_payload(no_decision)

    def test_sin_datos_reales(self):
        # No sockets, external evidence ni mutaciones. Solo contratos puros.
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("red prohibida")):
            self.assertEqual(health()["state"], "HEALTHY")
            self.assertFalse(merge_window()["allowed"])
            self.assertEqual(request(actor="not-owner")["action"], "rejected")
            self.assertEqual(validate_payload(valid_v2_payload())["status"], "ready")
        result = health()
        self.assertIs(result["execute"], False)
        self.assertEqual(result["authority"], "unchanged")
        self.assertFalse(any(
            key in result for key in ("password", "token", "secret", "email")
        ))


if __name__ == "__main__":
    unittest.main()
