import json
import unittest

from scripts.orquestador_kit import PlanError
from scripts.orquestar_fabrica import _existing_tasks


def invalid_marker(epic: int) -> str:
    # JSON válido y epic identificable, pero esquema deliberadamente inválido:
    # falta task_key y sobran campos.
    payload = {
        "version": 1,
        "epic": epic,
        "order": 1,
        "owner": "pl0n3r",
        "roles": ["ingenieria-software"],
        "depends_on": [],
        "paths": ["scripts/example.py"],
        "legacy_key": "OLD",
    }
    return f"<!-- factory-plan-task {json.dumps(payload, separators=(',', ':'))} -->"


class OrchestratorHistoryTests(unittest.TestCase):
    def test_unrelated_closed_invalid_marker_does_not_block_current_epic(self):
        issues = [
            {
                "number": 62,
                "state": "closed",
                "state_reason": "not_planned",
                "body": invalid_marker(99),
            }
        ]
        warnings = []

        result = _existing_tasks(issues, 143, warnings)

        self.assertEqual(result, {})
        self.assertEqual(
            warnings,
            ["Issue #62: marker histórico inválido aislado (épico #99)."],
        )

    def test_invalid_marker_in_current_epic_still_fails_closed(self):
        issues = [
            {
                "number": 63,
                "state": "closed",
                "state_reason": "not_planned",
                "body": invalid_marker(143),
            }
        ]

        with self.assertRaisesRegex(
            PlanError,
            r"Issue #63 tiene marker de tarea inválido",
        ):
            _existing_tasks(issues, 143, [])

    def test_closed_marker_with_duplicate_epic_still_fails_closed(self):
        body = (
            '<!-- factory-plan-task '
            '{"version":1,"epic":99,"epic":143,"legacy_key":"OLD"}'
            ' -->'
        )

        with self.assertRaisesRegex(
            PlanError,
            r"Issue #66 tiene marker de tarea inválido",
        ):
            _existing_tasks(
                [{"number": 66, "state": "closed", "body": body}],
                143,
                [],
            )

    def test_invalid_marker_on_active_task_still_fails_closed(self):
        issues = [
            {
                "number": 64,
                "state": "open",
                "body": invalid_marker(99),
            }
        ]

        with self.assertRaisesRegex(
            PlanError,
            r"Issue #64 tiene marker de tarea inválido",
        ):
            _existing_tasks(issues, 143, [])

    def test_ignored_historical_corruption_is_reported(self):
        body = invalid_marker(77) + "\nSECRET_PAYLOAD_SHOULD_NOT_LEAK"
        warnings = []

        _existing_tasks(
            [{
                "number": 65,
                "state": "closed",
                "state_reason": "completed",
                "body": body,
            }],
            143,
            warnings,
        )

        self.assertEqual(len(warnings), 1)
        self.assertIn("Issue #65", warnings[0])
        self.assertIn("épico #77", warnings[0])
        self.assertNotIn("SECRET_PAYLOAD", warnings[0])


if __name__ == "__main__":
    unittest.main()
