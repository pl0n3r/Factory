#!/usr/bin/env python3
"""Factory #1799: ejecutar contratos de continuidad y PR merge con fakes.

Solo datos sinteticos; no red, secretos ni lectura de matrices de cobertura.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import runpy
import unittest

from scripts import coordinar_trabajo as coord


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "trabajo/issue-1799"
ISSUE = 1799
PR = 41


class _CoordAPI:
    """Interfaz minima que usa el coordinador real, sin acceso externo."""

    def __init__(self) -> None:
        self.issue_state = "open"
        self.statuses: list[str] = []
        self.deleted: list[str] = []
        self.pulls = {
            PR: {
                "number": PR,
                "state": "open",
                "merged": False,
                "head": {"ref": BRANCH},
                "base": {"ref": "main"},
                "body": "Closes #1799",
            }
        }
        self.files = {PR: {"tests/test_cobertura_factory_08.py"}}

    def pull(self, number: int) -> dict:
        return self.pulls[number]

    def issue(self, number: int) -> dict:
        if number != ISSUE:
            raise AssertionError("Issue sintetico desconocido")
        return {
            "number": ISSUE,
            "state": self.issue_state,
            "labels": [{"name": "estado: disponible"}],
            "body": "",
        }

    def open_pulls(self) -> list[dict]:
        return [value for value in self.pulls.values()
                if value.get("state") == "open"]

    def pull_files(self, number: int) -> set[str]:
        return self.files[number]

    def issue_comments(self, number: int) -> list[dict]:
        if number != ISSUE:
            raise AssertionError("Issue sintetico desconocido")
        return []

    def branch_sha(self, name: str) -> str | None:
        return "a" * 40 if name == BRANCH else None

    def delete_branch(self, name: str) -> None:
        self.deleted.append(name)

    def set_status(self, issue_number: int, status: str) -> None:
        if issue_number != ISSUE:
            raise AssertionError("No se permite tocar otro issue")
        self.statuses.append(status)


class CoberturaFactory08Tests(unittest.TestCase):
    """Cuatro AC canónicos, con subcasos del comportamiento que describen."""

    def test_contrato_principal(self) -> None:
        # El parser autentico del contrato STATE debe permitir continuar
        # desde un objetivo, SHA, intentos fallidos y accion siguiente.
        original = runpy.run_path(str(ROOT / "tests/test_conversacion_agentes.py"))
        parse = original["parse_state"]
        fields = set(original["CAMPOS"])
        note = (ROOT / "tests/fixtures/estado_compacto.md").read_text(encoding="utf-8")
        state = parse(note)
        self.assertEqual(set(state), fields)
        self.assertRegex(state["head"][0], r"^trabajo/issue-\d+@[0-9a-f]{40}$")
        for key in ("objetivo", "repo", "issue", "pr", "confirmado",
                    "no repetir", "pendiente", "siguiente"):
            self.assertTrue(state[key], key)
        with self.assertRaisesRegex(ValueError, "STATE"):
            parse("no es una nota\nobjetivo: sintetico")

        # Los helpers reales limitan el Issue y la relacion Closes/Fixes.
        self.assertEqual(coord.issue_from_branch(BRANCH), ISSUE)
        self.assertEqual(
            coord.closing_issues("Closes #1799\nFixes #999\nResolves #40"),
            {1799, 999, 40},
        )
        self.assertIsNone(coord.issue_from_branch("experimento/issue-1799"))
        api = _CoordAPI()
        coord.validate_pull(api, PR, require_reservation=False)

        # El caller conserva el evento closed para reconciliar; solo la
        # validacion queda condicionada a que merged NO sea true.
        caller = (ROOT / "template/.github/workflows/coordinacion.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("types: [opened, reopened, synchronize, edited, "
                      "ready_for_review, converted_to_draft, closed]", caller)
        self.assertIn("operation: pr", caller)
        event_guard = caller.split("  validar-pr-evento:\n", 1)[1].split(
            "\n  validar-pr:\n", 1
        )[0]
        self.assertIn("github.event.pull_request.merged != true", event_guard)
        validate_job = caller.split("\n  validar-pr:\n", 1)[1].split(
            "\n  issue:\n", 1
        )[0]
        self.assertIn("needs: validar-pr-evento", validate_job)
        self.assertIn("operation: validate", validate_job)

        reusable = (ROOT / ".github/workflows/coordinacion.yml").read_text(
            encoding="utf-8"
        )
        validation = reusable.split("\n  validar-pr:\n", 1)[1].split(
            "\n  sweep:\n", 1
        )[0]
        self.assertIn("inputs.operation == 'validate'", validation)
        self.assertIn("github.event_name == 'pull_request'", validation)
        self.assertIn("github.event.pull_request.merged == true", validation)
        self.assertIn("python3 .factory/scripts/coordinar_trabajo.py validar-pr",
                      validation)

        # Las tres rutas de regresion historica citadas en la especificacion
        # deben seguir siendo metodos ejecutables, no nombres inventados.
        cases = (
            ("tests/test_coordinacion_reusable_contract.py",
             "test_merged_pr_validation_is_neutral"),
            ("tests/test_consumer_coordination_template.py",
             "test_merged_pr_does_not_revalidate"),
            ("tests/test_coordinar_trabajo.py",
             "test_open_pr_with_closed_issue_still_fails_closed"),
        )
        for filename, method in cases:
            with self.subTest(reference=filename):
                source = (ROOT / filename).read_text(encoding="utf-8")
                parsed = ast.parse(source)
                functions = {node.name for node in ast.walk(parsed)
                             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
                self.assertIn(method, functions)

    def test_falla_cerrado(self) -> None:
        # PR abierto: el validador real nunca acepta Issue cerrado,
        # branch ajena, base incorrecta, relacion de cierre ausente ni
        # colision de archivos.
        api = _CoordAPI()
        api.issue_state = "closed"
        with self.assertRaisesRegex(coord.CoordinationError,
                                    "debe estar abierto durante el PR"):
            coord.validate_pull(api, PR, require_reservation=False)
        api.issue_state = "open"

        api.pulls[PR]["base"]["ref"] = "otro"
        with self.assertRaisesRegex(coord.CoordinationError, "base del PR debe ser main"):
            coord.validate_pull(api, PR, require_reservation=False)
        api.pulls[PR]["base"]["ref"] = "main"

        api.pulls[PR]["body"] = "Se arregla otro asunto"
        with self.assertRaisesRegex(coord.CoordinationError, "Closes #1799"):
            coord.validate_pull(api, PR, require_reservation=False)
        api.pulls[PR]["body"] = "Closes #1799"

        api.pulls[PR]["head"]["ref"] = "refs/heads/feature"
        with self.assertRaisesRegex(coord.CoordinationError, "formato canonico|formato canónico"):
            coord.validate_pull(api, PR, require_reservation=False)
        api.pulls[PR]["head"]["ref"] = BRANCH

        api.pulls[43] = {
            "number": 43, "state": "open",
            "base": {"ref": "main"}, "head": {"ref": "trabajo/issue-43"},
            "body": "Closes #43",
        }
        api.files[43] = {"tests/test_cobertura_factory_08.py"}
        with self.assertRaisesRegex(coord.CoordinationError, "Colisión con PR #43"):
            coord.validate_pull(api, PR, require_reservation=False)
        del api.pulls[43]
        del api.files[43]

        # Ausencia de V3 autentica falla incluso con PR/Issue validos.
        with self.assertRaisesRegex(coord.CoordinationError, "reserva activa"):
            coord.validate_pull(api, PR, require_reservation=True)
        self.assertFalse(coord.authorized("NONE"))
        self.assertTrue(coord.authorized("OWNER"))

        # El cierre sin merge solo devuelve la hoja a disponible; un
        # verdadero merge cierra el frente como completado.
        closed = dict(api.pulls[PR], state="closed", merged=False)
        coord.close_pr_reservation(api, ISSUE, BRANCH, closed, current=None)
        self.assertEqual(api.statuses[-1], coord.STATUS_AVAILABLE)
        merged = dict(closed, merged=True)
        coord.close_pr_reservation(api, ISSUE, BRANCH, merged, current=None)
        self.assertEqual(api.statuses[-1], coord.STATUS_COMPLETED)
        self.assertEqual(api.deleted, [BRANCH, BRANCH])

    def test_sin_datos_reales(self) -> None:
        # Fixture exclusivamente sintetico que llama al parser real.
        original = runpy.run_path(str(ROOT / "tests/test_conversacion_agentes.py"))
        parse = original["parse_state"]
        sample = (
            "STATE\n"
            "objetivo: validar continuidad ficticia\n"
            "repo: pl0n3r/Factory\n"
            "issue: #1799\n"
            "pr: #41\n"
            "head: trabajo/issue-1799@" + "a" * 40 + "\n"
            "decisiones:\n- sin trafico real\n"
            "confirmado:\n- comprobacion aislada\n"
            "no repetir:\n- reintento sin cambiar fixture\n"
            "pendiente:\n- pruebas unitarias\n"
            "siguiente: ejecutar suite sin red\n"
        )
        state = parse(sample)
        self.assertEqual(state["issue"], ["#1799"])
        self.assertEqual(state["no repetir"], ["reintento sin cambiar fixture"])
        self.assertEqual(state["siguiente"], ["ejecutar suite sin red"])
        self.assertEqual(set(state), set(original["CAMPOS"]))
        self.assertTrue(all(value for values in state.values() for value in values))
        api = _CoordAPI()
        coord.validate_pull(api, PR, require_reservation=False)
        self.assertEqual(api.deleted, [])
        self.assertEqual(api.statuses, [])

    def test_gate_validar_presente(self) -> None:
        # La prueba es informativa; la autoridad de CI es el check terminal
        # exact-HEAD publicado por Actions, nunca una asercion textual.
        pipeline = (ROOT / ".github/workflows/ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertRegex(pipeline, r"(?m)^    name: Validar$")
        self.assertIn("name: Validar contrato", pipeline)
        self.assertTrue(callable(coord.validate_pull))
        self.assertTrue(callable(coord.close_pr_reservation))


if __name__ == "__main__":
    unittest.main()
