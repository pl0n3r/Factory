#!/usr/bin/env python3
"""Regresión ejecutable del selector real de Seguridad y puertas humanas (#1124).

Evalúa exclusivamente el subconjunto de expresiones usado por la condición del
job en el YAML versionado. No usa GitHub, tokens ni workflow_dispatch.
"""
from __future__ import annotations

import ast
import re
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/seguridad.yml").read_text(encoding="utf-8")


def _job(name: str, following: str) -> str:
    return WORKFLOW.split(f"\n  {name}:\n", 1)[1].split(f"\n  {following}:\n", 1)[0]


def _selector() -> str:
    job = _job("materializar-respuesta", "sincronizar-decision")
    condition = job.split("    if: >-\n", 1)[1].split("    runs-on:", 1)[0]
    return " ".join(line.strip() for line in condition.strip().splitlines())


def _fixture(body: str = "/decidir A") -> dict:
    return {
        "github": {
            "event_name": "issue_comment",
            "event": {
                "issue": {"pull_request": None, "state": "open"},
                "sender": {"login": "pl0n3r"},
                "comment": {
                    "body": body,
                    "author_association": "OWNER",
                    "user": {"login": "pl0n3r", "type": "User"},
                },
            },
        }
    }


def _would_run(payload: dict) -> bool:
    """Interpreta la condición extraída del YAML, no una copia de la regla."""
    expression = _selector()

    def lookup(match: re.Match[str]) -> str:
        node: object = payload
        for part in match.group(0).split("."):
            node = node.get(part) if isinstance(node, dict) else None
        return repr(node)

    expression = re.sub(
        r"\bgithub(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b", lookup, expression
    )
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"\bnull\b", "None", expression)
    tree = ast.parse(expression, mode="eval")
    permitted = (
        ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.Compare,
        ast.Eq, ast.NotEq, ast.Constant, ast.Load,
    )
    if any(type(item) not in permitted for item in ast.walk(tree)):
        raise AssertionError("Condición no soportada por el evaluador seguro")
    return bool(eval(compile(tree, "<security-workflow-condition>", "eval"),
                     {"__builtins__": {}}, {}))


class SecurityCommentRoutingTests(unittest.TestCase):
    def test_prose_and_coordination_commands_do_not_trigger_gate(self):
        for body in (
            "", "Estado de QA actualizado", "/tomar", "/liberar",
            "/renovar-contrato 123", "No ejecuté /decidir A",
            "Nota: el comando /decidir B es un ejemplo.",
            "texto\n/decidir A", "/decidir A\nOtro texto",
            "/decidir A ", " /decidir C", "/decidir E",
            "/decidir A y B", "/DECIDIR A", "<script>/decidir A</script>",
        ):
            with self.subTest(body=body):
                self.assertFalse(_would_run(_fixture(body)))

    def test_only_owner_decision_commands_route(self):
        for option in "ABCD":
            with self.subTest(option=option):
                self.assertTrue(_would_run(_fixture("/decidir " + option)))

        for change in (
            lambda e: e["github"].update(event_name="issues"),
            lambda e: e["github"]["event"]["issue"].update(pull_request={}),
            lambda e: e["github"]["event"]["issue"].update(state="closed"),
            lambda e: e["github"]["event"]["comment"].update(author_association="MEMBER"),
            lambda e: e["github"]["event"]["comment"].update(author_association="NONE"),
            lambda e: e["github"]["event"]["comment"]["user"].update(type="Bot"),
            lambda e: e["github"]["event"]["sender"].update(login="intruso"),
        ):
            payload = deepcopy(_fixture())
            change(payload)
            with self.subTest(payload=payload):
                self.assertFalse(_would_run(payload))

    def test_security_workflow_event_and_permissions_are_preserved(self):
        header = WORKFLOW.split("\njobs:\n", 1)[0]
        for event in (
            "  pull_request:", "  push:", "  issues:",
            "  issue_comment:", "  workflow_dispatch:",
        ):
            self.assertIn(event, header)
        self.assertIn("  cancel-in-progress: false", header)
        self.assertIn("permissions:\n  contents: read", header)
        self.assertNotIn("issues: write", header)

        jobs = WORKFLOW.split("\njobs:\n", 1)[1]
        for name in (
            "validar-candidato", "preparar-cola", "materializar-respuesta",
            "sincronizar-decision",
        ):
            self.assertIn(f"  {name}:", jobs)

        materialize = _job("materializar-respuesta", "sincronizar-decision")
        self.assertIn("    timeout-minutes: 5", materialize)
        self.assertIn("    permissions:\n      contents: read\n      issues: write", materialize)
        self.assertIn("Autorizar evento antes de checkout", materialize)
        self.assertIn("Reconciliar puerta canónica antes de decidir", materialize)
        self.assertIn("Validar comando y materializar decisión", materialize)
        self.assertIn("steps.preflight.outputs.trusted == 'true'", materialize)
        self.assertIn("steps.gate_sync.outputs.canonical == 'true'", materialize)
        self.assertIn("AUTHOR_ASSOCIATION:", materialize)
        self.assertIn("DEFAULT_BRANCH:", materialize)
        self.assertEqual(len(re.findall(r"\bgithub\.event\.comment\.body == ", _selector())), 4)
        for option in "ABCD":
            self.assertIn(f"github.event.comment.body == '/decidir {option}'", _selector())
        self.assertNotIn("contains(", _selector())
        self.assertNotIn("startsWith(", _selector())

        other = _job("preparar-cola", "materializar-respuesta")
        self.assertIn("github.event_name == 'push'", other)
        self.assertIn("github.event_name == 'workflow_dispatch'", other)
        sync = WORKFLOW.split("\n  sincronizar-decision:\n", 1)[1]
        self.assertIn("github.event_name == 'issues'", sync)
        self.assertIn("Retirar de la cola si no es puerta válida y confiable", sync)


if __name__ == "__main__":
    unittest.main()
