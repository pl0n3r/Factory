"""Regresiones post-merge #1081: un diff no delega claims futuros (#1234)."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.coordinar_trabajo import parallel_file_grants_enabled
from scripts.orquestador_kit import (
    PlannedTask,
    build_task_marker,
    reservation_blockers,
    verified_new_file_claim_against_active_diff,
)


class PostGrantExclusivityTests(unittest.TestCase):
    def _issue(self, number, paths, status):
        task = PlannedTask(
            key=f"POST_GRANT_LEAF_{number}",
            title=f"Hoja {number}",
            owner="pl0n3r",
            paths=tuple(paths),
            depends_on=(),
        )
        return {
            "number": number,
            "state": "open",
            "labels": [{"name": status}],
            "body": build_task_marker(
                epic=1081,
                task=task,
                order=number,
                roles=["qa", "seguridad"],
                dependency_issues=[],
            ),
        }

    def _blockers(self, *, active_paths=("src/",), candidate_paths=("src/b.py",)):
        active = self._issue(50, active_paths, "estado: reservado")
        candidate = self._issue(51, candidate_paths, "estado: disponible")
        return reservation_blockers(
            candidate,
            [candidate, active],
            "pl0n3r",
            dependency_states={},
            active_task_snapshots={
                50: {"paths": list(active_paths), "depends_on": []},
            },
            active_dependency_states={50: {}},
            active_reservation_numbers={50},
            # El dictamen de un diff previo es diagnóstico, nunca un permiso.
            verified_file_independence=set(),
        )

    def test_directory_lease_prevents_file_grant_even_with_optin(self):
        """AC-01: ni el opt-in concede dos propietarios del mismo archivo."""
        with patch.dict(os.environ, {"CONDOR_PARALLEL_FILE_GRANTS": "1"}):
            self.assertFalse(parallel_file_grants_enabled())
            blockers = self._blockers()
        self.assertEqual(len(blockers), 1)
        self.assertIn("colisión con tarea activa #50", blockers[0])
        self.assertIn("src/b.py", blockers[0])

    def test_future_push_cannot_create_two_overlapping_owners(self):
        """AC-02: el titular de src/ puede ampliar su diff tras el snapshot."""
        initial = verified_new_file_claim_against_active_diff(
            ["src/b.py"], ["src/"],
            active_files=["src/a.py"],
            active_head="a" * 40,
            evidence_head="a" * 40,
            diff_complete=True,
            active_issue=50,
            active_lease="00000000-0000-4000-8000-000000000001",
        )
        self.assertTrue(initial["safe"])  # evidencia puntual, NO lease
        later = verified_new_file_claim_against_active_diff(
            ["src/b.py"], ["src/"],
            active_files=["src/a.py", "src/b.py"],
            active_head="b" * 40,
            evidence_head="b" * 40,
            diff_complete=True,
            active_issue=50,
            active_lease="00000000-0000-4000-8000-000000000001",
        )
        self.assertFalse(later["safe"])
        # La negativa se emite ANTES del primer grant, no al observar un PR.
        with patch.dict(os.environ, {"CONDOR_PARALLEL_FILE_GRANTS": "1"}):
            self.assertFalse(parallel_file_grants_enabled())
            self.assertTrue(self._blockers())

    def test_disjoint_claims_continue_to_parallelize(self):
        """AC-03: el flag nunca exime solapamientos, no serializa disjuntos."""
        for value in ("0", "1", "false", "off", "", "bogus"):
            with self.subTest(flag=value):
                with patch.dict(os.environ, {"CONDOR_PARALLEL_FILE_GRANTS": value}):
                    self.assertFalse(parallel_file_grants_enabled())
                    self.assertTrue(self._blockers())
                    self.assertEqual(
                        self._blockers(active_paths=("src/a.py",)),
                        [],
                    )
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(parallel_file_grants_enabled())
            self.assertTrue(self._blockers())

    def test_runbook_denies_snapshot_as_write_authority(self):
        """AC-04: documentación veta de forma explícita el grant por snapshot."""
        root = Path(__file__).resolve().parents[1]
        docs = (root / "docs" / "orquestador.md").read_text(encoding="utf-8")
        self.assertIn("exclusividad", docs.lower())
        self.assertIn("push futuro", docs)
        self.assertIn("únicamente como diagnóstico", docs)
        self.assertIn("no habilita grants", docs)
        self.assertIn("merge-train", docs)


if __name__ == "__main__":
    unittest.main()
