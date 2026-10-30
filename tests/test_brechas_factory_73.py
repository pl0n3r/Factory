"""Factory #1691: 16 brechas de handoff y kill switch con datos sintéticos.

La semántica local comprobable se distingue de la autoridad operativa externa:
UNKNOWN nunca certifica una mutación, una orden del dueño ni un ciclo de agentes.
Esta hoja no modifica ni promueve docs/matriz-cobertura.md.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_guards import evaluate_unattended_guards
from scripts.unattended_kill_switch import (
    CANONICAL_OWNER,
    CANONICAL_REPOSITORY_URL,
    CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"
HANDOFF = "docs/unattended-handoff-consumer-pack.md"
SWITCH = "docs/unattended-kill-switch.md"
H = HANDOFF + ":"
K = SWITCH + ":"
IDS = (
    H + "L68-U1", H + "L9-U1",
    K + "L11-U1", K + "L15-U1", K + "L19-U1", K + "L19-U2",
    K + "L20-U1", K + "L20-U2", K + "L21-U1", K + "L21-U2",
    K + "L25-U1", K + "L27-U1", K + "L31-U1", K + "L33-U1",
    K + "L37-U1", K + "L39-U1",
)
# No hay API local que pruebe quién autorizó la edición o que otro agente
# haya consultado GitHub antes de mutar. Mantener estas filas UNKNOWN.
GOVERNANCE_UNKNOWN = frozenset({
    K + "L20-U2", K + "L25-U1", K + "L27-U1", K + "L31-U1",
})
PERMISSIONS = {"reserve": False, "merge": False, "deploy": False,
               "spend": False, "live": False}
RUNNING = '<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->'
PAUSED = '<!-- factory-unattended-kill-switch {"version":1,"state":"PAUSED","owner":"pl0n3r"} -->'


def issue(body: str = RUNNING) -> dict[str, object]:
    return {"number": 767, "url": CANONICAL_SOURCE_URL,
            "repository_url": CANONICAL_REPOSITORY_URL, "state": "closed",
            "user": {"login": CANONICAL_OWNER}, "body": body}


def documents() -> dict[str, str]:
    return {path: (ROOT / path).read_text(encoding="utf-8")
            for path in (HANDOFF, SWITCH, "docs/matriz-cobertura.md")}


def pack() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    schema = json.loads((ROOT / "config/unattended-handoff-v1.schema.json")
                        .read_text(encoding="utf-8"))
    folder = ROOT / "tests/fixtures/unattended_handoff_v1"
    fixtures = {name: json.loads((folder / (name + ".json"))
                .read_text(encoding="utf-8"))
                for name in ("allow", "pause", "blocked", "unknown")}
    return schema, fixtures


def matrix_rows(raw: object) -> dict[str, tuple[str, ...]]:
    if type(raw) is not str:
        raise ValueError(UNKNOWN + ": matrix unavailable")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        parts = tuple(item.strip() for item in line.strip("|").split("|"))
        key = parts[0].strip(chr(96))
        if key not in IDS:
            continue
        if (key in found or len(parts) != 5 or
                parts[0] != chr(96) + key + chr(96) or
                not line.endswith("|")):
            raise ValueError(UNKNOWN + ": ambiguous matrix row " + key)
        found[key] = parts
    if set(found) != set(IDS):
        raise ValueError(UNKNOWN + ": missing matrix row")
    return found


def contract_deny(schema: object, fixtures: object) -> bool:
    """Acredita únicamente el contrato local de denegación, no consumidores."""
    if type(schema) is not dict or type(fixtures) is not dict:
        return False
    try:
        shape = schema["$defs"]["permissions"]
        if (shape["additionalProperties"] is not False or
                set(shape["required"]) != set(PERMISSIONS) or
                set(shape["properties"]) != set(PERMISSIONS)):
            return False
        if any(shape["properties"][key]["const"] is not False
               for key in PERMISSIONS):
            return False
        if set(fixtures) != {"allow", "pause", "blocked", "unknown"}:
            return False
        for name, payload in fixtures.items():
            if (type(payload) is not dict or payload["authority"] != "unchanged"
                    or type(payload["permissions"]) is not dict
                    or payload["permissions"] != PERMISSIONS
                    or any(type(value) is not bool
                           for value in payload["permissions"].values())):
                return False
            if (name == "unknown") != (payload["freshness"] == "unknown"):
                return False
            if name == "unknown" and (payload["action"] != "BLOCKED"
                                      or payload["next_transition"] != "BLOCKED"):
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def guard_still_applies(global_pause: bool) -> bool:
    """RUNNING quita solo la pausa global, no las demás guardas 4B."""
    if global_pause is not False:
        return False
    fencing = FencingDecision("keep", True, 7, 1, "a" * 64,
                              "b" * 64, 1, ("synthetic",))
    config = {"global_pause": False,
              "breakers": {"health": {"scope": "repo",
                                      "subject": "pl0n3r/Factory",
                                      "threshold": 3}},
              "ceilings": {"usage": 100, "cost": 50.0, "parallelism": 2}}
    evidence = {
        "breakers": {"health": {"consecutive_failures": 0,
                                 "fresh": True, "consistent": True}},
        "risk": "low", "second_pass": False,
        "sensitive": {"go_live": False, "spend": False,
                      "irreversible": False, "real_data": False},
        "production_change": False, "backup_required": False,
        "backup_verified": None,
    }
    def verdict(pause: bool, failures: int) -> tuple[str, tuple[str, ...], str]:
        config["global_pause"] = pause
        evidence["breakers"]["health"]["consecutive_failures"] = failures
        decision = evaluate_unattended_guards(
            fencing, config, evidence,
            {"usage": 10, "cost": 5.0, "parallelism": 1})
        return decision.action, decision.reasons, decision.authority
    return (
        verdict(False, 0) == ("ALLOW", ("guards_satisfied",), "unchanged")
        and verdict(False, 3) == ("PAUSE", ("circuit_breaker_open",), "unchanged")
        and verdict(True, 0) == ("PAUSE", ("global_pause_active",), "unchanged")
    )


def assess(
    docs: object, schema: object, fixtures: object, switch_payload: object
) -> dict[str, str]:
    result = dict.fromkeys(IDS, UNKNOWN)
    if type(docs) is not dict or set(docs) != {
        HANDOFF, SWITCH, "docs/matriz-cobertura.md"
    }:
        return result
    try:
        rows = matrix_rows(docs["docs/matriz-cobertura.md"])
        valid_sources = {}
        for key, row in rows.items():
            path, position = key.split(":L", 1)
            line_number = int(position.split("-", 1)[0])
            source = docs[path].splitlines()
            valid_sources[key] = (0 < line_number <= len(source)
                                  and row[1] in source[line_number - 1])
        running = evaluate_unattended_kill_switch(switch_payload)
        paused = evaluate_unattended_kill_switch(issue(PAUSED))
        missing = evaluate_unattended_kill_switch(None)
        reopened = issue()
        reopened["state"] = "open"
        invalid = evaluate_unattended_kill_switch(reopened)
        duplicated = evaluate_unattended_kill_switch(issue(RUNNING + PAUSED))
        handoff_ok = contract_deny(schema, fixtures)
        flags = {
            H + "L68-U1": handoff_ok,
            H + "L9-U1": handoff_ok,
            K + "L11-U1": running.state == "RUNNING"
                and duplicated.state == UNKNOWN and duplicated.global_pause,
            K + "L15-U1": invalid.state == UNKNOWN and invalid.global_pause,
            K + "L19-U1": running.state == "RUNNING"
                and running.global_pause is False,
            K + "L19-U2": guard_still_applies(running.global_pause),
            K + "L20-U1": paused.state == "PAUSED"
                and paused.global_pause is True,
            K + "L21-U1": missing.state == UNKNOWN,
            K + "L21-U2": missing.global_pause is True,
            K + "L33-U1": guard_still_applies(running.global_pause),
            K + "L37-U1": (invalid.state == UNKNOWN
                           and duplicated.state == UNKNOWN),
            K + "L39-U1": missing.state == UNKNOWN,
        }
        for key, passed in flags.items():
            if type(passed) is bool and passed and valid_sources[key]:
                result[key] = LOCAL
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return dict.fromkeys(IDS, UNKNOWN)
    return result


class BrechasFactory73Tests(unittest.TestCase):
    def test_contrato_principal(self):
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        docs = documents()
        self.assertEqual(set(matrix_rows(docs["docs/matriz-cobertura.md"])),
                         set(IDS))
        schema, fixtures = pack()
        results = assess(docs, schema, fixtures, issue())
        self.assertEqual(set(results), set(IDS))
        for key in IDS:
            with self.subTest(row=key):
                self.assertEqual(
                    results[key], UNKNOWN if key in GOVERNANCE_UNKNOWN else LOCAL)

    def test_falla_cerrado(self):
        docs = documents()
        schema, fixtures = pack()
        baseline = assess(docs, schema, fixtures, issue())
        for bad in (None, {}, issue(RUNNING + PAUSED), issue("sin marker"),
                    issue('<!-- factory-unattended-kill-switch {bad} -->')):
            with self.subTest(payload=repr(bad)[:80]):
                self.assertEqual(evaluate_unattended_kill_switch(bad).state,
                                 UNKNOWN)
                self.assertTrue(evaluate_unattended_kill_switch(bad).global_pause)
                self.assertEqual(assess(docs, schema, fixtures, bad)[K + "L19-U1"],
                                 UNKNOWN)
        mutated = dict(fixtures)
        mutated["allow"] = {**fixtures["allow"],
                            "permissions": {**PERMISSIONS, "merge": True}}
        self.assertFalse(contract_deny(schema, mutated))
        self.assertEqual(assess(docs, schema, mutated, issue())[H + "L68-U1"],
                         UNKNOWN)
        incomplete = dict(fixtures)
        incomplete.pop("unknown")
        self.assertFalse(contract_deny(schema, incomplete))
        altered = dict(docs)
        altered[HANDOFF] = ""
        self.assertEqual(assess(altered, schema, fixtures, issue())[H + "L9-U1"],
                         UNKNOWN)
        altered["docs/matriz-cobertura.md"] = ""
        self.assertTrue(all(value == UNKNOWN for value in
                            assess(altered, schema, fixtures, issue()).values()))
        self.assertEqual(baseline[K + "L19-U1"], LOCAL)
        self.assertTrue(guard_still_applies(False))
        self.assertFalse(guard_still_applies(True))
        # Si se elimina la rama circuit_breaker_open, esta cobertura falla.
        real_evaluator = evaluate_unattended_guards

        def without_breaker(fencing, config, evidence, measurements):
            sanitized = dict(evidence)
            sanitized["breakers"] = {
                "health": {**evidence["breakers"]["health"],
                           "consecutive_failures": 0},
            }
            return real_evaluator(fencing, config, sanitized, measurements)

        with patch(__name__ + ".evaluate_unattended_guards",
                   side_effect=without_breaker):
            self.assertFalse(guard_still_applies(False))

    def test_sin_datos_reales(self):
        with patch("socket.socket", side_effect=AssertionError("red prohibida")):
            docs = documents()
            schema, fixtures = pack()
            results = assess(docs, schema, fixtures, issue())
        self.assertEqual(results[H + "L68-U1"], LOCAL)
        self.assertEqual(set(fixtures), {"allow", "pause", "blocked", "unknown"})
        self.assertEqual(set(PERMISSIONS), {"reserve", "merge", "deploy",
                                            "spend", "live"})
        self.assertTrue(all(not value for value in PERMISSIONS.values()))

    def test_estados_unknown_explicitos(self):
        docs = documents()
        schema, fixtures = pack()
        results = assess(docs, schema, fixtures, issue())
        self.assertEqual({key for key, value in results.items()
                          if value == UNKNOWN}, GOVERNANCE_UNKNOWN)
        for key in GOVERNANCE_UNKNOWN:
            with self.subTest(row=key):
                self.assertIn(key, IDS)
                self.assertEqual(results[key], UNKNOWN)
        self.assertEqual(assess(None, schema, fixtures, issue()),
                         dict.fromkeys(IDS, UNKNOWN))
        self.assertEqual(assess(docs, None, fixtures, issue())[H + "L9-U1"],
                         UNKNOWN)


if __name__ == "__main__":
    unittest.main()
