import json
import unittest
from pathlib import Path

from puertas_humanas import (
    GateValidationError,
    MAX_EVENT_CHARS,
    classify_body,
    classify_event_text,
    validate_gate,
)


def gate(**changes):
    value = {
        "category": "legal",
        "context": "Se requiere elegir la política de retención antes de operación real.",
        "options": [
            {"id": "A", "label": "Retención corta"},
            {"id": "B", "label": "Retención larga"},
        ],
        "recommendation": "A",
        "safe_default": "A",
    }
    value.update(changes)
    return value


def body(value):
    return (
        "Contexto\n<!-- factory-human-gate "
        + json.dumps(value, separators=(",", ":"))
        + " -->"
    )


class GateTests(unittest.TestCase):
    def test_no_marker_is_not_a_human_gate(self):
        self.assertEqual(
            classify_body("Issue técnico ordinario"),
            {"status": "no-gate", "category": None},
        )

    def test_allowed_gate_is_classified(self):
        self.assertEqual(
            classify_body(body(gate())),
            {"status": "gate", "category": "legal"},
        )

    def test_unknown_category_is_invalid_gate(self):
        self.assertEqual(
            classify_body(body(gate(category="architecture"))),
            {"status": "invalid-gate", "category": None},
        )
        with self.assertRaisesRegex(GateValidationError, "lista cerrada"):
            validate_gate(gate(category="architecture"))

    def test_options_and_recommendation_are_validated(self):
        with self.assertRaisesRegex(GateValidationError, "option existente"):
            validate_gate(gate(recommendation="C"))
        with self.assertRaisesRegex(GateValidationError, "único"):
            validate_gate(
                gate(
                    options=[
                        {"id": "A", "label": "Uno"},
                        {"id": "A", "label": "Dos"},
                    ]
                )
            )

    def test_extra_fields_and_multiline_context_are_rejected(self):
        extra = gate()
        extra["unexpected_field"] = "x"
        with self.assertRaisesRegex(GateValidationError, "exactamente"):
            validate_gate(extra)
        with self.assertRaisesRegex(GateValidationError, "una línea"):
            validate_gate(gate(context="uno\ndos"))

    def test_malformed_marker_is_invalid_not_no_gate(self):
        self.assertEqual(
            classify_body('<!-- factory-human-gate {"category":"legal" -->'),
            {"status": "invalid-gate", "category": None},
        )
        self.assertEqual(
            classify_body("<!-- factory-human-gate ??? -->"),
            {"status": "invalid-gate", "category": None},
        )

    def test_multiple_markers_are_invalid_gate(self):
        value = body(gate())
        self.assertEqual(
            classify_body(value + "\n" + value),
            {"status": "invalid-gate", "category": None},
        )

    def test_event_classifier_reads_issue_only(self):
        payload = json.dumps(
            {
                "issue": {"body": body(gate(category="money"))},
                "payload": "ignored",
            }
        )
        self.assertEqual(classify_event_text(payload)["category"], "money")

    def test_oversized_event_is_invalid_gate_without_echo(self):
        self.assertEqual(
            classify_event_text("x" * (MAX_EVENT_CHARS + 1)),
            {"status": "invalid-gate", "category": None},
        )

    def test_workflow_rejects_untrusted_issue_authors_and_cleans_stale_queue(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "seguridad.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("AUTHOR_ASSOCIATION:", workflow)
        self.assertIn("OWNER|MEMBER|COLLABORATOR", workflow)
        self.assertIn("steps.actor.outputs.trusted == 'true'", workflow)
        self.assertIn("steps.gate.outputs.status == 'gate'", workflow)
        self.assertIn("steps.gate.outputs.status != 'gate'", workflow)
        self.assertIn("issues/$ISSUE/assignees", workflow)


if __name__ == "__main__":
    unittest.main()
