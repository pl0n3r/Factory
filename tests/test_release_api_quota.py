"""Regresiones offline del transporte de release y sus gates canónicos (#1132)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts import release_window as rw

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
        # Ejecutar la proyección jq REAL del workflow antes del selector.
        # Detecta regresiones donde un prefiltrado textual omite markers.
        workflow = _workflow()
        suffix = "' /tmp/release-search-verified-2.json > /tmp/release-issues-projected.json"
        end = workflow.index(suffix)
        begin = workflow.rfind("          jq '", 0, end)
        if begin < 0:
            raise AssertionError("No existe la proyección jq canónica.")
        expression = workflow[begin + len("          jq '"):end]
        projection = subprocess.run(
            ["jq", expression, str(file)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if projection.returncode:
            raise AssertionError("La proyección jq falló: " + projection.stderr)
        projected = Path(tmp) / "projected.json"
        projected.write_text(projection.stdout, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-c", _candidate_script(), str(projected)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise AssertionError(
                "La selección canónica debe operar offline: " + result.stderr
            )
        return [entry["number"] for entry in json.loads(result.stdout)]


def _fake_gh_error(*, phase: str, message: str, partial_stdout: str = "",
                   piped: bool = False) -> tuple[subprocess.CompletedProcess[str], int]:
    """Ejecuta el wrapper shell real con gh fake y cuenta llamadas efectivas."""
    helper = _block(HELPER_START, HELPER_END)
    with tempfile.TemporaryDirectory() as tmp:
        count = Path(tmp) / "calls.txt"
        output = Path(tmp) / "partial.json"
        fake = Path(tmp) / "gh"
        fake.write_text(
            '#!/bin/sh\n'
            'printf "called\n" >> "$FAKE_GH_COUNT"\n'
            'printf "%s\n" "$FAKE_GH_MESSAGE" >&2\n'
            'printf "%s" "$FAKE_GH_PARTIAL"\n'
            'exit 1\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)
        counter = {
            "search": "search_calls", "comments": "comments_calls_min",
            "metadata": "metadata_calls",
        }[phase]
        request = (
            'gh api --paginate "repos/fake/issues/1/comments?per_page=100" '
            '| cat > "$FAKE_GH_OUTPUT"\n'
            if piped else
            f"release_gh_api {phase} --paginate 'repos/fake/issues/1/comments?per_page=100' > \"$FAKE_GH_OUTPUT\"\n"
        )
        shell = (
            "set -euo pipefail\n"
            + helper + "\n"
            + "search_calls=0\ncomments_calls_min=0\nmetadata_calls=0\n"
            + f"{counter}=1\n"
            + request
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



def _active_gate_numbers(rows: list[dict], at: datetime) -> list[int]:
    """Ejecuta el filtro TTL REAL del workflow sobre un fixture offline."""
    workflow = _workflow()
    start = workflow.index("# RELEASE_ACTIVE_GATE_FILTER_START")
    end = workflow.index("# RELEASE_ACTIVE_GATE_FILTER_END", start)
    block = workflow[start:end]
    begin = block.index("<<'PY'") + len("<<'PY'")
    script = block[block.index("\n", begin) + 1:block.rindex("\n          PY")]
    script = textwrap.dedent(script)
    stamp = at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidates.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-c", script, str(path), stamp],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise AssertionError("Filtro fail-closed: " + result.stderr)
        return [row["number"] for row in json.loads(result.stdout)]


class ReleaseApiQuotaTests(unittest.TestCase):
    def test_release_search_bounded_snapshot_retry_keeps_fail_closed(self):
        """Un par inestable se descarta; cuotas y fallos agotados nunca certifican."""
        import shutil

        workflow = _workflow()
        start = "# RELEASE_SEARCH_BOUNDED_RETRY_START"
        end = "# RELEASE_SEARCH_BOUNDED_RETRY_END"
        self.assertEqual(workflow.count(start), 1)
        self.assertEqual(workflow.count(end), 1)
        block = textwrap.dedent(workflow.split(start, 1)[1].split(end, 1)[0])
        self.assertEqual(block.count("for snapshot_attempt in 1 2 3; do"), 1)
        self.assertEqual(block.count("for pass in 1 2; do"), 1)
        self.assertEqual(block.count("release_gh_api search -X GET"), 2)
        self.assertIn("if ! total_count=", block)
        self.assertIn("if ! {", block)
        self.assertIn("python3 - /tmp/release-search-p1-", block)
        self.assertIn("if ! python3 -m scripts.release_gate_search", block)
        self.assertIn("cmp -s /tmp/release-search-verified-1.json", block)
        self.assertIn("snapshot_attempt == 3", block)
        self.assertNotIn("|| true", block)
        self.assertNotIn("factory-release-executed", block)
        self.assertLess(block.index("release_gh_api search"), block.index("cmp -s"))
        # El wrapper no atrapa el error de transporte para reintentarlo.
        self.assertIn('release_gh_api search -X GET search/issues', block)
        if not shutil.which("jq"):
            self.skipTest("jq requerido para integración shell real")

        sample = {
            "total_count": 1, "incomplete_results": False,
            "items": [{
                "number": 900, "state": "closed", "title": "Gate sintético",
                "body": "sin permiso", "updated_at": "2026-10-22T09:00:00Z",
            }],
        }
        other = json.loads(json.dumps(sample))
        other["items"][0]["body"] = "nuevo snapshot consistente"
        partial = json.loads(json.dumps(sample))
        partial["incomplete_results"] = True

        fake_script = """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
counter = Path(os.environ["FAKE_GH_COUNT"])
n = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(n + 1))
if os.environ.get("FAKE_GH_QUOTA") == "1":
    print("HTTP 429 secondary rate limit exceeded", file=sys.stderr)
    sys.exit(1)
records = json.loads(Path(os.environ["FAKE_GH_SAMPLES"]).read_text())
print(json.dumps(records[n % len(records)]))
"""
        helper = _block(HELPER_START, HELPER_END)
        for snapshots, expected_calls, passes, quota in (
            ([sample, other, other, other], 4, True, False),
            ([sample, other], 6, False, False),
            ([partial, other, other], 3, True, False),
            ([sample], 1, False, True),
        ):
            with self.subTest(calls=expected_calls, passes=passes, quota=quota):
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder)
                    fake = path / "gh"
                    fake.write_text(fake_script, encoding="utf-8")
                    fake.chmod(0o755)
                    samples = path / "samples.json"
                    samples.write_text(json.dumps(snapshots), encoding="utf-8")
                    counter = path / "calls"
                    script = (
                        "set -euo pipefail\n"
                        + helper + "\n"
                        + "search_calls=0\ncomments_calls_min=0\nmetadata_calls=0\n"
                        + "REPOSITORY=pl0n3r/Factory\n"
                        + 'query="repo:$REPOSITORY is:issue factory-human-gate in:body"\n'
                        + block.replace("/tmp/release-", str(path / "release-"))
                        + "\necho VERIFIED\n"
                    )
                    environment = dict(os.environ, FAKE_GH_COUNT=str(counter),
                                       FAKE_GH_SAMPLES=str(samples),
                                       FAKE_GH_QUOTA="1" if quota else "0")
                    environment["PATH"] = str(path) + os.pathsep + environment.get("PATH", "")
                    result = subprocess.run(
                        ["bash", "-c", script], cwd=ROOT, env=environment,
                        capture_output=True, text=True, timeout=20, check=False,
                    )
                    self.assertEqual(int(counter.read_text()), expected_calls)
                    if passes:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("VERIFIED", result.stdout)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertNotIn("VERIFIED", result.stdout)
                    if quota:
                        self.assertIn("release_api_quota_exhausted phase=search",
                                      result.stderr)

    def test_primary_rate_limit_fails_closed_with_typed_evidence(self):
        result, calls = _fake_gh_error(
            phase="comments",
            message="gh: API rate limit exceeded for installation (HTTP 403)",
            partial_stdout='{"message":"fake failure"}',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, 1)
        self.assertIn("release_api_quota_exhausted phase=comments", result.stderr)
        self.assertIn("release_api_budget_min search=0 comments=1 metadata=0", result.stderr)
        self.assertIn("failed_phase=comments", result.stderr)
        self.assertIn("minimum_attempts_paginate_may_expand", result.stderr)
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
        self.assertIn("release_api_budget_min search=1 comments=0 metadata=0", search.stderr)
        self.assertIn("failed_phase=search", search.stderr)

        unknown, calls = _fake_gh_error(phase="metadata", message="HTTP 403 Forbidden")
        self.assertNotEqual(unknown.returncode, 0)
        self.assertEqual(calls, 1)
        self.assertIn("release_api_transport_failure phase=metadata", unknown.stderr)
        self.assertIn("release_api_budget_min search=0 comments=0 metadata=1", unknown.stderr)
        self.assertIn("failed_phase=metadata", unknown.stderr)

    def test_comment_pipeline_quota_failure_stays_fail_closed(self):
        # El gh del workflow corre en el lado izquierdo de una tubería.
        # Bajo pipefail, el contador heredado y el error deben sobrevivir.
        result, calls = _fake_gh_error(
            phase="comments",
            message="gh: secondary rate limit exceeded (HTTP 429)",
            partial_stdout='[{"id":1,"body":"sensitive"}]',
            piped=True,
        )
        self.assertEqual(calls, 1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release_api_quota_exhausted phase=comments", result.stderr)
        self.assertIn("release_api_budget_min search=0 comments=1 metadata=0", result.stderr)
        self.assertIn("failed_phase=comments", result.stderr)
        self.assertNotIn("sensitive", result.stderr)
        self.assertNotIn("INVALID_SUCCESS", result.stdout)

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
        now = datetime(2026, 10, 3, 10, 0, tzinfo=timezone.utc)
        valid_window = rw._render_gate(
            "1.0.23", "4" * 40, now, source_issue=900,
        )["body"]
        valid_legacy = "\n".join(
            line for line in valid_window.splitlines()
            if "factory-release-window" not in line
            and "factory-release-rearm" not in line
        )
        # JSON válido cuya categoría requiere decodificar un escape.
        escaped_legacy = valid_legacy.replace(
            '"factory-release"', r'"factory-\u0072elease"',
        )
        self.assertNotEqual(escaped_legacy, valid_legacy)
        rows = [
            {"number": 1, "body": "This issue mentions factory-release in narrative only"},
            {"number": 2, "body": '<!-- factory-human-gate {"category":"factory-release"} -->'},
            {"number": 3, "body": "<!-- factory-release-window bad-marker -->"},
            {"number": 4, "body": '<!-- factory-human-gate {"category":"operations"} -->'},
            {"number": 5, "body": escaped_legacy},
            {"number": 6, "body": valid_legacy},
            {"number": 7, "body": valid_window},
            {"number": 8, "body": "<!-- factory-human-gate {broken factory-release} -->"},
        ]
        # Debe coincidir con gate_records: los legacy malformados sin ventana
        # se ignoran; el window-intent malformado NUNCA se ignora.
        self.assertEqual(_candidate_numbers(rows), [3, 5, 6, 7])
        for number in (2, 5, 6, 8):
            item = rows[number - 1]
            record = {
                "issue": {
                    "number": number, "state": "closed", "title": "gate",
                    "body": item["body"], "updated_at": "2026-10-03T09:55:00Z",
                },
                "comments": [],
            }
            expected = 1 if number in (5, 6) else 0
            self.assertEqual(len(rw.gate_records([record])), expected)
        # Snapshot nuevo: no retener puertas ni decisiones previas.
        for item in rows:
            item["body"] = "Marcador eliminado, sin ventana"
        self.assertEqual(_candidate_numbers(rows), [])
        workflow = _workflow()
        first = workflow.index("cmp -s /tmp/release-search-verified-1.json")
        selector = workflow.index(CANDIDATES_START)
        self.assertLess(first, selector)
        self.assertIn("gh api --paginate", workflow)
        self.assertIn("incomplete_comment_pages", workflow)
        self.assertIn("WINDOW_INTENT_RE", workflow)
        self.assertNotIn("select((.body // \"\") | contains(\"factory-release\"))", workflow)
        self.assertIn("release-issues-projected.json", workflow)
        self.assertLess(workflow.index("release-issues-projected.json"),
                        workflow.index(CANDIDATES_START))

    def test_large_gate_inventory_transport_failure_fails_closed(self):
        """44 consultas secuenciales: fallo tardío no produce GREEN."""
        helper = _block(HELPER_START, HELPER_END)
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "gh"
            count = Path(tmp) / "count.txt"
            fake.write_text(
                "#!/bin/sh\n"
                "n=0\n"
                "if test -f \"$FAKE_GH_COUNT\"; then n=$(cat \"$FAKE_GH_COUNT\"); fi\n"
                "n=$((n + 1))\n"
                "echo \"$n\" > \"$FAKE_GH_COUNT\"\n"
                "if test \"$n\" -eq 44; then\n"
                "  echo 'service unavailable' >&2\n"
                "  exit 1\n"
                "fi\n"
                "echo '[]'\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            shell = (
                "set -euo pipefail\n"
                + helper + "\n"
                + "search_calls=4\ncomments_calls_min=0\nmetadata_calls=0\n"
                + "for n in $(seq 1 44); do\n"
                + "  comments_calls_min=$((comments_calls_min + 1))\n"
                + "  release_gh_api comments --paginate test-url | cat > /dev/null\n"
                + "done\n"
                + "echo INVALID_GREEN\n"
            )
            env = dict(os.environ, FAKE_GH_COUNT=str(count))
            env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
            result = subprocess.run(
                ["bash", "-c", shell], cwd=ROOT, env=env,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(int(count.read_text().strip()), 44)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "release_api_transport_failure phase=comments", result.stderr
            )
            self.assertIn(
                "search=4 comments=44 metadata=0 failed_phase=comments",
                result.stderr,
            )
            self.assertNotIn("INVALID_GREEN", result.stdout)
            self.assertNotIn("service unavailable", result.stderr)

    def test_large_gate_budget_preserves_active_and_executed_release_authority(self):
        """TTL acota fan-out, pero nunca oculta una ventana viva o inválida."""
        from datetime import timedelta

        now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)
        rows = []
        for n in range(1, 44):
            old = now - timedelta(days=n + 1)
            body = rw._render_gate(
                f"1.0.{n}", "a" * 40, old, source_issue=900
            )["body"]
            rows.append({"number": n, "body": body})
        active = rw._render_gate(
            "1.0.44", "b" * 40, now, source_issue=901
        )["body"]
        rows.append({"number": 44, "body": active})
        self.assertEqual(_active_gate_numbers(rows, now), [44])
        self.assertEqual(_active_gate_numbers(rows[:43], now), [])
        self.assertIn(
            "mv /tmp/release-issues-active.json /tmp/release-issues.json",
            _workflow(),
        )
        issue = {
            "number": 44, "state": "open", "title": "Factory 1.0.44",
            "body": active, "updated_at": "2026-10-14T02:00:00Z",
        }
        record = rw.gate_records([{"issue": issue, "comments": []}])
        self.assertEqual(rw.freeze_gate(record, now)["number"], 44)
        record[0]["executed"] = {"sha": "b" * 40, "run_id": 100}
        self.assertIsNone(rw.freeze_gate(record, now))
        # Toda ventana malformada, incluso obsoleta, sigue fallando cerrado.
        rows[0]["body"] = "<!-- factory-release-window invalid -->"
        with self.assertRaisesRegex(AssertionError, "Filtro fail-closed"):
            _active_gate_numbers(rows, now)


    def test_repeated_version_preserves_shadowing_canonical_gates(self):
        """Una ventana más nueva vencida/legacy todavía determina el canónico."""
        from datetime import timedelta

        now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)
        active_body = rw._render_gate(
            "1.0.33", "a" * 40, now, source_issue=800
        )["body"]
        expired_body = rw._render_gate(
            "1.0.33", "a" * 40, now - timedelta(hours=3),
            source_issue=800,
        )["body"]
        legacy_body = "\n".join(
            line for line in expired_body.splitlines()
            if "factory-release-window" not in line
            and "factory-release-rearm" not in line
        )
        for newer in (expired_body, legacy_body):
            with self.subTest(newer_window=("factory-release-window" in newer)):
                rows = [
                    {"number": 10, "body": active_body},
                    {"number": 11, "body": newer},
                ]
                self.assertEqual(_active_gate_numbers(rows, now), [10, 11])
                records = rw.gate_records([
                    {"issue": {
                        "number": item["number"],
                        "body": item["body"],
                        "title": "Gate canónico",
                        "state": "open" if item["number"] == 10 else "closed",
                        "updated_at": "2026-10-14T01:00:00Z",
                    }, "comments": []}
                    for item in rows
                ])
                self.assertIsNone(rw.freeze_gate(records, now))

    def test_report_excludes_comment_bodies_and_tokens(self):
        workflow = _workflow()
        helper = _block(HELPER_START, HELPER_END)
        self.assertIn("release_api_budget_min search=", workflow)
        self.assertIn("comments=$comments_calls_min metadata=$metadata_calls", workflow)
        self.assertIn("failed_phase=$phase", helper)
        self.assertIn("minimum_attempts_paginate_may_expand", helper)
        self.assertIn("metadata_calls=0", workflow)
        self.assertIn("metadata_calls=$((metadata_calls + 1))", workflow)
        self.assertIn("search_calls=$((search_calls + 1))", workflow)
        self.assertIn("comments_calls_min=$((comments_calls_min + 1))", workflow)
        self.assertIn("rm -f \"$error_file\"", helper)
        self.assertNotIn('cat "$error_file"', helper)
        self.assertNotIn('echo "$GH_TOKEN"', helper)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)


if __name__ == "__main__":
    unittest.main()
