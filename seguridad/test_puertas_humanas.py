import json
import unittest
from pathlib import Path
from urllib.parse import unquote
from unittest.mock import patch
from types import SimpleNamespace

from sincronizar_puerta import (
    BOT, BLOCKED, AVAILABLE, MARKER, OWNED,
    GateConflictError, gh_api, reconcile_gate, sync_invalid, sync_valid,
)

from puertas_humanas import (
    GateValidationError,
    MAX_EVENT_CHARS,
    classify_body,
    classify_event_text,
    gate_authority_contract,
    gate_identity,
    gate_identity_from_body,
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


def release_gate_body(
    *,
    version="1.0.16",
    sha="e8ac89801449669436cb3f30e4ccd102898a9d71",
    suffix="candidato validado",
):
    value = gate(
        category="factory-release",
        context=(
            f"Autorizar Factory v{version} exclusivamente para main@{sha}. "
            f"{suffix}"
        ),
    )
    return body(value)


def rich_release_gate_body(
    *,
    version="1.0.17",
    sha="65b649773f53c80880c10f166bdf0928d34f308e",
    publish_label="Publicar Factory 1.0.17",
    publish_effect="Ejecutar el release protegido.",
    hold_label="No publicar todavía",
    hold_effect="Mantener Factory@v1 sin cambios.",
    safe_default="B",
    publish_reversible=True,
    extra_option=False,
):
    options = [
        {
            "id": "A",
            "label": publish_label,
            "effect": publish_effect,
            "pros": ["Publicación controlada"],
            "cons": ["Cambia el canal estable"],
            "risk": "low",
            "cost": "",
            "reversible": publish_reversible,
        },
        {
            "id": "B",
            "label": hold_label,
            "effect": hold_effect,
            "pros": ["No cambia el canal estable"],
            "cons": ["Demora la publicación"],
            "risk": "low",
            "cost": "",
            "reversible": True,
        },
    ]
    if extra_option:
        options.append({
            "id": "C",
            "label": "Publicar en otro canal",
            "effect": "Usar un canal distinto de v1.",
            "pros": ["Aísla el cambio"],
            "cons": ["Amplía la superficie"],
            "risk": "medium",
            "cost": "",
            "reversible": True,
        })
    value = simple_gate(
        category="factory-release",
        context=(
            f"Autorizar Factory v{version} exclusivamente para main@{sha}."
        ),
        options=options,
        recommendation="A",
        safe_default=safe_default,
    )
    return body(value)


class MultiGateAPI:
    def __init__(self, issues, comments=None):
        self.issues = {
            item["number"]: json.loads(json.dumps(item))
            for item in issues
        }
        self.comments = {
            number: json.loads(json.dumps(values))
            for number, values in (comments or {}).items()
        }
        self.calls = []
        self.next_id = 2000

    def open_numbers(self):
        return sorted(
            number for number, issue in self.issues.items()
            if issue.get("state") == "open"
        )

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.endswith(
            "/issues?state=all&per_page=100"
        ):
            return [
                json.loads(json.dumps(self.issues[number]))
                for number in sorted(self.issues)
            ]
        if "/issues/" in path:
            tail = path.split("/issues/", 1)[1]
            raw_number = tail.split("/", 1)[0]
            if raw_number.isdigit():
                number = int(raw_number)
                issue = self.issues[number]
                if method == "GET" and tail == raw_number:
                    return json.loads(json.dumps(issue))
                if method == "GET" and tail.endswith(
                    "/comments?per_page=100"
                ):
                    return json.loads(json.dumps(
                        self.comments.get(number, [])
                    ))
                if method == "GET" and tail.endswith(
                    "/events?per_page=100"
                ):
                    return []
                if method == "POST" and tail.endswith("/comments"):
                    self.next_id += 1
                    value = {
                        "id": self.next_id,
                        "body": payload["body"],
                        "user": {"login": BOT, "type": "Bot"},
                    }
                    self.comments.setdefault(number, []).append(value)
                    return value
                if method == "POST" and tail.endswith("/labels"):
                    names = {
                        item["name"] for item in issue.get("labels", [])
                    }
                    for label in payload["labels"]:
                        if label not in names:
                            issue.setdefault("labels", []).append(
                                {"name": label}
                            )
                    return issue["labels"]
                if method == "DELETE" and "/labels/" in tail:
                    label = unquote(tail.rsplit("/", 1)[-1])
                    issue["labels"] = [
                        item for item in issue.get("labels", [])
                        if item["name"] != label
                    ]
                    return None
                if method == "PATCH" and tail == raw_number:
                    issue.update(payload)
                    return json.loads(json.dumps(issue))
        raise AssertionError(
            f"Unexpected GitHub API call: {method} {path}"
        )


def gate_issue(
    number,
    *,
    state="open",
    body_value=None,
    author_association="OWNER",
):
    return {
        "number": number,
        "state": state,
        "body": body_value or release_gate_body(),
        "author_association": author_association,
        "labels": [
            {"name": "prioridad: crítica"},
            {"name": "estado: requiere decisión"},
            {"name": "decisión: dueño"},
        ],
    }


class GateTests(unittest.TestCase):
    def test_no_marker_is_not_a_human_gate(self):
        self.assertEqual(
            classify_body("Issue técnico ordinario"),
            {"status": "no-gate", "category": None},
        )

    def test_marker_name_in_prose_is_not_gate_intent(self):
        self.assertEqual(
            classify_body(
                "El nombre canónico factory-human-gate puede mencionarse en prosa."
            ),
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

    def test_explain_simple_para_12_anos(self):
        value = simple_gate()
        value["explain_simple"] = (
            "Hay que elegir cómo guardar datos.\n"
            "Si no eliges, seguimos con la opción segura."
        )
        value["options"][0]["explain_simple"] = (
            "Es como guardar la tarea por menos tiempo."
        )
        normalized = validate_gate(value)
        self.assertIn("explain_simple", normalized)
        self.assertIn("explain_simple", normalized["options"][0])

        self.assertNotIn("explain_simple", validate_gate(simple_gate()))

        for bad in ("", "x" * 601, "a\nb\nc\nd\ne"):
            invalid = simple_gate()
            invalid["explain_simple"] = bad
            with self.subTest(root=bad):
                with self.assertRaises(GateValidationError):
                    validate_gate(invalid)

        invalid_option = simple_gate()
        invalid_option["options"][0]["explain_simple"] = "y" * 401
        with self.assertRaises(GateValidationError):
            validate_gate(invalid_option)

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

    def test_gate_scan_pagination_slurps_every_issue_page(self):
        def fake_run(command, **kwargs):
            self.assertIn("--paginate", command)
            self.assertIn("--slurp", command)
            self.assertIn(
                "repos/pl0n3r/Factory/issues?state=all&per_page=100",
                command,
            )
            return SimpleNamespace(
                stdout='[[{"number":575}],[{"number":581}]]'
            )

        with patch("sincronizar_puerta.subprocess.run", side_effect=fake_run):
            issues = gh_api(
                "GET",
                "repos/pl0n3r/Factory/issues?state=all&per_page=100",
            )
        self.assertEqual([item["number"] for item in issues], [575, 581])

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


class GateDedupTests(unittest.TestCase):
    def test_factory_release_authority_ignores_explanatory_copy(self):
        first = rich_release_gate_body(
            publish_label="Publicar Factory 1.0.17",
            publish_effect="Ejecutar el release protegido.",
        )
        equivalent = rich_release_gate_body(
            publish_label="Mover Factory@v1 a 1.0.17",
            publish_effect="Mover v1 y ejecutar el release protegido.",
            hold_label="Conservar 1.0.16",
            hold_effect="Mantener el alias estable en 1.0.16.",
        )

        first_raw = json.loads(
            first.split("<!-- factory-human-gate ", 1)[1].split(" -->", 1)[0]
        )
        equivalent_raw = json.loads(
            equivalent.split("<!-- factory-human-gate ", 1)[1].split(" -->", 1)[0]
        )
        self.assertEqual(
            gate_authority_contract(first_raw),
            gate_authority_contract(equivalent_raw),
        )

        legacy_first = gate(
            category="factory-release",
            context="Release legacy sin target exacto",
            options=[
                {"id": "A", "label": "Publicar", "effect": "Efecto A"},
                {"id": "B", "label": "No publicar", "effect": "Efecto B"},
            ],
            recommendation="A",
            safe_default="B",
        )
        legacy_changed = json.loads(json.dumps(legacy_first))
        legacy_changed["options"][0]["effect"] = "Efecto materialmente distinto"
        self.assertNotEqual(
            gate_authority_contract(legacy_first),
            gate_authority_contract(legacy_changed),
        )

    def test_release_1017_race_converges_without_body_edit(self):
        api = MultiGateAPI([
            gate_issue(
                665,
                body_value=rich_release_gate_body(
                    publish_effect="Ejecutar el release protegido.",
                ),
            ),
            gate_issue(
                666,
                body_value=rich_release_gate_body(
                    publish_label="Mover v1 y publicar",
                    publish_effect="Mover v1 y ejecutar release.",
                ),
            ),
            gate_issue(
                667,
                body_value=rich_release_gate_body(
                    publish_label="Publicar Factory",
                    publish_effect="Actualizar el canal protegido v1.",
                ),
            ),
        ])

        self.assertFalse(reconcile_gate(api, "pl0n3r/Factory", 667))
        self.assertEqual(api.open_numbers(), [665])
        self.assertEqual(api.issues[666]["state_reason"], "duplicate")
        self.assertEqual(api.issues[667]["state_reason"], "duplicate")

    def test_factory_release_target_remains_part_of_identity(self):
        current = rich_release_gate_body()
        other_sha = rich_release_gate_body(
            sha="7ed31389ca9c7fa706edfcb23af68a20a9824e4b",
        )
        other_version = rich_release_gate_body(version="1.0.18")

        api = MultiGateAPI([
            gate_issue(665, body_value=current),
            gate_issue(671, body_value=other_sha),
            gate_issue(672, body_value=other_version),
        ])

        self.assertTrue(reconcile_gate(api, "pl0n3r/Factory", 665))
        self.assertTrue(reconcile_gate(api, "pl0n3r/Factory", 671))
        self.assertTrue(reconcile_gate(api, "pl0n3r/Factory", 672))
        self.assertEqual(api.open_numbers(), [665, 671, 672])

    def test_factory_release_incompatible_machine_contract_fails_closed(self):
        variants = (
            rich_release_gate_body(safe_default="A"),
            rich_release_gate_body(publish_reversible=False),
            rich_release_gate_body(extra_option=True),
        )
        for incompatible in variants:
            with self.subTest(incompatible=incompatible):
                api = MultiGateAPI([
                    gate_issue(665, body_value=rich_release_gate_body()),
                    gate_issue(666, body_value=incompatible),
                ])
                with self.assertRaises(GateConflictError):
                    reconcile_gate(api, "pl0n3r/Factory", 665)
                self.assertEqual(api.open_numbers(), [665, 666])
                self.assertFalse(any(
                    method in {"POST", "PATCH", "DELETE"}
                    for method, _, _ in api.calls
                ))

        decision_a = (
            '<!-- factory-human-decision '
            '{"gate_sha256":"' + ("a" * 64)
            + '","option":"A","version":2} -->'
        )
        decision_b = (
            '<!-- factory-human-decision '
            '{"gate_sha256":"' + ("b" * 64)
            + '","option":"B","version":2} -->'
        )
        contradictory = MultiGateAPI(
            [
                gate_issue(665, body_value=rich_release_gate_body()),
                gate_issue(666, body_value=rich_release_gate_body()),
            ],
            comments={
                665: [{
                    "id": 1,
                    "body": decision_a,
                    "user": {"login": BOT, "type": "Bot"},
                }],
                666: [{
                    "id": 2,
                    "body": decision_b,
                    "user": {"login": BOT, "type": "Bot"},
                }],
            },
        )
        with self.assertRaises(GateConflictError):
            reconcile_gate(contradictory, "pl0n3r/Factory", 665)
        self.assertEqual(contradictory.open_numbers(), [665, 666])
        self.assertFalse(any(
            method in {"POST", "PATCH", "DELETE"}
            for method, _, _ in contradictory.calls
        ))

    def test_non_release_authority_still_uses_effect(self):
        first = simple_gate()
        changed = simple_gate()
        changed["options"][0]["label"] = "Retención mínima"
        changed["options"][0]["effect"] = "El dato se elimina inmediatamente."

        self.assertNotEqual(
            gate_authority_contract(first),
            gate_authority_contract(changed),
        )

    def test_equivalent_factory_release_gates_converge_to_oldest_issue(self):
        api = MultiGateAPI([
            gate_issue(575, body_value=release_gate_body(suffix="primera puerta")),
            gate_issue(578, body_value=release_gate_body(suffix="retry concurrente")),
        ])

        self.assertFalse(reconcile_gate(api, "pl0n3r/Factory", 578))
        self.assertEqual(api.open_numbers(), [575])
        self.assertEqual(api.issues[578]["state_reason"], "duplicate")
        duplicate_labels = {item["name"] for item in api.issues[578]["labels"]}
        self.assertIn("estado: completado", duplicate_labels)
        self.assertNotIn("estado: requiere decisión", duplicate_labels)
        self.assertNotIn("decisión: dueño", duplicate_labels)
        duplicate_comments = api.comments[578]
        self.assertEqual(len(duplicate_comments), 1)
        self.assertIn("canonical=575", duplicate_comments[0]["body"])

    def test_gate_identity_uses_category_and_exact_target(self):
        first = release_gate_body(suffix="texto A")
        equivalent = release_gate_body(suffix="texto B")
        other_sha = release_gate_body(
            sha="7ed31389ca9c7fa706edfcb23af68a20a9824e4b",
            suffix="texto A",
        )
        other_version = release_gate_body(
            version="1.0.17",
            suffix="texto A",
        )

        self.assertEqual(
            gate_identity_from_body(first),
            gate_identity_from_body(equivalent),
        )
        self.assertNotEqual(
            gate_identity_from_body(first),
            gate_identity_from_body(other_sha),
        )
        self.assertNotEqual(
            gate_identity_from_body(first),
            gate_identity_from_body(other_version),
        )
        legal = gate(category="legal", context="Mismo target textual")
        money = gate(category="money", context="Mismo target textual")
        self.assertNotEqual(gate_identity(legal), gate_identity(money))

    def test_concurrent_gate_sync_exposes_only_canonical_issue(self):
        api = MultiGateAPI([
            gate_issue(575, body_value=release_gate_body(suffix="sesión 1")),
            gate_issue(581, body_value=release_gate_body(suffix="sesión 2")),
        ])

        self.assertTrue(reconcile_gate(api, "pl0n3r/Factory", 575))
        self.assertFalse(reconcile_gate(api, "pl0n3r/Factory", 581))
        self.assertEqual(api.open_numbers(), [575])
        self.assertIn(
            "decisión: dueño",
            {item["name"] for item in api.issues[575]["labels"]},
        )
        self.assertNotIn(
            "decisión: dueño",
            {item["name"] for item in api.issues[581]["labels"]},
        )

    def test_historical_duplicates_reconcile_and_conflicts_fail_closed(self):
        historical = MultiGateAPI([
            gate_issue(575),
            gate_issue(578, state="closed"),
            gate_issue(581, body_value=release_gate_body(suffix="nuevo retry")),
        ])
        self.assertTrue(reconcile_gate(historical, "pl0n3r/Factory", 575))
        self.assertEqual(historical.open_numbers(), [575])

        decision = (
            '<!-- factory-human-decision '
            '{"gate_sha256":"'
            + ("a" * 64)
            + '","option":"A","version":2} -->'
        )
        conflict = MultiGateAPI(
            [
                gate_issue(575),
                gate_issue(581, body_value=release_gate_body(suffix="retry")),
            ],
            comments={
                581: [{
                    "id": 9,
                    "body": decision,
                    "user": {"login": BOT, "type": "Bot"},
                }],
            },
        )
        with self.assertRaises(GateConflictError):
            reconcile_gate(conflict, "pl0n3r/Factory", 575)
        self.assertEqual(conflict.open_numbers(), [575, 581])
        self.assertFalse(any(
            method in {"POST", "PATCH", "DELETE"}
            for method, _, _ in conflict.calls
        ))

        historical_conflict = MultiGateAPI(
            [
                gate_issue(575),
                gate_issue(
                    578,
                    state="closed",
                    body_value=release_gate_body(suffix="duplicada histórica"),
                ),
            ],
            comments={
                578: [{
                    "id": 10,
                    "body": decision,
                    "user": {"login": BOT, "type": "Bot"},
                }],
            },
        )
        with self.assertRaises(GateConflictError):
            reconcile_gate(historical_conflict, "pl0n3r/Factory", 575)
        self.assertEqual(historical_conflict.open_numbers(), [575])
        self.assertFalse(any(
            method in {"POST", "PATCH", "DELETE"}
            for method, _, _ in historical_conflict.calls
        ))

    def test_release_gate_race_regression_is_deterministic(self):
        api = MultiGateAPI([
            gate_issue(575, body_value=release_gate_body(suffix="original")),
            gate_issue(576, body_value=release_gate_body(suffix="race uno")),
            gate_issue(577, body_value=release_gate_body(suffix="race dos")),
            gate_issue(578, body_value=release_gate_body(suffix="retry uno")),
            gate_issue(581, body_value=release_gate_body(suffix="retry dos")),
        ])

        for number in (581, 577, 575, 578, 576):
            reconcile_gate(api, "pl0n3r/Factory", number)

        self.assertEqual(api.open_numbers(), [575])
        self.assertTrue(all(
            api.issues[number].get("state_reason") == "duplicate"
            for number in (576, 577, 578, 581)
        ))

    def test_reconciliation_keeps_lowest_issue_number(self):
        api = MultiGateAPI([
            gate_issue(581),
            gate_issue(578, body_value=release_gate_body(suffix="medio")),
            gate_issue(575, body_value=release_gate_body(suffix="más antiguo")),
        ])

        self.assertTrue(reconcile_gate(api, "pl0n3r/Factory", 575))
        self.assertEqual(api.open_numbers(), [575])



if __name__ == "__main__":
    unittest.main()
