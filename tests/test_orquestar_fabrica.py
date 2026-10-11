import json
import unittest
from datetime import datetime, timezone

from scripts.orquestador_kit import PlanError, parse_task_marker
from scripts.coordinar_trabajo import reservation_marker
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
        self.branches = set()
        self.pulls = []
        self.fail_comment_page_two = False
        self.fail_pull_page_two = False
        self.short_pull_pages = False
        self.fail_issue_page_two = False
        self.omit_issue_from_inventory = None
        self.omit_issue_only_ascending = None
        self.foreign_counter_override = None
        self.foreign_counter_race = False
        self.foreign_read_count = 0

    def branch_sha(self, branch):
        return "a" * 40 if branch in self.branches else None

    def issue(self, number):
        if number != 44:
            return self.issues[number]
        self.foreign_read_count += 1
        result = dict(self.issues[number])
        count = len(self.comments)
        if self.foreign_counter_override is not None:
            count = self.foreign_counter_override
        if self.foreign_counter_race and self.foreign_read_count >= 2:
            count += 1
        result["comments"] = count
        return result

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
        if (
            method == "GET" and "/issues?state=all&sort=created&direction=" in path
            and "&per_page=100&page=" in path
        ):
            page = int(path.rsplit("page=", 1)[1])
            if page == 2 and self.fail_issue_page_two:
                return {"message": "partial issue inventory"}
            reverse = "direction=desc" in path
            issues = sorted(
                self.issues.values(), key=lambda item: item["number"],
                reverse=reverse,
            )
            omitted = self.omit_issue_from_inventory
            if omitted is None and not reverse:
                omitted = self.omit_issue_only_ascending
            if omitted is not None:
                issues = [item for item in issues if item["number"] != omitted]
            return [
                {**item, "id": item.get("id", item["number"])}
                for item in issues[(page - 1) * 100:page * 100]
            ]
        if method == "GET" and "/comments?per_page=100&page=" in path:
            page = int(path.rsplit("page=", 1)[1])
            if page == 2 and self.fail_comment_page_two:
                return {"message": "partial collection"}
            return self.comments[(page - 1) * 100:page * 100]
        if method == "GET" and "/pulls?state=open&per_page=100&page=" in path:
            page = int(path.rsplit("page=", 1)[1])
            if page == 2 and self.fail_pull_page_two:
                return {"message": "partial collection"}
            if self.short_pull_pages:
                return self.pulls[page - 1:page]
            return self.pulls[(page - 1) * 100:page * 100]
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

        with self.subTest("duplicate canonical task marker is atomic"):
            api = FakeGitHub()
            first = sync_plan(api, 3)
            issue = api.issues[first["issues"]["A"]]
            marker = parse_task_marker(issue["body"])
            self.assertIsNotNone(marker)
            start = issue["body"].find("<!-- factory-plan-task ")
            end = issue["body"].find(" -->", start) + len(" -->")
            canonical_marker = issue["body"][start:end]
            issue["body"] += "\n\n" + canonical_marker
            before = issue["body"]
            api.requests.clear()

            with self.assertRaisesRegex(
                PlanError,
                "marker de tarea inválido",
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


    def test_sync_plan_materializes_condor_datos_yml_with_derived_claims(self):
        api = FakeGitHub()
        api.repo = "pl0n3r/Condor"
        api.issues[3]["body"] = (
            '<!-- factory-plan {"version":1,"tasks":['
            '{"key":"PRIVACY","title":"Actualizar datos","owner":"pl0n3r",'
            '"paths":["datos.yml"],"depends_on":[]}'
            ']} -->'
        )

        result = sync_plan(api, 3)
        issue = api.issues[result["issues"]["PRIVACY"]]
        marker = parse_task_marker(issue["body"])

        self.assertIsNotNone(marker)
        assert marker is not None
        self.assertIn("datos.yml", marker["paths"])
        self.assertIn(
            "tests/php/Privacy/PrivacyAsCodeTest.php",
            marker["paths"],
        )
        self.assertIn(
            "docs/privacidad/politica-tratamiento.md",
            marker["paths"],
        )
        self.assertNotIn("config/version.php", marker["paths"])

    def test_active_task_does_not_silently_expand_derived_claims(self):
        api = FakeGitHub()
        api.issues[3]["body"] = (
            '<!-- factory-plan {"version":1,"tasks":['
            '{"key":"PRIVACY","title":"Actualizar datos","owner":"pl0n3r",'
            '"paths":["datos.yml"],"depends_on":[]}'
            ']} -->'
        )
        first = sync_plan(api, 3)
        issue = api.issues[first["issues"]["PRIVACY"]]
        before = issue["body"]
        issue["labels"] = [{"name": "estado: reservado"}]
        api.repo = "pl0n3r/Condor"
        api.requests.clear()

        with self.assertRaisesRegex(PlanError, "activo; su plan no puede mutar"):
            sync_plan(api, 3)

        self.assertEqual(issue["body"], before)
        self.assertFalse(
            any(
                method == "PATCH" and "/issues/" in path
                for method, path, _payload in api.requests
            )
        )

    @staticmethod
    def _legacy_foreign_marker(epic=999):
        marker = json.dumps({
            "version": 1,
            "epic": epic,
            "task_key": "LEGACY_TASK_KEY_TOO_LONG_FOR_CURRENT_CONTRACT",
            "order": 1,
            "owner": "pl0n3r",
            "roles": ["qa"],
            "depends_on": [],
            "paths": ["tests/old-task.py"],
        }, sort_keys=True, separators=(",", ":"))
        return f"<!-- factory-plan-task {marker} -->"

    def _inject_foreign(self, api, body=None, labels=()):
        api.issues[44] = {
            "number": 44,
            "state": "open",
            "title": "Foreign legacy task",
            "updated_at": "2026-10-11T07:00:00Z",
            "body": body if body is not None else self._legacy_foreign_marker(),
            "labels": [{"name": name} for name in labels],
        }
        return api.issues[44]

    def test_partial_issue_page_fails_closed_without_children(self):
        api = FakeGitHub()
        first = sync_plan(api, 3)
        missing = first["issues"]["B"]
        # [99, []] parece normal en ambos barridos, pero el reporte conoce B.
        for number in range(100, 197):
            api.issues[number] = {
                "number": number, "state": "open", "body": "",
                "labels": [], "title": f"Unrelated {number}",
            }
        api.omit_issue_from_inventory = missing
        before = {key: dict(value) for key, value in api.issues.items()}
        api.requests.clear()

        with self.assertRaisesRegex(PlanError, "reporte anterior"):
            sync_plan(api, 3)

        self.assertFalse(api.requests)
        self.assertEqual(api.issues, before)
        self.assertIn(missing, api.issues)

    def test_valid_paginated_inventory_remains_idempotent(self):
        api = FakeGitHub()
        for number in range(4, 103):
            api.issues[number] = {
                "number": number, "state": "open", "body": "",
                "labels": [], "title": f"Unrelated {number}",
            }
        api.next_issue = 103
        first = sync_plan(api, 3)
        self.assertEqual(first["issues"]["B"], 104)
        self.assertEqual(len(api.issues), 102)

        second = sync_plan(api, 3)
        third = sync_plan(api, 3)
        self.assertEqual(second["issues"], first["issues"])
        self.assertEqual(third["issues"], first["issues"])
        self.assertEqual(len(api.issues), 102)
        self.assertEqual(len(api.comments), 1)

    def test_ambiguous_issue_inventory_is_atomic(self):
        for defect in (
            "duplicate_number", "missing_one_direction", "page_two",
            "truncated_report_comments", "missing_report",
        ):
            with self.subTest(defect=defect):
                api = FakeGitHub()
                if defect == "duplicate_number":
                    api.issues[44] = {
                        "id": 44, "number": 3, "state": "open",
                        "body": "", "labels": [], "title": "Duplicate",
                    }
                elif defect == "missing_one_direction":
                    api.issues[44] = {
                        "number": 44, "state": "open", "body": "",
                        "labels": [], "title": "Omitted",
                    }
                    api.omit_issue_only_ascending = 44
                else:
                    for number in range(100, 199):
                        api.issues[number] = {
                            "number": number, "state": "open", "body": "",
                            "labels": [], "title": f"Unrelated {number}",
                        }
                    api.fail_issue_page_two = True
                if defect in ("truncated_report_comments", "missing_report"):
                    sync_plan(api, 3)
                    if defect == "truncated_report_comments":
                        api.comments.extend({
                            "id": number, "user": {"login": "someone"},
                            "body": "noise",
                        } for number in range(2, 102))
                        api.fail_comment_page_two = True
                    else:
                        api.comments.clear()
                    api.requests.clear()
                next_issue = api.next_issue
                with self.assertRaises(PlanError):
                    sync_plan(api, 3)
                self.assertFalse(api.requests)
                self.assertEqual(api.next_issue, next_issue)

    def test_global_issue_inventory_must_be_complete_and_unambiguous(self):
        api = FakeGitHub()
        for number in range(100, 199):
            api.issues[number] = {"number": number, "state": "open", "body": "",
                                  "labels": [], "title": f"Unrelated {number}"}
        api.fail_issue_page_two = True
        with self.assertRaisesRegex(PlanError, "Colección de autoridad incompleta"):
            sync_plan(api, 3)
        self.assertFalse(api.requests, "no mutations before inventory proof")
        self.assertEqual(len(api.issues), 100)
        for bad_id in (3, 0, True, "untrusted"):
            with self.subTest(bad_id=bad_id):
                api = FakeGitHub()
                api.issues[44] = {"id": bad_id, "number": 44, "state": "open",
                                  "body": "", "labels": [], "title": "Unrelated"}
                with self.assertRaises(PlanError):
                    sync_plan(api, 3)
                self.assertFalse(api.requests)

    def test_foreign_unreserved_invalid_marker_is_isolated(self):
        api = FakeGitHub()
        foreign = self._inject_foreign(api, labels=["estado: bloqueado"])
        before = dict(foreign)
        result = sync_plan(api, 3)
        self.assertEqual(result["tasks"], 2)
        self.assertEqual(set(result["issues"]), {"A", "B"})
        self.assertEqual(foreign, before, "foreign issue must not be rewritten")
        self.assertTrue(any("#44" in w and "#999" in w for w in result["warnings"]))
        self.assertEqual(len(api.issues), 4)
        self.assertFalse(any(
            method == "PATCH" and path.endswith("/issues/44")
            for method, path, _ in api.requests
        ))

    def test_target_or_ambiguous_invalid_marker_remains_blocking(self):
        original = self._legacy_foreign_marker()
        ambiguous = [
            self._legacy_foreign_marker(epic=3),
            original.replace('"epic":999', '"epic":999,"epic":999'),
            original.replace('"version":1', '"version":1,"version":1'),
            original + "\n" + original,
            original.replace('"epic":999,', ''),
            original + "\n<!-- factory-plan-task-->",
        ]
        for body in ambiguous:
            with self.subTest(body=body[-100:]):
                api = FakeGitHub()
                foreign = self._inject_foreign(api, body=body)
                before = dict(foreign)
                with self.assertRaises(PlanError):
                    sync_plan(api, 3)
                self.assertEqual(foreign, before)
                self.assertEqual(api.requests, [], "reject before any mutation")

    def test_foreign_active_invalid_marker_remains_blocking(self):
        cases = ("estado: reservado", "estado: en revisión",
                 "estado: requiere recuperación", "active_lease",
                 "orphan_branch", "malformed_lease")
        for case in cases:
            with self.subTest(case=case):
                api = FakeGitHub()
                label = case if case.startswith("estado:") else "estado: bloqueado"
                self._inject_foreign(api, labels=[label])
                if case == "active_lease":
                    api.comments.append({
                        "id": 9, "user": {"login": "github-actions[bot]"},
                        "body": reservation_marker(
                            "pl0n3r", "12345678-1234-1234-1234-123456789abc",
                            "trabajo/issue-44", True, "tomar"),
                    })
                elif case == "orphan_branch":
                    api.branches.add("trabajo/issue-44")
                elif case == "malformed_lease":
                    api.comments.append({
                        "id": 9, "user": {"login": "github-actions[bot]"},
                        "body": '<!-- condor-reserva {"active":true} -->',
                    })
                pattern = "reserva ambiguo" if case == "malformed_lease" else "."
                with self.assertRaisesRegex(PlanError, pattern):
                    sync_plan(api, 3)
                self.assertEqual(api.requests, [])

    def test_foreign_open_pr_blocks_isolation_even_without_canonical_branch(self):
        for ref, title, body, short in (
            ("feature/alternative", "Implementar", "Closes #44", False),
            ("trabajo/issue-44", "Implementar", "", False),
            ("work/issue-44", "Implementar", "", False),
            ("feature/alternative", "Implementar", "Closes #44", True),
        ):
            with self.subTest(ref=ref, body=body):
                api = FakeGitHub()
                foreign = self._inject_foreign(api, labels=["estado: bloqueado"])
                before = dict(foreign)
                api.pulls.append({"id": 71, "number": 71, "title": title,
                                  "body": body, "head": {"ref": ref}})
                if short:
                    api.short_pull_pages = True
                    api.pulls.insert(0, {"id": 70, "number": 70, "title": "Other",
                                         "body": "", "head": {"ref": "feature/other"}})
                with self.assertRaises(PlanError):
                    sync_plan(api, 3)
                self.assertEqual(foreign, before)
                self.assertFalse(api.requests)

    def test_foreign_incomplete_comment_or_pr_pagination_fails_closed(self):
        for which in ("comment", "pull"):
            with self.subTest(which=which):
                api = FakeGitHub()
                self._inject_foreign(api, labels=["estado: bloqueado"])
                if which == "comment":
                    api.comments.extend({"id": n, "user": {"login": "someone"},
                                         "body": "noise"} for n in range(100, 200))
                    api.fail_comment_page_two = True
                else:
                    api.pulls.extend({"id": n, "number": n, "title": "Other",
                                      "body": "", "head": {"ref": f"feature/{n}"}}
                                     for n in range(100, 200))
                    api.fail_pull_page_two = True
                with self.assertRaisesRegex(PlanError, "incompleta o inválida"):
                    sync_plan(api, 3)
                self.assertFalse(api.requests)

    def test_foreign_duplicate_collection_ids_and_malformed_pr_fail_closed(self):
        for kind in ("duplicate_comments", "duplicate_pulls", "malformed_pull"):
            with self.subTest(kind=kind):
                api = FakeGitHub()
                self._inject_foreign(api, labels=["estado: bloqueado"])
                if kind == "duplicate_comments":
                    api.comments.extend({"id": 9, "user": {"login": "someone"},
                                         "body": "noise"} for _ in range(2))
                if kind == "duplicate_pulls":
                    api.pulls.extend({"id": 9, "number": 9, "title": "Other",
                                      "body": "", "head": {"ref": "feature/a"}}
                                     for _ in range(2))
                if kind == "malformed_pull":
                    api.pulls.append({"id": 9, "number": 9, "title": "Other"})
                with self.assertRaises(PlanError):
                    sync_plan(api, 3)
                self.assertFalse(api.requests)

    def test_foreign_second_page_active_lease_is_not_ignored(self):
        api = FakeGitHub()
        self._inject_foreign(api, labels=["estado: bloqueado"])
        api.comments.extend({"id": n, "body": "filler",
                             "user": {"login": "someone"}} for n in range(1, 101))
        api.comments.append({
            "id": 101, "user": {"login": "github-actions[bot]"},
            "body": reservation_marker(
                "pl0n3r", "12345678-1234-1234-1234-123456789abc",
                "trabajo/issue-44", True, "tomar"),
        })
        with self.assertRaises(PlanError):
            sync_plan(api, 3)
        self.assertEqual(api.requests, [])

    def test_foreign_comment_count_and_snapshot_race_fail_closed(self):
        for scenario in ("undercount", "overcount", "second_read_race"):
            with self.subTest(scenario=scenario):
                api = FakeGitHub()
                self._inject_foreign(api, labels=["estado: bloqueado"])
                api.comments.append({
                    "id": 3, "body": "ordinary", "user": {"login": "someone"},
                })
                if scenario == "undercount":
                    api.foreign_counter_override = 0
                elif scenario == "overcount":
                    api.foreign_counter_override = 2
                else:
                    api.foreign_counter_race = True
                with self.assertRaises(PlanError):
                    sync_plan(api, 3)
                self.assertEqual(api.requests, [])

    def test_foreign_missing_counter_is_not_proof_of_no_lease(self):
        api = FakeGitHub()
        self._inject_foreign(api, labels=["estado: bloqueado"])
        original_issue = api.issue

        def incomplete_issue(number):
            result = original_issue(number)
            if number == 44:
                result.pop("comments", None)
            return result

        api.issue = incomplete_issue
        with self.assertRaisesRegex(PlanError, "inventario previo ambiguo"):
            sync_plan(api, 3)
        self.assertEqual(api.requests, [])

if __name__ == "__main__":
    unittest.main()
