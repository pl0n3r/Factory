#!/usr/bin/env python3
"""Factory#1852: pruebas conductuales de STATE/Presence sin infraestructura real."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import copy
import json
import unittest

from scripts.unattended_state_source import project_state_presence

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-02T04:10:00Z"
RID = "11111111-2222-4333-8444-555555555555"
HEAD = "a" * 40


def comment(user, body, at="2026-10-02T04:09:00Z"):
    return {"user": {"login": user}, "body": body, "created_at": at, "updated_at": at}


def reservation(active=True, at="2026-10-02T04:09:00Z", **changes):
    payload = {
        "version": 3,
        "owner": "pl0n3r",
        "reservation_id": RID,
        "branch": "trabajo/issue-775",
        "active": active,
        "reason": "tomar" if active else "pr-merged",
        "acceptance_sha256": "b" * 64,
        "task_marker_sha256": "c" * 64,
        "task_paths": ["scripts/unattended_state_source.py"],
        "task_depends_on": [745, 767],
    }
    payload.update(changes)
    return comment(
        "github-actions[bot]",
        f"<!-- condor-reserva {json.dumps(payload, separators=(',', ':'))} -->",
        at,
    )


def release_v1(at="2026-10-02T04:09:30Z", **changes):
    payload = {
        "active": False,
        "branch": "trabajo/issue-775",
        "owner": "pl0n3r",
        "reason": "liberar",
        "reservation_id": RID,
        "version": 1,
    }
    payload.update(changes)
    return comment(
        "github-actions[bot]",
        f"<!-- condor-reserva {json.dumps(payload, separators=(',', ':'))} -->",
        at,
    )


def state_payload(**changes):
    value = {
        "work_identity": "pl0n3r/Factory#775",
        "repository": "pl0n3r/Factory",
        "branch": "trabajo/issue-775",
        "head_sha": HEAD,
        "reservation_id": RID,
        "risk": "medium",
        "severity": "S3",
        "evidence": ["Factory#775", f"head@{HEAD}"],
        "last_state": "implementing",
        "next_action": "run acceptance",
        "blockers": [],
        "updated_at": "2026-10-02T04:08:30Z",
    }
    value.update(changes)
    return value


def state_comment(state=None, *, user="pl0n3r", at="2026-10-02T04:09:00Z"):
    payload = {"version": 1, "state": state or state_payload()}
    return comment(
        user,
        f"<!-- factory-state {json.dumps(payload, separators=(',', ':'))} -->",
        at,
    )


def project(comments, **changes):
    args = {
        "repository": "pl0n3r/Factory",
        "issue_number": 775,
        "comments": comments,
        "now": NOW,
        "state_stale_minutes": 20,
        "reservation_stale_minutes": 15,
        "branch_head_sha": HEAD,
    }
    args.update(changes)
    return project_state_presence(**args)



import socket
import subprocess
from unittest.mock import patch
from urllib import request
from scripts.unattended_watchdog import validate_state

class CoberturaFactory61Tests(unittest.TestCase):
    """AC-01/02/03: ejercer código real con fixtures sintéticos, nunca la matriz."""

    def test_contrato_principal(self):
        # L11/L13: STATE pasa realmente el validador 4C y binding exacto V3.
        checked = validate_state(
            state_payload(),
            now=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
            stale_after_minutes=20,
        )
        self.assertEqual(checked["work_identity"], "pl0n3r/Factory#775")
        self.assertEqual(checked["head_sha"], HEAD)
        self.assertEqual(checked["freshness"], "fresh")
        actual = project([reservation(), state_comment()])
        self.assertEqual(actual.status, "READY")
        self.assertEqual(actual.authority, "unchanged")
        self.assertEqual(actual.reservation_id, RID)
        self.assertEqual(actual.state, state_payload())
        self.assertNotIn("freshness", actual.state)

        # L17: un comentario externo no puede sustituir la última lease del bot.
        fake = comment("outside-user", reservation(active=False)["body"],
                       "2026-10-02T04:09:45Z")
        self.assertEqual(project([reservation(), state_comment(), fake]).status,
                         "READY")

        # L18: liberaciones terminales v3 completa y v1 mínima no dan READY.
        released = project([
            reservation(), state_comment(),
            reservation(active=False, reason="pr-merged",
                        at="2026-10-02T04:09:30Z"),
        ])
        self.assertEqual(released.status, "UNKNOWN")
        self.assertIsNone(released.state)
        forced = project([reservation(), state_comment(), release_v1()])
        self.assertEqual(forced.status, "UNKNOWN")
        self.assertIsNone(forced.reservation_id)

        # L21/L29/L30/L31/L33: no inferir sesiones, heartbeat ni capacidad.
        self.assertEqual(actual.presence["source"], "factory-state-github")
        self.assertEqual(actual.presence["sessions"], [])
        self.assertEqual(actual.presence["capacity"], {
            "known_slots": 0, "eligible_free_slots": 0,
            "degraded_slots": 0, "freshness": "unknown",
        })
        self.assertIn("presence_heartbeat_unavailable", actual.reasons)
        self.assertIn("presence_capacity_unknown", actual.reasons)

        # L41: freshness está en reasons, no dentro de STATE reinyectable.
        stale = project([
            reservation(),
            state_comment(state_payload(updated_at="2026-10-02T03:30:00Z")),
        ])
        self.assertEqual(stale.status, "READY")
        self.assertIn("state_stale", stale.reasons)
        self.assertNotIn("freshness", stale.state)
        recalculated = validate_state(
            stale.state,
            now=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
            stale_after_minutes=20,
        )
        self.assertEqual(recalculated["freshness"], "stale")

    def test_falla_cerrado(self):
        # L13-U1/U2/U3, L19 y L20: inconsistencias reales fallan cerrado.
        bad_states = {
            "repository": state_payload(repository="pl0n3r/Other"),
            "identity": state_payload(work_identity="pl0n3r/Factory#776"),
            "head": state_payload(head_sha="d" * 40),
            "reservation": state_payload(
                reservation_id="22222222-2222-4222-8222-222222222222"),
            "branch": state_payload(branch="trabajo/issue-776"),
            "future": state_payload(updated_at="2026-10-02T04:11:00Z"),
            "secret": state_payload(evidence=["token=fixture-rechazado"]),
            "pii": state_payload(blockers=["sample@example.invalid"]),
            "unknown_field": state_payload(unexpected="invalid"),
        }
        for name, payload in bad_states.items():
            with self.subTest(state=name):
                outcome = project([reservation(), state_comment(payload)])
                self.assertEqual(outcome.status, "BLOCKED")
                self.assertIsNone(outcome.state)
                self.assertEqual(outcome.authority, "unchanged")

        # Timestamp STATE posterior al comentario aunque no sea futuro global.
        self.assertEqual(project([
            reservation(),
            state_comment(state_payload(updated_at="2026-10-02T04:09:15Z")),
        ]).status, "BLOCKED")

        # L18: se rechazan V1 activa, extras, hashes y listas ambiguas.
        bad_leases = [
            {"version": 1}, {"task_paths": ["a", "a"]},
            {"task_depends_on": [745, 745]},
            {"acceptance_sha256": "invalid"},
            {"task_marker_sha256": "invalid"},
            {"unexpected": 1},
            {"branch": "trabajo/issue-776"},
        ]
        for mutation in bad_leases:
            with self.subTest(lease=mutation):
                self.assertEqual(
                    project([reservation(**mutation), state_comment()]).status,
                    "BLOCKED",
                )

        # L19: solo STATE del titular de la lease es confiable.
        foreign = project([
            reservation(), state_comment(user="outsider"),
        ])
        self.assertEqual(foreign.status, "UNKNOWN")
        self.assertIn("state_marker_unavailable", foreign.reasons)
        missing = project([reservation()])
        self.assertEqual(missing.status, "UNKNOWN")
        self.assertIn("state_marker_unavailable", missing.reasons)

        # Una lease caducada no se reinterpreta como permiso.
        expired = project([
            reservation(at="2026-10-02T03:40:00Z"),
            state_comment(state_payload(updated_at="2026-10-02T03:39:30Z"),
                          at="2026-10-02T03:40:30Z"),
        ])
        self.assertEqual(expired.status, "UNKNOWN")
        self.assertIn("reservation_stale", expired.reasons)

    def test_sin_datos_reales(self):
        # L95 y B03/B04 siguen requiriendo observación productiva (B);
        # L97/L98 expresan política del simulacro, no una ejecución E2E (C).
        def deny(*args, **kwargs):
            raise AssertionError("I/O externo no autorizado")
        with patch.object(socket, "create_connection", deny), \
             patch.object(request, "urlopen", deny), \
             patch.object(subprocess, "run", deny):
            valid = project([reservation(), state_comment()])
            unknown = project([])
            blocked = project([
                reservation(),
                state_comment(state_payload(blockers=["someone@example.invalid"])),
            ])
        self.assertEqual(
            (valid.status, unknown.status, blocked.status),
            ("READY", "UNKNOWN", "BLOCKED"),
        )
        self.assertEqual(valid.authority, "unchanged")
        self.assertEqual(valid.presence["sessions"], [])
        self.assertIsNone(unknown.state)
        self.assertIsNone(blocked.state)


if __name__ == "__main__":
    unittest.main()
