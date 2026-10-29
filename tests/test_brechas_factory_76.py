#!/usr/bin/env python3
"""Factory #1694: dieciséis cláusulas de STATE/Presence y simulacro 4D.

LOCAL_CONTRACT no acredita SLO medidos, rollback productivo o go-live.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_unattended_state_source import (  # noqa: E402
    HEAD, NOW, RID, project, release_v1, reservation,
    state_comment, state_payload,
)
from test_unattended_safe_mode_e2e import (  # noqa: E402
    guard_evidence, run_pipeline, state as drill_state, watchdog_evidence,
)
from scripts.unattended_watchdog import validate_state  # noqa: E402

UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
MATRIX = "docs/matriz-cobertura.md"
DRILL = "docs/unattended-safe-mode-drill.md"
MODE = "docs/unattended-safe-mode.md"
SOURCE = "docs/unattended-state-source.md"

CLAUSES = {
    f"{DRILL}:L97-U1": (DRILL, 97, "Cualquier fallo del simulacro"),
    f"{DRILL}:L98-U1": (DRILL, 98, "no puede debilitar esos contratos"),
    f"{MODE}:B03": (MODE, None, "SLO de cada producto requiere"),
    f"{MODE}:B04": (MODE, None, "Rollback operativo y simulacro"),
    f"{SOURCE}:L11-U1": (SOURCE, 11, "El objeto state usa exactamente"),
    f"{SOURCE}:L13-U1": (SOURCE, 13, "Con una reserva activa"),
    f"{SOURCE}:L13-U2": (SOURCE, 13, "si el caller aporta"),
    f"{SOURCE}:L13-U3": (SOURCE, 13, "El updated_at del STATE"),
    f"{SOURCE}:L17-U1": (SOURCE, 17, "La lease autoritativa"),
    f"{SOURCE}:L18-U1": (SOURCE, 18, "Se aceptan exactamente tres"),
    f"{SOURCE}:L18-U2": (SOURCE, 18, "V1 activa, extras"),
    f"{SOURCE}:L19-U1": (SOURCE, 19, "El STATE aceptado"),
    f"{SOURCE}:L20-U1": (SOURCE, 20, "Campos desconocidos"),
    f"{SOURCE}:L21-U1": (SOURCE, 21, "STATE no sustituye"),
    f"{SOURCE}:L29-U1": (SOURCE, 29, "sessions=[]"),
    f"{SOURCE}:L30-U1": (SOURCE, 30, "capacidad known_slots=0"),
}
IDS = tuple(CLAUSES)
UNKNOWN_REASONS = {
    f"{MODE}:B03": "sin objetivos por consumidor y medidas autenticadas",
    f"{MODE}:B04": "sin autoridad/backup/rollback E2E productivo exact-SHA",
}


def documents() -> dict[str, str]:
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in (MATRIX, DRILL, MODE, SOURCE)}


def rows(docs: object) -> dict[str, tuple[str, ...]]:
    """Comprueba las 16 filas exactas; nunca promueve cobertura sin evidencia."""
    required = {MATRIX, DRILL, MODE, SOURCE}
    if (type(docs) is not dict or set(docs) != required
            or any(type(value) is not str or not value for value in docs.values())):
        raise ValueError(UNKNOWN + ": missing/invalid source")
    found: dict[str, tuple[str, ...]] = {}
    for line in docs[MATRIX].splitlines():
        if not line.startswith("| "):
            continue
        cells = tuple(part.strip() for part in line.strip("|").split("|"))
        identifier = cells[0].strip(chr(96))
        if identifier not in CLAUSES:
            continue
        file, number, snippet = CLAUSES[identifier]
        if (identifier in found or len(cells) != 5
                or cells[0] != chr(96) + identifier + chr(96)
                or cells[2] != "NO_VERIFICABLE"
                or not cells[1].replace(chr(96), "").startswith(snippet)
                or not cells[3] or cells[4] != "—"):
            raise ValueError(UNKNOWN + ": duplicate/promoted/malformed " + identifier)
        source = docs[file].splitlines()
        if number is not None:
            if (number < 1 or number > len(source)
                    or snippet[:17] not in source[number - 1].replace(chr(96), "")):
                raise ValueError(UNKNOWN + ": source drift " + identifier)
        elif identifier.endswith(":B03"):
            if ("## 5. SLOs operativos" not in docs[file]
                    or "Si un objetivo no está configurado, su estado es" not in docs[file]):
                raise ValueError(UNKNOWN + ": SLO not sourced")
        elif ("## 8. Simulacro controlado" not in docs[file]
              or "backup previo" not in docs[file]):
            raise ValueError(UNKNOWN + ": rollback authority not sourced")
        found[identifier] = cells
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": incomplete sixteen-row scope")
    return found


def observed() -> dict[str, bool]:
    """Regresiones del código real con fixtures locales y reloj explícito."""
    good = project([reservation(), state_comment()])
    raw = state_payload()
    normalized = validate_state(
        raw, now=datetime.fromisoformat(NOW.replace("Z", "+00:00")),
        stale_after_minutes=20,
    )
    fail_backup, watched_backup = run_pipeline(
        guard_ev=guard_evidence(
            production_change=True, backup_required=True,
            backup_verified=False,
        ),
        watch_ev=watchdog_evidence(
            reservation=None, state=drill_state(reservation_id=None),
        ),
    )
    fail_unknown, watched_unknown = run_pipeline(
        guard_ev=guard_evidence(risk=UNKNOWN),
        watch_ev=watchdog_evidence(
            reservation=None, state=drill_state(reservation_id=None),
        ),
    )
    def projection(candidate, **changes):
        return project([reservation(), state_comment(candidate)], **changes)

    binding = [
        projection(state_payload(work_identity="pl0n3r/Factory#999")),
        projection(state_payload(repository="pl0n3r/Condor")),
        projection(state_payload(reservation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")),
        projection(state_payload(branch="trabajo/issue-999")),
    ]
    timestamp = projection(state_payload(updated_at="2026-10-02T04:09:30Z"))
    branch = projection(raw, branch_head_sha="d" * 40)
    forged = reservation(at="2026-10-02T04:09:30Z")
    forged["user"]["login"] = "pl0n3r"
    ignored = project([reservation(), state_comment(), forged])
    released = project([reservation(), state_comment(), release_v1()])
    released_v3 = project([
        reservation(), state_comment(),
        reservation(active=False, at="2026-10-02T04:09:30Z", reason="pr-merged"),
    ])
    forbidden = [
        project([reservation(version=2), state_comment()]),
        project([reservation(acceptance_sha256="invalid"), state_comment()]),
        project([reservation(task_marker_sha256="invalid"), state_comment()]),
        project([reservation(task_paths=["a", "a"]), state_comment()]),
        project([reservation(task_depends_on=[2, 2]), state_comment()]),
        project([reservation(surprise=True), state_comment()]),
        project([reservation(active=False, reason="tomar"), state_comment()]),
        project([release_v1(active=True), state_comment()]),
    ]
    secret_invalid = [
        projection(state_payload(extra=True)),
        projection(state_payload(evidence=["token=TOP-SECRET"])),
        projection(state_payload(blockers=["contact user@example.com"])),
        projection(state_payload(head_sha="invalid")),
        projection(state_payload(updated_at="2026-10-02T04:11:00Z")),
    ]
    foreign = project([reservation(), state_comment(user="untrusted")])
    presence = good.presence
    allowed = good.status == "READY" and good.authority == "unchanged"
    def blocked(results):
        return all(
            result.status == "BLOCKED" and result.authority == "unchanged"
            and result.state is None for result in results
        )
    return {
        f"{DRILL}:L97-U1": (
            fail_backup.action == watched_backup.action == "BLOCKED"
            and "required_backup_not_verified" in fail_backup.reasons
            and fail_unknown.action == watched_unknown.action == "BLOCKED"
            and "risk_unknown" in fail_unknown.reasons
        ),
        f"{DRILL}:L98-U1": (
            fail_backup.authority == watched_backup.authority == "unchanged"
            and fail_unknown.authority == watched_unknown.authority == "unchanged"
            and not fail_backup.pause_allowed
        ),
        f"{MODE}:B03": False,
        f"{MODE}:B04": False,
        f"{SOURCE}:L11-U1": (
            allowed and good.state == raw
            and normalized["work_identity"] == "pl0n3r/Factory#775"
            and normalized["freshness"] == "fresh"
            and "freshness" not in good.state
        ),
        f"{SOURCE}:L13-U1": blocked(binding),
        f"{SOURCE}:L13-U2": blocked([branch]),
        f"{SOURCE}:L13-U3": blocked([timestamp]),
        f"{SOURCE}:L17-U1": (
            ignored.status == "READY"
            and released.status == "UNKNOWN"
            and released.reservation_id is None
        ),
        f"{SOURCE}:L18-U1": (
            allowed and released_v3.status == "UNKNOWN"
            and released.status == "UNKNOWN"
            and released_v3.authority == "unchanged"
        ),
        f"{SOURCE}:L18-U2": blocked(forbidden),
        f"{SOURCE}:L19-U1": (
            foreign.status == "UNKNOWN" and foreign.state is None
            and "state_marker_unavailable" in foreign.reasons
        ),
        f"{SOURCE}:L20-U1": blocked(secret_invalid),
        f"{SOURCE}:L21-U1": (
            good.authority == "unchanged"
            and "presence_heartbeat_unavailable" in good.reasons
            and "presence_capacity_unknown" in good.reasons
            and good.state["work_identity"] == "pl0n3r/Factory#775"
        ),
        f"{SOURCE}:L29-U1": allowed and presence["sessions"] == [],
        f"{SOURCE}:L30-U1": allowed and presence["capacity"] == {
            "known_slots": 0,
            "eligible_free_slots": 0,
            "degraded_slots": 0,
            "freshness": "unknown",
        },
    }


def assess(docs: object, checks: object) -> dict[str, str]:
    results = dict.fromkeys(IDS, UNKNOWN)
    try:
        rows(docs)
    except (ValueError, TypeError, IndexError, KeyError):
        return results
    if type(checks) is not dict or set(checks) != set(IDS):
        return results
    for key in IDS:
        if key not in UNKNOWN_REASONS and checks[key] is True:
            results[key] = LOCAL
    return results


def operational(_identifier: object, _claim: object = None) -> str:
    return UNKNOWN


class BrechasFactory76Tests(unittest.TestCase):
    def test_contrato_principal(self):
        docs = documents()
        self.assertEqual(set(rows(docs)), set(IDS))
        checks = observed()
        self.assertEqual(set(checks), set(IDS))
        results = assess(docs, checks)
        self.assertEqual(len(results), 16)
        for key in IDS:
            with self.subTest(identifier=key):
                self.assertIs(type(checks[key]), bool)
                self.assertEqual(
                    UNKNOWN if key in UNKNOWN_REASONS else LOCAL,
                    results[key],
                )

    def test_falla_cerrado(self):
        docs = documents()
        good = dict.fromkeys(IDS, True)
        for key in IDS:
            line = next(line for line in docs[MATRIX].splitlines()
                        if line.startswith("| " + chr(96) + key + chr(96) + " |"))
            for bad in (
                docs[MATRIX].replace(line, "", 1),
                docs[MATRIX] + "\n" + line,
                docs[MATRIX].replace(
                    line, line.replace("NO_VERIFICABLE", "CUBIERTO", 1), 1,
                ),
            ):
                with self.subTest(identifier=key):
                    self.assertEqual(
                        {UNKNOWN}, set(assess({**docs, MATRIX: bad}, good).values()),
                    )
            path, number, _ = CLAUSES[key]
            altered = dict(docs)
            lines = altered[path].splitlines()
            if number is not None:
                lines[number - 1] = "SOURCE REDACTED"
            else:
                lines = ["SOURCE REDACTED"]
            altered[path] = "\n".join(lines)
            self.assertEqual({UNKNOWN}, set(assess(altered, good).values()))
            self.assertEqual(UNKNOWN, assess(docs, {**good, key: False})[key])
        for invalid in (None, {}, {MATRIX: docs[MATRIX]}):
            self.assertEqual({UNKNOWN}, set(assess(invalid, good).values()))
        self.assertEqual({UNKNOWN}, set(assess(docs, None).values()))

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0] for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
        imported |= {
            node.module.split(".")[0] for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertFalse(imported & {
            "requests", "httpx", "urllib", "pymysql",
            "playwright", "selenium", "subprocess",
        })
        with patch.object(socket, "socket",
                          side_effect=AssertionError("network prohibited")):
            checks = observed()
        self.assertTrue(checks[f"{SOURCE}:L29-U1"])
        self.assertFalse(checks[f"{MODE}:B03"])
        self.assertFalse(checks[f"{MODE}:B04"])

    def test_estados_unknown_explicitos(self):
        docs = documents()
        checks = dict.fromkeys(IDS, True)
        results = assess(docs, checks)
        self.assertEqual(
            {key for key, status in results.items() if status == UNKNOWN},
            set(UNKNOWN_REASONS),
        )
        for key, reason in UNKNOWN_REASONS.items():
            with self.subTest(identifier=key):
                self.assertGreater(len(reason), 25)
                self.assertEqual(results[key], UNKNOWN)
                for claim in (None, {"ci": "success"},
                              {"production": "VERIFIED"},
                              {"backup_verified": True},
                              {"rollback": "authorized"},
                              {"consumer_slo": 100}):
                    self.assertEqual(operational(key, claim), UNKNOWN)
        self.assertNotIn("VALIDATED_IN_PRODUCTION", results.values())


if __name__ == "__main__":
    unittest.main()
