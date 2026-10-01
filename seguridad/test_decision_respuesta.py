import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from decision_respuesta import (
    BOT,
    COMPLETED,
    DECISION_LABEL,
    DecisionError,
    gh_api,
    materialize_decision,
)


def gate_body(
    options=("A", "B"),
    context="La decisión requiere autorización explícita antes de cualquier efecto.",
):
    gate = {
        "category": "money",
        "context": context,
        "options": [
            {"id": option, "label": f"Opción {option}"}
            for option in options
        ],
        "recommendation": options[0],
        "safe_default": options[0],
    }
    return (
        "Contexto\n<!-- factory-human-gate "
        + json.dumps(gate, separators=(",", ":"))
        + " -->"
    )


def event(
    command="/decidir B",
    association="OWNER",
    user_type="User",
    issue_body=None,
):
    return {
        "repository": {"full_name": "pl0n3r/Factory"},
        "issue": {
            "number": 519,
            "body": gate_body() if issue_body is None else issue_body,
        },
        "comment": {
            "body": command,
            "author_association": association,
            "user": {"login": "pl0n3r", "type": user_type},
        },
    }


class FakeAPI:
    def __init__(
        self, *, body=None, labels=None, state="open",
        crash_after_evidence_once=False,
        mutate_body_on_issue_get=None,
        replacement_body=None,
        equivalent_open=None,
        equivalent_all=None,
        comments_by_issue=None,
    ):
        self.issue = {
            "number": 519,
            "state": state,
            "body": gate_body() if body is None else body,
            "labels": [
                {"name": name}
                for name in (
                    labels
                    or {
                        "tipo: infraestructura",
                        "prioridad: alta",
                        "estado: bloqueado",
                        "equipo: externo",
                        DECISION_LABEL,
                    }
                )
            ],
        }
        self.comments = []
        self.calls = []
        self.next_id = 1000
        self.crash_after_evidence_once = crash_after_evidence_once
        self.mutate_body_on_issue_get = mutate_body_on_issue_get
        self.replacement_body = replacement_body
        self.issue_gets = 0
        self.equivalent_open = list(equivalent_open or [])
        self.equivalent_all = list(
            equivalent_all
            if equivalent_all is not None
            else self.equivalent_open
        )
        self.comments_by_issue = {
            int(number): list(values)
            for number, values in (comments_by_issue or {}).items()
        }

    def label_names(self):
        return {item["name"] for item in self.issue["labels"]}

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.endswith(
            "/issues?state=all&per_page=100"
        ):
            values = [json.loads(json.dumps(self.issue))]
            values.extend(json.loads(json.dumps(self.equivalent_all)))
            return values
        if method == "GET" and path.endswith("/issues/519"):
            self.issue_gets += 1
            if (
                self.mutate_body_on_issue_get == self.issue_gets
                and self.replacement_body is not None
            ):
                self.issue["body"] = self.replacement_body
            return json.loads(json.dumps(self.issue))
        if method == "GET" and path.endswith("/comments?per_page=100"):
            marker = "/issues/"
            number = int(path.split(marker, 1)[1].split("/", 1)[0])
            if number == 519:
                return json.loads(json.dumps(self.comments))
            return json.loads(json.dumps(
                self.comments_by_issue.get(number, [])
            ))
        if method == "POST" and path.endswith("/comments"):
            self.next_id += 1
            value = {
                "id": self.next_id,
                "body": payload["body"],
                "user": {"login": BOT, "type": "Bot"},
            }
            self.comments.append(value)
            if self.crash_after_evidence_once:
                self.crash_after_evidence_once = False
                raise RuntimeError("simulated crash after evidence")
            return value
        if method == "POST" and path.endswith("/labels"):
            for label in payload["labels"]:
                if label not in self.label_names():
                    self.issue["labels"].append({"name": label})
            return self.issue["labels"]
        if method == "PATCH" and path.endswith("/issues/519"):
            self.issue["state"] = payload["state"]
            self.issue["state_reason"] = payload["state_reason"]
            if "labels" in payload:
                self.issue["labels"] = [
                    {"name": name} for name in payload["labels"]
                ]
            return self.issue
        raise AssertionError(f"Unexpected API call: {method} {path}")


class DecisionRespuestaTests(unittest.TestCase):
    def test_authorized_exact_command_completes_valid_gate(self):
        api = FakeAPI()
        changed = materialize_decision(event(), api, "pl0n3r/Factory")

        self.assertTrue(changed)
        self.assertEqual(api.issue["state"], "closed")
        self.assertEqual(api.issue["state_reason"], "completed")
        self.assertNotIn(DECISION_LABEL, api.label_names())
        self.assertNotIn("estado: bloqueado", api.label_names())
        self.assertIn(COMPLETED, api.label_names())
        self.assertIn("prioridad: alta", api.label_names())
        self.assertIn("tipo: infraestructura", api.label_names())
        self.assertIn("equipo: externo", api.label_names())
        self.assertEqual(len(api.comments), 1)
        self.assertIn('"option":"B"', api.comments[0]["body"])
        self.assertIn("sin ejecutar el efecto", api.comments[0]["body"])

    def test_evidence_v2_binds_gate_fingerprint_and_semantic_drift_fails_closed(self):
        api = FakeAPI()
        self.assertTrue(materialize_decision(event(), api, "pl0n3r/Factory"))
        marker = api.comments[0]["body"].split("-->", 1)[0]
        payload = json.loads(
            marker.removeprefix("<!-- factory-human-decision ").strip()
        )
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["option"], "B")
        self.assertRegex(payload["gate_sha256"], r"^[0-9a-f]{64}$")

        semantic_before_journal = FakeAPI(
            mutate_body_on_issue_get=2,
            replacement_body=gate_body(
                ("A", "B"),
                context="La puerta cambió antes de publicar el journal.",
            ),
        )
        self.assertFalse(
            materialize_decision(
                event(), semantic_before_journal, "pl0n3r/Factory"
            )
        )
        self.assertEqual(semantic_before_journal.issue["state"], "open")
        self.assertIn(DECISION_LABEL, semantic_before_journal.label_names())
        self.assertEqual(semantic_before_journal.comments, [])
        self.assertFalse(any(
            call[0] == "PATCH" for call in semantic_before_journal.calls
        ))

        semantic = FakeAPI(
            mutate_body_on_issue_get=3,
            replacement_body=gate_body(
                ("A", "B"),
                context="La decisión cambió semánticamente pero conserva las letras.",
            ),
        )
        self.assertFalse(
            materialize_decision(event(), semantic, "pl0n3r/Factory")
        )
        self.assertEqual(semantic.issue["state"], "open")
        self.assertIn(DECISION_LABEL, semantic.label_names())
        self.assertEqual(len(semantic.comments), 1)
        self.assertFalse(any(
            call[0] == "PATCH" for call in semantic.calls
        ))


    def test_untrusted_bot_or_free_text_is_noop(self):
        cases = (
            event(association="NONE"),
            event(association="MEMBER"),
            event(association="COLLABORATOR"),
            event(user_type="Bot"),
            event(command="/decidir B "),
            event(command="Decisión del dueño: B"),
            event(command="/decidir b"),
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                api = FakeAPI()
                self.assertFalse(
                    materialize_decision(candidate, api, "pl0n3r/Factory")
                )
                self.assertEqual(api.issue["state"], "open")
                self.assertEqual(api.comments, [])
                self.assertFalse(any(call[0] != "GET" for call in api.calls))

    def test_invalid_option_marker_or_queue_fails_closed(self):
        invalid_marker = '<!-- factory-human-gate {"category":"money" -->'
        cases = (
            (event("/decidir C"), FakeAPI()),
            (event(), FakeAPI(body=invalid_marker)),
            (
                event(),
                FakeAPI(labels={"estado: bloqueado", "prioridad: alta"}),
            ),
        )
        for candidate, api in cases:
            with self.subTest(body=api.issue["body"], labels=api.label_names()):
                before = json.dumps(api.issue, sort_keys=True)
                self.assertFalse(
                    materialize_decision(candidate, api, "pl0n3r/Factory")
                )
                self.assertEqual(json.dumps(api.issue, sort_keys=True), before)
                self.assertEqual(api.comments, [])
                self.assertFalse(any(call[0] != "GET" for call in api.calls))

    def test_retry_is_idempotent(self):
        api = FakeAPI()
        self.assertTrue(materialize_decision(event(), api, "pl0n3r/Factory"))
        self.assertFalse(materialize_decision(event(), api, "pl0n3r/Factory"))

        evidence = [
            item for item in api.comments
            if item["user"]["login"] == BOT
            and item["body"].startswith("<!-- factory-human-decision ")
        ]
        self.assertEqual(len(evidence), 1)
        closes = [
            call for call in api.calls
            if call[0] == "PATCH" and call[1].endswith("/issues/519")
        ]
        self.assertEqual(len(closes), 1)

        old_gate = gate_body()
        current_gate = gate_body(
            context="La puerta cambió después del comentario original."
        )
        delayed = FakeAPI(body=current_gate)
        self.assertFalse(
            materialize_decision(
                event(issue_body=old_gate),
                delayed,
                "pl0n3r/Factory",
            )
        )
        self.assertEqual(delayed.issue["state"], "open")
        self.assertEqual(delayed.comments, [])
        self.assertFalse(any(
            call[0] != "GET" for call in delayed.calls
        ))

        partial = FakeAPI(crash_after_evidence_once=True)
        with self.assertRaisesRegex(
            RuntimeError, "simulated crash after evidence"
        ):
            materialize_decision(event(), partial, "pl0n3r/Factory")

        self.assertEqual(partial.issue["state"], "open")
        self.assertIn(DECISION_LABEL, partial.label_names())
        self.assertIn("estado: bloqueado", partial.label_names())
        self.assertNotIn(COMPLETED, partial.label_names())
        partial_evidence = [
            item for item in partial.comments
            if item["user"]["login"] == BOT
            and item["body"].startswith("<!-- factory-human-decision ")
        ]
        self.assertEqual(len(partial_evidence), 1)

        self.assertTrue(
            materialize_decision(event(), partial, "pl0n3r/Factory")
        )
        self.assertEqual(partial.issue["state"], "closed")
        self.assertEqual(partial.issue["state_reason"], "completed")
        self.assertEqual(
            len([
                item for item in partial.comments
                if item["user"]["login"] == BOT
                and item["body"].startswith("<!-- factory-human-decision ")
            ]),
            1,
        )

        stale = FakeAPI(
            mutate_body_on_issue_get=2,
            replacement_body=gate_body(("A", "C")),
        )
        self.assertFalse(
            materialize_decision(event(), stale, "pl0n3r/Factory")
        )
        self.assertEqual(stale.issue["state"], "open")
        self.assertIn(DECISION_LABEL, stale.label_names())
        self.assertEqual(stale.comments, [])
        self.assertFalse(any(call[0] != "GET" for call in stale.calls))

        stale_final = FakeAPI(
            mutate_body_on_issue_get=4,
            replacement_body=gate_body(("A", "C")),
        )
        self.assertFalse(
            materialize_decision(event(), stale_final, "pl0n3r/Factory")
        )
        self.assertEqual(stale_final.issue["state"], "open")
        self.assertIn(DECISION_LABEL, stale_final.label_names())
        self.assertEqual(len(stale_final.comments), 1)
        self.assertFalse(any(
            call[0] == "PATCH" for call in stale_final.calls
        ))

    def test_legacy_evidence_does_not_resume(self):
        legacy = FakeAPI()
        legacy.comments.append({
            "id": 42,
            "body": '<!-- factory-human-decision {"option":"B","version":1} -->',
            "user": {"login": BOT, "type": "Bot"},
        })
        with self.assertRaises(DecisionError):
            materialize_decision(event(), legacy, "pl0n3r/Factory")
        self.assertEqual(legacy.issue["state"], "open")
        self.assertFalse(any(
            call[0] != "GET" for call in legacy.calls
        ))

    def test_decision_materialization_has_no_parent_side_effects(self):
        api = FakeAPI()
        self.assertTrue(materialize_decision(event(), api, "pl0n3r/Factory"))

        for method, path, payload in api.calls:
            if (
                method == "GET"
                and path.endswith("/issues?state=all&per_page=100")
            ):
                continue
            self.assertIn("/issues/519", path)
            self.assertNotIn("/issues/577", path)
            self.assertNotIn("/issues/384", path)
            if payload is not None:
                text = json.dumps(payload, ensure_ascii=False)
                self.assertNotIn("billing", text)
                self.assertNotIn("go-live", text)
                self.assertNotIn("parent", text)
        self.assertEqual(
            [
                call[2] for call in api.calls
                if call[0] == "PATCH" and call[1].endswith("/issues/519")
            ],
            [{
                "state": "closed",
                "state_reason": "completed",
                "labels": [
                    "equipo: externo",
                    "prioridad: alta",
                    "tipo: infraestructura",
                    COMPLETED,
                ],
            }],
        )

    def test_workflow_contract_is_comment_scoped_and_minimal(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "seguridad.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("issues:\n    types: [opened, edited, reopened]", workflow)
        self.assertIn("issue_comment:\n    types: [created]", workflow)
        self.assertIn("materializar-respuesta:", workflow)
        self.assertIn(
            "if: github.event_name == 'issues' && github.event.issue.state == 'open'",
            workflow,
        )
        section = workflow.split("  materializar-respuesta:", 1)[1]
        self.assertIn("contents: read", section)
        self.assertIn("issues: write", section)
        self.assertIn("github.event.repository.default_branch", section)
        self.assertIn("persist-credentials: false", section)
        self.assertIn("Autorizar evento antes de checkout", section)
        self.assertIn("steps.preflight.outputs.trusted == 'true'", section)
        materializer = section.split("  sincronizar-decision:", 1)[0]
        self.assertIn("OWNER) trusted=true", materializer)
        self.assertNotIn("OWNER|MEMBER|COLLABORATOR) trusted=true", materializer)
        self.assertIn('"$REF_NAME" == "$DEFAULT_BRANCH"', section)
        self.assertLess(
            section.index("Autorizar evento antes de checkout"),
            section.index("actions/checkout@"),
        )
        self.assertIn("seguridad/decision_respuesta.py", section)
        self.assertIn("Reconciliar puerta canónica antes de decidir", materializer)
        self.assertIn("python3 seguridad/sincronizar_puerta.py valid", materializer)
        self.assertIn("steps.gate_sync.outputs.canonical == 'true'", materializer)
        self.assertNotIn("pull_request_target:", workflow)
        self.assertNotIn("secrets:", section)

    def test_workflow_does_not_requeue_closed_issue(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "seguridad.yml"
        ).read_text(encoding="utf-8")
        sync = workflow.split("  sincronizar-decision:", 1)[1]
        self.assertIn(
            "if: github.event_name == 'issues' && github.event.issue.state == 'open'",
            sync,
        )


class DecisionPaginationTests(unittest.TestCase):
    def test_decision_scan_pagination_slurps_every_issue_page(self):
        def fake_run(command, **kwargs):
            self.assertIn("--paginate", command)
            self.assertIn("--slurp", command)
            self.assertIn(
                "repos/pl0n3r/Factory/issues?state=all&per_page=100",
                command,
            )
            return SimpleNamespace(
                stdout='[[{"number":519}],[{"number":520}]]'
            )

        with patch("decision_respuesta.subprocess.run", side_effect=fake_run):
            issues = gh_api(
                "GET",
                "repos/pl0n3r/Factory/issues?state=all&per_page=100",
            )
        self.assertEqual([item["number"] for item in issues], [519, 520])


class DecisionTests(unittest.TestCase):
    def test_decision_rejects_ambiguous_equivalent_open_gates(self):
        duplicate = {
            "number": 520,
            "state": "open",
            "body": gate_body(),
            "labels": [{"name": DECISION_LABEL}],
        }
        api = FakeAPI(equivalent_open=[duplicate])

        self.assertFalse(
            materialize_decision(event(), api, "pl0n3r/Factory")
        )
        self.assertEqual(api.issue["state"], "open")
        self.assertEqual(api.comments, [])
        self.assertFalse(any(
            method != "GET" for method, _, _ in api.calls
        ))

    def test_decision_rejects_historical_equivalent_journal(self):
        historical = {
            "number": 520,
            "state": "closed",
            "body": gate_body(),
            "labels": [{"name": COMPLETED}],
        }
        journal = {
            "id": 77,
            "body": (
                '<!-- factory-human-decision '
                '{"gate_sha256":"'
                + ("a" * 64)
                + '","option":"A","version":2} -->'
            ),
            "user": {"login": BOT, "type": "Bot"},
        }
        api = FakeAPI(
            equivalent_all=[historical],
            comments_by_issue={520: [journal]},
        )

        self.assertFalse(
            materialize_decision(event(), api, "pl0n3r/Factory")
        )
        self.assertEqual(api.issue["state"], "open")
        self.assertEqual(api.comments, [])
        self.assertFalse(any(
            method != "GET" for method, _, _ in api.calls
        ))

        clean = FakeAPI(equivalent_all=[historical])
        self.assertTrue(
            materialize_decision(event(), clean, "pl0n3r/Factory")
        )



if __name__ == "__main__":
    unittest.main()
