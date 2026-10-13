import unittest
import unicodedata
from pathlib import Path

from scripts.orquestador_kit import (
    PlannedTask,
    build_task_marker,
    parallel_compatibility_evidence,
    parse_task_marker,
    reservation_blockers,
    task_marker_fingerprint,
    verified_changed_file_overlap,
    verified_new_file_claim_against_active_diff,
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
        internal = Path(
            ".github/workflows/coordinacion-trabajo.yml"
        ).read_text(encoding="utf-8")
        reusable = Path(
            ".github/workflows/coordinacion.yml"
        ).read_text(encoding="utf-8")

        for workflow in (internal, reusable):
            self.assertIn(
                "group: factory-coordination-${{ github.repository_id }}",
                workflow,
            )
            self.assertIn("cancel-in-progress: false", workflow)

        self.assertIn("queue: max", internal)
        self.assertNotIn("queue: max", reusable)

        actionlint = Path(".github/actionlint.yaml").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/coordinacion-trabajo.yml:", actionlint)
        self.assertIn(".github/workflows/coordinacion.yml:", actionlint)
        self.assertEqual(
            actionlint.count('unexpected key "queue" for "concurrency" section'),
            3,
        )
        self.assertIn(
            "template/.github/workflows/coordinacion.yml:", actionlint
        )
        self.assertNotIn("**/*.yml", actionlint)
        self.assertNotIn("**/*.yaml", actionlint)

        template = Path(
            "template/.github/workflows/coordinacion.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn(
            "group: factory-coordination-${{ github.repository_id }}",
            template,
        )


    def test_claims_pr_workflow_deduplicates_canonical_filenames(self) -> None:
        """El gate API-only rechaza alias casefold/NFC dentro del mismo diff."""
        workflow = Path(".github/workflows/coordinacion-trabajo.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'return unicodedata.normalize("NFC", path.casefold())', workflow
        )
        self.assertIn(
            'len({canonical(path) for path in files}) == len(files)', workflow
        )

        def unique(files: list[str]) -> bool:
            return len({
                unicodedata.normalize("NFC", path.casefold()) for path in files
            }) == len(files)

        for files, expected in (
            (["src/a.php", "src/b.php"], True),
            (["src/Cache.php", "src/cache.php"], False),
            (["docs/café.md", "docs/cafe\u0301.md"], False),
            (["src/a.php", "src/a.php"], False),
        ):
            with self.subTest(files=files):
                self.assertEqual(unique(files), expected)


    def test_claims_pr_workflow_does_not_skip_fork_prs(self) -> None:
        """Un fork debe fallar por identidad, no satisfacer un check omitido."""
        workflow = Path(".github/workflows/coordinacion-trabajo.yml").read_text(
            encoding="utf-8"
        )
        job = workflow.split("\n  claims-pr:\n", 1)[1].split(
            "\n  estado-pr:\n", 1
        )[0]
        predicate = job.split("    if: >-\n", 1)[1].split(
            "    runs-on:", 1
        )[0]
        self.assertIn("github.event_name == 'pull_request'", predicate)
        self.assertIn("github.event.action != 'closed'", predicate)
        self.assertNotIn("head.repo.full_name", predicate)
        self.assertIn('(head.get("repo") or {}).get("full_name") == repo', job)
        self.assertNotIn("actions/checkout", job)

    def test_claims_pr_workflow_requires_live_issue_authority(self) -> None:
        """Ejecuta el Python real del gate con API sintética y sin red."""
        import io
        import json
        import os
        from unittest import mock
        from urllib.parse import urlsplit

        workflow = Path(".github/workflows/coordinacion-trabajo.yml").read_text(
            encoding="utf-8"
        )
        opener = "          python3 - <<'PY'\n"
        self.assertEqual(workflow.count(opener), 1)
        inline = workflow.split(opener, 1)[1].split("          PY\n", 1)[0]
        script = "\n".join(line[10:] for line in inline.splitlines()) + "\n"
        sha = "a" * 40
        marker = {
            "version": 3, "active": True,
            "branch": "trabajo/issue-1081", "owner": "pl0n3r",
            "reservation_id": "123e4567-e89b-12d3-a456-426614174000",
            "task_paths": ["tests/test_parallel_coordination.py"],
        }
        issue_path = "/repos/pl0n3r/Factory/issues/1081"
        pr_path = "/repos/pl0n3r/Factory/pulls/1083"
        scenarios = (
            ("valid", {}, False, True),
            ("closed", {"state": "closed"}, False, False),
            ("blocked", {"labels": [{"name": "estado: bloqueado"}]}, False, False),
            ("conflict", {"labels": [
                {"name": "estado: en revisión"}, {"name": "status: blocked"},
            ]}, False, False),
            ("missing_owner", {"assignees": []}, False, False),
            ("wrong_owner", {"assignees": [{"login": "otro"}]}, False, False),
            ("race_after_diff", {}, True, False),
            ("fork", {}, False, False),
        )
        for name, updates, race, accepted in scenarios:
            with self.subTest(case=name):
                reads = [0]

                def fake_urlopen(request, timeout=0):
                    address = urlsplit(request.full_url)
                    url = address.path
                    if url == pr_path:
                        value = {
                            "state": "open", "changed_files": 1,
                            "head": {
                                "ref": "trabajo/issue-1081", "sha": sha,
                                "repo": {"full_name": (
                                    "other/repository" if name == "fork"
                                    else "pl0n3r/Factory"
                                )},
                            },
                            "base": {"ref": "main", "sha": "b" * 40},
                        }
                    elif url == issue_path:
                        reads[0] += 1
                        value = {
                            "number": 1081, "state": "open",
                            "updated_at": "2026-10-10T12:00:00Z",
                            "labels": [{"name": "estado: en revisión"}],
                            "assignees": [{"login": "pl0n3r"}],
                        }
                        value.update(updates)
                        if race and reads[0] > 1:
                            value["labels"] = [{"name": "estado: bloqueado"}]
                    elif url == issue_path + "/comments":
                        value = [{"user": {"login": "github-actions[bot]"},
                                  "body": "<!-- condor-reserva "
                                  + json.dumps(marker, separators=(",", ":"))
                                  + " -->"}]
                    elif url == pr_path + "/files":
                        value = [{"filename": "tests/test_parallel_coordination.py",
                                  "status": "modified"}]
                    elif url == "/repos/pl0n3r/Factory/git/ref/heads/trabajo%2Fissue-1081":
                        value = {"object": {"sha": sha}}
                    else:
                        self.fail("Unexpected authenticated REST path: " + url)
                    return io.BytesIO(json.dumps(value).encode("utf-8"))

                env = {
                    "GH_TOKEN": "fake-only", "REPOSITORIO": "pl0n3r/Factory",
                    "PR": "1083", "EXPECTED_HEAD": sha,
                }
                with mock.patch.dict(os.environ, env), mock.patch(
                    "urllib.request.urlopen", side_effect=fake_urlopen
                ):
                    if accepted:
                        exec(compile(script, "<inline-claims-pr>", "exec"),
                             {"__name__": "__main__"})
                        self.assertEqual(reads[0], 2)
                    else:
                        with self.assertRaisesRegex(
                            AssertionError,
                            "PR identity mismatch" if name == "fork"
                            else "issue authority invalid",
                        ):
                            exec(compile(script, "<inline-claims-pr>", "exec"),
                                 {"__name__": "__main__"})
                        if name == "fork":
                            self.assertEqual(reads[0], 0)
                        else:
                            self.assertGreaterEqual(reads[0], 1)

    def test_partial_active_issue_does_not_globally_block_next_disjoint_issue(self) -> None:
        """AC-06: un label activo huérfano sin reserva confiable no bloquea el siguiente leaf."""
        orphan = planned_issue(
            473,
            ["tests/test_observability_fabric.py"],
            status="estado: en revisión",
        )
        candidate = planned_issue(478, ["scripts/disaster_recovery_policy.py"])

        blockers = reservation_blockers(
            candidate,
            [orphan, candidate],
            "pl0n3r",
            {},
            active_task_snapshots={},
            active_dependency_states={},
            active_reservation_numbers=set(),
        )

        self.assertEqual(blockers, [])

    def test_repaired_dispatcher_re_evaluates_next_issue_without_internal_state_edits(self) -> None:
        """AC-07: una reserva válida sigue siendo autoridad; el estado huérfano no requiere claims inventados."""
        orphan = planned_issue(
            473,
            ["tests/test_observability_fabric.py"],
            status="estado: en revisión",
        )
        active = planned_issue(
            474,
            ["config/recovery/brvtal.json"],
            status="estado: reservado",
        )
        candidate = planned_issue(478, ["scripts/disaster_recovery_policy.py"])
        active_marker = parse_task_marker(active["body"])
        self.assertIsNotNone(active_marker)

        blockers = reservation_blockers(
            candidate,
            [orphan, active, candidate],
            "pl0n3r",
            {},
            active_task_snapshots={474: active_marker},
            active_dependency_states={474: {}},
            active_reservation_numbers={474},
        )

        self.assertEqual(blockers, [])


    def _changed_proof(self, left, right, *, left_claims=("src/",),
                       right_claims=("src/",), **override):
        baseline = {
            "left_files": left,
            "right_files": right,
            "left_head": "a" * 40,
            "right_head": "b" * 40,
            "left_evidence_head": "a" * 40,
            "right_evidence_head": "b" * 40,
            "left_complete": True,
            "right_complete": True,
            "other_issue": 754,
            "other_lease": "a6206a44-ba69-455a-86ed-a0a3728e601d",
        }
        baseline.update(override)
        return verified_changed_file_overlap(left_claims, right_claims, **baseline)

    def test_verified_disjoint_files_inside_directory_claim_can_run_in_parallel(self) -> None:
        """AC-01: únicamente la prueba exact-SHA completa distingue archivos."""
        evidence = self._changed_proof(["src/activity.php"], ["src/collector.php"])
        self.assertEqual(evidence["reason"], "verified_disjoint_changed_files")
        self.assertTrue(evidence["safe"])
        self.assertEqual(evidence["files"], [])

    def test_case_and_unicode_aliases_are_file_collisions(self) -> None:
        """Un filesystem insensible a case/NFC no puede crear falsas disjunciones."""
        names = (
            ("src/Cache.php", "src/cache.php"),
            ("src/Café.php", "src/Cafe\u0301.php"),
            ("src/Straße.php", "src/STRASSE.php"),
        )
        for left, right in names:
            with self.subTest(left=left, right=right):
                for claims in (
                    {"left_claims": ("src/",), "right_claims": ("src/",)},
                    {"left_claims": (left,), "right_claims": (right,)},
                ):
                    evidence = self._changed_proof([left], [right], **claims)
                    self.assertFalse(evidence["safe"], evidence)
                    self.assertEqual(evidence["reason"], "shared_changed_files")
                    self.assertEqual(set(evidence["files"]), {left, right})
                check = verified_new_file_claim_against_active_diff(
                    [left], ["src/"], active_files=[right],
                    active_head="a" * 40, evidence_head="a" * 40,
                    diff_complete=True, active_issue=754,
                    active_lease="a6206a44-ba69-455a-86ed-a0a3728e601d",
                )
                self.assertFalse(check["safe"], check)
                self.assertEqual(check["reason"], "file_already_modified_by_active_branch")

    def test_canonical_aliases_in_one_diff_fail_closed(self) -> None:
        """Dos grafías del mismo path no son dos cambios independientes."""
        left, alias = "src/Cache.php", "src/cache.php"
        result = self._changed_proof([left, alias], ["src/other.php"])
        self.assertFalse(result["safe"], result)
        self.assertEqual(result["reason"], "changed_files_noncanonical")
        verdict = verified_new_file_claim_against_active_diff(
            [left, alias], ["src/"], active_files=["src/other.php"],
            active_head="a" * 40, evidence_head="a" * 40,
            diff_complete=True, active_issue=754,
            active_lease="a6206a44-ba69-455a-86ed-a0a3728e601d",
        )
        self.assertFalse(verdict["safe"], verdict)
        self.assertEqual(verdict["reason"], "candidate_requires_exact_unique_files")
        verdict = verified_new_file_claim_against_active_diff(
            ["src/other.php"], ["src/"], active_files=[left, alias],
            active_head="a" * 40, evidence_head="a" * 40,
            diff_complete=True, active_issue=754,
            active_lease="a6206a44-ba69-455a-86ed-a0a3728e601d",
        )
        self.assertFalse(verdict["safe"], verdict)
        self.assertEqual(verdict["reason"], "changed_files_outside_active_claims")

    def test_identical_changed_file_remains_exclusive(self) -> None:
        """AC-02: dos líneas con el mismo archivo no se desbloquean."""
        evidence = self._changed_proof(["src/activity.php"], ["src/activity.php"])
        self.assertFalse(evidence["safe"])
        self.assertEqual(evidence["reason"], "shared_changed_files")
        self.assertEqual(evidence["files"], ["src/activity.php"])

    def test_collision_names_file_and_active_lease(self) -> None:
        """AC-03: el diagnóstico señala archivo, Issue y UUID de reserva."""
        evidence = self._changed_proof(
            ["src/collector.php", "src/activity.php"], ["src/collector.php"]
        )
        self.assertFalse(evidence["safe"])
        self.assertEqual(evidence["files"], ["src/collector.php"])
        self.assertEqual(evidence["other_issue"], 754)
        self.assertEqual(
            evidence["other_lease"], "a6206a44-ba69-455a-86ed-a0a3728e601d"
        )

    def test_missing_truncated_or_stale_diff_fails_closed(self) -> None:
        """AC-04: identidad y cardinalidad del diff son autoridad obligatoria."""
        cases = (
            {"left_files": None},
            {"right_files": []},
            {"left_complete": False},
            {"right_complete": False},
            {"left_evidence_head": "c" * 40},
            {"right_evidence_head": "c" * 40},
            {"left_evidence_head": None},
            {"right_files": ["src/outside.php"], "right_claims": ("src/other/",)},
            {"left_files": ["src/activity.php", "src/activity.php"]},
        )
        for override in cases:
            left_claims = override.pop("left_claims", ("src/",))
            right_claims = override.pop("right_claims", ("src/",))
            with self.subTest(override=override):
                evidence = self._changed_proof(
                    ["src/activity.php"], ["src/other.php"],
                    left_claims=left_claims, right_claims=right_claims, **override
                )
                self.assertFalse(evidence["safe"], evidence)

    def test_version_and_lockfile_overlap_needs_serial_merge_evidence(self) -> None:
        """AC-05: README/lock/version NO son excepciones implícitas."""
        for path in ("config/version.php", "README.md", "package-lock.json"):
            with self.subTest(path=path):
                result = self._changed_proof(
                    [path], [path], left_claims=(path,), right_claims=(path,)
                )
                self.assertFalse(result["safe"])
                self.assertEqual(result["files"], [path])

    def test_same_file_nonoverlapping_hunks_require_merge_train_authority(self) -> None:
        """AC-06: el arbitraje por archivo no finge conocer hunks o rebase."""
        result = self._changed_proof(
            ["src/collector.php"], ["src/collector.php"],
            left_claims=("src/collector.php",),
            right_claims=("src/collector.php",),
        )
        self.assertFalse(result["safe"])
        self.assertEqual(result["reason"], "shared_changed_files")


    def _candidate_preflight(self, candidate, changed, **kw):
        values = dict(
            active_files=changed,
            active_head="a" * 40,
            evidence_head="a" * 40,
            diff_complete=True,
            active_issue=754,
            active_lease="29f4ed31-828d-450a-ba83-3887b03f27b7",
        )
        values.update(kw)
        return verified_new_file_claim_against_active_diff(
            candidate, ["src/"], **values
        )

    def test_candidate_file_lease_v3_allows_verified_disjoint_active_diff(self) -> None:
        result = self._candidate_preflight(
            ["src/missing.php"], ["src/current.php", "src/other.php"]
        )
        self.assertTrue(result["safe"])
        self.assertEqual(
            result["reason"], "candidate_files_disjoint_from_verified_active_diff"
        )
        self.assertEqual(result["active_issue"], 754)

    def test_candidate_file_lease_v3_rejects_modified_same_file(self) -> None:
        result = self._candidate_preflight(["src/current.php"], ["src/current.php"])
        self.assertFalse(result["safe"])
        self.assertEqual(result["files"], ["src/current.php"])

    def test_candidate_file_lease_v3_rejects_directory_candidate(self) -> None:
        result = self._candidate_preflight(["src/"], ["src/current.php"])
        self.assertFalse(result["safe"])
        self.assertEqual(result["reason"], "candidate_requires_exact_unique_files")

    def test_candidate_file_lease_v3_rejects_stale_and_absent_diff(self) -> None:
        cases = (
            {"active_files": None},
            {"active_files": []},
            {"evidence_head": "b" * 40},
            {"diff_complete": False},
            {"active_files": ["other/file.php"]},
            {"active_files": ["src/current.php", "src/current.php"]},
            {"active_lease": ""},
        )
        for override in cases:
            with self.subTest(override=override):
                result = self._candidate_preflight(
                    ["src/next.php"], ["src/current.php"], **override
                )
                self.assertFalse(result["safe"], result)

    def test_candidate_file_lease_v3_never_exempts_version_or_lock_conflict(self) -> None:
        for path in ("README.md", "package-lock.json", "config/version.php"):
            with self.subTest(path=path):
                result = verified_new_file_claim_against_active_diff(
                    [path], [path],
                    active_files=[path],
                    active_head="a" * 40,
                    evidence_head="a" * 40,
                    diff_complete=True,
                    active_issue=136,
                    active_lease="40ff674a-ce7a-410e-80d1-979b75ca9385",
                )
                self.assertFalse(result["safe"])
                self.assertEqual(result["files"], [path])


if __name__ == "__main__":
    unittest.main()
