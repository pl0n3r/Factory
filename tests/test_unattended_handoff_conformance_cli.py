#!/usr/bin/env python3
"""Regresiones de la CLI offline de conformidad Factory#798."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import socket
import subprocess
from unittest import TestCase
from unittest.mock import patch

from scripts import unattended_handoff_conformance_cli as cli


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "unattended_handoff_v1"


def _fixture(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / f"{name}.json").open(encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


class UnattendedHandoffConformanceCliTests(TestCase):
    def test_cli_validates_local_fixture_deterministically(self):
        for name in ("allow", "pause", "blocked", "unknown"):
            with self.subTest(name=name):
                payload = _fixture(name)
                first = cli.evaluate_document(payload)
                second = cli.evaluate_document(payload)
                self.assertEqual(first, second)
                self.assertEqual(
                    first,
                    {"version": 1, "conformant": True, "code": "conformant"},
                )

        invalid = _fixture("allow")
        invalid["version"] = 2
        self.assertEqual(
            cli.evaluate_document(invalid),
            {
                "version": 1,
                "conformant": False,
                "code": "schema_validation_failed",
            },
        )

        output = StringIO()
        exit_code = cli.main(
            [],
            stdin=StringIO(json.dumps(_fixture("allow"))),
            stdout=output,
        )
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {"code": "conformant", "conformant": True, "version": 1},
        )

    def test_cli_is_secret_free_and_external_io_free(self):
        secret = "super-secret-value-that-must-not-leak"
        payload = _fixture("allow")
        payload["token"] = secret

        with (
            patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("network forbidden"),
            ),
            patch.object(
                subprocess,
                "run",
                side_effect=AssertionError("subprocess forbidden"),
            ),
        ):
            output = StringIO()
            exit_code = cli.main(
                [],
                stdin=StringIO(json.dumps(payload)),
                stdout=output,
            )

        self.assertEqual(exit_code, 2)
        rendered = output.getvalue()
        self.assertNotIn(secret, rendered)
        self.assertNotIn("token", rendered)
        self.assertEqual(
            json.loads(rendered),
            {
                "code": "schema_validation_failed",
                "conformant": False,
                "version": 1,
            },
        )

        duplicate_output = StringIO()
        duplicate_code = cli.main(
            [],
            stdin=StringIO('{"version":1,"version":1}'),
            stdout=duplicate_output,
        )
        self.assertEqual(duplicate_code, 2)
        self.assertEqual(
            json.loads(duplicate_output.getvalue())["code"],
            "duplicate_json_key",
        )

        source = (ROOT / "scripts" / "unattended_handoff_conformance_cli.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "urllib",
            "requests",
            "http.client",
            "subprocess.",
            "socket.",
            "github",
        ):
            self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    import unittest

    unittest.main()
