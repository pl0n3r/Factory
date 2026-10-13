"""Exact executable acceptance contract for Factory critical Incident #1076."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.release_gate_search import SearchEvidenceError, verified_inventory

ROOT = Path(__file__).resolve().parents[1]


def _items(total: int = 116) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"number": 2000 + n, "state": "closed", "title": "Issue", "body": "No gate",
         "updated_at": "2026-10-11T10:00:00Z"} for n in range(total)
    ]
    for index, number, body in (
        (20, 896, "<!-- factory-human-gate-duplicate canonical=895 -->"),
        (110, 895, "<!-- factory-release canonical gate -->"),
    ):
        if index < total:
            rows[index] = {**rows[index], "number": number, "body": body}
    return rows


def _page(rows: list[dict[str, object]], total: int) -> dict[str, object]:
    return {"total_count": total, "incomplete_results": False, "items": rows}


class ReleaseGateSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _items()
        self.first = _page(self.rows[:100], 116)
        self.second = _page(self.rows[100:], 116)
        self.projection = [{key: row[key] for key in
                            ("number", "state", "title", "body", "updated_at")}
                           for row in self.rows]

    def test_paginated_search_includes_duplicate_and_canonical_gate(self) -> None:
        result = verified_inventory(self.first, self.second, self.projection)
        self.assertEqual(len(result), 116)
        self.assertEqual([row["number"] for row in result if "factory-" in row["body"]],
                         [896, 895])
        self.assertEqual(set(result[0]), {"number", "state", "title", "body", "updated_at"})

    def test_missing_or_ambiguous_search_pages_fail_closed(self) -> None:
        for name, first, second, verified in (
            ("missing second", self.first, None, self.projection),
            ("truncated second", self.first, _page(self.rows[100:-1], 116), self.projection),
            ("inconsistent totals", self.first, _page(self.rows[100:], 117), self.projection),
            ("partial first", {**self.first, "incomplete_results": True}, self.second, self.projection),
            ("duplicate IDs", self.first,
             _page([{**self.rows[100], "number": 896}, *self.rows[101:]], 116),
             self.projection),
            ("excess volume", _page([], 201), self.second, self.projection),
            ("ambiguous projection", self.first, self.second, self.projection[:-1]),
            ("tampered projection", self.first, self.second,
             [{**self.projection[0], "body": "rewritten"}, *self.projection[1:]]),
            ("unexpected second", _page(self.rows[:70], 70), _page([], 70),
             self.projection[:70]),
            ("bad time", self.first,
             _page([*self.rows[100:-1], {**self.rows[-1], "updated_at": "2026-02-30T00:00:00Z"}], 116),
             self.projection),
        ):
            with self.subTest(name=name), self.assertRaises(SearchEvidenceError):
                verified_inventory(first, second, verified)
        self.assertEqual(verified_inventory(_page([], 0), None, []), [])

    def test_factory_ci_requires_complete_paginated_search(self) -> None:
        workflow = (ROOT / ".github/workflows/factory-ci.yml").read_text(encoding="utf-8")
        self.assertIn("python3 -m scripts.release_gate_search", workflow)
        self.assertIn("/tmp/release-search-verified-" + chr(36) + "{pass}.json", workflow)
        self.assertIn("for pass in 1 2; do", workflow)
        self.assertIn("cmp -s /tmp/release-search-verified-1.json", workflow)
        self.assertLess(workflow.index("python3 -m scripts.release_gate_search"),
                        workflow.index("cmp -s /tmp/release-search-verified-1.json"))
        with tempfile.TemporaryDirectory() as tmp:
            p1, p2, pv = (Path(tmp) / name for name in ("first.json", "second.json", "verified.json"))
            for path, data in ((p1, self.first), (p2, self.second), (pv, self.projection)):
                path.write_text(json.dumps(data), encoding="utf-8")
            args = [sys.executable, "-m", "scripts.release_gate_search", str(p1), str(p2), str(pv)]
            ok = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            pv.write_text(json.dumps(self.projection[:-1]), encoding="utf-8")
            bad = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("Search Issues evidence rejected", bad.stderr)


    def test_evidence_paths_outside_temp_dir_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inside = Path(tmp) / "ok.json"
            inside.write_text("[]", encoding="utf-8")
            outside = str(Path(tmp) / ".." / ".." / ".." / "etc" / "passwd")
            args = [sys.executable, "-m", "scripts.release_gate_search",
                    outside, str(inside), str(inside)]
            bad = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("Search Issues evidence rejected", bad.stderr)

    def test_duplicate_json_keys_fail_closed_at_cli_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p1, p2, pv = (Path(tmp) / n for n in
                          ("first.json", "second.json", "verified.json"))
            p2.write_text(json.dumps(self.second), encoding="utf-8")
            pv.write_text(json.dumps(self.projection), encoding="utf-8")
            original = json.dumps(self.first)
            for needle, duplicate in (
                ('"total_count": 116,', '"total_count": 0, "total_count": 116,'),
                ('"items": [', '"items": [], "items": ['),
                ('"number": 2000,', '"number": 9, "number": 2000,'),
            ):
                with self.subTest(duplicate=needle):
                    self.assertIn(needle, original)
                    p1.write_text(original.replace(needle, duplicate, 1),
                                  encoding="utf-8")
                    args = [sys.executable, "-m", "scripts.release_gate_search",
                            str(p1), str(p2), str(pv)]
                    result = subprocess.run(args, cwd=ROOT, capture_output=True,
                                            text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Search Issues evidence rejected", result.stderr)

            # Ambiguity in the second page or published projection is equally
            # untrustworthy, even when the first page is canonical.
            p1.write_text(original, encoding="utf-8")
            for path, data, needle, duplicate in (
                (p2, self.second, '"number": 2100,',
                 '"number": 9, "number": 2100,'),
                (pv, self.projection, '"body": "No gate",',
                 '"body": "tampered", "body": "No gate",'),
            ):
                with self.subTest(source=path.name):
                    raw = json.dumps(data)
                    self.assertIn(needle, raw)
                    path.write_text(raw.replace(needle, duplicate, 1),
                                    encoding="utf-8")
                    result = subprocess.run(args, cwd=ROOT, capture_output=True,
                                            text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Search Issues evidence rejected", result.stderr)
                    path.write_text(raw, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
