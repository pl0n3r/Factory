"""Factory#1849: causal, offline regressions for handoff v1 and kill switch.

D-classified consumer integrations cannot be proved from this Factory-only pack.
This test never consults the coverage matrix or a live consumer.
"""
from __future__ import annotations

from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
from urllib import request as urllib_request

from scripts import unattended_handoff_conformance_cli as conformance
from scripts.adaptive_fencing import FencingDecision
from scripts.unattended_cycle_handoff import project_unattended_cycle_handoff
from scripts.unattended_guards import evaluate_unattended_guards
from scripts.unattended_kill_switch import (
    CANONICAL_OWNER, CANONICAL_REPOSITORY_URL, CANONICAL_SOURCE_URL,
    evaluate_unattended_kill_switch,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "unattended_handoff_v1" / "allow.json"
PREFIX = "docs/unattended-handoff-consumer-pack.md:"
KILL = "docs/unattended-kill-switch.md:"

# Concrete functions used below directly exercise the runtime (not merely a
# documentation or matrix assertion). IDs permit later row-level reconciliation.
A = frozenset(PREFIX + line for line in (
    "L49-U1", "L51-U1", "L52-U1", "L53-U1", "L54-U1", "L55-U1",
    "L56-U1", "L58-U1", "L63-U1", "L64-U1", "L67-U1", "L68-U1",
    "L9-U1",
)) | frozenset(KILL + line for line in (
    "L11-U1", "L15-U1", "L19-U1", "L19-U2", "L20-U1",
))
D = {
    PREFIX + "L5-U1": "ControlBot/FactoryRunner runtime consumer integration is not part of Factory's read-only pack",
    PREFIX + "L43-U1": "both external consumers calling schema validation is not implemented/testable in this repo; only Factory's CLI validates",
}
PERMISSIONS = dict.fromkeys(("reserve", "merge", "deploy", "spend", "live"), False)


def _cycle(action: str = "ALLOW", *, freshness: str = "fresh") -> dict[str, object]:
    selected = "Factory#synthetic" if action == "ALLOW" else None
    provenance = {
        "head_sha": "a" * 40,
        "dispatch_ref": "synthetic:dispatch",
        "guard_ref": "b" * 64,
        "watchdog_ref": "c" * 64,
        "freshness": freshness,
    }
    return {
        "version": 1, "action": action, "authority": "unchanged",
        "selected": selected, "selected_class": "medium" if selected else None,
        "freshness": freshness, "reasons": ("synthetic-reason",),
        "provenance": None if freshness == "unknown" else provenance,
        "components": {"watchdog": {
            "action": action, "incident_codes": ("synthetic-incident",),
            "state_freshness": freshness, "interrupt_owner": False,
            "evidence_ref": "synthetic:watchdog",
        }},
    }


def _issue(marker: str = "RUNNING", *, state: str = "closed") -> dict[str, object]:
    return {
        "number": 767, "url": CANONICAL_SOURCE_URL,
        "repository_url": CANONICAL_REPOSITORY_URL, "state": state,
        "user": {"login": CANONICAL_OWNER},
        "body": ("<!-- factory-unattended-kill-switch "
                 + json.dumps({"version": 1, "state": marker, "owner": CANONICAL_OWNER})
                 + " -->"),
    }


def _guard(pause: bool, *, breaker_fresh: bool = True):
    config = {
        "global_pause": pause,
        "breakers": {"health": {"scope": "repo", "subject": "pl0n3r/Factory", "threshold": 3}},
        "ceilings": {"usage": 100, "cost": 50.0, "parallelism": 2},
    }
    evidence = {
        "breakers": {"health": {"consecutive_failures": 0, "fresh": breaker_fresh, "consistent": True}},
        "risk": "low", "second_pass": False,
        "sensitive": dict.fromkeys(("go_live", "spend", "irreversible", "real_data"), False),
        "production_change": False, "backup_required": False, "backup_verified": None,
    }
    fence = FencingDecision("keep", False, 1, 1, "a" * 64, "b" * 64, 1, ("synthetic",))
    return evaluate_unattended_guards(
        fence, config, evidence, {"usage": 1, "cost": 1.0, "parallelism": 1}
    )


class CoberturaFactory58Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        self.assertEqual((len(A), len(D), len(A | set(D))), (18, 2, 20))

        # L9/L63/L64: local file -> real parser -> canonical schema conformance.
        inline = FIXTURE.read_text(encoding="utf-8")
        payload = json.loads(inline)
        self.assertEqual(conformance.evaluate_document(payload)["code"], "conformant")
        output = StringIO()
        self.assertEqual(conformance.main([], stdin=StringIO(inline), stdout=output), 0)
        self.assertEqual(json.loads(output.getvalue())["conformant"], True)

        # L49/L51-L58/L67/L68: real read-only projector keeps evidence and
        # prohibits even an ALLOW document from granting operational power.
        for action, freshness in (("ALLOW", "fresh"), ("PAUSE", "fresh"), ("BLOCKED", "unknown")):
            with self.subTest(action=action):
                cycle = _cycle(action, freshness=freshness)
                doc = project_unattended_cycle_handoff(cycle)
                self.assertEqual(doc["action"], action)
                self.assertEqual(doc["next_transition"], action)
                self.assertEqual(doc["authority"], "unchanged")
                self.assertEqual(doc["permissions"], PERMISSIONS)
                for permission in PERMISSIONS:  # separate assertion for each row L52..L56
                    self.assertIs(doc["permissions"][permission], False)
                self.assertEqual(doc["reasons"], cycle["reasons"])
                self.assertEqual(doc["provenance"], cycle["provenance"])
                self.assertEqual(doc["incidents"], ("synthetic-incident",))
                self.assertIs(doc["interrupt_owner"], False)
                self.assertTrue(conformance.evaluate_document(json.loads(json.dumps(doc)))["conformant"])

        # Kill L11/L15/L19/L19-U2/L20: exact canonical marker and issue state,
        # RUNNING does not override remaining 4B guards; PAUSED closes it.
        running = evaluate_unattended_kill_switch(_issue())
        paused = evaluate_unattended_kill_switch(_issue("PAUSED"))
        self.assertEqual((running.state, running.global_pause), ("RUNNING", False))
        self.assertEqual((paused.state, paused.global_pause), ("PAUSED", True))
        self.assertEqual(_guard(running.global_pause).action, "ALLOW")
        self.assertEqual(_guard(running.global_pause, breaker_fresh=False).action, "BLOCKED")
        paused_guard = _guard(paused.global_pause)
        self.assertEqual(paused_guard.action, "BLOCKED")
        self.assertIn("global_pause_active", paused_guard.reasons)

    def test_falla_cerrado(self) -> None:
        valid = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for field, replacement in (
            ("version", 2), ("authority", "elevated"),
            ("permissions", {**PERMISSIONS, "reserve": True}),
            ("permissions", {**PERMISSIONS, "merge": True}),
            ("permissions", {**PERMISSIONS, "deploy": True}),
            ("permissions", {**PERMISSIONS, "spend": True}),
            ("permissions", {**PERMISSIONS, "live": True}),
            ("freshness", "unknown"), ("unexpected", "synthetic"),
        ):
            with self.subTest(field=field, replacement=replacement):
                bad = deepcopy(valid)
                bad[field] = replacement
                self.assertFalse(conformance.evaluate_document(bad)["conformant"])
        missing = deepcopy(valid)
        del missing["permissions"]
        self.assertFalse(conformance.evaluate_document(missing)["conformant"])

        for raw, error in (('{"version":1,"version":1}', "duplicate_json_key"), ("{", "invalid_json")):
            out = StringIO()
            self.assertEqual(conformance.main([], stdin=StringIO(raw), stdout=out), 2)
            self.assertEqual(json.loads(out.getvalue())["code"], error)

        for wrong in (None, {}, _issue(state="open"), _issue("UNKNOWN")):
            with self.subTest(wrong=wrong):
                result = evaluate_unattended_kill_switch(wrong)
                self.assertEqual((result.state, result.global_pause), ("UNKNOWN", True))
        duplicate = _issue()
        duplicate["body"] += "\n" + _issue("PAUSED")["body"]
        self.assertEqual(evaluate_unattended_kill_switch(duplicate).reason, "kill_switch_marker_count_invalid")
        for wrong in ({"authority": "elevated"}, {"action": "UNKNOWN"}, {"extra": 1}):
            with self.subTest(wrong=wrong):
                result = project_unattended_cycle_handoff({**_cycle(), **wrong})
                self.assertEqual(result["action"], "BLOCKED")
                self.assertEqual(result["permissions"], PERMISSIONS)

    def test_sin_datos_reales(self) -> None:
        fake_secret = "synthetic-secret-must-not-escape"
        bad = json.loads(FIXTURE.read_text(encoding="utf-8"))
        bad["token"] = fake_secret
        with (
            patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")),
            patch.object(urllib_request, "urlopen", side_effect=AssertionError("network forbidden")),
            patch.object(subprocess, "run", side_effect=AssertionError("subprocess forbidden")),
        ):
            output = StringIO()
            code = conformance.main([json.dumps(bad)], stdin=StringIO(""), stdout=output)
            self.assertEqual(code, 2)
            self.assertFalse(conformance.evaluate_document(bad)["conformant"])
            self.assertEqual(project_unattended_cycle_handoff(_cycle())["permissions"], PERMISSIONS)
            self.assertTrue(evaluate_unattended_kill_switch(_issue("PAUSED")).global_pause)
        self.assertNotIn(fake_secret, output.getvalue())
        self.assertNotIn("token", output.getvalue())
        self.assertTrue(all(row.startswith("docs/") for row in A | set(D)))


if __name__ == "__main__":
    unittest.main()
