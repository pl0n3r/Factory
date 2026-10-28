"""Factory#1663: 16 regresiones offline de Portfolio Signals y PR labels.

Datos exclusivamente sintéticos: no verifica eventos historicos de GitHub,
no concede permisos owner ni activa rulesets.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from portfolio.signals import PortfolioSignalsError, explain_tradeoffs, validate_portfolio_item
from scripts.pr_label_governance import (
    GITHUB_ACTIONS_INTEGRATION_ID, GovernanceError, RULESET_NAME,
    audit_repository, merged_pr_alert_plan, owner_commands, uniform_ruleset_payload,
)

ROOT = Path(__file__).resolve().parents[1]
UNITS = (
    "docs/portfolio-signals.md:L47-U1",
    "docs/portfolio-signals.md:L48-U1",
    "docs/portfolio-signals.md:L49-U1",
    "docs/portfolio-signals.md:L55-U1",
    "docs/portfolio-signals.md:L7-U1",
    "docs/portfolio-signals.md:L8-U1",
    "docs/portfolio-signals.md:L9-U1",
    "docs/pr-label-governance.md:L19-U1",
    "docs/pr-label-governance.md:L23-U1",
    "docs/pr-label-governance.md:L3-U1",
    "docs/pr-label-governance.md:L32-U1",
    "docs/pr-label-governance.md:L33-U1",
    "docs/pr-label-governance.md:L34-U1",
    "docs/pr-label-governance.md:L35-U1",
    "docs/pr-label-governance.md:L36-U1",
    "docs/pr-label-governance.md:L38-U1",
)


def known(value, *, source="declared", confidence=0.9, ref="synthetic:Factory1663"):
    return {"status": "known", "value": value, "source": source,
            "confidence": confidence, "provenance": [ref]}


def unknown():
    return {"status": "unknown", "value": None, "source": None,
            "confidence": 0, "provenance": []}


def item(work_id, *, unlocks=2, risk="low", minutes=10):
    return {
        "version": 1, "work_id": work_id, "eligible": True, "owner_priority": "high",
        "signals": {
            "unlocks": known(unlocks),
            "urgency": known("medium"),
            "risk": known(risk, source="estimated", confidence=0.6),
            "cost": known({"agent_minutes": minutes, "ci_minutes": 4, "tokens": 150},
                          source="estimated", confidence=0.6),
            "impact": known({"technical": "high", "product": "medium"},
                            ref="synthetic:feedback-6"),
            "reversibility": known("reversible"),
        },
    }


def synthetic_event():
    """No acredita el evento histórico FactoryRunner PR #82."""
    return {
        "pr": {"number": 82, "merged_at": "2026-01-01T00:00:00Z",
               "head": {"sha": "a" * 40}},
        "check_runs": [{
            "id": 1, "name": "validar-pr / Labels", "status": "completed",
            "conclusion": "failure", "completed_at": "2026-01-01T00:00:01Z",
        }],
        "comments": [],
    }


class BrechasFactory45Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {}
        for line in (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            columns = [value.strip() for value in line.split("|")]
            key = columns[1].strip(chr(96) + " ") if len(columns) > 4 else ""
            if key in UNITS:
                if key in cls.rows:
                    raise AssertionError("Unidad duplicada: " + key)
                cls.rows[key] = columns

    def test_contrato_principal(self):
        """AC-01: cada fila exacta tiene aserción o un UNKNOWN explícito."""
        first = item("synthetic:Factory1663-a", unlocks=2)
        first["signals"]["cost"] = unknown()
        second = item("synthetic:Factory1663-b", unlocks=7, risk="high", minutes=40)
        report = explain_tradeoffs([second, first])
        signals = validate_portfolio_item(second)["signals"]
        payload = uniform_ruleset_payload()
        rules = payload["rules"]
        parameters = rules[0]["parameters"]
        checks = parameters["required_status_checks"]
        commands = owner_commands(["Factory"])
        alert = merged_pr_alert_plan(synthetic_event())
        # No se usa un evento fabricado para demostrar un hecho histórico.
        historical = {"status": "UNKNOWN", "reason": "historical_evidence_not_observed"}
        owner = {"status": "UNKNOWN", "reason": "owner_action_not_observed"}

        by_id = {
            "docs/portfolio-signals.md:L47-U1": report["decision"] is None,
            "docs/portfolio-signals.md:L48-U1": report["authority"] == "owner_unchanged",
            "docs/portfolio-signals.md:L49-U1": report["uncertainty"] == [
                {"work_id": first["work_id"], "signal": "cost"}],
            "docs/portfolio-signals.md:L55-U1": (
                report["dimensions"]["unlocks"][1]["value"] == 7
                and report["dimensions"]["risk"][1]["value"] == "high"
                and report["dimensions"]["cost"][1]["value"]["agent_minutes"] == 40
                and report["decision"] is None
            ),
            "docs/portfolio-signals.md:L7-U1": (
                signals["impact"]["value"] == {"technical": "high", "product": "medium"}
                and signals["impact"]["source"] == "declared"
            ),
            "docs/portfolio-signals.md:L8-U1": (
                signals["cost"]["value"] == {"agent_minutes": 40, "ci_minutes": 4, "tokens": 150}
                and signals["cost"]["source"] == "estimated"
                and signals["cost"]["confidence"] == 0.6
            ),
            "docs/portfolio-signals.md:L9-U1": (
                signals["impact"]["provenance"] == ["synthetic:feedback-6"]
                and report["uncertainty"][0]["signal"] == "cost"
            ),
            "docs/pr-label-governance.md:L19-U1": (
                alert["action"] == "create" and "pr=82" in alert["body"]
                and historical["status"] == "UNKNOWN"
            ),
            "docs/pr-label-governance.md:L23-U1": (
                len(rules) == 1 and rules[0]["type"] == "required_status_checks"
                and len(checks) == 1 and checks[0]["context"] == "Etiquetas"
            ),
            "docs/pr-label-governance.md:L3-U1": (
                owner["status"] == "UNKNOWN"
                and commands[1].startswith("gh api --method POST repos/pl0n3r/Factory/rulesets")
            ),
            "docs/pr-label-governance.md:L32-U1": (
                payload["name"] == RULESET_NAME == "factory-required-labels"
            ),
            "docs/pr-label-governance.md:L33-U1": (
                payload["target"] == "branch" and payload["enforcement"] == "active"
            ),
            "docs/pr-label-governance.md:L34-U1": (
                payload["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
            ),
            "docs/pr-label-governance.md:L35-U1": (
                checks == [{"context": "Etiquetas",
                            "integration_id": GITHUB_ACTIONS_INTEGRATION_ID}]
                and GITHUB_ACTIONS_INTEGRATION_ID == 15368
            ),
            "docs/pr-label-governance.md:L36-U1": (
                parameters["strict_required_status_checks_policy"] is False
                and payload["bypass_actors"] == []
            ),
            "docs/pr-label-governance.md:L38-U1": (
                owner["reason"] == "owner_action_not_observed"
                and "ruleset-payload" in commands[0]
                and all("--method POST" in command for command in commands[1:])
            ),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(set(by_id), set(UNITS))
        self.assertEqual(set(self.rows), set(UNITS))
        for identifier in UNITS:
            with self.subTest(unit=identifier):
                self.assertEqual(self.rows[identifier][3], "NO_VERIFICABLE")
                self.assertTrue(by_id[identifier], identifier + ": NO_VERIFICABLE")

    def test_falla_cerrado(self):
        """AC-02: no derivar SUCCESS a partir de desconocidos o formas inválidas."""
        first = item("synthetic:a")
        second = item("synthetic:b")
        first["signals"]["cost"] = unknown()
        self.assertIsNone(validate_portfolio_item(first)["signals"]["cost"]["value"])
        with self.assertRaises(PortfolioSignalsError):
            explain_tradeoffs([first, second | {"owner_priority": "medium"}])
        with self.assertRaises(PortfolioSignalsError):
            explain_tradeoffs([first, second | {"eligible": False}])
        invalid = copy.deepcopy(first)
        invalid["signals"]["cost"]["value"] = {
            "agent_minutes": 0, "ci_minutes": 0, "tokens": 0,
        }
        with self.assertRaises(PortfolioSignalsError):
            validate_portfolio_item(invalid)
        self.assertEqual(
            audit_repository("Factory", rulesets=None, branch_protection=None)["status"],
            "unknown",
        )
        with self.assertRaises(GovernanceError):
            audit_repository("Factory", rulesets={}, branch_protection={})
        pending = synthetic_event()
        pending["check_runs"] = [{"name": "Labels", "status": "in_progress"}]
        self.assertEqual(merged_pr_alert_plan(pending)["reason"], "label_check_not_terminal")

    def test_sin_datos_reales(self):
        """AC-03: fixtures ficticios sin red, PII, tokens ni secretos."""
        fixtures = [item("synthetic:a"), item("synthetic:b"), synthetic_event()]
        encoded = json.dumps(fixtures, sort_keys=True)
        self.assertIn("synthetic", encoded)
        self.assertNotIn("https://", encoded)
        self.assertNotIn("password", encoded.lower())
        self.assertNotIn("token_secret", encoded.lower())
        self.assertNotIn("@gmail", encoded.lower())
        self.assertNotIn("authorization", encoded.lower())
        self.assertEqual(fixtures[2]["pr"]["head"]["sha"], "a" * 40)

    def test_estados_unknown_explicitos(self):
        """AC-04: autoridad owner e histórico sin prueba quedan UNKNOWN."""
        missing = [
            {"status": "UNKNOWN", "reason": "historical_evidence_not_observed"},
            {"status": "UNKNOWN", "reason": "owner_action_not_observed"},
        ]
        for evidence in missing:
            with self.subTest(reason=evidence["reason"]):
                self.assertEqual(evidence["status"], "UNKNOWN")
                self.assertNotIn("success", evidence.values())
        audit = audit_repository("Factory", rulesets=None, branch_protection={})
        self.assertEqual(audit["status"], "unknown")
        self.assertFalse(audit["rulesets_visible"])
        first = item("synthetic:a")
        first["signals"]["impact"] = unknown()
        report = explain_tradeoffs([first, item("synthetic:b")])
        self.assertEqual(report["uncertainty"], [
            {"work_id": "synthetic:a", "signal": "impact"},
        ])
        self.assertIsNone(report["decision"])


if __name__ == "__main__":
    unittest.main()
