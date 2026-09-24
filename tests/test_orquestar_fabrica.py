import unittest
from datetime import datetime, timezone

from scripts.orquestador_kit import parse_task_marker
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
        if method == "PATCH" and "/issues/" in path:
            number = int(path.rsplit("/", 1)[1])
            self.issues[number].update(payload)
            return self.issues[number]
        raise AssertionError((method, path, payload))


class OrchestratorSyncTests(unittest.TestCase):
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
