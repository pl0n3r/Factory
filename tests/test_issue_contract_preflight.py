import inspect
import io
import json
import unittest
from unittest import mock

from scripts import issue_contract_preflight as preflight


VALID_BODY = """### Contexto
Contexto de prueba.

### Alcance
Validación offline.

### Fuera de alcance
Sin red.

### Criterios de aceptación
- [ ] [AC-01] criterio de prueba.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"test","target":"tests/test_issue_contract_preflight.py::IssueContractPreflightTests::test_valid_body_returns_acceptance_and_task_fingerprints_with_claims"}]} -->

### Rutas reclamadas
- scripts/example.py

<!-- factory-plan-task {"version":1,"epic":699,"task_key":"PREFLIGHT_TEST_V1","order":1,"owner":"pl0n3r","roles":["qa"],"depends_on":[1,2],"paths":["scripts/example.py","tests/example.py"]} -->
"""


class IssueContractPreflightTests(unittest.TestCase):
    def test_valid_body_returns_acceptance_and_task_fingerprints_with_claims(self):
        result = preflight.evaluate_issue_body(VALID_BODY)

        self.assertTrue(result["valid"])
        self.assertEqual(result["version"], 1)
        self.assertRegex(result["acceptance_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["task_marker_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["task_key"], "PREFLIGHT_TEST_V1")
        self.assertEqual(
            result["paths"],
            ["scripts/example.py", "tests/example.py"],
        )
        self.assertEqual(result["depends_on"], [1, 2])
        self.assertEqual(
            result["criteria"],
            [
                {
                    "id": "AC-01",
                    "kind": "test",
                    "target": (
                        "tests/test_issue_contract_preflight.py::"
                        "IssueContractPreflightTests::"
                        "test_valid_body_returns_acceptance_and_task_fingerprints_with_claims"
                    ),
                }
            ],
        )

    def test_invalid_acceptance_headings_or_criteria_fail_before_task_processing(self):
        invalid = VALID_BODY.replace("### Contexto", "### Context")
        with mock.patch.object(preflight, "parse_task_marker") as task_parser:
            with self.assertRaises(preflight.IssueContractPreflightError) as ctx:
                preflight.evaluate_issue_body(invalid)

        self.assertEqual(ctx.exception.code, "acceptance_invalid")
        task_parser.assert_not_called()

    def test_missing_or_invalid_factory_plan_task_fails_closed(self):
        missing = VALID_BODY.split("<!-- factory-plan-task", 1)[0]
        with self.assertRaises(preflight.IssueContractPreflightError) as missing_ctx:
            preflight.evaluate_issue_body(missing)
        self.assertEqual(missing_ctx.exception.code, "task_missing")

        invalid = VALID_BODY.replace(
            '"task_key":"PREFLIGHT_TEST_V1"',
            '"task_key":"lowercase"',
        )
        with self.assertRaises(preflight.IssueContractPreflightError) as invalid_ctx:
            preflight.evaluate_issue_body(invalid)
        self.assertEqual(invalid_ctx.exception.code, "task_invalid")

    def test_cli_is_deterministic_offline_and_never_needs_github_credentials(self):
        first = io.StringIO()
        second = io.StringIO()

        self.assertEqual(
            preflight.main([], stdin=io.StringIO(VALID_BODY), stdout=first),
            0,
        )
        self.assertEqual(
            preflight.main([], stdin=io.StringIO(VALID_BODY), stdout=second),
            0,
        )
        self.assertEqual(first.getvalue(), second.getvalue())
        self.assertTrue(json.loads(first.getvalue())["valid"])

        source = inspect.getsource(preflight)
        for forbidden in (
            "urllib",
            "requests",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "api.github.com",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
