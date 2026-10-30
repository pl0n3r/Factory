"""Factory #1850: evidencia conductual de kill switch y drill 4B/4C.

Usa implementaciones reales con fixtures sintéticos; no toca matrices,
credenciales, red, producción ni estado remoto.
"""
from __future__ import annotations

from contextlib import ExitStack
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request

from scripts.unattended_kill_switch import (
    CANONICAL_OWNER, CANONICAL_REPOSITORY_URL, CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)

RUNNING = '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
PAUSED = '<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","owner":"pl0n3r"} -->'


def issue(body=RUNNING):
    return {
        "number": 767, "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL,
        "state": "closed", "user": {"login": CANONICAL_OWNER},
        "body": body,
    }


def drill_helpers():
    """Reutiliza solo builders sintéticos del drill; la lógica viene de 4B/4C."""
    path = Path(__file__).with_name("test_unattended_safe_mode_e2e.py")
    spec = importlib.util.spec_from_file_location("_factory_59_drill_fixtures", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se puede cargar fixture 4D")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoberturaFactory59Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drill = drill_helpers()

    def _healthy_watch_evidence(self):
        return self.drill.watchdog_evidence(
            reservation=None,
            state=self.drill.state(reservation_id=None),
        )

    def test_contrato_principal(self):
        # Kill L20-U2, L21-U1/U2, L33-U1, L39-U1, L40-U1.
        on = evaluate_unattended_kill_switch(issue())
        off = evaluate_unattended_kill_switch(issue(PAUSED))
        self.assertEqual(
            (on.state, on.global_pause, on.reason, on.authority),
            ("RUNNING", False, "kill_switch_running", "unchanged"),
        )
        self.assertEqual(
            (off.state, off.global_pause, off.reason, off.authority),
            ("PAUSED", True, "kill_switch_paused", "unchanged"),
        )
        bad = evaluate_unattended_kill_switch(None)
        self.assertEqual((bad.state, bad.global_pause), ("UNKNOWN", True))

        # Drill L23-U1, L24-U1, L25-U1: baseline real 4B -> 4C.
        healthy_guard, healthy_watch = self.drill.run_pipeline(
            watch_ev=self._healthy_watch_evidence(),
        )
        self.assertEqual(
            (healthy_guard.action, healthy_guard.pause_allowed, healthy_guard.authority),
            ("ALLOW", False, "unchanged"),
        )
        self.assertEqual(
            (healthy_watch.action, healthy_watch.authority, healthy_watch.interrupt_owner),
            ("ALLOW", "unchanged", False),
        )
        self.assertEqual(healthy_watch.incidents, ())
        self.assertEqual(healthy_watch.new_alert_fingerprints, ())

        # Kill L20-U2, L40-U1 y drill L30-U1: pausa con fencing autorizado.
        paused_guard, paused_watch = self.drill.run_pipeline(
            fence=self.drill.fencing("replan", True),
            guard_cfg=self.drill.guard_config(global_pause=off.global_pause),
            watch_ev=self._healthy_watch_evidence(),
        )
        self.assertEqual(
            (paused_guard.action, paused_guard.pause_allowed, paused_guard.authority),
            ("PAUSE", True, "unchanged"),
        )
        self.assertIn("global_pause_active", paused_guard.reasons)
        self.assertEqual(
            (paused_watch.action, paused_watch.authority),
            ("PAUSE", "unchanged"),
        )

        # RUNNING nunca permite sortear otras guardas 4B.
        risk_guard, risk_watch = self.drill.run_pipeline(
            guard_cfg=self.drill.guard_config(global_pause=on.global_pause),
            guard_ev=self.drill.guard_evidence(risk="UNKNOWN"),
            watch_ev=self._healthy_watch_evidence(),
        )
        self.assertEqual(risk_guard.action, "BLOCKED")
        self.assertIn("risk_unknown", risk_guard.reasons)
        self.assertEqual(risk_watch.action, "BLOCKED")

    def test_falla_cerrado(self):
        # Kill L37-U1, L39-U1, L40-U1, L46-U1: rechazos reales por fuente.
        cases = (
            (None, "source_unreadable"),
            ({}, "unexpected_issue"),
            ({**issue(), "number": 768}, "unexpected_issue"),
            ({**issue(), "url": "https://api.github.com/repos/pl0n3r/Factory/issues/768"}, "unexpected_issue_url"),
            ({**issue(), "repository_url": "https://api.github.com/repos/pl0n3r/Other"}, "unexpected_repository"),
            ({**issue(), "state": "open"}, "unexpected_issue_state"),
            ({**issue(), "user": {"login": "other"}}, "unexpected_issue_author"),
            (issue("sin marker"), "kill_switch_marker_count_invalid"),
            (issue(RUNNING + "\n" + PAUSED), "kill_switch_marker_count_invalid"),
            (issue(RUNNING + "\n<!-- FACTORY-UNATTENDED-KILL-SWITCH"), "kill_switch_marker_count_invalid"),
            (issue('<!-- FACTORY-UNATTENDED-KILL-SWITCH {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'), "kill_switch_marker_invalid_syntax"),
            (issue('<!-- factory-unattended-kill-switch {broken} -->'), "kill_switch_marker_invalid_json"),
            (issue('<!-- factory-unattended-kill-switch {"version":2,"state":"RUNNING","owner":"pl0n3r"} -->'), "kill_switch_marker_invalid_version"),
            (issue('<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"other"} -->'), "kill_switch_marker_invalid_owner"),
            (issue('<!-- factory-unattended-kill-switch {"version":1,"state":"UNKNOWN","owner":"pl0n3r"} -->'), "kill_switch_marker_invalid_state"),
            (issue('<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","state":"RUNNING","owner":"pl0n3r"} -->'), "kill_switch_marker_duplicate_key"),
        )
        for payload, reason in cases:
            with self.subTest(reason=reason, payload=str(payload)[:80]):
                result = evaluate_unattended_kill_switch(payload)
                self.assertEqual(
                    (result.state, result.global_pause, result.reason, result.authority),
                    ("UNKNOWN", True, reason, "unchanged"),
                )

        # Si fencing no autoriza una pausa, 4B/4C fallan cerrado.
        guard, watch = self.drill.run_pipeline(
            fence=self.drill.fencing("keep", False),
            guard_cfg=self.drill.guard_config(global_pause=True),
            watch_ev=self._healthy_watch_evidence(),
        )
        self.assertEqual((guard.action, guard.pause_allowed), ("BLOCKED", False))
        self.assertIn("adaptive_pause_not_allowed", guard.reasons)
        self.assertEqual((watch.action, watch.authority), ("BLOCKED", "unchanged"))

    def test_sin_datos_reales(self):
        # Los tres contratos se ejecutan sin red/subprocess; la prueba no
        # interpreta la identidad del creador como provenance del último editor.
        with ExitStack() as stack:
            guards = [
                stack.enter_context(patch.object(socket, "create_connection", side_effect=AssertionError("network"))),
                stack.enter_context(patch.object(request, "urlopen", side_effect=AssertionError("network"))),
                stack.enter_context(patch.object(subprocess, "run", side_effect=AssertionError("subprocess"))),
                stack.enter_context(patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess"))),
                stack.enter_context(patch.object(os, "system", side_effect=AssertionError("subprocess"))),
            ]
            running = evaluate_unattended_kill_switch(issue())
            paused = evaluate_unattended_kill_switch(issue(PAUSED))
            guard, watch = self.drill.run_pipeline(
                fence=self.drill.fencing("replan", True),
                guard_cfg=self.drill.guard_config(global_pause=paused.global_pause),
                watch_ev=self._healthy_watch_evidence(),
            )
            self.assertEqual((running.global_pause, paused.global_pause), (False, True))
            self.assertEqual((guard.action, watch.action), ("PAUSE", "PAUSE"))
            self.assertEqual((guard.authority, watch.authority), ("unchanged", "unchanged"))
            for forbidden in guards:
                forbidden.assert_not_called()


if __name__ == "__main__":
    unittest.main()
