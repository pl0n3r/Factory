import json
import tempfile
import unittest
from pathlib import Path

from scripts.aceptacion_kit import (
    AcceptanceError,
    CheckPending,
    Criterion,
    contract_fingerprint,
    parse_contract,
    run_named_test,
    validate_payload,
    verify_check,
    verify_checks_only,
)


def issue_body(criteria_lines, machine_rows, version=1):
    marker = json.dumps(
        {"version": version, "criteria": machine_rows},
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

    def test_acceptance_marker_version_requires_strict_integer_type(self):
        """AC-01: version acepta solo el entero exacto 1."""
        row = {"id": "AC-01", "kind": "check", "target": "Tests de scripts"}
        for version in (True, False, 1.0, 2.0, "1", None, 0, 2):
            with self.subTest(version=version):
                with self.assertRaisesRegex(AcceptanceError, "version=1"):
                    parse_contract(
                        issue_body(
                            "- [ ] [AC-01] Debe pasar.",
                            [row],
                            version=version,
                        )
                    )

    def test_canonical_acceptance_fingerprint_remains_stable(self):
        """AC-04: el guard de tipo no altera la huella canónica existente."""
        body = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [{"id": "AC-01", "kind": "check", "target": "Tests de scripts"}],
        )
        self.assertEqual(
            contract_fingerprint(body),
            "7889f18cb8c388b068c95d0a7563227c4cf4681820a1a7565d0a8d03dff8e0e8",
        )

    def test_contract_rejects_non_string_kind_without_typeerror(self):
        body = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [
                {
                    "id": "AC-01",
                    "kind": [],
                    "target": "Tests de scripts",
                }
            ],
        )

        with self.assertRaisesRegex(AcceptanceError, "kind/target inválidos"):
            parse_contract(body)

    def test_pinned_contract_rejects_transient_weakening(self):
        """Una evidencia máquina debilitada cambia la huella fijada."""
        original = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [
                {
                    "id": "AC-01",
                    "kind": "check",
                    "target": "Tests de scripts",
                }
            ],
        )
        weakened = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [
                {
                    "id": "AC-01",
                    "kind": "check",
                    "target": "Lint de workflows",
                }
            ],
        )
        peripheral_edit = original.replace(
            "Contexto verificable.",
            "Contexto verificable con nota adicional.",
        )

        self.assertNotEqual(
            contract_fingerprint(original),
            contract_fingerprint(weakened),
        )
        self.assertEqual(
            contract_fingerprint(original),
            contract_fingerprint(peripheral_edit),
        )

    def test_payload_rejects_contract_drift_against_pinned_fingerprint(self):
        """El gate ejecuta solo el contrato fijado por la reserva."""
        original = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [
                {
                    "id": "AC-01",
                    "kind": "check",
                    "target": "Tests de scripts",
                }
            ],
        )
        changed = original.replace("Debe pasar.", "Debe pasar debilitado.")
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

        payload = {
            "issue": {"body": original},
            "checks": checks,
            "acceptance_sha256": contract_fingerprint(original),
        }
        self.assertEqual(validate_payload(payload)["verified"], ["AC-01"])

        payload["issue"] = {"body": changed}
        with self.assertRaisesRegex(
            AcceptanceError,
            "cambió después de la reserva",
        ):
            validate_payload(payload)

    def test_protected_payload_requires_pinned_fingerprint(self):
        """El flujo protegido rechaza payloads legacy sin pin."""
        body = issue_body(
            "- [ ] [AC-01] Debe pasar.",
            [
                {
                    "id": "AC-01",
                    "kind": "check",
                    "target": "Tests de scripts",
                }
            ],
        )
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
        payload = {
            "issue": {"body": body},
            "checks": checks,
            "require_pin": True,
        }

        with self.assertRaisesRegex(
            AcceptanceError,
            "requiere acceptance_sha256",
        ):
            validate_payload(payload)

        payload["acceptance_sha256"] = contract_fingerprint(body)
        self.assertEqual(validate_payload(payload)["verified"], ["AC-01"])

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

    def test_named_test_can_import_from_repo_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests_dir = root / "tests"
            tests_dir.mkdir()
            (root / "helper.py").write_text(
                "VALUE = 7\n",
                encoding="utf-8",
            )
            (tests_dir / "test_sample.py").write_text(
                "import unittest\n"
                "from helper import VALUE\n"
                "class Demo(unittest.TestCase):\n"
                "    def test_import(self):\n"
                "        self.assertEqual(VALUE, 7)\n",
                encoding="utf-8",
            )
            run_named_test(
                Criterion(
                    "AC-01",
                    "test",
                    "tests/test_sample.py::Demo::test_import",
                ),
                root,
            )

    def test_named_test_can_import_sibling_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            security_dir = root / "seguridad"
            security_dir.mkdir()
            (security_dir / "sibling_helper.py").write_text(
                "VALUE = 11\n",
                encoding="utf-8",
            )
            (security_dir / "test_sample.py").write_text(
                "import unittest\n"
                "from sibling_helper import VALUE\n"
                "class Demo(unittest.TestCase):\n"
                "    def test_import(self):\n"
                "        self.assertEqual(VALUE, 11)\n",
                encoding="utf-8",
            )
            run_named_test(
                Criterion(
                    "AC-01",
                    "test",
                    "seguridad/test_sample.py::Demo::test_import",
                ),
                root,
            )

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

    def test_workflow_paginates_check_runs(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "aceptacion.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'gh api --paginate "repos/$REPOSITORY/commits/$SHA/check-runs?per_page=100" --slurp',
            workflow,
        )
        self.assertIn(
            "jq '{check_runs: [.[].check_runs[]]}' /tmp/check-pages.json > /tmp/checks.json",
            workflow,
        )

    def test_check_after_first_api_page_is_verified(self):
        criterion = Criterion("AC-01", "check", "SonarCloud Code Analysis")
        checks = {
            "check_runs": [
                {
                    "id": index,
                    "name": f"metadata-{index}",
                    "status": "completed",
                    "conclusion": "success",
                }
                for index in range(1, 101)
            ]
            + [
                {
                    "id": 101,
                    "name": "SonarCloud Code Analysis",
                    "status": "completed",
                    "conclusion": "success",
                }
            ]
        }
        verify_check(criterion, checks)

    def test_check_collection_over_limit_fails_closed(self):
        criterion = Criterion("AC-01", "check", "Tests de scripts")
        checks = {
            "check_runs": [
                {
                    "id": index,
                    "name": f"check-{index}",
                    "status": "completed",
                    "conclusion": "success",
                }
                for index in range(1, 502)
            ]
        }
        with self.assertRaisesRegex(AcceptanceError, "lista acotada"):
            verify_check(criterion, checks)

    def test_workflow_keeps_readonly_check_permissions(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "aceptacion.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "permissions:\n      contents: read\n      issues: read\n      checks: read",
            workflow,
        )
        self.assertIn(
            '[[ "$EVENT_NAME" == "pull_request" ]]',
            workflow,
        )

    def test_latest_check_run_wins(self):
        criterion = Criterion("AC-01", "check", "Tests de scripts")
        with self.assertRaisesRegex(CheckPending, "sigue in_progress"):
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

    def test_nonterminal_check_is_retryable_but_terminal_failure_is_not(self):
        criterion = Criterion("AC-01", "check", "Contrato ControlBot")
        for checks in (
            {"check_runs": []},
            {"check_runs": [{"id": 10, "name": "Contrato ControlBot", "status": "queued", "conclusion": None}]},
            {"check_runs": [{"id": 11, "name": "Contrato ControlBot", "status": "in_progress", "conclusion": None}]},
        ):
            with self.subTest(checks=checks):
                with self.assertRaises(CheckPending):
                    verify_check(criterion, checks)

        with self.assertRaisesRegex(AcceptanceError, "terminó sin success"):
            verify_check(
                criterion,
                {"check_runs": [{"id": 12, "name": "Contrato ControlBot", "status": "completed", "conclusion": "failure"}]},
            )

    def test_latest_check_run_still_wins_during_retry(self):
        criterion = Criterion("AC-01", "check", "Contrato ControlBot")
        checks = {
            "check_runs": [
                {"id": 20, "name": "Contrato ControlBot", "status": "completed", "conclusion": "success"},
                {"id": 21, "name": "Contrato ControlBot", "status": "in_progress", "conclusion": None},
            ]
        }
        with self.assertRaises(CheckPending):
            verify_checks_only([criterion], checks)
        checks["check_runs"][1].update(status="completed", conclusion="success")
        self.assertEqual(verify_checks_only([criterion], checks), ["AC-01"])

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
