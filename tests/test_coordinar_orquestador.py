import unittest

from scripts.coordinar_trabajo import CoordinationError, reserve_work
from scripts.orquestador_kit import PlannedTask, build_task_marker


class MinimalGitHub:
    def __init__(self, current, others, dependencies=None):
        self.current = current
        self.others = others
        self.dependencies = dependencies or {}

    def issue(self, number):
        return self.dependencies.get(number, self.current)

    def open_issues(self):
        return self.others


class CoordinationOrchestratorTests(unittest.TestCase):
    def test_reserve_work_enforces_planned_owner_before_branch_creation(self):
        task = PlannedTask(
            key="A",
            title="A",
            owner="pl0n3r",
            paths=("scripts/a.py",),
            depends_on=(),
        )
        current = {
            "number": 50,
            "state": "open",
            "body": build_task_marker(
                epic=3,
                task=task,
                order=1,
                roles=["ingenieria-software"],
                dependency_issues=[],
            ),
            "labels": [{"name": "estado: disponible"}],
        }
        api = MinimalGitHub(current, [current])
        with self.assertRaisesRegex(CoordinationError, "planificada"):
            reserve_work(api, 50, "otro-owner", "MEMBER")

    def test_reserve_work_enforces_open_dependencies(self):
        task = PlannedTask(
            key="B",
            title="B",
            owner="pl0n3r",
            paths=("docs/b.md",),
            depends_on=(),
        )
        current = {
            "number": 51,
            "state": "open",
            "body": build_task_marker(
                epic=3,
                task=task,
                order=2,
                roles=["contenido"],
                dependency_issues=[50],
            ),
            "labels": [{"name": "estado: disponible"}],
        }
        dependency = {
            "number": 50,
            "state": "open",
            "body": "",
            "labels": [{"name": "estado: reservado"}],
        }
        api = MinimalGitHub(
            current,
            [current, dependency],
            dependencies={50: dependency},
        )
        with self.assertRaisesRegex(CoordinationError, "dependencias no completadas"):
            reserve_work(api, 51, "pl0n3r", "OWNER")


if __name__ == "__main__":
    unittest.main()
