#!/usr/bin/env python3
"""Factory #1827: pruebas de funciones reales, sin afirmar evidencia operativa.

17 unidades A ejecutables; 3 unidades C documentales/históricas se clasifican
para reconciliación posterior. No se inspecciona la matriz de cobertura.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest

from portfolio.signals import (
    PortfolioSignalsError, SIGNALS, explain_tradeoffs, validate_portfolio_item,
)
from scripts.pr_label_governance import (
    GITHUB_ACTIONS_INTEGRATION_ID, GovernanceError, REQUIRED_CONTEXT,
    RULESET_TARGET_REPOSITORIES, audit_repository, merged_pr_alert_plan,
    owner_commands, uniform_ruleset_payload,
)

P = "docs/portfolio-signals.md"
G = "docs/pr-label-governance.md"
A = {
    *(f"{P}:L{line}-U1" for line in (7, 8, 9, 29, 31, 37, 39, 46, 47, 48, 49)),
    *(f"{G}:L{line}-U1" for line in (23, 32, 33, 34, 35, 36)),
}
C = {
    f"{P}:L55-U1": "Ejemplo narrativo de presentación de ControlBot; no existe renderer en el módulo",
    f"{G}:L19-U1": "Hecho histórico de FactoryRunner PR #82; requiere evidencia GitHub autenticada",
    f"{G}:L3-U1": "La administración owner-only es política de GitHub, no escritura de rulesets por este módulo",
}
ALL = A | set(C)
assert len(ALL) == 20 and len(A) == 17 and len(C) == 3


def known(value, ref: str, *, source: str = "declared", confidence: float = 0.8):
    return {"status": "known", "value": value, "confidence": confidence,
            "source": source, "provenance": [ref]}


def unknown():
    return {"status": "unknown", "value": None, "confidence": 0,
            "source": None, "provenance": []}


def work(work_id: str, *, eligible: bool = True, priority: str = "high"):
    return {
        "version": 1, "work_id": work_id,
        "owner_priority": priority, "eligible": eligible,
        "signals": {
            "unlocks": known(4, "fixture:deps", source="observed"),
            "urgency": known("high", "fixture:urgency"),
            "risk": known("medium", "fixture:risk"),
            "cost": known({"agent_minutes": 24, "ci_minutes": 5, "tokens": 900},
                          "fixture:cost", source="estimated", confidence=0.6),
            "impact": known({"technical": "high", "product": "medium"},
                            "fixture:feedback", source="declared"),
            "reversibility": known("reversible", "fixture:rollback"),
        },
    }


def label_alert(*, conclusion: str = "failure", merged: bool = True):
    return {
        "pr": {"number": 82, "merged_at": "2026-10-02T00:00:00Z" if merged else None,
               "head": {"sha": "a" * 40}},
        "check_runs": [{"name": "validar-pr / Labels", "status": "completed",
                        "conclusion": conclusion, "id": 7,
                        "completed_at": "2026-10-02T00:00:00Z",
                        "details_url": "https://github.com/example/synthetic"}],
        "comments": [],
    }


class CoberturaFactory36Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: 17 predicados por fila invocan código productivo con fixtures."""
        a, b = work("fixture/a"), work("fixture/b")
        b["signals"]["unlocks"] = known(8, "fixture:deps-b")
        b["signals"]["risk"] = unknown()
        first = validate_portfolio_item(a)
        second = validate_portfolio_item(b)
        comparison = explain_tradeoffs([b, a])
        dimensions = comparison["dimensions"]
        payload = uniform_ruleset_payload()
        checks = payload["rules"][0]["parameters"]
        required = checks["required_status_checks"]
        commands = owner_commands()
        proofs = {
            f"{P}:L7-U1": (first["signals"]["impact"]["value"] ==
                            {"technical": "high", "product": "medium"}
                            and first["signals"]["impact"]["source"] == "declared"),
            f"{P}:L8-U1": (first["signals"]["cost"]["value"] ==
                            {"agent_minutes": 24, "ci_minutes": 5, "tokens": 900}
                            and first["signals"]["cost"]["confidence"] == 0.6
                            and first["signals"]["cost"]["source"] == "estimated"),
            f"{P}:L9-U1": (first["signals"]["risk"]["provenance"] ==
                            ["fixture:risk"] and first["signals"]["risk"]["status"] == "known"),
            f"{P}:L29-U1": (first["signals"]["unlocks"]["confidence"] == 0.8
                             and second["signals"]["risk"]["confidence"] == 0),
            f"{P}:L31-U1": (dimensions["cost"][0]["provenance"] == ["fixture:cost"]
                             and dimensions["unlocks"][1]["provenance"] == ["fixture:deps-b"]),
            f"{P}:L37-U1": (len(comparison["items"]) == 2
                             and all({"work_id", "owner_priority", "eligible", "signals"}
                                     <= set(item) for item in comparison["items"])),
            f"{P}:L39-U1": (all(i["eligible"] is True for i in comparison["items"])
                             and [i["work_id"] for i in comparison["items"]] ==
                             ["fixture/a", "fixture/b"]),
            f"{P}:L46-U1": comparison["owner_priority_authoritative"] is True,
            f"{P}:L47-U1": comparison["decision"] is None,
            f"{P}:L48-U1": comparison["authority"] == "owner_unchanged",
            f"{P}:L49-U1": comparison["uncertainty"] ==
                             [{"work_id": "fixture/b", "signal": "risk"}],
            f"{G}:L23-U1": (len(payload["rules"]) == 1 and
                             payload["rules"][0]["type"] == "required_status_checks" and
                             len(required) == 1 and required[0]["context"] == REQUIRED_CONTEXT and
                             "GrindFlow" not in RULESET_TARGET_REPOSITORIES and
                             len(commands) == 1 + len(RULESET_TARGET_REPOSITORIES)),
            f"{G}:L32-U1": payload["name"] == "factory-required-labels",
            f"{G}:L33-U1": payload["target"] == "branch" and payload["enforcement"] == "active",
            f"{G}:L34-U1": payload["conditions"]["ref_name"] ==
                             {"include": ["~DEFAULT_BRANCH"], "exclude": []},
            f"{G}:L35-U1": required == [{"context": "Etiquetas", "integration_id":
                                         GITHUB_ACTIONS_INTEGRATION_ID}],
            f"{G}:L36-U1": (checks["strict_required_status_checks_policy"] is False
                             and checks["do_not_enforce_on_create"] is False
                             and payload["bypass_actors"] == []),
        }
        self.assertEqual(set(proofs), A)
        self.assertEqual(set(proofs) | set(C), ALL)
        for row, ok in proofs.items():
            with self.subTest(row=row):
                self.assertIs(ok, True, f"Sin prueba de comportamiento: {row}")

    def test_falla_cerrado(self) -> None:
        """AC-02: permisos, confianza, referencias y claims inválidos se rechazan."""
        valid = work("fixture/a")
        for field, value in (("eligible", None), ("eligible", "true"),
                             ("owner_priority", "unknown"), ("version", 2)):
            invalid = copy.deepcopy(valid)
            invalid[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(PortfolioSignalsError):
                    validate_portfolio_item(invalid)
        for signal, key, value in (
            ("cost", "confidence", float("nan")),
            ("cost", "confidence", 1.2),
            ("risk", "provenance", []),
            ("risk", "source", "forged"),
            ("impact", "value", {"technical": "high", "product": "untrusted"}),
        ):
            invalid = copy.deepcopy(valid)
            invalid["signals"][signal][key] = value
            with self.subTest(signal=signal, key=key):
                with self.assertRaises(PortfolioSignalsError):
                    validate_portfolio_item(invalid)
        for pair in (
            [valid, work("fixture/b", eligible=False)],
            [valid, work("fixture/b", priority="critical")],
            [valid, work("fixture/a")],
            [valid, {"work_id": "fixture/foreign"}],
        ):
            with self.subTest(case=str(pair[1].get("work_id"))):
                with self.assertRaises(PortfolioSignalsError):
                    explain_tradeoffs(pair)
        with self.assertRaises(GovernanceError):
            owner_commands(["Factory", "outsider"])
        with self.assertRaises(GovernanceError):
            audit_repository("outsider", rulesets=[], branch_protection={})
        with self.assertRaises(GovernanceError):
            audit_repository("Factory", rulesets={}, branch_protection={})
        plan = merged_pr_alert_plan(label_alert())
        self.assertEqual(plan["action"], "create")
        self.assertEqual(plan["reason"], "merged_with_non_green_labels")
        self.assertIn("failure", plan["body"])
        duplicate = label_alert()
        duplicate["comments"] = [{"body": plan["body"]}]
        self.assertEqual(merged_pr_alert_plan(duplicate)["reason"], "already_alerted")
        self.assertEqual(merged_pr_alert_plan(label_alert(merged=False))["reason"],
                         "not_merged")
        self.assertEqual(merged_pr_alert_plan(label_alert(conclusion="success"))["reason"],
                         "label_check_green")

    def test_sin_datos_reales(self) -> None:
        """AC-03: la suite es pura, determinista, sin red ni credenciales."""
        for key in SIGNALS:
            self.assertIn(key, work("fixture/test")["signals"])
        self.assertEqual(len(ALL), 20)
        self.assertEqual(len(A), 17)
        self.assertEqual(len(C), 3)
        self.assertTrue(all(reason for reason in C.values()))
        data = json.dumps(explain_tradeoffs([work("fixture/a"), work("fixture/b")]))
        self.assertNotIn("github_pat_", data)
        self.assertNotIn("ghp_", data)
        self.assertNotIn("email", data.lower())
        self.assertIsNone(explain_tradeoffs([work("fixture/a"), work("fixture/b")])["decision"])
        imports = set()
        for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.update(x.name.split(".")[0] for x in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(imports & {"requests", "urllib", "httpx", "socket", "subprocess"})

    def test_estados_unknown_explicitos(self) -> None:
        """AC-04: UNKNOWN nunca se transforma en permiso ni fuente verde."""
        a = work("fixture/a")
        b = work("fixture/b")
        b["signals"]["cost"] = unknown()
        compare = explain_tradeoffs([a, b])
        self.assertEqual(compare["dimensions"]["cost"][1], {
            "work_id": "fixture/b", "status": "unknown", "value": None,
            "confidence": 0, "source": None, "provenance": [],
        })
        self.assertEqual(compare["uncertainty"],
                         [{"work_id": "fixture/b", "signal": "cost"}])
        forged = copy.deepcopy(b)
        forged["signals"]["cost"]["confidence"] = 0.5
        with self.assertRaises(PortfolioSignalsError):
            explain_tradeoffs([a, forged])
        audit = audit_repository("Factory", rulesets=None, branch_protection={})
        self.assertEqual(audit["status"], "unknown")
        self.assertFalse(audit["rulesets_visible"])
        not_observed = label_alert()
        not_observed["check_runs"] = []
        self.assertEqual(merged_pr_alert_plan(not_observed)["reason"], "no_label_check")
        pending = label_alert()
        pending["check_runs"][0]["status"] = "in_progress"
        self.assertEqual(merged_pr_alert_plan(pending)["reason"],
                         "label_check_not_terminal")


if __name__ == "__main__":
    unittest.main()
