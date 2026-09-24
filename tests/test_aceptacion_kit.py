import json
import tempfile
import unittest
from pathlib import Path

from scripts.aceptacion_kit import (
    AcceptanceError,
    Criterion,
    parse_contract,
    run_named_test,
    verify_check,
)


def issue_body(criteria_lines, machine_rows):
    marker = json.dumps(
        {"version": 1, "criteria": machine_rows},
        separators=(",", ":"),
    )
    return f"""### Contexto

Contexto verificable.

### Alcance

Alcance verificable.

### Fuera de alcance

Nada adicional.

### Criterios de aceptación

{criteria_lines}

### Contrato ejecutable

<!-- factory-acceptance {marker} -->
"""


class AcceptanceContractTests(unittest.TestCase):
    def test_contract_rejects_missing_sections_and_mismatch(self):
        row = {
            "id": "AC-01",
            "kind": "check",
            "target": "Tests de scripts",
        }
        valid = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [row],
        )
        self.assertEqual(parse_contract(valid)[0].id, "AC-01")
        with self.assertRaisesRegex(AcceptanceError, "Sección obligatoria"):
            parse_contract(valid.replace("### Alcance", "### Otro"))
        with self.assertRaisesRegex(AcceptanceError, "no coinciden"):
            parse_contract(
                issue_body(
                    "- [ ] [AC-02] Otro.",
                    [row],
                )
            )

    def test_named_test_runs_exact_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            target = tests_dir / "test_sample.py"
            target.write_text(
                "import unittest\n"
                "class Demo(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(2 + 2, 4)\n"
                "    def test_not_selected(self):\n"
                "        self.fail('no debe correr')\n",
                encoding="utf-8",
            )
            criterion = Criterion(
                "AC-01",
                "test",
                "tests/test_sample.py::Demo::test_ok",
            )
            run_named_test(criterion, root)

    def test_named_test_rejects_missing_or_failing_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n"
                "class Demo(unittest.TestCase):\n"
                "    def test_bad(self):\n"
                "        self.fail('fallo esperado')\n",
                encoding="utf-8",
            )
            with self.assertRaises(AcceptanceError):
                run_named_test(
                    Criterion(
                        "AC-01",
                        "test",
                        "tests/test_sample.py::Demo::test_bad",
                    ),
                    root,
                )
            with self.assertRaises(AcceptanceError):
                run_named_test(
                    Criterion(
                        "AC-01",
                        "test",
                        "tests/test_sample.py::Demo::test_missing",
                    ),
                    root,
                )

    def test_check_must_exist_and_be_success(self):
        criterion = Criterion("AC-01", "check", "Tests de scripts")
        checks = {
            "check_runs": [
                {
                    "id": 10,
                    "name": "Tests de scripts",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }
        verify_check(criterion, checks)
        with self.assertRaisesRegex(AcceptanceError, "no terminó success"):
            verify_check(
                criterion,
                {
                    "check_runs": [
                        {
                            "id": 11,
                            "name": "Tests de scripts",
                            "status": "completed",
                            "conclusion": "failure",
                        }
                    ]
                },
            )
        with self.assertRaisesRegex(AcceptanceError, "no existe check"):
            verify_check(criterion, {"check_runs": []})

    def test_latest_check_run_wins(self):
        criterion = Criterion("AC-01", "check", "Tests de scripts")
        with self.assertRaisesRegex(AcceptanceError, "no terminó success"):
            verify_check(
                criterion,
                {
                    "check_runs": [
                        {
                            "id": 10,
                            "name": "Tests de scripts",
                            "status": "completed",
                            "conclusion": "success",
                        },
                        {
                            "id": 12,
                            "name": "Tests de scripts",
                            "status": "in_progress",
                            "conclusion": None,
                        },
                    ]
                },
            )

    def test_self_referential_checks_are_rejected(self):
        for target in ("Validar", "Criterios de aceptación"):
            body = issue_body(
                "- [ ] [AC-01] Criterio.",
                [{"id": "AC-01", "kind": "check", "target": target}],
            )
            with self.subTest(target=target):
                with self.assertRaisesRegex(AcceptanceError, "autorreferencial"):
                    parse_contract(body)


if __name__ == "__main__":
    unittest.main()
