#!/usr/bin/env python3
"""Factory #1829: pruebas de contratos ejecutables reales y aislados.

A = 15 filas con aserciones sobre funciones reales; B = 2 que requieren
observación GitHub/producción autenticada; C = 3 obligaciones normativas.
No inspecciona ni modifica ninguna matriz de cobertura.
"""
from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import patch

from scripts.preview_kit import PreviewError, run_preview
from scripts.orquestador_kit import (
    verified_changed_file_overlap, verified_new_file_claim_against_active_diff,
)
from scripts.salud_cola_snapshot import REPOSITORIES, SnapshotError, assemble_inventory
from scripts.salud_cola import QueueHealthError, diagnose_queue
from scripts.unattended_global_idle import CANONICAL_REPOSITORIES, evaluate_global_idle_snapshot
from scripts.work_inventory import WorkInventoryError, project_inventory
from scripts.automerge_construccion import evaluate as evaluate_merge
from scripts.release_auto_policy import evaluate as evaluate_release

PREVIEW = "docs/preview-preproduccion.md"
PRINCIPLES = "docs/principios-construccion.md"
A_ROWS = {
    f"{PREVIEW}:L9-U1",
    *(f"{PRINCIPLES}:L11-U{i}" for i in (1, 2, 3, 5, 6)),
    f"{PRINCIPLES}:L15-U1",
    *(f"{PRINCIPLES}:L19-U{i}" for i in (1, 2, 3)),
    *(f"{PRINCIPLES}:L23-U{i}" for i in (1, 2, 3)),
    f"{PRINCIPLES}:L27-U1", f"{PRINCIPLES}:L27-U3",
}
B_ROWS = {
    f"{PREVIEW}:L37-U2": (
        "El skipped real de push y success de pull_request requieren ejecuciones "
        "GitHub Actions autenticadas; un fake offline no certifica el workflow."
    ),
    f"{PRINCIPLES}:L23-U4": (
        "VALIDATED_IN_PRODUCTION requiere comprobante de producción, identidad "
        "y SHA autenticados; una prueba local no acredita el estado de live."
    ),
}
C_ROWS = {
    f"{PRINCIPLES}:L11-U4": (
        "La condición verificable de desbloqueo en el Issue es una obligación "
        "de coordinación externa; un snapshot local no certifica ese comentario."
    ),
    f"{PRINCIPLES}:L27-U2": (
        "D-063 exige atestación válida y autoridad legal del propietario; "
        "los datos sintéticos no sustituyen consentimiento real."
    ),
    f"{PRINCIPLES}:L3-U1": (
        "El aviso de que un documento no autoriza merges ni releases es "
        "normativo, sin función runtime independiente en esta hoja."
    ),
}
ALL_ROWS = A_ROWS | set(B_ROWS) | set(C_ROWS)
assert len(A_ROWS) == 15 and len(B_ROWS) == 2 and len(C_ROWS) == 3
assert len(ALL_ROWS) == 20


def issue(number: int, label: str, *, blocker: dict | None = None) -> dict:
    return {"number": number, "labels": [label],
            "pull_request": False, "blocker": blocker}


def queue_snapshot() -> dict:
    cases = {
        "Factory": [issue(1, "estado: disponible")],
        "Condor": [issue(2, "estado: reservado")],
        "GrindFlow": [issue(3, "estado: bloqueado", blocker={
            "cause": "human_gate", "roadmap": False})],
        "brvtal": [issue(4, "estado: planificado")],
        "ControlBot": [issue(5, "estado: en revisión")],
        "AutoFactory": [issue(6, "estado: requiere recuperación")],
    }
    reports = [
        {"name": name, "pages": [
            {"page_number": 1, "has_next": False, "issues": cases.get(name, [])}
        ]}
        for name in REPOSITORIES
    ]
    return assemble_inventory(
        reports, agent_capacity=None, rate_limit={"limit": 100, "remaining": 100},
    )


def idle_snapshot() -> dict:
    return {"version": 1, "repositories": [
        {"repository": repo, "freshness": "fresh", "ready": False,
         "reserved": False, "reviewing": False, "ambiguous": False,
         "source_ref": "fixture"}
        for repo in CANONICAL_REPOSITORIES
    ]}


def overlap(*, right_files=None, evidence_sha=None, right_complete=True) -> dict:
    return verified_changed_file_overlap(
        ("tests/",), ("tests/",),
        left_files=["tests/a.py"],
        right_files=["tests/b.py"] if right_files is None else right_files,
        left_head="a" * 40, right_head="b" * 40,
        left_evidence_head="a" * 40,
        right_evidence_head="b" * 40 if evidence_sha is None else evidence_sha,
        left_complete=True, right_complete=right_complete,
        other_issue=42, other_lease="fixture-lease",
    )


def release_snapshot() -> dict:
    head = "a" * 40
    return {
        "candidate_sha": head, "observed_main_sha": head,
        "published_v1_sha": "b" * 40, "v1_tag_protected": True,
        "evidence_authenticated": True, "kill_switch_state": "RUNNING",
        "freeze_active": False, "security_veto": False,
        "owner_decision": {
            "option": "A", "candidate_sha": head, "category": "factory-release",
            "journal_verified": True, "owner": "pl0n3r",
        },
        "checks": [
            {"name": name, "head_sha": head, "status": "completed",
             "conclusion": "success", "authenticated": True}
            for name in ("Validar", "SonarCloud Code Analysis", "CodeQL")
        ],
    }


class CoberturaFactory38Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: un predicado por cada fila A, llamando código productivo."""
        stages: list[str] = []

        def capture(stage: str) -> int:
            stages.append(stage)
            return 0

        with patch.dict(os.environ, {}, clear=True):
            run_preview(
                version="1.2.3", sha="a" * 40, migration_mode="none",
                runner=capture, verification_runner=capture,
            )
        diagnosed = diagnose_queue(queue_snapshot())
        repos = diagnosed["repositories"]
        global_idle = idle_snapshot()
        idle = evaluate_global_idle_snapshot(global_idle)
        missing = copy.deepcopy(global_idle)
        missing["repositories"].pop()
        stale = copy.deepcopy(global_idle)
        stale["repositories"][0]["freshness"] = "unknown"
        blocked = project_inventory({
            "repository_ref": "pl0n3r/Factory",
            "leaves": [
                {"key": "test:blocked", "title": "fixture", "state": "blocked",
                 "priority": "critical", "source_refs": ["fixture"]}
            ],
            "narrative": [],
        })
        planned = project_inventory({
            "repository_ref": "pl0n3r/Factory", "leaves": [],
            "narrative": [
                {"identity": "fixture-idea", "title": "future",
                 "kind": "future_idea", "source_ref": "fixture"}
            ],
        })
        changed = overlap()
        candidate = verified_new_file_claim_against_active_diff(
            ["tests/b.py"], ["tests/"], active_files=["tests/a.py"],
            active_head="a" * 40, evidence_head="a" * 40,
            diff_complete=True, active_issue=42, active_lease="lease-fixture",
        )
        outdated = overlap(evidence_sha="c" * 40)
        conflict = overlap(right_files=["tests/a.py"])
        release = evaluate_release(release_snapshot())
        denied = evaluate_release({
            **release_snapshot(),
            "owner_decision": {**release_snapshot()["owner_decision"], "option": "B"},
        })
        # El adaptador antiguo que solo admite 4 estados rechaza el sexto:
        # la excepción es evidencia ejecutada, no una aserción sobre documentación.
        with self.assertRaises(WorkInventoryError):
            project_inventory({
                "repository_ref": "pl0n3r/Factory",
                "leaves": [
                    {"key": "fixture", "title": "fixture",
                     "state": "recovery_required", "priority": "high",
                     "source_refs": ["fixture"]}
                ],
                "narrative": [],
            })

        proofs = {
            f"{PREVIEW}:L9-U1":
                stages[:3] == ["build", "backup", "deploy"],
            f"{PRINCIPLES}:L11-U1":
                idle["idle_global"] is True
                and evaluate_global_idle_snapshot(missing)["idle_global"] is False,
            f"{PRINCIPLES}:L11-U2":
                blocked["state"] == "ALL_BLOCKED" and blocked["next_work"] is None,
            f"{PRINCIPLES}:L11-U3":
                set(repos["Factory"]["counts"]) ==
                {"available", "reserved", "blocked", "planned", "in_review",
                 "recovery_required"}
                and diagnosed["open_total"] == 6,
            f"{PRINCIPLES}:L11-U5":
                diagnosed["recovery_required_total"] == 1
                and repos["AutoFactory"]["counts"]["recovery_required"] == 1
                and diagnosed["available_total"] == 1,
            f"{PRINCIPLES}:L11-U6":
                diagnosed["recovery_required_total"] == 1
                and diagnosed["can_dispatch"] is False,
            f"{PRINCIPLES}:L15-U1":
                stages[-3:] == ["preview-health", "preview-smoke", "preview-e2e"],
            f"{PRINCIPLES}:L19-U1":
                changed["safe"] is True
                and changed["reason"] == "verified_disjoint_changed_files"
                and candidate["safe"] is True,
            f"{PRINCIPLES}:L19-U2":
                outdated["safe"] is False
                and outdated["reason"] == "diff_stale_or_incomplete",
            f"{PRINCIPLES}:L19-U3":
                conflict["safe"] is False
                and conflict["reason"] == "shared_changed_files",
            f"{PRINCIPLES}:L23-U1":
                planned["state"] == "NO_WORK"
                and blocked["state"] != planned["state"],
            f"{PRINCIPLES}:L23-U2":
                evaluate_global_idle_snapshot(stale)["idle_global"] is False
                and evaluate_merge({}).eligible is False,
            f"{PRINCIPLES}:L23-U3":
                evaluate_release({
                    **release_snapshot(), "observed_main_sha": "c" * 40,
                })["reason"] == "main_sha_mismatch",
            f"{PRINCIPLES}:L27-U1":
                release["state"] == "REVIEW_ONLY"
                and release["authorizes_release"] is False
                and release["network_calls"] == 0,
            f"{PRINCIPLES}:L27-U3":
                denied["reason"] == "owner_authority_missing_or_wrong_sha"
                and denied["release_tag_writes"] == 0
                and release["release_tag_writes"] == 0,
        }
        self.assertEqual(set(proofs), A_ROWS)
        for row, proven in proofs.items():
            with self.subTest(row=row):
                self.assertTrue(proven, row)

    def test_falla_cerrado(self) -> None:
        """AC-02: falta de evidencia o autoridad no da readiness."""
        wrong = queue_snapshot()
        wrong["repositories"][0]["counts"]["available"] = 5
        with self.assertRaises(QueueHealthError):
            diagnose_queue(wrong)
        with self.assertRaises(SnapshotError):
            assemble_inventory(
                [{"name": "Factory", "pages": []}], None,
                {"limit": 100, "remaining": 100},
            )
        self.assertFalse(overlap(right_complete=False)["safe"])
        self.assertFalse(overlap(right_files=["tests/a.py"])["safe"])
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PreviewError):
                run_preview(
                    version="1.2.3", sha="a" * 40, migration_mode="none",
                    phase="live", runner=lambda _: 0, verification_runner=lambda _: 0,
                )
        self.assertFalse(evaluate_release({
            **release_snapshot(), "observed_main_sha": "c" * 40,
        })["authorizes_release"])

    def test_sin_datos_reales(self) -> None:
        """AC-03: fakes sintéticos; cero red, credenciales y despliegue live."""
        events: list[str] = []
        with patch.dict(os.environ, {}, clear=True):
            run_preview(
                version="1.2.3", sha="f" * 40, migration_mode="none",
                runner=lambda stage: events.append(stage) or 0,
                verification_runner=lambda stage: events.append(stage) or 0,
            )
        self.assertEqual(len(events), 6)
        self.assertFalse(evaluate_release(release_snapshot())["authorizes_release"])
        self.assertEqual((len(A_ROWS), len(B_ROWS), len(C_ROWS), len(ALL_ROWS)),
                         (15, 2, 3, 20))


if __name__ == "__main__":
    unittest.main()
