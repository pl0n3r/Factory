import unittest
from datetime import datetime, timezone

from scripts.orquestador_kit import PlanError, parse_task_marker
from scripts.orquestar_fabrica import sync_plan


class FakeGitHub:
    repo = "pl0n3r/factory"

    def __init__(self):
        now = datetime.now(timezone.utc).isoformat()
        self.issues = {
            3: {
                "number": 3,
                "state": "open",
                "title": "Epic",
                "body": (
                    '<!-- factory-plan {"version":1,"tasks":['
                    '{"key":"A","title":"Crear script","owner":"pl0n3r",'
                    '"paths":["scripts/a.py"],"depends_on":[]},'
                    '{"key":"B","title":"Documentar","owner":"pl0n3r",'
                    '"paths":["docs/b.md"],"depends_on":["A"]}'
                    ']} -->'
                ),
                "labels": [
                    {"name": "tipo: infraestructura"},
                    {"name": "prioridad: crítica"},
                ],
                "created_at": now,
            }
        }
        self.next_issue = 10
        self.comments = []
        self.labels = set()
        self.requests = []

    def issue(self, number):
        return self.issues[number]

    def paginate(self, path):
        if "/issues?state=all" in path:
            return list(self.issues.values())
        return []

    def issue_comments(self, issue_number):
        return list(self.comments)

    def ensure_label(self, name, color, description):
        self.labels.add(name)

    def try_assign(self, issue_number, login):
        self.issues[issue_number]["assignees"] = [{"login": login}]

    def remove_label(self, issue_number, label):
        self.issues[issue_number]["labels"] = [
            item
            for item in self.issues[issue_number].get("labels", [])
            if item["name"] != label
        ]

    def add_labels(self, issue_number, labels):
        current = {
            item["name"]
            for item in self.issues[issue_number].get("labels", [])
        }
        current.update(labels)
        self.issues[issue_number]["labels"] = [
            {"name": name} for name in sorted(current)
        ]

    def comment(self, issue_number, body):
        self.comments.append({
            "id": len(self.comments) + 1,
            "body": body,
            "user": {"login": "github-actions[bot]"},
        })

    def request(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        if method == "POST" and path.endswith("/issues"):
            number = self.next_issue
            self.next_issue += 1
            issue = {
                "number": number,
                "state": "open",
                "title": payload["title"],
                "body": payload["body"],
                "labels": [{"name": name} for name in payload["labels"]],
                "assignees": [{"login": name} for name in payload["assignees"]],
            }
            self.issues[number] = issue
            return issue
        if method == "PATCH" and "/issues/comments/" in path:
            comment_id = int(path.rsplit("/", 1)[1])
            for comment in self.comments:
                if comment["id"] == comment_id:
                    comment["body"] = payload["body"]
                    return comment
        if method == "POST" and path.endswith("/assignees"):
            number = int(path.split("/issues/", 1)[1].split("/", 1)[0])
            self.issues[number]["assignees"] = [
                {"login": name} for name in payload["assignees"]
            ]
            return self.issues[number]
        if method == "PATCH" and "/issues/" in path:
            number = int(path.rsplit("/", 1)[1])
            self.issues[number].update(payload)
            return self.issues[number]
        raise AssertionError((method, path, payload))


class OrquestarFabricaTests(unittest.TestCase):
    def test_sync_materializes_dag_and_is_idempotent(self):
        api = FakeGitHub()
        first = sync_plan(api, 3)
        self.assertEqual(first["order"], ["A", "B"])
        self.assertEqual(first["tasks"], 2)
        self.assertEqual(len(api.issues), 3)
        issue_a = api.issues[first["issues"]["A"]]
        issue_b = api.issues[first["issues"]["B"]]
        marker_a = parse_task_marker(issue_a["body"])
        marker_b = parse_task_marker(issue_b["body"])
        self.assertEqual(marker_a["depends_on"], [])
        self.assertEqual(marker_b["depends_on"], [issue_a["number"]])
        self.assertIn(
            "rol: ingenieria-software",
            {item["name"] for item in issue_a["labels"]},
        )
        self.assertEqual(len(api.comments), 1)

        second = sync_plan(api, 3)
        self.assertEqual(second["issues"], first["issues"])
        self.assertEqual(len(api.issues), 3)
        self.assertEqual(len(api.comments), 1)

    @staticmethod
    def _acceptance_enrichment():
        return (
            "\n\n### Contexto\n\nContexto enriquecido.\n\n"
            "### Alcance\n\nAlcance enriquecido.\n\n"
            "### Fuera de alcance\n\nFuera de alcance enriquecido.\n\n"
            "### Criterios de aceptación\n\n"
            "- [ ] [AC-01] Conservar contrato.\n\n"
            "### Contrato ejecutable\n\n"
            '<!-- factory-acceptance {"version":1,"criteria":['
            '{"id":"AC-01","kind":"test","target":'
            '"tests/test_orquestar_fabrica.py::OrquestarFabricaTests::'
            'test_resync_preserves_enriched_acceptance_contract"}]} -->'
        )

    def test_resync_preserves_enriched_acceptance_contract(self):
        api = FakeGitHub()
        first = sync_plan(api, 3)
        issue = api.issues[first["issues"]["A"]]
        enrichment = self._acceptance_enrichment()
        issue["body"] += enrichment
        before = issue["body"]

        sync_plan(api, 3)

        after = api.issues[issue["number"]]["body"]
        self.assertTrue(after.endswith(enrichment))
        self.assertIn("### Contexto", after)
        self.assertIn("### Alcance", after)
        self.assertIn("### Fuera de alcance", after)
        self.assertEqual(after.count("<!-- factory-acceptance "), 1)
        self.assertEqual(before, after)

    def test_resync_updates_plan_marker_without_duplicating_acceptance(self):
        api = FakeGitHub()
        first = sync_plan(api, 3)
        issue = api.issues[first["issues"]["B"]]
        enrichment = self._acceptance_enrichment()
        issue["body"] += enrichment

        api.issues[3]["body"] = api.issues[3]["body"].replace(
            '"paths":["docs/b.md"]',
            '"paths":["docs/b.md","docs/b-extra.md"]',
        )
        sync_plan(api, 3)

        after = api.issues[issue["number"]]["body"]
        parsed = parse_task_marker(after)
        self.assertEqual(parsed["paths"], ["docs/b.md", "docs/b-extra.md"])
        self.assertEqual(after.count("<!-- factory-plan-task "), 1)
        self.assertEqual(after.count("<!-- factory-acceptance "), 1)
        self.assertTrue(after.endswith(enrichment))

    def test_resync_is_body_idempotent(self):
        api = FakeGitHub()
        first = sync_plan(api, 3)
        issue = api.issues[first["issues"]["A"]]
        issue["body"] += self._acceptance_enrichment()

        sync_plan(api, 3)
        once = api.issues[issue["number"]]["body"]
        sync_plan(api, 3)
        twice = api.issues[issue["number"]]["body"]

        self.assertEqual(once, twice)

    def test_ambiguous_enrichment_fails_closed(self):
        with self.subTest("canonical block edited"):
            api = FakeGitHub()
            first = sync_plan(api, 3)
            issue = api.issues[first["issues"]["A"]]
            issue["body"] = issue["body"].replace(
                "Owner: @pl0n3r",
                "Owner: @intruso",
            )
            before = issue["body"]
            api.requests.clear()

            with self.assertRaisesRegex(PlanError, "Body enriquecido ambiguo"):
                sync_plan(api, 3)

            self.assertFalse(any(
                call[0] == "PATCH" and "/issues/" in call[1]
                for call in api.requests
            ))
            self.assertEqual(api.issues[issue["number"]]["body"], before)

        with self.subTest("malformed second task marker"):
            api = FakeGitHub()
            first = sync_plan(api, 3)
            issue = api.issues[first["issues"]["A"]]
            issue["body"] += "\n\n<!-- factory-plan-task-->"
            before = issue["body"]
            api.requests.clear()

            with self.assertRaisesRegex(
                PlanError,
                "factory-plan-task adicional o malformado",
            ):
                sync_plan(api, 3)

            self.assertFalse(any(
                call[0] == "PATCH" and "/issues/" in call[1]
                for call in api.requests
            ))
            self.assertEqual(api.issues[issue["number"]]["body"], before)

        with self.subTest("malformed acceptance type"):
            api = FakeGitHub()
            first = sync_plan(api, 3)
            issue = api.issues[first["issues"]["A"]]
            issue["body"] += self._acceptance_enrichment().replace(
                '"kind":"test"',
                '"kind":[]',
            )
            before = issue["body"]
            api.requests.clear()

            with self.assertRaisesRegex(
                PlanError,
                "Contrato de aceptación enriquecido inválido",
            ):
                sync_plan(api, 3)

            self.assertFalse(any(
                call[0] == "PATCH" and "/issues/" in call[1]
                for call in api.requests
            ))
            self.assertEqual(api.issues[issue["number"]]["body"], before)

        with self.subTest("later task ambiguity is atomic"):
            api = FakeGitHub()
            first = sync_plan(api, 3)
            issue_a = api.issues[first["issues"]["A"]]
            issue_b = api.issues[first["issues"]["B"]]
            before_a = issue_a["body"]
            before_b = issue_b["body"].replace(
                "Owner: @pl0n3r",
                "Owner: @intruso",
            )
            issue_b["body"] = before_b
            api.requests.clear()

            with self.assertRaisesRegex(PlanError, "Body enriquecido ambiguo"):
                sync_plan(api, 3)

            self.assertFalse(any(
                call[0] == "PATCH" and "/issues/" in call[1]
                for call in api.requests
            ))
            self.assertEqual(issue_a["body"], before_a)
            self.assertEqual(issue_b["body"], before_b)

    def test_epic_requires_exactly_one_type_and_priority(self):
        api = FakeGitHub()
        api.issues[3]["labels"] = [{"name": "tipo: infraestructura"}]
        with self.assertRaisesRegex(Exception, "tipo y una prioridad"):
            sync_plan(api, 3)

    def test_removed_materialized_task_fails_closed(self):
        api = FakeGitHub()
        sync_plan(api, 3)
        api.issues[3]["body"] = (
            '<!-- factory-plan {"version":1,"tasks":['
            '{"key":"A","title":"Crear script","owner":"pl0n3r",'
            '"paths":["scripts/a.py"],"depends_on":[]}'
            ']} -->'
        )
        with self.assertRaisesRegex(Exception, "No se eliminan"):
            sync_plan(api, 3)


if __name__ == "__main__":
    unittest.main()
