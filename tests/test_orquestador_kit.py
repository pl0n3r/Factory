import json
import unittest

from scripts.orquestador_kit import (
    PlanError,
    PlannedTask,
    build_task_marker,
    claims_overlap,
    parse_plan,
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
