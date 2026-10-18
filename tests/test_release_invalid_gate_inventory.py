#!/usr/bin/env python3
"""AC-01..03 de Factory #1287: snapshot REST y journal bot solo de lectura.

Ejecuta los fragmentos REALES del workflow contra fixtures offline. Un marker de
invalidación no acredita qué versión del body fue invalidada ni autoriza release.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/factory-ci.yml"
COMMENT_PIPE = re.compile(
    r"gh api --paginate[^\n]*\|\s*jq -s -e '.*?'\s*>\s*/tmp/release-comments\.json",
    re.DOTALL,
)
BOT = "github-actions[bot]"
INVALID = "<!-- factory-invalid-gate -->"
DATE = "2026-10-15T11:00:00Z"
LATER = "2026-10-15T12:00:00Z"


def _script(begin: str, end: str) -> str:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count(begin) == workflow.count(end) == 1
    block = workflow.split(begin, 1)[1].split(end, 1)[0]
    assert "<<'PY'\n" in block
    return textwrap.dedent(block.split("<<'PY'\n", 1)[1].split("\n          PY", 1)[0])


def _issue(**overrides: object) -> dict[str, object]:
    return {
        "number": 511,
        "state": "closed",
        "state_reason": "duplicate",
        "title": "Puerta histórica",
        "body": "<!-- factory-human-gate invalid -->",
        "updated_at": LATER,
        **overrides,
    }


def _bot(**overrides: object) -> dict[str, object]:
    return {
        "id": 42,
        "user": {"login": BOT},
        "body": INVALID,
        "created_at": DATE,
        "updated_at": DATE,
        **overrides,
    }


class ReleaseInvalidGateInventoryTests(unittest.TestCase):
    def _project(self, first: dict, second: dict | None = None) -> tuple[subprocess.CompletedProcess[str], object]:
        script = _script("# RELEASE_INVALID_GATE_METADATA_BEGIN",
                         "# RELEASE_INVALID_GATE_METADATA_END")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = []
            for idx in range(2):
                page = first if idx == 0 else (first if second is None else second)
                p1 = root / f"search-{idx}-1.json"
                p2 = root / f"search-{idx}-2.json"
                p1.write_text(json.dumps({"items": [page]}), encoding="utf-8")
                p2.write_text("null", encoding="utf-8")
                raw.extend((str(p1), str(p2)))
            published = root / "published.json"
            projected = {key: first[key] for key in (
                "number", "state", "title", "body", "updated_at"
            )}
            published.write_text(json.dumps([projected]), encoding="utf-8")
            done = subprocess.run(
                ["python3", "-c", script, *raw, str(published)],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )
            data = json.loads(published.read_text(encoding="utf-8"))
            return done, data

    def _filter(self, rows: list[dict], *, pages: list | None = None,
                gh_exit_code: int = 0) -> tuple[subprocess.CompletedProcess[str], object]:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        matches = COMMENT_PIPE.findall(workflow)
        self.assertEqual(len(matches), 1, "Ejecutar la tubería real, no una copia")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "gh"
            fake.write_text(
                '#!/bin/sh\ncat "$FAKE_PAGES"\nexit "$FAKE_EXIT"\n',
                encoding="utf-8",
            )
            fake.chmod(0o700)
            source = root / "pages.jsonl"
            source.write_text("".join(json.dumps(x) + "\n" for x in
                                      ([rows] if pages is None else pages)), encoding="utf-8")
            destination = root / "comments.json"
            script = matches[0].replace("/tmp/release-comments.json", str(destination))
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ.get("PATH", ""),
                   "FAKE_PAGES": str(source), "FAKE_EXIT": str(gh_exit_code),
                   "REPOSITORY": "pl0n3r/Factory", "number": "511"}
            done = subprocess.run(
                ["bash", "-c", "set -euo pipefail\n" + script],
                cwd=ROOT, capture_output=True, text=True, env=env, timeout=12,
            )
            data = json.loads(destination.read_text(encoding="utf-8")) if done.returncode == 0 else None
            return done, data

    def _validate(self, issue: dict, rows: list) -> subprocess.CompletedProcess[str]:
        script = _script("# RELEASE_INVALID_GATE_JOURNAL_BEGIN",
                         "# RELEASE_INVALID_GATE_JOURNAL_END")
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "journal.json"
            file.write_text(json.dumps(rows), encoding="utf-8")
            return subprocess.run(
                ["python3", "-c", script, json.dumps(issue), str(file)],
                cwd=ROOT, capture_output=True, text=True, timeout=10,
            )

    def test_bot_invalid_gate_marker_preserved_read_only(self):
        issue = _issue()
        projected, values = self._project(issue)
        self.assertEqual(projected.returncode, 0, projected.stderr)
        self.assertEqual(len(values), 1)
        for field in ("number", "state", "state_reason", "updated_at"):
            self.assertEqual(values[0][field], issue[field])

        filtered, comments = self._filter([_bot()])
        self.assertEqual(filtered.returncode, 0, filtered.stderr)
        self.assertEqual(comments, [_bot()])
        self.assertEqual(self._validate(values[0], comments).returncode, 0)
        producer_body = (
            INVALID + "\n<!-- factory-invalid-gate-owner:bot -->\n"
            + "⛔ Puerta humana inválida. Motivo de validación: missing recommendation"
        )
        # El productor seguridad/sincronizar_puerta.py::sync_invalid
        # publica la línea marker seguida de owner opcional y motivo.
        produced, preserved = self._filter([_bot(body=producer_body)])
        self.assertEqual(produced.returncode, 0, produced.stderr)
        self.assertEqual(preserved, [_bot(body=producer_body)])
        self.assertEqual(self._validate(values[0], preserved).returncode, 0)

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cmp -s /tmp/release-search-verified-1.json", workflow)
        self.assertLess(workflow.index("# RELEASE_INVALID_GATE_METADATA_BEGIN"),
                        workflow.index("# RELEASE_GATE_CANDIDATES_START"))
        self.assertIn("python3 scripts/release_window.py pr-check", workflow)
        self.assertIn("A bot comment is provenance only", workflow)

    def test_untrusted_or_incomplete_comments_fail_closed(self):
        issue = _issue()
        # Origin, marker and pagination guard are the production jq pipeline.
        for name, records, expected_good in (
            ("outsider", [_bot(user={"login": "outsider"})], True),
            ("wrong marker", [_bot(body="narrative factory-invalid-gate")], False),
            ("missing id", [{k: v for k, v in _bot().items() if k != "id"}], False),
            ("missing user", [{k: v for k, v in _bot().items() if k != "user"}], False),
            ("missing body", [{k: v for k, v in _bot().items() if k != "body"}], False),
            ("missing created_at", [_bot(created_at=None)], False),
            ("marker not anchored", [_bot(body="other\\n" + INVALID)], False),
            ("same-line suffix", [_bot(body=INVALID + " corrupted")], False),
        ):
            with self.subTest(name=name):
                result, rows = self._filter(records)
                self.assertEqual(result.returncode == 0, expected_good, result.stderr)
                if name == "outsider":
                    self.assertEqual(rows, [], "Un autor ajeno jamás es un journal bot")
        for name, pages in (
            ("incomplete", [[_bot()] * 100]),
            ("duplicate", [[_bot(), _bot()]]),
            ("not array", [{"message": "fake"}]),
            ("excess", [[_bot(id=i+1) for i in range(101)]]),
        ):
            with self.subTest(name=name):
                result, _ = self._filter([], pages=pages)
                self.assertNotEqual(result.returncode, 0)

        for name, bad_issue, bad_row in (
            ("no reason", _issue(state_reason=None), _bot()),
            ("missing reason", {k:v for k,v in issue.items() if k!="state_reason"}, _bot()),
            ("reopened", _issue(state="open", state_reason="reopened"), _bot()),
            ("future comment", issue, _bot(updated_at="2026-10-16T10:00:00Z")),
            ("invalid date", issue, _bot(created_at="2026-02-30T10:00:00Z")),
            ("missing updated", issue, {k:v for k,v in _bot().items() if k!="updated_at"}),
            ("missing body", issue, _bot(body="not a marker")),
            ("untrusted author", issue, _bot(user={"login":"not-a-bot"})),
        ):
            with self.subTest(name=name):
                done = self._validate(bad_issue, [bad_row])
                self.assertNotEqual(done.returncode, 0, done.stdout)
                self.assertNotIn("Traceback", done.stderr)
        drift, _ = self._project(issue, _issue(state_reason="completed"))
        self.assertNotEqual(drift.returncode, 0, "No aceptar dos lecturas distintas")
        drift, _ = self._project(issue, _issue(body="edited after invalidation"))
        self.assertNotEqual(drift.returncode, 0, "El journal no liga un body cambiado")

    def test_real_bot_journal_does_not_lift_live_freeze(self):
        """Marcador de invalidación no sustituye una excepción crítica real."""
        from datetime import datetime, timezone
        from scripts import release_window as rw

        opening = datetime(2026, 10, 15, 11, 0, tzinfo=timezone.utc)
        rendered = rw._render_gate("1.0.23", "a" * 40, opening, source_issue=900)
        producer_body = (
            INVALID + "\n<!-- factory-invalid-gate-owner:bot -->\n"
            + "⛔ Puerta humana inválida. Motivo de validación: archived"
        )
        row = {
            "issue": {
                "number": 511, "state": "open", "title": "Puerta factory-release",
                "body": rendered["body"], "updated_at": LATER,
            },
            "comments": [_bot(body=producer_body)],
        }
        outcome = rw.check_pull_request({
            "now": "2026-10-15T11:10:00Z",
            "gates": [row],
            "pr": {"number": 1392, "body": ""},
            "work_issue": {
                "number": 1287, "state": "open",
                "labels": [{"name": "prioridad: baja"}],
            },
        })
        self.assertFalse(outcome["allowed"], outcome)
        self.assertEqual(outcome["reason"], "factory_release_window_active")
        self.assertEqual(outcome["gate_issue"], 511)

    def test_existing_bot_journal_filters_remain_compatible(self):
        source = [
            {"id": 1, "user": {"login": BOT}, "body": "factory-human-decision"},
            {"id": 2, "user": {"login": BOT}, "body": "factory-release-executed"},
            {"id": 3, "user": {"login": BOT}, "body": "factory-human-gate-duplicate"},
            {"id": 4, "user": {"login": "alice"}, "body": INVALID},
            {"id": 5, "user": {"login": BOT}, "body": "unrelated"},
        ]
        filtered, values = self._filter(source)
        self.assertEqual(filtered.returncode, 0, filtered.stderr)
        self.assertEqual(values, [
            {"user": {"login": BOT}, "body": row["body"]} for row in source[:3]
        ])
        self.assertEqual(self._validate(_issue(), values).returncode, 0)
        self.assertIn("| {user: {login: .user.login}, body: (.body // \"\")}",
                      WORKFLOW.read_text(encoding="utf-8"))
        # The live evaluator remains the original parser; historic bot journals
        # have no body fingerprint and cannot grant no_active_release_window.
        self.assertTrue((ROOT / "scripts/release_window.py").exists())


if __name__ == "__main__":
    unittest.main()
