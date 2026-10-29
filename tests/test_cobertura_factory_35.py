#!/usr/bin/env python3
"""Factory #1826: synthetic, source-executing coverage for performance and portfolio.

Test-only implementation under an authentic V3 lease; no deployment.
This does not certify real provenance, a live CodeRabbit timeline or moving Factory@v1.
"""
from __future__ import annotations

import ast
import copy
import json
import re
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "tests"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from performance.remediation import (
    PerformanceRemediationError, evaluate_before_after, plan_remediation,
)
from performance.team_compiler_bridge import (
    PerformanceTeamCompilerBridgeError, compile_performance_team,
)
from portfolio.signals import (
    PortfolioSignalsError, explain_tradeoffs, validate_portfolio_item,
)
from scripts.work_origin import validate_work_item
import test_performance_remediation as perf_fixture
import test_performance_team_compiler_bridge as team_fixture
import test_portfolio_signals as portfolio_fixture

# A is executable local behavior only; it is NOT full-world provenance or release.
A_ROWS = (
    "docs/performance-remediation.md:L21-U1",
    "docs/performance-remediation.md:L23-U2",
    "docs/performance-remediation.md:L25-U1",
    "docs/performance-remediation.md:L25-U2",
    "docs/performance-remediation.md:L29-U1",
    "docs/performance-remediation.md:L3-U1",
    "docs/performance-remediation.md:L9-U1",
    "docs/performance-team-compiler-bridge.md:L3-U1",
    "docs/portfolio-signals.md:L10-U1",
    "docs/portfolio-signals.md:L18-U1",
    "docs/portfolio-signals.md:L22-U1",
    "docs/portfolio-signals.md:L23-U1",
    "docs/portfolio-signals.md:L27-U1",
    "docs/portfolio-signals.md:L28-U1",
)
# Requires authentic external observer/producer, governance, or release authority.
B_ROWS = {
    "docs/politica-revisor-externo.md:B01": "Base policy and authentic CI in downstream consumer, not a local static sample",
    "docs/politica-revisor-externo.md:B02": "Actual bot rate limit and OWNER retry with authenticated GitHub event order",
    "docs/politica-revisor-externo.md:B03": "Authenticated, complete REST timeline and exact SHA identity required",
    "docs/politica-revisor-externo.md:B04": "Factory@v1 movement requires a distinct release gate and downstream rollout",
}
C_ROWS = {
    "docs/performance-remediation.md:L25-U4": "Real detection authority remains with detector and authorized producer",
    "docs/performance-remediation.md:L25-U5": "Caller obligation to authenticate evidence and applied change",
}
ALL_ROWS = tuple(A_ROWS) + tuple(B_ROWS) + tuple(C_ROWS)
assert len(ALL_ROWS) == 20 and len(set(ALL_ROWS)) == 20


def matrix_rows(text: object) -> dict[str, str]:
    """Validate the 20 actual matrix rows without counting this as coverage."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("UNKNOWN: matrix absent")
    rows: dict[str, str] = {}
    for line in text.splitlines():
        for key in ALL_ROWS:
            if line.startswith("| `" + key + "` |"):
                if key in rows or "| NO_VERIFICABLE |" not in line:
                    raise ValueError("UNKNOWN: duplicated or promoted " + key)
                rows[key] = line
                break
    if set(rows) != set(ALL_ROWS):
        raise ValueError("UNKNOWN: missing rows")
    return rows


def comparable():
    before = perf_fixture.finding()
    after = perf_fixture.finding(
        classification="PERF_INFO", breach=False,
        observed={**before["observed"], "value": 220,
                  "observed_at": "2026-09-28T20:06:00Z"},
        identity={"sha": "b" * 40, "release": "v1.2.4"},
        evidence_ref="run:3",
    )
    return before, after


class CoberturaFactory35Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """Run the real behavior for all 14 locally executable slices."""
        matrix = (ROOT / "docs" / "matriz-cobertura.md").read_text(encoding="utf-8")
        rows = matrix_rows(matrix)
        self.assertEqual(len(rows), 20)
        self.assertEqual(len(A_ROWS), 14)
        self.assertEqual(len(B_ROWS), 4)
        self.assertEqual(len(C_ROWS), 2)

        old, new = comparable()
        adopted = evaluate_before_after(old, new)
        # L21: exact project/surface/metric, matching budget & CURRENT.
        self.assertEqual(adopted["decision"], "ADOPT")
        self.assertEqual((adopted["project"], adopted["surface"], adopted["metric"]),
                         ("condor", "inventory", "latency_p95"))
        # L23: distinct evidence_ref AND build identity, newer UTC timestamp.
        self.assertEqual((adopted["before_evidence_ref"], adopted["after_evidence_ref"]),
                         ("run:2", "run:3"))
        self.assertEqual(adopted["delta"], -80)
        # L25-U1, L25-U2: finite sampled observation and canonical units.
        measured = copy.deepcopy(new)
        measured["observed"]["sample_count"] = 31_536_000
        measured["observed"]["window_seconds"] = 31_536_000
        self.assertEqual(evaluate_before_after(old, measured)["decision"], "ADOPT")
        self.assertEqual(old["observed"]["unit"], old["budget"]["unit"])
        # L3: actual Work Origin validation, not free-form queue work.
        plan = plan_remediation(old, perf_fixture.triage(), perf_fixture.proposal())
        validated = validate_work_item(plan["work_item"])
        self.assertEqual(validated["origin_mode"], "automatic")
        self.assertEqual(validated["project_id"], "condor")
        # L9: fail-closed remediation; L29: pure artifacts, no execution.
        self.assertEqual(plan["decision"], "AUTO_REPAIR")
        self.assertTrue(plan["queue_required"])
        self.assertFalse(plan["execute_actions"])
        self.assertEqual(plan["authority"], "unchanged")
        # Team bridge: real detection validated with required UTC clock.
        team = compile_performance_team(team_fixture.detected(300),
                                        evaluated_at=team_fixture.NOW)
        self.assertEqual(team["decision"], "TEAM_RECOMMENDED")
        self.assertEqual(team["primary"], "dba")
        self.assertTrue({"dba", "ingenieria-software", "qa"} <= set(team["roles"]))
        self.assertFalse(team["execute_actions"])

        # Portfolio L10: no automatic decision or change of owner priority.
        a, b = portfolio_fixture.item("synthetic:a"), portfolio_fixture.item("synthetic:b")
        b["signals"]["unlocks"] = portfolio_fixture.known(7, "fixture:deps/b")
        b["signals"]["impact"] = portfolio_fixture.known(
            {"technical": "low", "product": "high"}, "fixture:impact/b")
        b["signals"]["reversibility"] = portfolio_fixture.known(
            "partially_reversible", "fixture:rollback/b")
        report = explain_tradeoffs([b, a])
        self.assertTrue(report["owner_priority_authoritative"])
        self.assertEqual(report["authority"], "owner_unchanged")
        self.assertIsNone(report["decision"])
        # L18, L22, L23 and L28: structured values actually normalized.
        dims = report["dimensions"]
        self.assertEqual([x["value"] for x in dims["unlocks"]], [3, 7])
        self.assertEqual(dims["impact"][1]["value"],
                         {"technical": "low", "product": "high"})
        self.assertEqual(dims["reversibility"][1]["value"], "partially_reversible")
        self.assertEqual(dims["cost"][0]["value"]["agent_minutes"], 40)
        # L27: known and unknown statuses are distinct, unknown never invented.
        unknown = copy.deepcopy(a)
        unknown["signals"]["risk"] = portfolio_fixture.unknown()
        normalized = validate_portfolio_item(unknown)
        self.assertEqual(normalized["signals"]["risk"]["status"], "unknown")
        self.assertIsNone(normalized["signals"]["risk"]["value"])
        self.assertEqual(len(explain_tradeoffs([unknown, b])["uncertainty"]), 1)

    def test_falla_cerrado(self) -> None:
        """Malformed matrices, conflicting metrics, absent permissions and forged evidence."""
        raw = (ROOT / "docs" / "matriz-cobertura.md").read_text(encoding="utf-8")
        rows = matrix_rows(raw)
        for key in ALL_ROWS:
            with self.subTest(row=key):
                line = rows[key]
                with self.assertRaises(ValueError):
                    matrix_rows(raw.replace(line, "", 1))
                with self.assertRaises(ValueError):
                    matrix_rows(raw + "\n" + line)
                with self.assertRaises(ValueError):
                    matrix_rows(raw.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO", 1)))
        with self.assertRaises(ValueError):
            matrix_rows(None)

        old, after = comparable()
        for k, v in (("project", "wrong-project"), ("surface", "orders"),
                     ("metric", "memory")):
            bad = copy.deepcopy(after)
            bad[k] = v
            with self.subTest(field=k):
                with self.assertRaises(PerformanceRemediationError):
                    evaluate_before_after(old, bad)
        for field, value in (("sample_count", True), ("window_seconds", 0),
                             ("window_seconds", 31_536_001)):
            bad = copy.deepcopy(after)
            bad["observed"][field] = value
            with self.assertRaises(PerformanceRemediationError):
                evaluate_before_after(old, bad)
        bad = copy.deepcopy(after)
        bad["budget"]["unit"] = "bytes"
        with self.assertRaises(PerformanceRemediationError):
            evaluate_before_after(old, bad)
        reuse = copy.deepcopy(after)
        reuse["evidence_ref"] = old["evidence_ref"]
        self.assertEqual(evaluate_before_after(old, reuse)["decision"],
                         "REVERT_OR_REPLAN")
        reuse = copy.deepcopy(after)
        reuse["identity"] = old["identity"]
        self.assertEqual(evaluate_before_after(old, reuse)["decision"],
                         "REVERT_OR_REPLAN")
        stale = copy.deepcopy(after)
        stale["evidence_state"] = "STALE"
        self.assertEqual(evaluate_before_after(old, stale)["decision"],
                         "REVERT_OR_REPLAN")
        self.assertNotEqual(
            plan_remediation(old, perf_fixture.triage(),
                             perf_fixture.proposal(within_authority=False))["decision"],
            "AUTO_REPAIR",
        )
        with self.assertRaises(PerformanceTeamCompilerBridgeError):
            compile_performance_team(team_fixture.detected(300),
                                    evaluated_at="2026-09-28T20:31:00Z")
        bad_item = portfolio_fixture.item()
        bad_item["signals"]["unlocks"] = portfolio_fixture.known(-1, "fixture:bad")
        with self.assertRaises(PortfolioSignalsError):
            validate_portfolio_item(bad_item)
        missing = portfolio_fixture.item()
        missing["signals"]["risk"] = portfolio_fixture.unknown()
        missing["signals"]["risk"]["confidence"] = 0.9
        with self.assertRaises(PortfolioSignalsError):
            validate_portfolio_item(missing)
        other = portfolio_fixture.item("synthetic:foreign", priority="critical")
        with self.assertRaises(PortfolioSignalsError):
            explain_tradeoffs([portfolio_fixture.item("synthetic:high"), other])

    def test_sin_datos_reales(self) -> None:
        """Synthetic fixtures only. No external network, secrets or deployment."""
        self.assertEqual(set(A_ROWS) | set(B_ROWS) | set(C_ROWS), set(ALL_ROWS))
        for reason in (*B_ROWS.values(), *C_ROWS.values()):
            self.assertTrue(reason)
        performance = plan_remediation(
            perf_fixture.finding(), perf_fixture.triage(), perf_fixture.proposal())
        comparison = evaluate_before_after(*comparable())
        tradeoffs = explain_tradeoffs([
            portfolio_fixture.item("synthetic:a"),
            portfolio_fixture.item("synthetic:b"),
        ])
        for result in (performance, comparison, tradeoffs):
            serialized = json.dumps(result, ensure_ascii=False)
            self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", serialized))
            self.assertNotIn("github_pat_", serialized)
            self.assertNotIn("ghp_", serialized)
        self.assertFalse(performance["execute_actions"])
        self.assertIsNone(tradeoffs["decision"])
        script = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(script)
        dangerous = {"requests", "urllib", "socket", "httpx", "subprocess"}
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & dangerous)


if __name__ == "__main__":
    unittest.main()