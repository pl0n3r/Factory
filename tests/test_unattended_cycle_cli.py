#!/usr/bin/env python3
"""Regresiones de la CLI offline del ciclo desatendido Factory#773."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
from unittest import TestCase
from unittest.mock import patch
import urllib.request

from scripts import unattended_cycle_cli as cli


def snapshot() -> dict[str, object]:
    return {
        "version": 1,
        "dispatch": {
            "selected": "Factory#773",
            "selected_class": "high",
            "next_action": {"step": "normal"},
            "ready_not_selected": [],
            "excluded": {},
            "candidates": {},
            "aging_threshold": 3,
            "active_tranche": None,
            "unattended": {
                "enabled": True,
                "action": "ALLOW",
                "authority": "unchanged",
                "reasons": [],
            },
        },
        "guard": {
            "action": "ALLOW",
            "authority": "unchanged",
            "pause_allowed": False,
            "reasons": ["guards_satisfied"],
            "evidence_fingerprint": "a" * 64,
        },
        "watchdog": {
            "action": "ALLOW",
            "authority": "unchanged",
            "incidents": [],
            "new_alert_fingerprints": [],
            "interrupt_owner": False,
            "daily_summary": {
                "active_fronts": ["Factory#773"],
                "state_freshness": "fresh",
                "incidents": [],
                "blockers": [],
                "human_gates": [],
                "integrated": [],
                "reverted": [],
                "next_actions": ["compose"],
            },
            "evidence_fingerprint": "b" * 64,
        },
        "provenance": {
            "head_sha": "c" * 40,
            "dispatch_ref": "dispatcher:exact-snapshot",
            "guard_ref": "a" * 64,
            "watchdog_ref": "b" * 64,
            "freshness": "fresh",
        },
    }


def run_stdin(payload: dict[str, object]) -> tuple[int, str]:
    stdin = io.StringIO(json.dumps(payload))
    stdout = io.StringIO()
    return cli.main([], stdin=stdin, stdout=stdout), stdout.getvalue()


class UnattendedCycleCliTests(TestCase):
    def test_cli_emits_deterministic_secret_free_cycle_from_local_snapshot(self):
        original = cli.compose_unattended_cycle
        with patch.object(
            cli,
            "compose_unattended_cycle",
            wraps=original,
        ) as compose:
            first_rc, first = run_stdin(snapshot())

        second_rc, second = run_stdin(snapshot())

        self.assertEqual(first_rc, 0)
        self.assertEqual(second_rc, 0)
        self.assertEqual(first, second)
        compose.assert_called_once()

        parsed = json.loads(first)
        self.assertEqual(parsed["action"], "ALLOW")
        self.assertEqual(parsed["authority"], "unchanged")
        self.assertEqual(parsed["selected"], "Factory#773")
        self.assertEqual(parsed["freshness"], "fresh")
        self.assertEqual(parsed["provenance"]["head_sha"], "c" * 40)
        lowered = first.lower()
        self.assertNotIn("password=", lowered)
        self.assertNotIn("secret=", lowered)
        self.assertNotIn("token=", lowered)
        self.assertNotIn("@example.", lowered)

        unsafe = snapshot()
        unsafe["dispatch"]["selected"] = "token=do-not-emit"
        unsafe_rc, unsafe_output = run_stdin(unsafe)
        self.assertEqual(unsafe_rc, 2)
        self.assertEqual(json.loads(unsafe_output), {"error": "invalid_snapshot"})
        self.assertNotIn("do-not-emit", unsafe_output)

    def test_cli_is_confined_and_performs_no_network_or_external_mutation(self):
        raw = json.dumps(snapshot())

        with (
            patch.object(socket, "create_connection", side_effect=AssertionError("network")),
            patch.object(urllib.request, "urlopen", side_effect=AssertionError("network")),
            patch.object(subprocess, "run", side_effect=AssertionError("process")),
            patch.object(Path, "write_text", side_effect=AssertionError("write")),
            patch.object(Path, "write_bytes", side_effect=AssertionError("write")),
            patch.object(Path, "unlink", side_effect=AssertionError("delete")),
            patch.object(Path, "rename", side_effect=AssertionError("rename")),
            patch.object(Path, "replace", side_effect=AssertionError("replace")),
            patch.object(os, "remove", side_effect=AssertionError("delete")),
            patch.object(os, "replace", side_effect=AssertionError("replace")),
        ):
            stdin = io.StringIO(raw)
            stdout = io.StringIO()
            rc = cli.main([], stdin=stdin, stdout=stdout)

        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue())["action"], "ALLOW")

        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory) / "snapshot.json"
            external.write_text(raw, encoding="utf-8")
            before = external.read_bytes()
            stdout = io.StringIO()
            original_resolve = Path.resolve

            def guarded_resolve(path: Path, *args, **kwargs):
                if path == external:
                    raise AssertionError("external path must be rejected before resolve")
                return original_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", guarded_resolve):
                rc = cli.main(
                    ["--snapshot", str(external)],
                    stdin=io.StringIO(""),
                    stdout=stdout,
                )
            after = external.read_bytes()

        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(stdout.getvalue()), {"error": "invalid_snapshot"})
        self.assertEqual(before, after)


if __name__ == "__main__":
    import unittest

    unittest.main()
