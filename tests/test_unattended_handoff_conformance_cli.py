#!/usr/bin/env python3
"""Regresiones de la CLI offline de conformidad Factory#798."""

from __future__ import annotations

from copy import deepcopy
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

        invalid_cases: list[dict[str, object]] = []

        invalid = _fixture("allow")
        invalid["version"] = 2
        invalid_cases.append(invalid)

        invalid = _fixture("allow")
        provenance = invalid["provenance"]
        assert isinstance(provenance, dict)
        provenance["head_sha"] = "z" * 40
        invalid_cases.append(invalid)

        invalid = _fixture("allow")
        invalid["unexpected"] = True
        invalid_cases.append(invalid)

        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                self.assertEqual(
                    cli.evaluate_document(invalid),
                    {
                        "version": 1,
                        "conformant": False,
                        "code": "schema_validation_failed",
                    },
                )

        inline = json.dumps(_fixture("allow"))
        output = StringIO()
        exit_code = cli.main([inline], stdin=StringIO(""), stdout=output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            json.loads(output.getvalue()),
            {"code": "conformant", "conformant": True, "version": 1},
        )

        stdin_output = StringIO()
        stdin_code = cli.main(
            [],
            stdin=StringIO(inline),
            stdout=stdin_output,
        )
        self.assertEqual(stdin_code, 0)
        self.assertEqual(json.loads(stdin_output.getvalue())["code"], "conformant")

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
                [json.dumps(payload)],
                stdin=StringIO(""),
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

        failure_cases = (
            ('{"version":1,"version":1}', "duplicate_json_key"),
            ("{", "invalid_json"),
            ("x" * (cli.MAX_INPUT_BYTES + 1), "input_too_large"),
        )
        for raw, expected_code in failure_cases:
            with self.subTest(expected_code=expected_code):
                failure_output = StringIO()
                failure_code = cli.main(
                    [],
                    stdin=StringIO(raw),
                    stdout=failure_output,
                )
                self.assertEqual(failure_code, 2)
                self.assertEqual(
                    json.loads(failure_output.getvalue())["code"],
                    expected_code,
                )

        invalid_hash = deepcopy(_fixture("allow"))
        provenance = invalid_hash["provenance"]
        assert isinstance(provenance, dict)
        provenance["guard_ref"] = "0" * 63 + "g"
        self.assertFalse(cli.evaluate_document(invalid_hash)["conformant"])

        source = (ROOT / "scripts" / "unattended_handoff_conformance_cli.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "import re",
            "re.search",
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
