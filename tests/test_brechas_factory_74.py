#!/usr/bin/env python3
"""Factory #1692: 16 brechas del kill switch y del simulacro 4D.

LOCAL_CONTRACT acredita solo comportamiento puro reproducible; UNKNOWN deja
explícitas las fronteras que requieren evidencia de agentes/operación real.
No se modifica ni promociona la matriz de cobertura.
"""
from __future__ import annotations

from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

from scripts.unattended_kill_switch import (
    CANONICAL_OWNER,
    CANONICAL_REPOSITORY_URL,
    CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_unattended_safe_mode_e2e import (  # noqa: E402
    fencing,
    guard_config,
    guard_evidence,
    presence,
    run_pipeline,
    state,
    watchdog_evidence,
)

K = "docs/unattended-kill-switch.md:"
D = "docs/unattended-safe-mode-drill.md:"
MATRIX = "docs/matriz-cobertura.md"
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
IDS = (
    K + "L40-U1", K + "L41-U1", K + "L42-U1",
    K + "L46-U1", K + "L48-U1", K + "L52-U1",
    D + "L16-U1", D + "L23-U1", D + "L24-U1",
    D + "L25-U1", D + "L30-U1", D + "L31-U1",
    D + "L34-U1", D + "L40-U1", D + "L41-U1",
    D + "L42-U1",
)
# El contrato puro no prueba comportamiento de agentes remotos, autoría de
# edición, emisiones al dueño ni ausencia de efectos fuera del simulacro.
UNKNOWN_REASONS = {
    K + "L41-U1": "no se puede certificar cero mutaciones de otros agentes",
    K + "L42-U1": "no existe emisor real de una línea en el parser puro",
    K + "L48-U1": "user.login es creador, no último editor del marker",
    K + "L52-U1": "no se observa el preflight de cada ciclo remoto",
    D + "L16-U1": "no se prueba ausencia de datos reales fuera del fixture",
    D + "L34-U1": "no se observa creación autónoma externa al simulacro",
}
RUNNING = (
    '<!-- factory-unattended-kill-switch '
    '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
)


def issue(body: str = RUNNING) -> dict[str, object]:
    return {
        "number": 767,
        "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL,
        "state": "closed",
        "user": {"login": CANONICAL_OWNER},
        "body": body,
    }


def documents() -> dict[str, str]:
    return {
        path: (ROOT / path).read_text(encoding="utf-8")
        for path in (K[:-1], D[:-1], MATRIX)
    }


def matrix_rows(docs: object) -> dict[str, tuple[str, ...]]:
    """Contrato de presencia y procedencia, no promoción de NO_VERIFICABLE."""
    if type(docs) is not dict or set(docs) != {K[:-1], D[:-1], MATRIX}:
        raise ValueError(UNKNOWN + ": fuentes incompletas")
    if any(type(value) is not str for value in docs.values()):
        raise ValueError(UNKNOWN + ": fuente no textual")
    rows: dict[str, tuple[str, ...]] = {}
    for line in docs[MATRIX].splitlines():
        if not line.startswith("| "):
            continue
        parts = tuple(x.strip() for x in line.strip("|").split("|"))
        key = parts[0].strip("`")
        if key not in IDS:
            continue
        if key in rows or len(parts) != 5 or parts[0] != f"`{key}`":
            raise ValueError(UNKNOWN + ": fila duplicada o ambigua " + key)
        if parts[2] != "NO_VERIFICABLE":
            raise ValueError(UNKNOWN + ": no asumir estado conciliado " + key)
        path, number = key.split(":L", 1)
        number = int(number.split("-", 1)[0])
        source = docs[path].splitlines()
        if not 0 < number <= len(source) or parts[1] not in source[number - 1]:
            raise ValueError(UNKNOWN + ": fuente desalineada " + key)
        rows[key] = parts
    if set(rows) != set(IDS):
        raise ValueError(UNKNOWN + ": faltan filas")
    return rows


def assess(docs: object) -> dict[str, str]:
    result = dict.fromkeys(IDS, UNKNOWN)
    try:
        matrix_rows(docs)

        missing = evaluate_unattended_kill_switch(None)
        duplicate = evaluate_unattended_kill_switch(
            issue(RUNNING + "\n<!-- FACTORY-UNATTENDED-KILL-SWITCH")
        )
        paused_guard, paused_watch = run_pipeline(
            fence=fencing("replan", True),
            guard_cfg=guard_config(global_pause=missing.global_pause),
            watch_ev=watchdog_evidence(
                reservation=None, state=state(reservation_id=None)
            ),
        )
        blocked_guard, blocked_watch = run_pipeline(
            fence=fencing("keep", False),
            guard_cfg=guard_config(global_pause=True),
            watch_ev=watchdog_evidence(
                reservation=None, state=state(reservation_id=None)
            ),
        )
        healthy_guard, healthy_watch = run_pipeline(
            watch_ev=watchdog_evidence(
                reservation=None, state=state(reservation_id=None)
            ),
        )

        unknown_presence = presence()
        unknown_presence["sessions"][0]["freshness"] = "unknown"
        _, presence_watch = run_pipeline(
            watch_ev=watchdog_evidence(
                presence=unknown_presence,
                reservation=None,
                state=state(reservation_id=None),
            ),
        )
        _, stale_watch = run_pipeline(
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(reservation_id=None, updated_at="2026-10-02T01:20:00Z"),
            ),
        )
        _, idle_watch = run_pipeline(
            watch_ev=watchdog_evidence(
                reservation=None,
                state=state(reservation_id=None),
                work_ready=True,
                ready_since="2026-10-02T01:30:00Z",
                next_dispatch_planned=False,
            ),
        )
        flags = {
            K + "L40-U1": missing.state == UNKNOWN
                and missing.global_pause is True
                and paused_guard.action == "PAUSE",
            K + "L46-U1": duplicate.state == UNKNOWN
                and duplicate.global_pause is True
                and duplicate.reason == "kill_switch_marker_count_invalid",
            D + "L23-U1": (
                healthy_guard.action, healthy_guard.pause_allowed,
                healthy_guard.authority
            ) == ("ALLOW", False, "unchanged"),
            D + "L24-U1": healthy_watch.action == "ALLOW"
                and healthy_watch.authority == "unchanged",
            D + "L25-U1": not healthy_watch.incidents
                and healthy_watch.interrupt_owner is False
                and not healthy_watch.new_alert_fingerprints,
            D + "L30-U1": paused_guard.action == "PAUSE"
                and paused_guard.pause_allowed is True
                and paused_watch.action == "PAUSE"
                and paused_watch.authority == "unchanged",
            D + "L31-U1": blocked_guard.action == "BLOCKED"
                and blocked_guard.pause_allowed is False
                and "adaptive_pause_not_allowed" in blocked_guard.reasons
                and blocked_watch.action == "BLOCKED",
            D + "L40-U1": presence_watch.action == "BLOCKED"
                and "presence_insufficient" in {
                    x.code for x in presence_watch.incidents
                },
            D + "L41-U1": stale_watch.action == "BLOCKED"
                and stale_watch.daily_summary.state_freshness == "stale"
                and "state_stale" in {x.code for x in stale_watch.incidents},
            D + "L42-U1": idle_watch.action == "BLOCKED"
                and "ready_without_dispatch" in {
                    x.code for x in idle_watch.incidents
                },
        }
        if set(flags) | set(UNKNOWN_REASONS) != set(IDS):
            return result
        for row, holds in flags.items():
            if type(holds) is bool and holds:
                result[row] = LOCAL
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return dict.fromkeys(IDS, UNKNOWN)
    return result


class BrechasFactory74Tests(unittest.TestCase):
    def test_contrato_principal(self):
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        docs = documents()
        self.assertEqual(set(matrix_rows(docs)), set(IDS))
        result = assess(docs)
        self.assertEqual(set(result), set(IDS))
        for row in IDS:
            with self.subTest(row=row):
                self.assertEqual(
                    result[row], UNKNOWN if row in UNKNOWN_REASONS else LOCAL
                )

    def test_falla_cerrado(self):
        docs = documents()
        for path in docs:
            bad = dict(docs)
            bad[path] = ""
            with self.subTest(path=path):
                self.assertEqual(assess(bad), dict.fromkeys(IDS, UNKNOWN))
        self.assertEqual(assess(None), dict.fromkeys(IDS, UNKNOWN))

        for payload in (
            None,
            issue(RUNNING + "\n" + RUNNING),
            issue('<!-- factory-unattended-kill-switch {invalid} -->'),
            {**issue(), "state": "open"},
            {**issue(), "user": {"login": "other"}},
        ):
            with self.subTest(payload=repr(payload)[:70]):
                denied = evaluate_unattended_kill_switch(payload)
                self.assertEqual(denied.state, UNKNOWN)
                self.assertTrue(denied.global_pause)
                self.assertEqual(denied.authority, "unchanged")

        closed, _ = run_pipeline(
            guard_ev=guard_evidence(risk=UNKNOWN),
            watch_ev=watchdog_evidence(
                reservation=None, state=state(reservation_id=None)
            ),
        )
        self.assertEqual((closed.action, closed.authority),
                         ("BLOCKED", "unchanged"))

    def test_sin_datos_reales(self):
        with patch.object(socket, "socket", side_effect=AssertionError("red prohibida")):
            result = assess(documents())
        self.assertEqual(result[D + "L23-U1"], LOCAL)
        self.assertEqual(result[K + "L40-U1"], LOCAL)
        self.assertEqual(result[D + "L16-U1"], UNKNOWN)
        self.assertEqual(result[D + "L34-U1"], UNKNOWN)
        # El fixture no concede autoridad para gasto, datos reales o go-live.
        flags = guard_evidence()["sensitive"]
        self.assertEqual(
            flags, {"go_live": False, "spend": False,
                    "irreversible": False, "real_data": False}
        )

    def test_estados_unknown_explicitos(self):
        self.assertEqual(len(UNKNOWN_REASONS), 6)
        self.assertEqual(set(UNKNOWN_REASONS) | {
            key for key in assess(documents()) if key not in UNKNOWN_REASONS
        }, set(IDS))
        statuses = assess(documents())
        self.assertEqual(
            {key for key, status in statuses.items() if status == UNKNOWN},
            set(UNKNOWN_REASONS),
        )
        for row, explanation in UNKNOWN_REASONS.items():
            with self.subTest(row=row):
                self.assertIn(row, IDS)
                self.assertGreater(len(explanation), 20)
                self.assertEqual(statuses[row], UNKNOWN)
        self.assertTrue(all(status != "VERIFIED" for status in statuses.values()))


if __name__ == "__main__":
    unittest.main()
