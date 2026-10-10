#!/usr/bin/env python3
"""Regresiones del snapshot autenticado de puertas de release (#1075)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts import release_window as rw


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/factory-ci.yml").read_text(encoding="utf-8")


def release_gate_issues() -> list[dict[str, object]]:
    """116 resultados: duplicado #896 en página 1; canónico #895 en página 2."""
    items: list[dict[str, object]] = [
        {"number": 10000 + i, "state": "closed", "title": "irrelevante",
         "body": "Sin puerta", "updated_at": "2026-10-09T00:00:00Z"}
        for i in range(116)
    ]
    gate = rw._render_gate(
        "1.0.23", "a" * 40, datetime(2026, 10, 9, tzinfo=timezone.utc),
        source_issue=927,
    )["body"]
    for index, number in ((20, 896), (110, 895)):
        items[index] = {
            "number": number, "state": "closed", "title": "Puerta de release",
            "body": gate, "updated_at": "2026-10-09T00:00:00Z",
        }
    return items


def page(items: list[dict[str, object]], total: int = 116) -> dict[str, object]:
    return {"total_count": total, "incomplete_results": False, "items": items}


class ReleaseWindowSnapshotCompleteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        job = WORKFLOW.split("  release_window:", 1)[1].split(
            "  coordinacion:", 1
        )[0]
        marker = (
            "python3 - /tmp/release-search-p1.json "
            "/tmp/release-search-p2.json <<'PY' > /tmp/release-issues.json"
        )
        assert job.count(marker) == 1, "Fragmento de lectura paginada ausente"
        cls.parser = textwrap.dedent(
            job.split(marker, 1)[1].split("\n          PY", 1)[0]
        )
        assert "conteo incompleto" in cls.parser

    def run_parser(
        self, first: object, second: object,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "first.json"
            p2 = Path(tmp) / "second.json"
            p1.write_text(json.dumps(first), encoding="utf-8")
            p2.write_text(json.dumps(second), encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-c", self.parser, str(p1), str(p2)],
                capture_output=True, text=True, timeout=10, check=False,
            )

    def test_search_pages_collect_all_results_beyond_first_100(self) -> None:
        """AC-01: no perder #895 cuando #896 llegó desde la primera página."""
        items = release_gate_issues()
        result = self.run_parser(page(items[:100]), page(items[100:]))
        self.assertEqual(result.returncode, 0, result.stderr)
        complete = json.loads(result.stdout)
        self.assertEqual(len(complete), 116)
        selected = [row for row in complete if "factory-release" in row["body"]]
        self.assertEqual({row["number"] for row in selected}, {895, 896})
        self.assertTrue(all(set(row) == {
            "number", "state", "title", "body", "updated_at"
        } for row in selected))
        evidence = [
            {"issue": row, "comments": (
                [{"user": {"login": "github-actions[bot]"},
                  "body": "<!-- factory-human-gate-duplicate canonical=895 -->"}]
                if row["number"] == 896 else []
            )}
            for row in selected
        ]
        records = rw.gate_records(evidence)
        self.assertEqual({r["number"]: r["duplicate_of"] for r in records},
                         {895: None, 896: 895})

    def test_missing_inconsistent_duplicate_or_excess_search_results_fail_closed(self) -> None:
        """AC-02: cualquier omisión o ambigüedad niega la evaluación del freeze."""
        items = release_gate_issues()
        first = page(items[:100])
        second = page(items[100:])
        invalid_cases = {
            "sin segunda página": (first, None),
            "segunda truncada": (first, page(items[100:115])),
            "segunda larga": (first, page(items[100:] + [items[0]])),
            "total distinto": (first, page(items[100:], total=117)),
            "indexación incompleta": (first, {**second, "incomplete_results": True}),
            "id repetido": (first, page(items[100:115] + [items[0]])),
            "id ausente": (first, page(items[100:115] + [{**items[115], "number": None}])),
            "body ausente": (first, page(items[100:115] + [{**items[115], "body": None}])),
            "total excedido": ({**first, "total_count": 201}, second),
            "total booleano": ({**first, "total_count": True}, second),
            "página inicial incompleta": ({**first, "incomplete_results": True}, second),
            "página extra": (page(items[:50], total=50), page([])),
        }
        for name, (p1, p2) in invalid_cases.items():
            with self.subTest(name=name):
                result = self.run_parser(p1, p2)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Search Issues incompleta", result.stderr)

    def test_factory_ci_preserves_bounded_release_projection_and_gate_validation(self) -> None:
        """AC-03: las páginas y los comentarios se leen sin omitir seguridad."""
        job = WORKFLOW.split("  release_window:", 1)[1].split(
            "  coordinacion:", 1
        )[0]
        for required in (
            "-f page=1", "-f page=2", "-f per_page=100",
            "-f sort=created -f order=asc",
            "(.total_count >= 0 and .total_count <= 200)",
            "incomplete_results", "conteo incompleto",
            'select(.user.login == "github-actions[bot]")',
            "| {user: {login: .user.login}, body: (.body // \"\")}",
            "factory-human-gate-duplicate",
            "factory-release-executed",
            "factory-human-decision",
            "python3 scripts/release_window.py pr-check",
            "| {number, state, title, body, updated_at}",
            '("number", "state", "title", "body", "updated_at")',
        ):
            self.assertIn(required, job)
        self.assertEqual(rw.MAX_ROWS, 200)
        self.assertNotIn("> /tmp/release-search.json", job)


if __name__ == "__main__":
    unittest.main()
