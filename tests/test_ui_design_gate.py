#!/usr/bin/env python3
"""Puerta de diseño visual para issues de UI; ejecución offline determinista."""
from __future__ import annotations

import io
import json
import re
import unittest
from pathlib import Path

from scripts import issue_contract_preflight as preflight
from tests.test_issue_contract_preflight import VALID_BODY


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    ".claude/skills/impeccable/SKILL.md",
    ".claude/skills/make-interfaces-feel-better/SKILL.md",
)
DESIGN = (
    "### Diseño\n"
    f"- Referencia: {SKILLS[0]} (modo Operate; reference/craft-floor.md).\n"
    f"- Referencia: {SKILLS[1]}.\n\n"
)
CAPTURES = "capturas antes/después a 390 px y 1440 px"


def issue_with_claims(paths: list[str], *, design: str = "", captures: bool = False) -> str:
    payload = json.dumps(paths, ensure_ascii=False, separators=(",", ":"))
    body = VALID_BODY.replace(
        '"paths":["scripts/example.py","tests/example.py"]',
        '"paths":' + payload,
    )
    if captures:
        body = body.replace("criterio de prueba.", CAPTURES + ".")
    if design:
        body = body.replace("### Rutas reclamadas", design + "### Rutas reclamadas")
    return body


class UiDesignGateTests(unittest.TestCase):
    def test_visual_file_claims_require_design_and_capture_acceptance(self) -> None:
        paths = (
            "frontend/src/styles/layout.css",
            "frontend/src/pages/Settings.tsx",
            "frontend/src/pages/Settings.js",
            "templates/public/landing.html",
            "symfony/templates/signup.html.twig",
            "resources/views/signup.blade.php",
        )
        for path in paths[:-1]:
            with self.subTest(path=path):
                with self.assertRaises(preflight.IssueContractPreflightError) as error:
                    preflight.evaluate_issue_body(issue_with_claims([path]))
                self.assertEqual(error.exception.code, "ui_design_invalid")
                self.assertIn("### Diseño", str(error.exception))

                result = preflight.evaluate_issue_body(
                    issue_with_claims([path], design=DESIGN, captures=True)
                )
                self.assertTrue(result["valid"])
                self.assertEqual(result["paths"], [path])

    def test_ui_directory_claim_requires_evidence(self) -> None:
        with self.assertRaises(preflight.IssueContractPreflightError) as error:
            preflight.evaluate_issue_body(issue_with_claims(["frontend/"]))
        self.assertEqual(error.exception.code, "ui_design_invalid")

    def test_missing_skill_and_missing_capture_criterion_fail_closed(self) -> None:
        path = "frontend/src/pages/Settings.tsx"
        cases = [
            (DESIGN.replace(SKILLS[0], "impeccable"), True),
            (DESIGN.replace(SKILLS[1], "make-interfaces-feel-better"), True),
            (DESIGN, False),
            (DESIGN, True),
        ]
        for index, (design, captures) in enumerate(cases):
            body = issue_with_claims([path], design=design, captures=captures)
            if index == 3:
                body = body.replace("390 px", "391 px")
            with self.subTest(case=index):
                with self.assertRaises(preflight.IssueContractPreflightError) as error:
                    preflight.evaluate_issue_body(body)
                self.assertEqual(error.exception.code, "ui_design_invalid")

    def test_design_heading_only_in_prose_is_not_valid(self) -> None:
        body = issue_with_claims(["frontend/App.tsx"], captures=True)
        body = body.replace("### Rutas reclamadas", "La sección Diseño está pendiente.\n\n### Rutas reclamadas")
        with self.assertRaises(preflight.IssueContractPreflightError):
            preflight.evaluate_issue_body(body)

    def test_non_ui_issue_keeps_contract_and_cli_behavior(self) -> None:
        for paths in (
            ["scripts/example.py", "tests/example.py"],
            ["scripts/worker.js", "backend/index.ts"],
            ["docs/operations.md"],
        ):
            with self.subTest(paths=paths):
                body = issue_with_claims(paths)
                result = preflight.evaluate_issue_body(body)
                self.assertTrue(result["valid"])
                output = io.StringIO()
                self.assertEqual(preflight.main([], stdin=io.StringIO(body), stdout=output), 0)
                self.assertTrue(json.loads(output.getvalue())["valid"])

        output = io.StringIO()
        self.assertEqual(
            preflight.main(
                [],
                stdin=io.StringIO(issue_with_claims(["frontend/App.tsx"])),
                stdout=output,
            ),
            2,
        )
        reason = json.loads(output.getvalue())
        self.assertEqual(reason["code"], "ui_design_invalid")
        self.assertIn("### Diseño", reason["reason"])

    def test_plan_and_pr_template_publish_same_quality_gate(self) -> None:
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
        self.assertIn("### Interfaz", plan)
        self.assertIn("390", plan)
        self.assertIn("1440", plan)
        self.assertIn("CodeRabbit FINAL", plan)
        for skill in SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, plan)
                self.assertIn(skill, template)
        self.assertIn("craft-floor.md", plan)
        self.assertIn("Capturas 390/1440 y checklist de diseño", template)


if __name__ == "__main__":
    unittest.main()
