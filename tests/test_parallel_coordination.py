import unittest
from pathlib import Path

from scripts.orquestador_kit import (
    PlannedTask,
    build_task_marker,
    parallel_compatibility_evidence,
    parse_task_marker,
    reservation_blockers,
    task_marker_fingerprint,
)


def planned_issue(
    number: int,
    paths: list[str],
    *,
    status: str = "estado: disponible",
    depends_on: tuple[int, ...] = (),
) -> dict:
    task = PlannedTask(
        key=f"TASK_{number}",
        title=f"Tarea {number}",
        owner="pl0n3r",
        paths=tuple(paths),
        depends_on=(),
    )
    return {
        "number": number,
        "state": "open",
        "state_reason": None,
        "labels": [{"name": status}],
        "body": build_task_marker(
            epic=143,
            task=task,
            order=number,
            roles=["ingenieria-software"],
            dependency_issues=list(depends_on),
        ),
    }


def unplanned_issue(
    number: int,
    *,
    status: str = "estado: disponible",
) -> dict:
    return {
        "number": number,
        "state": "open",
        "state_reason": None,
        "labels": [{"name": status}],
        "body": "",
    }


class ParallelCoordinationTests(unittest.TestCase):
    def test_disjoint_ready_tasks_can_run_concurrently(self) -> None:
        active = planned_issue(
            10,
            ["scripts/a.py"],
            status="estado: reservado",
        )
        candidate = planned_issue(11, ["docs/b.md"])

        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
        )

        self.assertEqual(blockers, [])
        evidence = parallel_compatibility_evidence(
            candidate,
            [active, candidate],
        )
        self.assertEqual(len(evidence), 1)
        self.assertIn("#10", evidence[0])
        self.assertIn("claims disjuntos", evidence[0])

    def test_overlapping_claim_blocks_parallel_reservation(self) -> None:
        active = planned_issue(
            10,
            ["scripts/"],
            status="estado: reservado",
        )
        candidate = planned_issue(11, ["scripts/b.py"])

        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
        )

        self.assertTrue(any("colisión" in blocker for blocker in blockers))

    def test_active_claims_use_pinned_snapshot_after_issue_edit(self) -> None:
        active = planned_issue(
            10,
            ["scripts/a.py"],
            status="estado: reservado",
        )
        pinned = parse_task_marker(active["body"])
        self.assertIsNotNone(pinned)
        original_pin = task_marker_fingerprint(pinned)

        edited = planned_issue(
            10,
            ["docs/changed.md"],
            status="estado: reservado",
        )
        active["body"] = edited["body"]
        self.assertNotEqual(
            task_marker_fingerprint(parse_task_marker(active["body"])),
            original_pin,
        )

        candidate = planned_issue(11, ["scripts/a.py"])
        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
            {10: pinned},
            {10: {}},
        )

        self.assertTrue(any("colisión" in blocker for blocker in blockers))

    def test_reopened_dependency_of_active_task_blocks_new_parallel_work(self) -> None:
        active = planned_issue(
            10,
            ["scripts/a.py"],
            status="estado: reservado",
            depends_on=(9,),
        )
        pinned = parse_task_marker(active["body"])
        self.assertIsNotNone(pinned)
        candidate = planned_issue(11, ["docs/b.md"])

        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
            {10: pinned},
            {10: {9: {"state": "open", "state_reason": None}}},
        )

        self.assertTrue(
            any(
                "tarea activa #10 tiene dependencias no completadas: #9" in blocker
                for blocker in blockers
            )
        )

    def test_completed_dependency_of_active_task_allows_disjoint_work(self) -> None:
        active = planned_issue(
            10,
            ["scripts/a.py"],
            status="estado: reservado",
            depends_on=(9,),
        )
        pinned = parse_task_marker(active["body"])
        self.assertIsNotNone(pinned)
        candidate = planned_issue(11, ["docs/b.md"])

        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
            {},
            {10: pinned},
            {10: {9: {"state": "closed", "state_reason": "completed"}}},
        )

        self.assertEqual(blockers, [])

    def test_open_dependency_blocks_parallel_reservation(self) -> None:
        dependency = planned_issue(10, ["scripts/a.py"])
        candidate = planned_issue(
            11,
            ["docs/b.md"],
            depends_on=(10,),
        )

        blockers = reservation_blockers(
            candidate,
            [dependency, candidate],
            "pl0n3r",
            {10: {"state": "open", "state_reason": None}},
        )

        self.assertTrue(
            any("dependencias no completadas" in blocker for blocker in blockers)
        )

    def test_unplanned_work_keeps_conservative_repo_limit(self) -> None:
        active = planned_issue(
            10,
            ["scripts/a.py"],
            status="estado: reservado",
        )
        candidate = unplanned_issue(11)

        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
        )

        self.assertTrue(
            any("trabajo no planificado" in blocker for blocker in blockers)
        )

        active_unplanned = unplanned_issue(
            12,
            status="estado: en revisión",
        )
        planned_candidate = planned_issue(13, ["docs/c.md"])
        blockers = reservation_blockers(
            planned_candidate,
            [active_unplanned, planned_candidate],
            "pl0n3r",
            {},
        )
        self.assertTrue(
            any("no está planificada" in blocker for blocker in blockers)
        )

    def test_english_profile_active_status_is_also_exclusive(self) -> None:
        active = planned_issue(10, ["scripts/a.py"])
        active["labels"] = [{"name": "status: reserved"}]
        candidate = unplanned_issue(11)

        blockers = reservation_blockers(
            candidate,
            [active, candidate],
            "pl0n3r",
        )

        self.assertTrue(
            any("trabajo no planificado" in blocker for blocker in blockers)
        )

    def test_plan_documents_dag_based_parallelism(self) -> None:
        plan = Path("PLAN-AGENTES.md").read_text(encoding="utf-8")

        self.assertIn("**uno por defecto**", plan)
        self.assertIn("dependencias satisfechas", plan)
        self.assertIn("claims disjuntos", plan)
        self.assertIn("Tras perder una carrera de reserva", plan)
        self.assertNotIn(
            "**Nunca** tomes un repo donde otro agente tiene una reserva activa",
            plan,
        )

    def test_coordination_workflows_serialize_reservation_decisions(self) -> None:
        for path in (
            Path(".github/workflows/coordinacion-trabajo.yml"),
            Path(".github/workflows/coordinacion.yml"),
        ):
            workflow = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    "group: factory-coordination-${{ github.repository_id }}",
                    workflow,
                )
                self.assertIn("cancel-in-progress: false", workflow)

        template = Path(
            "template/.github/workflows/coordinacion.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "group: factory-coordination-${{ github.repository_id }}",
            template,
        )


if __name__ == "__main__":
    unittest.main()
