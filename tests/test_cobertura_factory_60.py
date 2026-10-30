"""Factory #1851: regresión funcional aislada para el simulacro 4B + 4C.

Las aserciones ejercen los evaluadores reales con fixtures sintéticos. No se
consulta ninguna matriz de cobertura ni se invocan endpoints, shells o releases.
"""
from __future__ import annotations

import copy
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request as urllib_request

from scripts.unattended_guards import (
    evaluate_unattended_guards,
    guard_blocks_global_dispatch,
)
from scripts.unattended_watchdog import evaluate_unattended_watchdog
from test_unattended_safe_mode_e2e import (
    fencing, guard_config, guard_evidence, measurements, presence,
    run_pipeline, smoke_incident, state, watchdog_config, watchdog_evidence,
)


def safe_watch(**changes):
    """Evidence 4C without live reservation or authority claims."""
    return watchdog_evidence(
        reservation=None, state=state(reservation_id=None), **changes
    )


class CoberturaFactory60Tests(unittest.TestCase):
    def test_contrato_principal(self):
        # L5: composición real de 4B/4C, sin política duplicada.
        guard, watch = run_pipeline(watch_ev=safe_watch())
        self.assertEqual((guard.action, guard.authority), ("ALLOW", "unchanged"))
        self.assertEqual((watch.action, watch.authority), ("ALLOW", "unchanged"))
        self.assertEqual(watch.incidents, ())
        self.assertFalse(watch.interrupt_owner)
        self.assertFalse(guard_blocks_global_dispatch(guard))

        # L31: no se puede pedir una pausa sin autoridad de fencing.
        blocked, protected = run_pipeline(
            fence=fencing("keep", False),
            guard_cfg=guard_config(global_pause=True),
            watch_ev=safe_watch(),
        )
        self.assertEqual((blocked.action, blocked.pause_allowed),
                         ("BLOCKED", False))
        self.assertIn("adaptive_pause_not_allowed", blocked.reasons)
        self.assertEqual((protected.action, protected.authority),
                         ("BLOCKED", "unchanged"))

        # L34: con fencing válido, PAUSE conserva autoridad sin crear trabajo.
        paused, pause_watch = run_pipeline(
            fence=fencing("replan", True),
            guard_cfg=guard_config(global_pause=True),
            watch_ev=safe_watch(),
        )
        self.assertEqual((paused.action, paused.pause_allowed, paused.authority),
                         ("PAUSE", True, "unchanged"))
        self.assertEqual((pause_watch.action, pause_watch.authority),
                         ("PAUSE", "unchanged"))
        self.assertTrue(guard_blocks_global_dispatch(paused))

        # L40-43 + L46: Presence UNKNOWN, STATE stale, ready sin despacho
        # y reserva sin progreso generan códigos distintos, sin duplicados.
        unknown_presence = presence()
        unknown_presence["sessions"][0]["freshness"] = "unknown"
        evidence = watchdog_evidence(
            presence=unknown_presence,
            work_ready=True,
            ready_since="2026-10-02T01:30:00Z",
            next_dispatch_planned=False,
            reservation={
                "active": True,
                "work_identity": "pl0n3r/Factory#746",
                "updated_at": "2026-10-02T01:20:00Z",
                "freshness": "stale",
            },
            state=state(updated_at="2026-10-02T01:20:00Z"),
        )
        healthy, first = run_pipeline(watch_ev=evidence)
        self.assertEqual(healthy.action, "ALLOW")
        self.assertEqual((first.action, first.authority),
                         ("BLOCKED", "unchanged"))
        self.assertEqual(first.daily_summary.state_freshness, "stale")
        self.assertTrue({
            "presence_insufficient", "state_stale",
            "ready_without_dispatch", "reservation_without_progress",
        } <= {incident.code for incident in first.incidents})
        self.assertTrue(first.new_alert_fingerprints)
        repeated = copy.deepcopy(evidence)
        repeated["already_alerted_fingerprints"] = list(
            first.new_alert_fingerprints
        )
        _, second = run_pipeline(watch_ev=repeated)
        self.assertEqual(second.new_alert_fingerprints, ())
        self.assertTrue(all(item.repeated for item in second.incidents))

        # L52: smoke S1 solo informa a 4C; el rollback es next_action
        # ya presente en la evidencia sintética, sin ejecutar nada.
        action = "rollback reversible already authorized at exact SHA"
        authorized, observed = run_pipeline(
            fence=fencing("replan", True),
            guard_cfg=guard_config(global_pause=True),
            guard_ev=guard_evidence(
                production_change=True,
                backup_required=True,
                backup_verified=True,
            ),
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(
                    reservation_id=None,
                    severity="S1",
                    evidence=["synthetic-drill", "rollback-authorized",
                              "exact-sha", "backup-verified"],
                    next_action=action,
                ),
                incidents=[smoke_incident("S1", "fresh")],
                next_actions=[action],
            ),
        )
        self.assertEqual((authorized.action, authorized.authority),
                         ("PAUSE", "unchanged"))
        self.assertEqual((observed.action, observed.authority),
                         ("PAUSE", "unchanged"))
        self.assertTrue(observed.interrupt_owner)
        self.assertIn(action, observed.daily_summary.next_actions)

    def test_falla_cerrado(self):
        # L62, L63, L64 y L65: backup no verificado, acción destructiva
        # o riesgo UNKNOWN quedan BLOCKED en 4B y no se rehabilitan en 4C.
        cases = (
            (
                guard_evidence(
                    production_change=True,
                    backup_required=True,
                    backup_verified=False,
                ),
                "required_backup_not_verified",
            ),
            (
                guard_evidence(sensitive={
                    "go_live": False, "spend": False,
                    "irreversible": True, "real_data": False,
                }),
                "sensitive_authority_not_granted",
            ),
            (guard_evidence(risk="UNKNOWN"), "risk_unknown"),
        )
        for ev, reason in cases:
            with self.subTest(reason=reason):
                action = "stop and escalate: " + reason
                guard, watched = run_pipeline(
                    guard_ev=ev,
                    watch_ev=watchdog_evidence(
                        reservation=None,
                        state=state(reservation_id=None, next_action=action),
                        next_actions=[action],
                        incidents=[smoke_incident("S1")],
                    ),
                )
                self.assertEqual((guard.action, guard.authority),
                                 ("BLOCKED", "unchanged"))
                self.assertIn(reason, guard.reasons)
                self.assertTrue(guard_blocks_global_dispatch(guard))
                self.assertEqual((watched.action, watched.authority),
                                 ("BLOCKED", "unchanged"))
                self.assertIn(action, watched.daily_summary.next_actions)

        # L74: UNKNOWN no se usa para interrumpir ni convertir bloqueo
        # en autorización; S1/S2 frescos sí interrumpen por evidencia.
        for severity, interrupt in (
            ("S1", True), ("S2", True), ("S3", False), ("UNKNOWN", False),
        ):
            with self.subTest(severity=severity):
                _, watched = run_pipeline(
                    watch_ev=watchdog_evidence(
                        reservation=None,
                        state=state(reservation_id=None),
                        incidents=[smoke_incident(severity)],
                    ),
                )
                self.assertEqual(watched.interrupt_owner, interrupt)
                if severity == "UNKNOWN":
                    self.assertEqual(watched.action, "BLOCKED")

        # L80-U1, L80-U2: todas las fronteras sensibles siguen cerradas;
        # no hay aprobación implícita por el simulacro.
        for flag in ("go_live", "spend", "irreversible", "real_data"):
            with self.subTest(flag=flag):
                flags = dict.fromkeys(
                    ("go_live", "spend", "irreversible", "real_data"), False
                )
                flags[flag] = True
                guard = evaluate_unattended_guards(
                    fencing(), guard_config(),
                    guard_evidence(sensitive=flags), measurements(),
                )
                watched = evaluate_unattended_watchdog(
                    guard, watchdog_config(), safe_watch()
                )
                self.assertEqual(guard.action, "BLOCKED")
                self.assertEqual((watched.action, watched.authority),
                                 ("BLOCKED", "unchanged"))
                self.assertIn("sensitive_authority_not_granted", guard.reasons)

        no_backup = evaluate_unattended_guards(
            fencing(), guard_config(),
            guard_evidence(
                production_change=True,
                backup_required=True,
                backup_verified=None,
            ),
            measurements(),
        )
        self.assertEqual(no_backup.action, "BLOCKED")
        self.assertIn("required_backup_not_verified", no_backup.reasons)

        # Datos incoherentes tampoco autorizan ni despacho ni ejecución.
        invalid = evaluate_unattended_guards(
            fencing(), guard_config(),
            guard_evidence(risk="UNKNOWN", second_pass=None),
            measurements(),
        )
        self.assertEqual(invalid.action, "BLOCKED")
        self.assertTrue(guard_blocks_global_dispatch(invalid))

    def test_sin_datos_reales(self):
        # Únicamente datos sintéticos e interfaces puras; ningún acceso a
        # producción, red, shell, workflows, tags ni credenciales.
        def unavailable(*args, **kwargs):
            raise AssertionError("I/O prohibido en regresión 4D")

        with patch.object(socket, "create_connection", side_effect=unavailable), \
             patch.object(urllib_request, "urlopen", side_effect=unavailable), \
             patch.object(subprocess, "run", side_effect=unavailable):
            guard, watchdog = run_pipeline(watch_ev=safe_watch())
            self.assertEqual((guard.action, guard.authority),
                             ("ALLOW", "unchanged"))
            self.assertEqual((watchdog.action, watchdog.authority),
                             ("ALLOW", "unchanged"))
            for flag in ("spend", "real_data"):
                sensitive = dict.fromkeys(
                    ("go_live", "spend", "irreversible", "real_data"), False
                )
                sensitive[flag] = True
                rejected, observed = run_pipeline(
                    guard_ev=guard_evidence(sensitive=sensitive),
                    watch_ev=safe_watch(),
                )
                self.assertEqual((rejected.action, rejected.authority),
                                 ("BLOCKED", "unchanged"))
                self.assertEqual((observed.action, observed.authority),
                                 ("BLOCKED", "unchanged"))


if __name__ == "__main__":
    unittest.main()
