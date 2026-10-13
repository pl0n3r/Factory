#!/usr/bin/env python3
"""Pruebas de la lectura real de comentarios para el gate de release."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "factory-ci.yml"
COMMAND_PATTERN = re.compile(
    r'gh api --paginate[^\n]*\|\s*jq -s -e \x27.*?\x27\s*>\s*/tmp/release-comments\.json',
    re.DOTALL,
)


def comment(number: int, login: str, body: str) -> dict:
    return {"id": number, "user": {"login": login}, "body": body}


class ReleaseCommentPagesTests(unittest.TestCase):
    def _command(self) -> str:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        matches = COMMAND_PATTERN.findall(workflow)
        self.assertEqual(len(matches), 1, "Falta la tubería canónica real")
        return matches[0]

    def _run_pages(
        self, pages: list[object], *, gh_exit_code: int = 0
    ) -> tuple[subprocess.CompletedProcess[str], object]:
        self.assertIsNotNone(shutil.which("jq"), "CI necesita jq para probar la tubería real")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_gh = root / "gh"
            fake_gh.write_text(
                '#!/bin/sh\ncat "$TEST_COMMENT_PAGES"\nexit "$TEST_GH_EXIT_CODE"\n',
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            fixture = root / "pages.jsonl"
            fixture.write_text(
                "".join(json.dumps(page, separators=(",", ":")) + "\n" for page in pages),
                encoding="utf-8",
            )
            destination = root / "filtered.json"
            command = self._command().replace(
                "/tmp/release-comments.json", str(destination)
            )
            env = dict(os.environ)
            env.update({
                "PATH": directory + os.pathsep + env.get("PATH", ""),
                "TEST_COMMENT_PAGES": str(fixture),
                "TEST_GH_EXIT_CODE": str(gh_exit_code),
                "REPOSITORY": "pl0n3r/Factory",
                "number": "1070",
            })
            result = subprocess.run(
                ["bash", "-c", "set -euo pipefail\n" + command],
                cwd=ROOT, env=env, capture_output=True, text=True, check=False,
                timeout=12,
            )
            payload = (
                json.loads(destination.read_text(encoding="utf-8"))
                if result.returncode == 0 else None
            )
            return result, payload

    def test_single_and_two_pages_preserve_relevant_bot_markers(self):
        empty, value = self._run_pages([[]])
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(value, [])

        one_page = [
            comment(1, "alice", "factory-human-decision sensitive-human-text"),
            comment(2, "github-actions[bot]", "irrelevant"),
            comment(3, "github-actions[bot]", "factory-human-decision"),
            comment(4, "github-actions[bot]", "factory-release-executed"),
            comment(5, "github-actions[bot]", "factory-human-gate-duplicate"),
        ]
        single, filtered = self._run_pages([one_page])
        self.assertEqual(single.returncode, 0, single.stderr)
        self.assertEqual(len(filtered), 3)
        self.assertTrue(all(row["user"]["login"] == "github-actions[bot]" for row in filtered))
        self.assertNotIn("sensitive-human-text", json.dumps(filtered))
        self.assertEqual([row["body"] for row in filtered],
                         ["factory-human-decision", "factory-release-executed",
                          "factory-human-gate-duplicate"])

        first = [comment(n, "human", "private body") for n in range(1, 101)]
        second = [comment(101, "github-actions[bot]", "factory-human-decision")]
        multiple, filtered = self._run_pages([first, second])
        self.assertEqual(multiple.returncode, 0, multiple.stderr)
        self.assertEqual(filtered, [{"user": {"login": "github-actions[bot]"},
                                    "body": "factory-human-decision"}])

    def test_malformed_or_incomplete_comment_pages_fail_closed(self):
        first = [comment(n, "human", "body") for n in range(1, 101)]
        cases = {
            "missing_pages": [],
            "invalid_root": [{"message": "synthetic error"}],
            "flat_object": [comment(1, "human", "body")],
            "truncated_nonfinal_page": [[comment(1, "human", "x")],
                                        [comment(2, "human", "x")]],
            "duplicate_id": [first, [comment(7, "human", "x")]],
            "missing_id": [[{"user": {"login": "github-actions[bot]"},
                             "body": "factory-human-decision"}]],
            "invalid_user": [[{"id": 1, "user": "private", "body": "x"}]],
            "invalid_body": [[{"id": 1, "user": {"login": "github-actions[bot]"},
                               "body": None}]],
            "too_many_per_page": [[comment(n, "human", "x") for n in range(1, 102)]],
            "too_many_pages": [first for _ in range(11)],
            # Sin prueba de terminalidad, el último lote de 100 falla cerrado.
            "terminal_full_page_unverified": [first],
            "ten_terminal_full_pages_unverified": [
                [comment(page * 100 + n, "human", "x") for n in range(1, 101)]
                for page in range(10)
            ],
        }
        for name, pages in cases.items():
            with self.subTest(name=name):
                result, filtered = self._run_pages(pages)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(filtered)
                self.assertNotIn("private body", result.stderr)

        # Un HTTP 403 con stdout JSON válido nunca puede acreditar un gate.
        one, filtered = self._run_pages(
            [[comment(1, "github-actions[bot]", "factory-human-decision")]],
            gh_exit_code=22,
        )
        self.assertNotEqual(one.returncode, 0, "HTTP 403 no puede acreditar un gate")
        self.assertIsNone(filtered)

        # Tampoco una segunda página completa si gh termina sin éxito.
        first = [comment(n, "human", "body") for n in range(1, 101)]
        two, filtered = self._run_pages(
            [first, [comment(101, "github-actions[bot]", "factory-release-executed")]],
            gh_exit_code=22,
        )
        self.assertNotEqual(two.returncode, 0, "API parcial no es evidencia")
        self.assertIsNone(filtered)


    def test_release_issue_inventory_read_failure_stops_before_gate(self):
        """Run the exact workflow inventory reader; zero items remain valid."""
        source = WORKFLOW.read_text(encoding="utf-8")
        release = source.split("\n  release_window:", 1)[1].split(
            "\n  coordinacion:", 1
        )[0]
        matches = re.findall(
            r"(?m)^\s+(jq -s -c '[^\n]+' /tmp/release-issues\.json"
            r" > /tmp/release-issues\.jsonl)$",
            release,
        )
        self.assertEqual(len(matches), 1, "Falta lector materializado único")
        self.assertNotIn("done < <(", release)
        self.assertIn("done < /tmp/release-issues.jsonl", release)
        self.assertLess(
            release.index("jq -s -c 'if length == 1"),
            release.index("printf '[]"),
            "La validación debe ocurrir antes de crear gates vacíos",
        )
        self.assertIsNotNone(shutil.which("jq"), "Prueba de jq real obligatoria")
        scenarios = [
            ("empty_valid", "[]\n", True, []),
            ("one_valid", '[{"number":7}]\n', True, ['{"number":7}']),
            ("truncated", "[\n", False, None),
            ("wrong_root", "{}\n", False, None),
            ("null_root", "null\n", False, None),
            ("two_roots", "[]\n[]\n", False, None),
            ("missing_file", None, False, None),
        ]
        for name, payload, accepted, expected in scenarios:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                input_file = Path(directory) / "release-issues.json"
                output_file = Path(directory) / "release-issues.jsonl"
                if payload is not None:
                    input_file.write_text(payload, encoding="utf-8")
                command = matches[0].replace(
                    "/tmp/release-issues.jsonl", str(output_file)
                ).replace("/tmp/release-issues.json", str(input_file))
                process = subprocess.run(
                    ["bash", "-c", "set -euo pipefail\n" + command + "\necho GATES_MAY_RUN"],
                    cwd=ROOT, capture_output=True, text=True, check=False, timeout=10,
                )
                self.assertEqual(process.returncode == 0, accepted, process.stderr)
                self.assertEqual("GATES_MAY_RUN" in process.stdout, accepted)
                if accepted:
                    self.assertEqual(
                        output_file.read_text(encoding="utf-8").splitlines(), expected
                    )
                else:
                    self.assertNotIn("GATES_MAY_RUN", process.stdout)

    def test_workflow_contains_strict_paginated_comment_read(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(len(COMMAND_PATTERN.findall(source)), 1)
        command = self._command()
        self.assertIn("gh api --paginate", command)
        self.assertIn("jq -s -e", command)
        self.assertNotIn("--slurp", command)
        self.assertIn("invalid_comment_shape", command)
        self.assertIn("duplicate_comment_id", command)
        self.assertIn("incomplete_comment_pages", command)
        self.assertIn("(.[-1] | length) == 100", command)
        self.assertIn("factory-human-gate-duplicate", command)
        release_job = source.split("\n  release_window:", 1)[1].split(
            "\n  coordinacion:", 1
        )[0]
        self.assertIn("issues: read", release_job)
        self.assertIn("set -euo pipefail", release_job)
        self.assertNotIn("issues: write", release_job)
        self.assertIn("scripts/release_window.py pr-check", release_job)
        self.assertIn("cmp -s /tmp/release-search-verified-1.json", release_job)
        self.assertNotIn("|| true", command)


if __name__ == "__main__":
    unittest.main()
