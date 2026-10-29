#!/usr/bin/env python3
"""Factory #1819: contratos offline de memoria, NO_WORK y observador V3.

Las observaciones de Fase A son candidatas, nunca validación de producción.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from lecciones.memoria import LessonValidationError, token_comparison, validate_lesson
from scripts.no_work_dedup import (
    CANONICAL_SINK, REPOSITORIES, NoWorkInventoryError,
    NoWorkPublicationState, decide_no_work, inventory_fingerprint,
    revalidate_no_work_application,
)
from scripts.lease_auto_release_integration import (
    _GhReadOnlyAPI, local_active_issue_ids, preview_integrated_activity,
)
from scripts.lease_auto_release_run import evaluate_phase_a_candidate
from scripts.lease_phase_a_artifact_qa import ArtifactQAError, inspect_artifact

ROOT = Path(__file__).resolve().parents[1]
REPO = "pl0n3r/Factory"
SHA = "a" * 40

# Sólo estas nueve unidades son ejecutables offline; las otras once son B/C
# y se documentan en el Issue y PR, sin fingir pruebas nominales de cobertura.
OFFLINE = frozenset({
    "docs/memoria-institucional.md:L5-U2",
    "docs/memoria-institucional.md:L9-U1",
    "docs/no-work-dedup.md:B01",
    "docs/no-work-dedup.md:B02",
    "docs/no-work-dedup.md:B03",
    "docs/observador-reservas-consumidor.md:L10-U1",
    "docs/observador-reservas-consumidor.md:L27-U1",
    "docs/observador-reservas-consumidor.md:L53-U1",
    "docs/observador-reservas-consumidor.md:L61-U1",
})

LESSON = {
    "id": "fixture-lesson-01", "project": REPO, "kind": "rework",
    "occurred_at": "2026-10-01T00:00:00Z",
    "what": "Rework sintético", "why": "Caso borde sintético",
    "prevention": "Regresión determinista",
    "source": "pl0n3r/Factory#1819",
}


def inventory() -> dict:
    repositories = {
        name: {"available": [], "recovery": [], "reservations": [],
               "blockers": [], "pull_requests": []}
        for name in REPOSITORIES
    }
    repositories["Factory"]["available"] = [1819]
    repositories["Condor"]["reservations"] = [{
        "issue": 14, "reservation_id": "synthetic-lease",
        "owner": "fixture-owner", "branch": "trabajo/issue-14",
        "active": True,
    }]
    repositories["ControlBot"]["pull_requests"] = [{
        "number": 21, "state": "open", "head_sha": SHA,
    }]
    return {"kill_switch": {"state": "RUNNING", "owner": "fixture-owner"},
            "repositories": repositories}


def manifest(run_id: int = 415) -> dict:
    return {
        "schema_version": 1, "repository": REPO, "head_sha": SHA,
        "run_id": str(run_id), "status": "candidate_terminal",
        "terminal_certified": False, "release_authorized": False,
        "mutations": 0, "valid_observations": 1, "unknown_observations": 0,
        "issues": [{
            "issue": 1819, "state": "read_only", "action": "wait",
            "reason": "activity_window", "activity_age_minutes": 8,
            "activity_source": "issue_comment",
            "release_authorized": False, "lock_verified": False,
            "cas_verified": False, "mutations": 0,
        }],
    }


def receipt(run_id: int = 415) -> dict:
    return {
        "id": run_id, "repository": REPO, "head_sha": SHA,
        "event": "schedule", "status": "completed",
        "conclusion": "success", "artifact_attested": True,
        "completed_at": "2026-10-01T00:00:00Z",
    }


def zipped(value: dict) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("lease-audit-evidence.json", json.dumps(value))
    return buffer.getvalue()


class CoberturaFactory28Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        # memoria L9: valida una lección con fuente GitHub verificable.
        item = validate_lesson(LESSON, "fixture")
        self.assertEqual(item["project"], REPO)
        self.assertEqual(item["source"], "pl0n3r/Factory#1819")

        # memoria L5: compara tokens reales de la función con corte temporal,
        # sin permitir contaminar un proyecto con muestras de otro.
        samples = [
            ("pl0n3r/Factory#11", "2026-09-30T00:00:00Z", 120),
            ("pl0n3r/Factory#12", "2026-10-01T00:00:00Z", 80),
            ("pl0n3r/Factory#13", "2026-10-03T00:00:00Z", 50),
            ("pl0n3r/Factory#14", "2026-10-04T00:00:00Z", 50),
            ("pl0n3r/Condor#99", "2026-10-03T00:00:00Z", 9999),
        ]
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "synthetic-metrics.jsonl"
            file.write_text("".join(json.dumps({
                "task_id": task, "task_type": "agent-bootstrap",
                "completed_at": when, "tokens_input": tokens,
            }) + "\n" for task, when, tokens in samples), encoding="utf-8")
            compared = token_comparison(
                file, "2026-10-02T00:00:00Z", REPO, min_samples=2)
            self.assertEqual(compared["status"], "measured")
            self.assertEqual(compared["before_samples"], 2)
            self.assertEqual(compared["after_samples"], 2)
            self.assertEqual(compared["reduction_pct"], 50.0)

        # no-work B01: huella de los siete repos; la metadata observacional
        # no cambia el fingerprint, pero el HEAD material de un PR sí.
        original = inventory()
        fp = inventory_fingerprint(original)
        shuffled = deepcopy(original)
        shuffled["repositories"] = dict(reversed(list(shuffled["repositories"].items())))
        shuffled["repositories"]["Condor"]["reservations"][0][
            "observed_at"] = "2026-10-01T00:00:00Z"
        self.assertEqual(inventory_fingerprint(shuffled), fp)
        changed = deepcopy(original)
        changed["repositories"]["ControlBot"]["pull_requests"][0][
            "head_sha"] = "b" * 40
        self.assertNotEqual(inventory_fingerprint(changed), fp)

        # no-work B02: create/update/omit dentro del sink único Factory#904.
        created = decide_no_work(original, None, 100)
        self.assertEqual((created.action, created.sink), ("create", CANONICAL_SINK))
        prior = NoWorkPublicationState(904, fp, 100)
        self.assertEqual(decide_no_work(original, prior, 101).action, "omit")
        updated = decide_no_work(changed, prior, 102)
        self.assertEqual((updated.action, updated.comment_id), ("update", 904))
        self.assertEqual(decide_no_work(original, prior, 1900).action, "update")

        # no-work B03: CAS previo rechaza una observación republicada.
        self.assertEqual(
            revalidate_no_work_application(updated, prior).action, "apply")
        self.assertEqual(
            revalidate_no_work_application(
                updated, NoWorkPublicationState(904, fp, 101)
            ).action, "recompute")

        # observador L10: artefacto verificable sólo como candidato, no
        # permiso para Fase B ni credencial de procedencia autenticada.
        meta = {"id": 415, "repository": REPO, "head_sha": SHA,
                "event": "schedule", "status": "completed",
                "conclusion": "success"}
        candidate = inspect_artifact(zipped(manifest()), meta)
        self.assertEqual(candidate["status"], "MATCHED_CANDIDATE")
        for field in ("artifact_attested", "terminal_certified",
                      "release_authorized"):
            self.assertIs(candidate[field], False)
        self.assertEqual(candidate["mutations"], 0)

        # observador L53: el evaluador puro no autoriza Fase B aunque
        # reciba un recibo sintético con la forma de schedule verificado.
        evaluated = evaluate_phase_a_candidate(
            [manifest()], [receipt()], [], repository=REPO)
        self.assertEqual(evaluated.status, "insufficient_observation")
        self.assertEqual(evaluated.valid_cycles, 1)
        self.assertIs(evaluated.release_authorized, False)

        # observador L27: el censo local sólo acepta Issues activos claros.
        self.assertEqual(local_active_issue_ids([[{
            "number": 1819, "state": "open",
            "labels": [{"name": "estado: reservado"}],
        }]], REPO), [1819])

    def test_falla_cerrado(self) -> None:
        for bad in ({**LESSON, "source": "https://not-github.invalid/a"},
                    {**LESSON, "kind": "guess"}):
            with self.subTest(source=bad["source"], kind=bad["kind"]):
                with self.assertRaises(LessonValidationError):
                    validate_lesson(bad, "fixture")

        missing = inventory()
        del missing["repositories"]["FactoryRunner"]
        with self.assertRaisesRegex(NoWorkInventoryError,
                                    "repositories_incomplete"):
            inventory_fingerprint(missing)
        paused = inventory()
        paused["kill_switch"]["state"] = "PAUSED"
        with self.assertRaisesRegex(NoWorkInventoryError, "kill_switch_paused"):
            decide_no_work(paused, None, 100)
        duplicate = inventory()
        duplicate["repositories"]["Condor"]["available"] = [14]
        with self.assertRaisesRegex(NoWorkInventoryError,
                                    "available_reserved_conflict"):
            inventory_fingerprint(duplicate)

        decision = decide_no_work(inventory(), None, 200)
        self.assertEqual(revalidate_no_work_application(
            decision, NoWorkPublicationState(
                904, decision.fingerprint, 199,
            )).action, "recompute")

        meta = {"id": 415, "repository": REPO, "head_sha": SHA,
                "event": "schedule", "status": "completed",
                "conclusion": "success"}
        for variation in ({**meta, "event": "workflow_dispatch"},
                          {**meta, "head_sha": "b" * 40}):
            with self.assertRaises(ArtifactQAError):
                inspect_artifact(zipped(manifest()), variation)
        elevated = manifest()
        elevated["release_authorized"] = True
        with self.assertRaises(ArtifactQAError):
            inspect_artifact(zipped(elevated), meta)

        self.assertIsNone(local_active_issue_ids([], REPO))
        self.assertIsNone(local_active_issue_ids([[{
            "number": 1819, "state": "open",
            "labels": [{"name": "estado: reservado"},
                       {"name": "estado: en revisión"}],
        }]], REPO))
        self.assertIsNone(local_active_issue_ids([[{
            "number": 1819, "state": "open", "labels": [],
        }]], "attacker/Factory"))

        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        preview = preview_integrated_activity(
            object(), object(), 1819, now=now)
        self.assertEqual(preview.state, "UNKNOWN")
        self.assertIs(preview.release_authorized, False)
        self.assertIs(preview.lock_verified, False)
        self.assertIs(preview.cas_verified, False)
        self.assertEqual(
            preview_integrated_activity(object(), object(), 0,
                                        now=now).reason, "invalid_issue")

    def test_sin_datos_reales(self) -> None:
        api = _GhReadOnlyAPI(repo=REPO)
        with patch("subprocess.run", side_effect=AssertionError(
                "El transporte no debe ejecutarse")) as run:
            for method, path in (
                ("POST", "/repos/pl0n3r/Factory/issues/1819"),
                ("GET", "/repos/pl0n3r/Factory/actions/secrets"),
                ("GET", "https://example.invalid/secret"),
                ("GET", "/repos/attacker/repo/issues/1"),
            ):
                with self.subTest(method=method, path=path):
                    with self.assertRaises(PermissionError):
                        api.request(method, path)
            run.assert_not_called()
        candidate = evaluate_phase_a_candidate(
            [manifest()], [receipt()], [], repository=REPO)
        self.assertIs(candidate.release_authorized, False)
        self.assertEqual(candidate.hypothetical_releases, 0)

    def test_validar_exigido(self) -> None:
        # AC-04 protege contrato CI; sólo GitHub acredita Validar exact-SHA.
        ci = (ROOT / ".github/workflows/ci.yml").read_text("utf-8")
        self.assertIn("  validar:", ci)
        self.assertIn("    name: Validar", ci)
        self.assertIn("    needs: [event_guard, preflight, php, node]", ci)
        ref = "ref: " + "$" + "{{ github.event_name == 'pull_request' && github.event.pull_request.head.sha || github.sha }}"
        self.assertIn(ref, ci)


if __name__ == "__main__":
    unittest.main()
