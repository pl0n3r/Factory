"""Regresiones offline del transporte de release y sus gates canónicos (#1132)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "factory-ci.yml"
HELPER_START = "# RELEASE_API_HELPER_START"
HELPER_END = "# RELEASE_API_HELPER_END"
CANDIDATES_START = "# RELEASE_GATE_CANDIDATES_START"
CANDIDATES_END = "# RELEASE_GATE_CANDIDATES_END"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    body = _workflow()
    if body.count(start) != 1 or body.count(end) != 1:
        raise AssertionError("La implementación del gate debe tener un bloque único.")
    lines = body.splitlines()
    begin = next(i for i, line in enumerate(lines) if start in line)
    finish = next(i for i, line in enumerate(lines) if end in line)
    if finish <= begin:
        raise AssertionError("Delimitadores del workflow desordenados.")
    return textwrap.dedent("\n".join(lines[begin:finish + 1]))


def _candidate_script() -> str:
    block = _block(CANDIDATES_START, CANDIDATES_END)
    lines = block.splitlines()
    begin = next(i for i, line in enumerate(lines) if line.startswith("python3 - "))
    end = next(i for i, line in enumerate(lines[begin + 1:], begin + 1)
               if line.strip() == "PY")
    return "\n".join(lines[begin + 1:end]) + "\n"


def _candidate_numbers(rows: list[dict]) -> list[int]:
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / "verified.json"
        file.write_text(json.dumps(rows), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-c", _candidate_script(), str(file)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise AssertionError(
                "La selección canónica debe operar offline: " + result.stderr
            )
        return [entry["number"] for entry in json.loads(result.stdout)]


def _fake_gh_error(*, phase: str, message: str, partial_stdout: str = "") -> tuple[subprocess.CompletedProcess[str], int]:
    """Ejecuta el wrapper shell real con gh fake y cuenta llamadas efectivas."""
    helper = _block(HELPER_START, HELPER_END)
    with tempfile.TemporaryDirectory() as tmp:
        count = Path(tmp) / "calls.txt"
        output = Path(tmp) / "partial.json"
        fake = Path(tmp) / "gh"
        fake.write_text(
            '#!/bin/sh\n'
            'printf "called\\n" >> "$FAKE_GH_COUNT"\n'
            'printf "%s\\n" "$FAKE_GH_MESSAGE" >&2\n'
            'printf "%s" "$FAKE_GH_PARTIAL"\n'
            'exit 1\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)
        shell = (
            "set -euo pipefail\n"
            + helper + "\n"
            + f"release_gh_api {phase} --paginate 'repos/fake/issues/1/comments?per_page=100' > \"$FAKE_GH_OUTPUT\"\n"
            + "echo INVALID_SUCCESS\n"
        )
        env = dict(os.environ, FAKE_GH_COUNT=str(count),
                   FAKE_GH_MESSAGE=message, FAKE_GH_PARTIAL=partial_stdout,
                   FAKE_GH_OUTPUT=str(output))
        env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
        result = subprocess.run(["bash", "-c", shell], cwd=ROOT, env=env,
                                text=True, capture_output=True, check=False)
        calls = count.read_text(encoding="utf-8").count("called") if count.exists() else 0
        return result, calls


class ReleaseApiQuotaTests(unittest.TestCase):
    def test_primary_rate_limit_fails_closed_with_typed_evidence(self):
        result, calls = _fake_gh_error(
            phase="comments",
            message="gh: API rate limit exceeded for installation (HTTP 403)",
            partial_stdout='{"message":"fake failure"}',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, 1)
        self.assertIn("release_api_quota_exhausted phase=comments", result.stderr)
        self.assertIn("fail_closed=true", result.stderr)
        self.assertNotIn("INVALID_SUCCESS", result.stdout)
        self.assertNotIn("fake failure", result.stderr)
        self.assertNotIn("GITHUB_TOKEN", result.stderr)

        search, search_calls = _fake_gh_error(
            phase="search", message="gh: API rate limit exceeded for installation"
        )
        self.assertNotEqual(search.returncode, 0)
        self.assertEqual(search_calls, 1)
        self.assertIn("release_api_quota_exhausted phase=search", search.stderr)

        unknown, calls = _fake_gh_error(phase="metadata", message="HTTP 403 Forbidden")
        self.assertNotEqual(unknown.returncode, 0)
        self.assertEqual(calls, 1)
        self.assertIn("release_api_transport_failure phase=metadata", unknown.stderr)

    def test_bounded_secondary_backoff_and_reset_deadline(self):
        # Sin Retry-After verificable, ningún reintento automático es seguro;
        # la política conservadora ejecuta exactamente un intento y falla.
        for reason in ("HTTP 429 secondary rate limit", "secondary rate limit exceeded"):
            with self.subTest(reason=reason):
                result, calls = _fake_gh_error(phase="comments", message=reason)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, 1)
                self.assertIn("release_api_quota_exhausted", result.stderr)
                self.assertNotIn("INVALID_SUCCESS", result.stdout)
        helper = _block(HELPER_START, HELPER_END)
        self.assertNotIn("sleep ", helper)
        self.assertNotIn("|| true", helper)
        self.assertNotIn("Retry-After: 0", helper)

    def test_complete_exact_head_snapshot_never_reuses_stale_human_gates(self):
        body_real = '<!-- factory-human-gate {"category":"factory-release"} -->'
        body_window_bad = '<!-- factory-release-window bad-marker -->'
        rows = [
            {"number": 1, "body": "This issue mentions factory-release in narrative only"},
            {"number": 2, "body": body_real},
            {"number": 3, "body": body_window_bad},
            {"number": 4, "body": '<!-- factory-human-gate {"category":"operations"} -->'},
        ]
        self.assertEqual(_candidate_numbers(rows), [2, 3])
        # Un snapshot actualizado se reevalúa íntegro, sin caché de decisiones.
        rows[1]["body"] = "No marker; the decision has changed"
        rows[2]["body"] = "Window marker removed"
        self.assertEqual(_candidate_numbers(rows), [])
        workflow = _workflow()
        first = workflow.index("cmp -s /tmp/release-search-verified-1.json")
        selector = workflow.index(CANDIDATES_START)
        self.assertLess(first, selector)
        self.assertIn("gh api --paginate", workflow)
        self.assertIn("incomplete_comment_pages", workflow)
        self.assertIn("factory-release-window", workflow)
        self.assertIn("select((.body // \"\") | contains(\"factory-release\"))", workflow)
        self.assertLess(workflow.index("release-issues-prefilter.json"),
                        workflow.index(CANDIDATES_START))

    def test_report_excludes_comment_bodies_and_tokens(self):
        workflow = _workflow()
        helper = _block(HELPER_START, HELPER_END)
        self.assertIn("release_api_budget_min search=", workflow)
        self.assertIn("comments=$comments_calls_min metadata=2", workflow)
        self.assertIn("rm -f \"$error_file\"", helper)
        self.assertNotIn('cat "$error_file"', helper)
        self.assertNotIn('echo "$GH_TOKEN"', helper)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)


if __name__ == "__main__":
    unittest.main()
