"""Regression del corte documental Factory #1499 (sin GitHub I/O)."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

DOC = Path(__file__).resolve().parents[1] / "docs/reconciliacion-issues-20261024.md"
EXPECTED = {1499, 1412, 1382, 1296, 1082, 1080, 305, 304}
ISSUE = re.compile(r"^\[#(\d+)\]\(https://github\.com/pl0n3r/Factory/issues/\1\)$")
EVIDENCE = re.compile(r"\[[^\]]+\]\(https://github\.com/[^\s)]+\)")


class ReconciliacionIssuesTests(unittest.TestCase):
    def test_acceptance(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("a0f710a47be25924ddbf38ef99e790b8aa45f5f8", text)
        self.assertIn("fotografía fechada", text)
        self.assertIn("0 cierres automáticos", text)
        self.assertIn("Factory@v1", text)
        rows = [line for line in text.splitlines() if line.startswith("| [#")]
        self.assertEqual(len(rows), len(EXPECTED))
        seen = set()
        for line in rows:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            self.assertEqual(len(cells), 4, msg=line)
            issue, decision, evidence, pending = cells
            match = ISSUE.fullmatch(issue)
            self.assertIsNotNone(match, msg=issue)
            number = int(match.group(1))
            self.assertNotIn(number, seen)
            seen.add(number)
            self.assertIn(decision, {"Mantener abierto", "Actualizar"})
            self.assertRegex(evidence, EVIDENCE)
            self.assertGreater(len(pending), 60)
        self.assertEqual(seen, EXPECTED)
        self.assertIn("#1499 no cuenta como completado", text)
        self.assertIn("flag OFF", text)
        self.assertIn("10 commits", text)


if __name__ == "__main__":
    unittest.main()
