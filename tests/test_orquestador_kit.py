import json
import unittest

from scripts.orquestador_kit import (
    PlanError,
    PlannedTask,
    build_task_marker,
    claims_overlap,
    parse_plan,
    parse_task_marker,
    reservation_blockers,
    topological_order,
)


def plan(tasks):
    payload = json.dumps({"version": 1, "tasks": tasks}, separators=(",", ":"))
    return f"Epic\n<!-- factory-plan {payload} -->"


def task(key, *, paths, depends_on=None, owner="pl0n3r"):
    return {
        "key": key,
        "title": f"Tarea {key}",
        "owner": owner,
        "paths": paths,
        "depends_on": depends_on or [],
    }


class OrchestratorKitTests(unittest.TestCase):
    def test_marker_name_in_prose_is_not_malformed_marker(self):
        """AC-01: nombres textuales no crean marker ni error de marker."""
        prose = (
            "Documenta factory-plan y `factory-plan-task` sin comentarios HTML. "
            "También permite prefijos de palabras como factory-plan-tasking."
        )
        self.assertIsNone(parse_task_marker(prose))
        with self.assertRaisesRegex(PlanError, "debe declarar"):
            parse_plan(prose)

    def test_truncated_html_marker_still_fails_closed(self):
        """AC-02: cualquier inicio HTML real malformado invalida el body."""
        marker = build_task_marker(
            epic=3,
            task=PlannedTask(
                key="A",
                title="A",
                owner="pl0n3r",
                paths=("scripts/a.py",),
                depends_on=(),
            ),
            order=1,
            roles=["qa"],
            dependency_issues=[],
        )
        for body, parser in (
            ("<!-- factory-plan-task", parse_task_marker),
            ("<!-- factory-plan-task\t", parse_task_marker),
            ("<!-- factory-plan", parse_plan),
            (f"{marker}\n<!-- factory-plan-task", parse_task_marker),
            (f"{marker}\n<!-- factory-plan-task\t", parse_task_marker),
        ):
            with self.subTest(body=body):
                with self.assertRaisesRegex(PlanError, "malformado"):
                    parser(body)

    def test_duplicate_html_markers_still_fail_closed(self):
        """AC-03: dos markers canónicos conservan rechazo determinista."""
        marker = build_task_marker(
            epic=3,
            task=PlannedTask(
                key="A",
                title="A",
                owner="pl0n3r",
                paths=("scripts/a.py",),
                depends_on=(),
            ),
            order=1,
            roles=["qa"],
            dependency_issues=[],
        )
        with self.assertRaisesRegex(PlanError, "único marker"):
            parse_task_marker(f"{marker}\n{marker}")

    def test_single_canonical_marker_parsing_is_unchanged(self):
        """AC-04: un marker canónico único conserva su payload."""
        marker = build_task_marker(
            epic=3,
            task=PlannedTask(
                key="A",
                title="Tarea A",
                owner="pl0n3r",
                paths=("scripts/a.py",),
                depends_on=(),
            ),
            order=1,
            roles=["qa"],
            dependency_issues=[],
        )
        parsed = parse_task_marker(marker)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["version"], 1)
        self.assertEqual(parsed["epic"], 3)
        self.assertEqual(parsed["task_key"], "A")
        self.assertEqual(parsed["paths"], ["scripts/a.py"])

    def test_issue_prose_can_describe_planning_contract_without_authority(self):
        """AC-05: describir contratos en prosa no materializa autoridad."""
        body = (
            "### Contexto\n\n"
            "Este Issue explica factory-plan-task.version y factory-plan.version.\n"
            "No contiene comentarios HTML de planificación."
        )
        self.assertIsNone(parse_task_marker(body))
        with self.assertRaisesRegex(PlanError, "debe declarar"):
            parse_plan(body)
        self.assertIsNone(
            parse_task_marker("<!-- factory-plan-taskXYZ {\"version\":1} -->")
        )

    def test_dag_has_deterministic_order(self):
        tasks = parse_plan(
            plan([
                task("B", paths=["docs/"], depends_on=["A"]),
                task("A", paths=["scripts/a.py"]),
                task("C", paths=["tests/c.py"], depends_on=["A"]),
            ])
        )
        self.assertEqual(
            [item.key for item in topological_order(tasks)],
            ["A", "B", "C"],
        )

    def test_render_graph_is_mermaid_with_dependencies(self):
        from scripts.orquestador_kit import render_graph

        tasks = parse_plan(
            plan([
                task("A", paths=["a.py"]),
                task("B", paths=["b.py"], depends_on=["A"]),
            ])
        )
        rendered = render_graph(
            3,
            tasks,
            {"A": 10, "B": 11},
            {"A": ["qa"], "B": ["contenido"]},
        )
        self.assertIn("```mermaid", rendered)
        self.assertIn("A --> B", rendered)
        self.assertIn("```", rendered)

    def test_cycle_fails_closed(self):
        with self.assertRaisesRegex(PlanError, "ciclo"):
            parse_plan(
                plan([
                    task("A", paths=["a.py"], depends_on=["B"]),
                    task("B", paths=["b.py"], depends_on=["A"]),
                ])
            )

    def test_parallel_overlap_requires_dependency(self):
        with self.assertRaisesRegex(PlanError, "solapadas"):
            parse_plan(
                plan([
                    task("A", paths=["scripts/"]),
                    task("B", paths=["scripts/b.py"]),
                ])
            )
        parsed = parse_plan(
            plan([
                task("A", paths=["scripts/"]),
                task("B", paths=["scripts/b.py"], depends_on=["A"]),
            ])
        )
        self.assertEqual(len(parsed), 2)

    def test_claim_overlap_understands_directory_prefixes(self):
        self.assertTrue(claims_overlap("scripts/", "scripts/a.py"))
        self.assertTrue(claims_overlap("README.md", "README.md"))
        self.assertFalse(claims_overlap("scripts/a.py", "scripts/b.py"))
        self.assertFalse(claims_overlap("docs/", "scripts/a.py"))

    def test_noncanonical_paths_fail_closed(self):
        for path in ("../x", "/etc/passwd", "src/*.py", "a/../b"):
            with self.subTest(path=path):
                with self.assertRaises(PlanError):
                    parse_plan(plan([task("A", paths=[path])]))

    def test_identifiers_are_ascii_only(self):
        with self.assertRaises(PlanError):
            parse_plan(plan([task("Á", paths=["a.py"])]))
        with self.assertRaises(PlanError):
            parse_plan(plan([task("A", paths=["a.py"], owner="dueño")]))

    def test_reservation_blocks_wrong_owner_dependency_and_active_collision(self):
        current_task = PlannedTask(
            key="B",
            title="B",
            owner="pl0n3r",
            paths=("scripts/b.py",),
            depends_on=(),
        )
        marker = build_task_marker(
            epic=3,
            task=current_task,
            order=2,
            roles=["ingenieria-software"],
            dependency_issues=[101],
        )
        current = {
            "number": 102,
            "body": marker,
            "labels": [{"name": "estado: disponible"}],
        }
        other_task = PlannedTask(
            key="X",
            title="X",
            owner="pl0n3r",
            paths=("scripts/",),
            depends_on=(),
        )
        other = {
            "number": 200,
            "body": build_task_marker(
                epic=9,
                task=other_task,
                order=1,
                roles=["ingenieria-software"],
                dependency_issues=[],
            ),
            "labels": [{"name": "estado: reservado"}],
        }
        dependency = {
            "number": 101,
            "body": "",
            "labels": [{"name": "estado: reservado"}],
        }
        blockers = reservation_blockers(
            current,
            [current, other, dependency],
            "otra-persona",
        )
        self.assertTrue(any("planificada" in item for item in blockers))
        self.assertTrue(any("dependencias no completadas" in item for item in blockers))
        self.assertTrue(any("colisión" in item for item in blockers))

    def test_cancelled_dependency_does_not_unlock_task(self):
        task_b = PlannedTask(
            key="B",
            title="B",
            owner="pl0n3r",
            paths=("docs/b.md",),
            depends_on=(),
        )
        current = {
            "number": 12,
            "body": build_task_marker(
                epic=3,
                task=task_b,
                order=2,
                roles=["contenido"],
                dependency_issues=[11],
            ),
            "labels": [{"name": "estado: disponible"}],
        }
        cancelled = {
            11: {"number": 11, "state": "closed", "state_reason": "not_planned"}
        }
        blockers = reservation_blockers(
            current,
            [current],
            "pl0n3r",
            cancelled,
        )
        self.assertTrue(any("dependencias no completadas" in item for item in blockers))

        completed = {
            11: {"number": 11, "state": "closed", "state_reason": "completed"}
        }
        self.assertEqual(
            reservation_blockers(current, [current], "pl0n3r", completed),
            [],
        )


if __name__ == "__main__":
    unittest.main()
