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


def simple_gate(**changes):
    value = gate(
        title_simple="¿Qué retención usamos?",
        summary_simple=(
            "Debemos definir cuánto tiempo conservamos este dato.\n"
            "La opción corta reduce exposición y costo."
        ),
        options=[
            {
                "id": "A",
                "label": "Retención corta",
                "effect": "El dato se elimina antes.",
                "pros": ["Menor exposición", "Menor costo"],
                "cons": ["Menos historial"],
                "risk": "low",
                "cost": "",
                "reversible": True,
            },
            {
                "id": "B",
                "label": "Retención larga",
                "effect": "El dato se conserva por más tiempo.",
                "pros": ["Más historial"],
                "cons": ["Mayor exposición"],
                "risk": "medium",
                "cost": "$",
                "reversible": True,
            },
        ],
        why_recommended="A reduce exposición y mantiene el objetivo operativo.",
        blocks="Bloquea el paso a live del tratamiento.",
    )
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

    def test_factory_release_category_is_allowed(self):
        self.assertEqual(
            classify_body(body(gate(category="factory-release"))),
            {"status": "gate", "category": "factory-release"},
        )

    def test_optional_simple_gate_fields(self):
        legacy = validate_gate(gate())
        enriched = validate_gate(simple_gate())

        self.assertNotIn("title_simple", legacy)
        self.assertEqual(enriched["title_simple"], "¿Qué retención usamos?")
        self.assertEqual(enriched["options"][0]["risk"], "low")
        self.assertEqual(enriched["options"][0]["cost"], "")
        self.assertTrue(enriched["options"][0]["reversible"])
        self.assertEqual(
            classify_body(body(gate())),
            {"status": "gate", "category": "legal"},
        )
        self.assertEqual(
            classify_body(body(simple_gate())),
            {"status": "gate", "category": "legal"},
        )

    def test_invalid_simple_gate_fields(self):
        invalid = []

        too_many_pros = simple_gate()
        too_many_pros["options"][0]["pros"] = [f"p{i}" for i in range(6)]
        invalid.append(too_many_pros)

        bad_risk = simple_gate()
        bad_risk["options"][0]["risk"] = "critical"
        invalid.append(bad_risk)

        bad_reversible = simple_gate()
        bad_reversible["options"][0]["reversible"] = "yes"
        invalid.append(bad_reversible)

        bad_summary = simple_gate(summary_simple="uno\ndos\ntres\ncuatro")
        invalid.append(bad_summary)

        unknown_root = simple_gate()
        unknown_root["secret_payload"] = "NO_ECHO_THIS"
        invalid.append(unknown_root)

        unknown_option = simple_gate()
        unknown_option["options"][0]["secret_payload"] = "NO_ECHO_THIS"
        invalid.append(unknown_option)

        for value in invalid:
            with self.subTest(value=value):
                result = classify_body(body(value))
                self.assertEqual(
                    result,
                    {"status": "invalid-gate", "category": None},
                )
                self.assertNotIn("NO_ECHO_THIS", json.dumps(result))

        with self.assertRaises(GateValidationError) as raised:
            validate_gate(unknown_root)
        self.assertNotIn("NO_ECHO_THIS", str(raised.exception))

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
        with self.assertRaisesRegex(GateValidationError, "campos simples"):
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
                "issue": {"body": body(simple_gate(category="money"))},
                "payload": "ignored",
            }
        )
        result = classify_event_text(payload)
        self.assertEqual(
            result,
            {"status": "gate", "category": "money"},
        )
        self.assertNotIn("summary_simple", result)

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
