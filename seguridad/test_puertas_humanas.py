import json
import unittest
from pathlib import Path
from urllib.parse import unquote
from unittest.mock import patch
from types import SimpleNamespace

from sincronizar_puerta import (
    BOT, BLOCKED, AVAILABLE, MARKER, OWNED,
    gh_api, sync_invalid, sync_valid,
)

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


class FakeIssueAPI:
    """GitHub falso que aplica POST/DELETE de etiquetas sin reemplazar las demás."""

    def __init__(self, labels=None, comments=None):
        self.labels = set(labels or {"prioridad: alta", "rol: qa", "estado: disponible"})
        self.comments = list(comments or [])
        self.events = []
        self.calls = []
        self.next_id = 1000

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.endswith("/comments?per_page=100"):
            return list(self.comments)
        if method == "GET" and path.endswith("/events?per_page=100"):
            return list(self.events)
        if method == "GET" and path.endswith("/issues/140"):
            return {"labels": [{"name": name} for name in sorted(self.labels)]}
        if method == "POST" and path.endswith("/comments"):
            self.next_id += 1
            self.comments.append({
                "id": self.next_id,
                "body": payload["body"],
                "user": {"login": BOT},
            })
            return self.comments[-1]
        if method == "PATCH" and "/issues/comments/" in path:
            identifier = int(path.rsplit("/", 1)[-1])
            comment = next(item for item in self.comments if item["id"] == identifier)
            comment["body"] = payload["body"]
            return comment
        if method == "POST" and path.endswith("/labels"):
            for label in payload["labels"]:
                self.labels.add(label)
                self.events.append({
                    "event": "labeled",
                    "label": {"name": label},
                    "actor": {"login": BOT},
                })
            return list(self.labels)
        if method == "DELETE" and "/labels/" in path:
            label = unquote(path.rsplit("/", 1)[-1])
            self.labels.remove(label)
            self.events.append({
                "event": "unlabeled",
                "label": {"name": label},
                "actor": {"login": BOT},
            })
            return None
        raise AssertionError(f"Unexpected GitHub API call: {method} {path}")


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

    def test_invalid_gate_reports_safe_error(self):
        bad_risk = simple_gate()
        bad_risk["options"][0]["risk"] = "private"
        risk = classify_body(body(bad_risk), include_reason=True)
        self.assertEqual(risk["status"], "invalid-gate")
        self.assertIn("option.risk", risk["reason"])
        self.assertIn("low, medium o high", risk["reason"])
        self.assertNotIn("private", json.dumps(risk))

        bad_blocks = simple_gate(blocks=["no es texto", "PRIVATE_MARKER_SECRET"])
        blocks = classify_body(body(bad_blocks), include_reason=True)
        self.assertEqual(blocks["status"], "invalid-gate")
        self.assertIn("blocks debe ser texto", blocks["reason"])
        self.assertNotIn("PRIVATE_MARKER_SECRET", json.dumps(blocks))

        malformed = classify_body(
            '<!-- factory-human-gate {"PRIVATE_MARKER_SECRET":',
            include_reason=True,
        )
        self.assertEqual(malformed["status"], "invalid-gate")
        self.assertEqual(malformed["reason"], "Marker de puerta incompleto o malformado.")
        self.assertNotIn("PRIVATE_MARKER_SECRET", json.dumps(malformed))

        api = FakeIssueAPI()
        for _ in range(105):
            api.next_id += 1
            api.comments.append({
                "id": api.next_id, "body": "otro comentario",
                "user": {"login": "otro"},
            })
        sync_invalid(api, "pl0n3r/Factory", 140, blocks["reason"])
        self.assertIn(BLOCKED, api.labels)
        self.assertIn("prioridad: alta", api.labels)
        self.assertIn("rol: qa", api.labels)
        bot_messages = [
            comment for comment in api.comments
            if comment["user"]["login"] == BOT
        ]
        self.assertEqual(len(bot_messages), 1)
        self.assertIn(OWNED, bot_messages[0]["body"])
        self.assertIn("blocks debe ser texto", bot_messages[0]["body"])
        self.assertNotIn("PRIVATE_MARKER_SECRET", bot_messages[0]["body"])
        sync_invalid(api, "pl0n3r/Factory", 140, blocks["reason"])
        self.assertEqual(len(api.comments), 106)
        self.assertEqual(
            len([call for call in api.calls if call[0] == "POST"
                 and call[1].endswith("/labels")]), 1,
        )

        # Una etiqueta de otro escritor entre lectura y restauración sobrevive.
        api.labels.add("equipo: externo")
        sync_valid(api, "pl0n3r/Factory", 140)
        self.assertIn(AVAILABLE, api.labels)
        self.assertNotIn(BLOCKED, api.labels)
        self.assertIn("equipo: externo", api.labels)

        # Ni un aviso propio antiguo permite restaurar un bloqueo manual nuevo.
        api.labels.remove(AVAILABLE)
        api.labels.add(BLOCKED)
        api.events.append({
            "event": "labeled",
            "label": {"name": BLOCKED},
            "actor": {"login": "maintainer"},
        })
        sync_valid(api, "pl0n3r/Factory", 140)
        self.assertIn(BLOCKED, api.labels)
        self.assertNotIn(AVAILABLE, api.labels)

        # Bloqueo preexistente: nunca adquiere propiedad del workflow.
        manual = FakeIssueAPI({"estado: bloqueado", "prioridad: alta"})
        sync_invalid(manual, "pl0n3r/Factory", 140, risk["reason"])
        self.assertNotIn(OWNED, manual.comments[0]["body"])
        sync_valid(manual, "pl0n3r/Factory", 140)
        self.assertIn(BLOCKED, manual.labels)
        self.assertFalse(any(
            call[0] == "DELETE" and "/labels/" in call[1]
            for call in manual.calls
        ))

    def test_invalid_gate_pagination_slurps_every_comment_page(self):
        def fake_run(command, **kwargs):
            self.assertIn("--paginate", command)
            self.assertIn("--slurp", command)
            return SimpleNamespace(stdout='[[{"id":1}],[{"id":2}]]')

        with patch("sincronizar_puerta.subprocess.run", side_effect=fake_run):
            comments = gh_api(
                "GET", "repos/pl0n3r/Factory/issues/140/comments?per_page=100"
            )
        self.assertEqual([item["id"] for item in comments], [1, 2])

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
