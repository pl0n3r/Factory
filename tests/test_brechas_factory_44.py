"""Factory #1662: 16 contratos offline, sin permisos, red ni observaciones reales.

Los ejemplos de revisión son exclusivamente sintéticos. Nunca acreditan una
revisión CodeRabbit real ni habilitan una publicación o un merge.
"""
from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from performance.detector import detect_performance
from performance.team_compiler_bridge import (
    PerformanceTeamCompilerBridgeError, compile_performance_team,
)
from portfolio.signals import (
    PortfolioSignalsError, explain_tradeoffs, validate_portfolio_item,
)
from scripts import politica_kit as policy

ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40
EVALUATED = "2026-09-28T20:06:00Z"
BOT = "coderabbitai[bot]"
UNITS = (
    "docs/performance-team-compiler-bridge.md:L3-U1",
    "docs/politica-revisor-externo.md:B01",
    "docs/politica-revisor-externo.md:B02",
    "docs/politica-revisor-externo.md:B03",
    "docs/politica-revisor-externo.md:B04",
    "docs/portfolio-signals.md:L10-U1",
    "docs/portfolio-signals.md:L18-U1",
    "docs/portfolio-signals.md:L22-U1",
    "docs/portfolio-signals.md:L23-U1",
    "docs/portfolio-signals.md:L27-U1",
    "docs/portfolio-signals.md:L28-U1",
    "docs/portfolio-signals.md:L29-U1",
    "docs/portfolio-signals.md:L31-U1",
    "docs/portfolio-signals.md:L37-U1",
    "docs/portfolio-signals.md:L39-U1",
    "docs/portfolio-signals.md:L46-U1",
)


def detection(*, value=300, bottleneck="database"):
    """Detección estructurada fabricada para tests; no procede de una API."""
    metric = {
        "id": "latency_p95", "label": "Latency p95",
        "baseline": {"value": 180, "unit": "ms", "observed_at": "2026-09-28T20:00:00Z"},
        "budget": {"operator": "lte", "value": 250, "unit": "ms"},
        "window": {"duration_seconds": 300, "min_samples": 20},
        "freshness": {"max_age_seconds": 900},
        "evidence": {"source": "ci", "ref": "synthetic:run:1",
                     "observed_at": "2026-09-28T20:00:00Z"},
        "allowed_actions": ["create_work_item", "measure_before_after"],
        "escalation_conditions": ["architecture_change", "cost_change"],
    }
    contract = {"version": 1, "project": "condor", "surfaces": [
        {"id": "inventory", "label": "Inventory", "metrics": [metric]},
    ]}
    observation = {
        "version": 1, "project": "condor", "surface": "inventory",
        "metric": "latency_p95", "value": value, "unit": "ms",
        "observed_at": "2026-09-28T20:05:00Z", "window_seconds": 300,
        "sample_count": 30, "severity": "high", "operational_impact": False,
        "bottleneck": bottleneck, "evidence_ref": "synthetic:run:2",
        "sha": HEAD, "release": "synthetic",
    }
    return detect_performance(contract, observation, evaluated_at=EVALUATED)


def known(value, *, source="declared", confidence=0.8):
    return {"status": "known", "value": value, "confidence": confidence,
            "source": source, "provenance": ["synthetic:Factory#1662"]}


def unknown():
    return {"status": "unknown", "value": None, "confidence": 0,
            "source": None, "provenance": []}


def work_item(identifier="pl0n3r/Factory#1662-a", *, eligible=True,
              priority="high"):
    return {
        "version": 1, "work_id": identifier,
        "owner_priority": priority, "eligible": eligible,
        "signals": {
            "unlocks": known(3), "urgency": known("medium"),
            "risk": known("low", source="estimated"),
            "cost": known({"agent_minutes": 20, "ci_minutes": 5, "tokens": 100}),
            "impact": known({"technical": "high", "product": "medium"}),
            "reversibility": known("reversible"),
        },
    }


def checks(*, head=HEAD):
    names = (
        "validate", "SonarCloud Code Analysis", "CodeQL", "tests",
        "validar-pr / Validar coordinación", "privacidad / Privacidad como código",
    )
    out = []
    for number, name in enumerate(names, 10):
        slug = ("sonarqubecloud" if name == "SonarCloud Code Analysis" else
                "github-advanced-security" if name == "CodeQL" else "github-actions")
        out.append(json.dumps({
            "id": number, "name": name, "head_sha": head,
            "status": "completed", "conclusion": "success",
            "completed_at": "2026-10-04T05:01:00Z",
            "app": {"slug": slug, "id": {
                "sonarqubecloud": 12526, "github-advanced-security": 57789,
                "github-actions": 15368,
            }[slug]},
        }))
    return out


def rate_limit(*, body="Review rate limited.", timestamp="2026-10-04T05:02:00Z",
               login=BOT):
    return json.dumps({
        "id": 202, "body": body, "created_at": timestamp,
        "user": {"type": "Bot", "login": login},
    })


def reviewer_no_quota(*, phase="construccion", comments=None, gate_checks=None,
                      reviews=None, threads=None, committed_at="2026-10-04T05:00:00Z"):
    return policy.validate_rate_limited_no_block(
        required_review_bot=BOT, head_sha=HEAD, head_committed_at=committed_at,
        phase=phase, review_lines=[] if reviews is None else reviews,
        comment_lines=[rate_limit()] if comments is None else comments,
        check_lines=checks() if gate_checks is None else gate_checks,
        thread_lines=[] if threads is None else threads,
    )


def policy_fallback(**overrides):
    options = dict(
        required_review_bot=BOT, head_sha=HEAD,
        head_committed_at="2026-10-04T05:00:00Z", phase="construccion",
        review_lines=[], comment_lines=[rate_limit()],
        check_lines=checks(), thread_lines=[], run_attempt=1,
    )
    options.update(overrides)
    return policy.validate_rate_limit_fallback(**options)


class BrechasFactory44Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: 16 IDs con aserción concreta o limitación UNKNOWN."""
        team = compile_performance_team(detection(), evaluated_at=EVALUATED)
        first = work_item()
        second = work_item("pl0n3r/Factory#1662-b")
        report = explain_tradeoffs([second, first])
        normalized = validate_portfolio_item(first)
        signals = normalized["signals"]
        policy_doc = (ROOT / "docs/politica-revisor-externo.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/politica.yml").read_text(encoding="utf-8")
        # El output de policy es una detección sintética; no acredita revisión real.
        limited = reviewer_no_quota()
        checks_by_id = {
            "docs/performance-team-compiler-bridge.md:L3-U1": (
                team["decision"] == "TEAM_RECOMMENDED"
                and team["primary"] == "dba"
                and {"dba", "qa"}.issubset(team["roles"])
                and team["authority"] == "unchanged"
                and not any(team[k] for k in ("dispatch", "create_work_item", "execute_actions"))
            ),
            "docs/politica-revisor-externo.md:B01": (
                policy.parse_phase_payload('{"phase":"construccion"}') == "construccion"
                and limited[0] == 202 and "BASE exacta" in policy_doc
                and all("success" in x for x in checks())
            ),
            "docs/politica-revisor-externo.md:B02": (
                policy.parse_phase_payload('{"phase":"live"}') == "live"
                and "HEAD exacto" in policy_doc
                and "@coderabbitai review" in policy_doc
            ),
            "docs/politica-revisor-externo.md:B03": (
                policy.MAX_TIMELINE_EVENTS == 500
                and "timeline REST" in policy_doc
                and "SHA-less" in policy_doc
            ),
            "docs/politica-revisor-externo.md:B04": (
                'factory_ref: {required: false, type: string, default: "v1"}' in workflow
                and "^[0-9a-f]{40}$" in workflow
                and "ref: v1" in workflow
                and "ref: ${{ inputs.factory_ref }}" in workflow
                and "No se modifica `Factory@v1`" in policy_doc
            ),
            "docs/portfolio-signals.md:L10-U1": (
                report["authority"] == "owner_unchanged"
                and report["decision"] is None and "winner" not in report
            ),
            "docs/portfolio-signals.md:L18-U1": (
                signals["unlocks"]["value"] == 3
                and report["dimensions"]["unlocks"][0]["value"] == 3
            ),
            "docs/portfolio-signals.md:L22-U1": (
                signals["impact"]["value"] == {"technical": "high", "product": "medium"}
            ),
            "docs/portfolio-signals.md:L23-U1": (
                signals["reversibility"]["value"] == "reversible"
            ),
            "docs/portfolio-signals.md:L27-U1": (
                signals["risk"]["status"] == "known"
                and set(signals) == {"unlocks", "urgency", "risk", "cost", "impact", "reversibility"}
            ),
            "docs/portfolio-signals.md:L28-U1": (
                signals["cost"]["value"] == {"agent_minutes": 20, "ci_minutes": 5, "tokens": 100}
            ),
            "docs/portfolio-signals.md:L29-U1": (
                signals["risk"]["confidence"] == 0.8
                and all(s["confidence"] > 0 for s in signals.values())
            ),
            "docs/portfolio-signals.md:L31-U1": (
                signals["unlocks"]["provenance"] == ["synthetic:Factory#1662"]
                and all(s["provenance"] for s in signals.values())
            ),
            "docs/portfolio-signals.md:L37-U1": (
                len(report["items"]) == 2 and len(report["dimensions"]) == 6
            ),
            "docs/portfolio-signals.md:L39-U1": (
                all(x["eligible"] for x in report["items"])
                and report["owner_priority"] == "high"
            ),
            "docs/portfolio-signals.md:L46-U1": (
                report["owner_priority_authoritative"] is True
                and report["authority"] == "owner_unchanged"
                and report["decision"] is None
            ),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(checks_by_id), set(UNITS))
        for identifier, satisfied in checks_by_id.items():
            with self.subTest(unit=identifier):
                self.assertTrue(satisfied, identifier + ": NO_VERIFICABLE")

    def test_falla_cerrado(self):
        """AC-02: rechazar evidencias huérfanas, permisos falsos y valores ambiguos."""
        with self.assertRaises(PerformanceTeamCompilerBridgeError):
            compile_performance_team(detection(), evaluated_at="2026-09-28T20:45:00Z")
        with self.assertRaises(PerformanceTeamCompilerBridgeError):
            compile_performance_team(detection(), evaluated_at="no-timestamp")
        with self.assertRaises(policy.PolicyError):
            reviewer_no_quota(phase="live")
        with self.assertRaises(policy.PolicyError):
            reviewer_no_quota(committed_at="2026-10-04T05:04:00Z")
        with self.assertRaises(policy.PolicyError):
            reviewer_no_quota(gate_checks=checks(head="b" * 40))
        with self.assertRaises(policy.PolicyError):
            reviewer_no_quota(comments=[rate_limit(login="unauthenticated[bot]")])
        with self.assertRaises(policy.PolicyError):
            policy_fallback()  # un único rate-limit no constituye el retry OWNER
        with self.assertRaises(policy.PolicyError):
            policy_fallback(run_attempt=2)  # sin Policy failure/OWNER exact-HEAD
        with self.assertRaises(policy.PolicyError):
            policy._sha_less_timeline_retry(
                timeline_lines=[], comment_lines=[], required_review_bot=BOT,
                head_sha=HEAD, head_committed_at="2026-10-04T05:00:00Z",
                failed_policy_checks=[],
            )
        with self.assertRaises(policy.PolicyError):
            policy._sha_less_timeline_retry(
                timeline_lines=[json.dumps({"event": "committed", "sha": HEAD}),
                                json.dumps({"event": "head_ref_force_pushed"})],
                comment_lines=[], required_review_bot=BOT,
                head_sha=HEAD, head_committed_at="2026-10-04T05:00:00Z",
                failed_policy_checks=[],
            )
        with self.assertRaises(policy.PolicyError):
            policy.parse_phase_payload('{"phase":"other"}')
        with self.assertRaises(policy.PolicyError):
            policy.validate_required_bot_review([json.dumps({
                "id": 1, "state": "COMMENTED", "body": "Review rate limited.",
                "commit_id": HEAD,
                "user": {"login": BOT, "type": "Bot"},
            })], BOT, HEAD)

        original = work_item()
        invalids = []
        for signal, field, value in (
            ("unlocks", "value", True),
            ("unlocks", "value", -1),
            ("impact", "value", {"technical": "high"}),
            ("reversibility", "value", "certain"),
            ("urgency", "confidence", float("nan")),
            ("risk", "confidence", 0),
            ("cost", "value", {"agent_minutes": -1, "ci_minutes": 5, "tokens": 100}),
            ("risk", "provenance", []),
            ("impact", "source", "unauthenticated"),
            ("risk", "status", "ambiguous"),
        ):
            data = copy.deepcopy(original)
            data["signals"][signal][field] = value
            invalids.append(data)
        for invalid in invalids:
            with self.subTest(payload=repr(invalid)[:90]):
                with self.assertRaises(PortfolioSignalsError):
                    validate_portfolio_item(invalid)
        with self.assertRaises(PortfolioSignalsError):
            explain_tradeoffs([work_item(), work_item(eligible=False,
                                                   identifier="pl0n3r/Factory#1662-b")])
        with self.assertRaises(PortfolioSignalsError):
            explain_tradeoffs([work_item(), work_item("pl0n3r/Factory#1662-b",
                                                   priority="low")])

    def test_sin_datos_reales(self):
        """AC-03: entradas sintéticas; sin credenciales, red o efectos laterales."""
        projection = explain_tradeoffs([
            work_item("pl0n3r/Factory#1662-b"), work_item(),
        ])
        generated = compile_performance_team(detection(), evaluated_at=EVALUATED)
        self.assertEqual([x["work_id"] for x in projection["items"]],
                         ["pl0n3r/Factory#1662-a", "pl0n3r/Factory#1662-b"])
        for forbidden in ("secret", "password", "credential", "token", "access_key",
                          "email", "owner_email", "api_key", "winner", "score"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, json.dumps(projection).lower())
                self.assertNotIn(forbidden, json.dumps(generated).lower())
        for prop in ("dispatch", "create_work_item", "execute_actions"):
            self.assertFalse(generated[prop])
        self.assertIsNone(projection["decision"])
        self.assertEqual(projection["authority"], "owner_unchanged")
        source = (ROOT / "portfolio/signals.py").read_text(encoding="utf-8")
        self.assertNotIn("requests.post(", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("subprocess.run(", source)
        self.assertEqual(detection()["evidence_ref"], "synthetic:run:2")

    def test_estados_unknown_explicitos(self):
        """AC-04: UNKNOWN no es cero, priorización ni autorización."""
        unknown_item = work_item()
        for key in ("unlocks", "cost", "impact"):
            unknown_item["signals"][key] = unknown()
        report = explain_tradeoffs([
            unknown_item, work_item("pl0n3r/Factory#1662-b"),
        ])
        for key in ("unlocks", "cost", "impact"):
            with self.subTest(signal=key):
                signal = report["dimensions"][key][0]
                self.assertEqual(signal["status"], "unknown")
                self.assertIsNone(signal["value"])
                self.assertEqual(signal["confidence"], 0)
                self.assertIsNone(signal["source"])
                self.assertIn({"work_id": "pl0n3r/Factory#1662-a", "signal": key},
                              report["uncertainty"])
        for forged_field, value in (("value", 0), ("confidence", 0.5),
                                    ("source", "declared")):
            invalid = copy.deepcopy(unknown_item)
            invalid["signals"]["cost"][forged_field] = value
            with self.subTest(field=forged_field):
                with self.assertRaises(PortfolioSignalsError):
                    validate_portfolio_item(invalid)
        self.assertIsNone(report["decision"])
        self.assertTrue(report["owner_priority_authoritative"])
        self.assertEqual(report["authority"], "owner_unchanged")
        with self.assertRaises(PerformanceTeamCompilerBridgeError):
            compile_performance_team(detection(), evaluated_at="2026-09-28T20:31:00Z")
        with self.assertRaises(policy.PolicyError):
            reviewer_no_quota(comments=[])


if __name__ == "__main__":
    unittest.main()