#!/usr/bin/env python3
"""Factory #1693: 16 contratos del simulacro 4D, exclusivamente sintéticos.

LOCAL_CONTRACT no es VERIFIED ni concede autoridad, operación ni go-live.
"""
from __future__ import annotations

import copy
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_unattended_safe_mode_e2e import (  # noqa: E402
    guard_evidence, presence, run_pipeline, smoke_incident,
    state, watchdog_evidence,
)

DOC = "docs/unattended-safe-mode-drill.md"
MATRIX = "docs/matriz-cobertura.md"
PREFIX = DOC + ":"
UNKNOWN, LOCAL = "UNKNOWN", "LOCAL_CONTRACT"
SUFFIXES = (
    "L43-U1", "L46-U1", "L5-U1", "L52-U1",
    "L62-U1", "L63-U1", "L64-U1", "L65-U1",
    "L74-U1", "L80-U1", "L80-U2", "L85-U1",
    "L92-U1", "L93-U1", "L94-U1", "L95-U1",
)
IDS = tuple(PREFIX + suffix for suffix in SUFFIXES)
UNKNOWN_REASONS = {
    PREFIX + "L52-U1": "no acredita ausencia de otros consumidores o efectos externos S1",
    PREFIX + "L65-U1": "next action sintética no ejecuta stop/escalation externa",
    PREFIX + "L80-U2": "los fixtures no acreditan permisos de todos los agentes reales",
    PREFIX + "L85-U1": "los siete criterios históricos requieren CI exact-HEAD real",
    PREFIX + "L92-U1": "publicación real Factory@v1 requiere evidencia externa",
    PREFIX + "L93-U1": "gasto o aprovisionamiento real requieren fuente operativa",
    PREFIX + "L94-U1": "credenciales o datos reales no se observan con fixtures",
    PREFIX + "L95-U1": "deploy, backup o rollback reales no se ejecutan aquí",
}


def documents() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in (DOC, MATRIX)}


def matrix_rows(docs: object) -> dict[str, tuple[str, ...]]:
    if (type(docs) is not dict or set(docs) != {DOC, MATRIX}
            or any(type(s) is not str for s in docs.values())):
        raise ValueError("UNKNOWN: fuente inválida")
    source = docs[DOC].splitlines()
    rows: dict[str, tuple[str, ...]] = {}
    for line in docs[MATRIX].splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(x.strip() for x in line.strip("|").split("|"))
        ident = cells[0].strip(chr(96))
        if ident not in IDS:
            continue
        if (ident in rows or len(cells) != 5
                or cells[0] != chr(96) + ident + chr(96)
                or cells[2] != "NO_VERIFICABLE"):
            raise ValueError("UNKNOWN: fila duplicada o promovida " + ident)
        number = int(ident.rsplit(":L", 1)[1].split("-", 1)[0])
        if (not 0 < number <= len(source)
                or cells[1] not in source[number - 1]
                or "Contraste" not in cells[3]):
            raise ValueError("UNKNOWN: procedencia/fuente no verificable " + ident)
        rows[ident] = cells
    if set(rows) != set(IDS):
        raise ValueError("UNKNOWN: faltan filas")
    return rows


def simulated_checks() -> dict[str, bool]:
    checks: dict[str, bool] = {}
    normal_guard, normal_watch = run_pipeline(
        watch_ev=watchdog_evidence(
            reservation=None, state=state(reservation_id=None),
        ),
    )
    checks["L5-U1"] = (
        normal_guard.action == normal_watch.action == "ALLOW"
        and normal_watch.authority == "unchanged"
        and not normal_watch.interrupt_owner
    )

    degraded = presence()
    degraded["sessions"][0]["freshness"] = "unknown"
    stale_evidence = watchdog_evidence(
        presence=degraded, work_ready=True,
        ready_since="2026-10-02T01:30:00Z",
        next_dispatch_planned=False,
        reservation={
            "active": True, "work_identity": "pl0n3r/Factory#746",
            "updated_at": "2026-10-02T01:20:00Z", "freshness": "stale",
        },
        state=state(updated_at="2026-10-02T01:20:00Z"),
    )
    stale_guard, stale_watch = run_pipeline(watch_ev=stale_evidence)
    checks["L43-U1"] = (
        stale_guard.action == "ALLOW"
        and stale_watch.action == "BLOCKED"
        and "reservation_without_progress"
        in {item.code for item in stale_watch.incidents}
    )
    repeated = copy.deepcopy(stale_evidence)
    repeated["already_alerted_fingerprints"] = list(
        stale_watch.new_alert_fingerprints
    )
    _, replay = run_pipeline(watch_ev=repeated)
    checks["L46-U1"] = (
        replay.action == "BLOCKED"
        and not replay.new_alert_fingerprints
        and bool(replay.incidents)
        and all(item.repeated for item in replay.incidents)
    )

    incident_guard, incident_watch = run_pipeline(
        watch_ev=watchdog_evidence(
            reservation=None, state=state(reservation_id=None),
            incidents=[smoke_incident("S1")],
        ),
    )
    checks["L52-U1"] = (
        incident_guard.authority == incident_watch.authority == "unchanged"
        and incident_watch.interrupt_owner
        and any(item.code == "reported" for item in incident_watch.incidents)
    )

    backup_guard, backup_watch = run_pipeline(
        guard_ev=guard_evidence(
            production_change=True, backup_required=True,
            backup_verified=False,
        ),
        watch_ev=watchdog_evidence(
            reservation=None,
            state=state(
                reservation_id=None,
                next_action="stop and escalate: backup not verified",
            ),
            next_actions=["stop and escalate: backup not verified"],
        ),
    )
    checks["L62-U1"] = (
        backup_guard.action == backup_watch.action == "BLOCKED"
        and "required_backup_not_verified" in backup_guard.reasons
        and backup_guard.authority == "unchanged"
    )
    checks["L65-U1"] = (
        backup_watch.action == "BLOCKED"
        and backup_watch.authority == "unchanged"
        and "stop and escalate: backup not verified"
        in backup_watch.daily_summary.next_actions
    )

    destructive_guard, destructive_watch = run_pipeline(
        guard_ev=guard_evidence(sensitive={
            "go_live": False, "spend": False,
            "irreversible": True, "real_data": False,
        }),
        watch_ev=watchdog_evidence(
            reservation=None, state=state(reservation_id=None),
        ),
    )
    checks["L63-U1"] = (
        destructive_guard.action == destructive_watch.action == "BLOCKED"
        and "sensitive_authority_not_granted" in destructive_guard.reasons
    )
    risk_guard, risk_watch = run_pipeline(
        guard_ev=guard_evidence(risk=UNKNOWN),
        watch_ev=watchdog_evidence(
            reservation=None, state=state(reservation_id=None),
            incidents=[smoke_incident(UNKNOWN)],
        ),
    )
    checks["L64-U1"] = (
        risk_guard.action == risk_watch.action == "BLOCKED"
        and "risk_unknown" in risk_guard.reasons
        and risk_guard.authority == "unchanged"
    )
    checks["L74-U1"] = (
        risk_watch.action == "BLOCKED"
        and not risk_watch.interrupt_owner
        and any("UNKNOWN:" in item for item in risk_watch.daily_summary.incidents)
    )

    for name, suffix in (
        ("go_live", "L80-U1"), ("spend", "L93-U1"),
        ("real_data", "L94-U1"), ("irreversible", "L95-U1"),
    ):
        flags = {
            "go_live": False, "spend": False,
            "irreversible": False, "real_data": False,
        }
        flags[name] = True
        guard, watch = run_pipeline(
            guard_ev=guard_evidence(sensitive=flags),
            watch_ev=watchdog_evidence(
                reservation=None, state=state(reservation_id=None),
            ),
        )
        checks[suffix] = (
            guard.action == watch.action == "BLOCKED"
            and guard.authority == watch.authority == "unchanged"
            and "sensitive_authority_not_granted" in guard.reasons
        )

    checks["L80-U2"] = all(
        checks[x] for x in ("L80-U1", "L62-U1", "L63-U1", "L64-U1")
    )
    checks["L85-U1"] = False  # jamás fabricar CI histórico exact-SHA
    checks["L92-U1"] = checks["L80-U1"]  # flag local, no publicación real
    return checks


def assess(docs: object) -> dict[str, str]:
    results = dict.fromkeys(IDS, UNKNOWN)
    try:
        matrix_rows(docs)
        checks = simulated_checks()
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return results
    for key in IDS:
        if checks.get(key[len(PREFIX):], False) and key not in UNKNOWN_REASONS:
            results[key] = LOCAL
    return results


def operational_status(_id: object, _claim: object = None) -> str:
    return UNKNOWN


class BrechasFactory75Tests(unittest.TestCase):
    def test_contrato_principal(self):
        docs = documents()
        self.assertEqual(set(matrix_rows(docs)), set(IDS))
        checks = simulated_checks()
        self.assertEqual(set(checks), set(SUFFIXES))
        results = assess(docs)
        self.assertEqual(len(results), 16)
        for key in IDS:
            with self.subTest(id=key):
                self.assertIsInstance(checks[key[len(PREFIX):]], bool)
                self.assertEqual(
                    results[key], UNKNOWN if key in UNKNOWN_REASONS else LOCAL,
                )

    def test_falla_cerrado(self):
        docs = documents()
        for key in IDS:
            with self.subTest(id=key):
                row = next(
                    line for line in docs[MATRIX].splitlines()
                    if line.startswith("| " + chr(96) + key + chr(96) + " |")
                )
                for broken in (
                    docs[MATRIX].replace(row, "", 1),
                    docs[MATRIX] + "\n" + row,
                    docs[MATRIX].replace(
                        row, row.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1,
                    ),
                ):
                    self.assertTrue(all(
                        x == UNKNOWN for x in
                        assess({**docs, MATRIX: broken}).values()
                    ))
                number = int(key.rsplit(":L", 1)[1].split("-", 1)[0])
                lines = docs[DOC].splitlines()
                lines[number - 1] = "redacted"
                self.assertTrue(all(
                    x == UNKNOWN for x in
                    assess({**docs, DOC: "\n".join(lines)}).values()
                ))
        for invalid in (None, {}, {DOC: docs[DOC]}, {MATRIX: docs[MATRIX]}):
            self.assertTrue(all(x == UNKNOWN for x in assess(invalid).values()))

    def test_sin_datos_reales(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network denied")):
            result = assess(documents())
        self.assertEqual(result[PREFIX + "L62-U1"], LOCAL)
        self.assertEqual(result[PREFIX + "L93-U1"], UNKNOWN)
        self.assertEqual(
            guard_evidence()["sensitive"],
            {"go_live": False, "spend": False, "irreversible": False,
             "real_data": False},
        )

    def test_estados_unknown_explicitos(self):
        results = assess(documents())
        self.assertEqual(len(UNKNOWN_REASONS), 8)
        self.assertEqual(
            {key for key, status in results.items() if status == UNKNOWN},
            set(UNKNOWN_REASONS),
        )
        for key, reason in UNKNOWN_REASONS.items():
            with self.subTest(id=key):
                self.assertIn(key, IDS)
                self.assertGreater(len(reason), 25)
        for claim in (
            {"ci": "success"}, {"production": "VERIFIED"}, {"live": True},
            {"backup_verified": True}, {"spend": True}, {"release": "v1"},
        ):
            self.assertEqual(operational_status("L85-U1", claim), UNKNOWN)
        self.assertNotIn("VERIFIED", results.values())


if __name__ == "__main__":
    unittest.main()
