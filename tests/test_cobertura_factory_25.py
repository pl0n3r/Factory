#!/usr/bin/env python3
"""Factory #1816: execute actual color and Phase-A code with synthetic inputs.

A rows are offline *subcontracts*, not total go-live or release coverage.
B/C rows are classified in the PR/Issue; no matrix row is promoted here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest import mock
import urllib.request
import zipfile

from scripts.sync_label_colors import (
    REPOSITORIES, REPOSITORY_LANGUAGE, SyncError, assert_safe_plan,
    load_catalogs, plan_repository, validate_catalog_parity,
)
from scripts.lease_phase_a_artifact_qa import inspect_artifact, ArtifactQAError
from scripts.lease_auto_release_run import evaluate_phase_a_candidate, run_cycle

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
REPO = "pl0n3r/Factory"
META = {
    "id": 415, "repository": REPO, "head_sha": SHA,
    "event": "schedule", "status": "completed", "conclusion": "success",
}
ROW = {
    "issue": 21, "state": "read_only", "action": "wait",
    "reason": "activity_window", "activity_age_minutes": 7,
    "activity_source": "workflow_push", "release_authorized": False,
    "lock_verified": False, "cas_verified": False, "mutations": 0,
}
MANIFEST = {
    "schema_version": 1, "repository": REPO, "head_sha": SHA,
    "run_id": "415", "status": "candidate_terminal",
    "terminal_certified": False, "release_authorized": False,
    "mutations": 0, "valid_observations": 1,
    "unknown_observations": 0, "issues": [ROW],
}
PREFIX_LABEL = "docs/label-color-sync.md:"
PREFIX_QA = "docs/lease-phase-a-artifact-qa.md:"
PREFIX_RESERVA = "docs/liberacion-automatica-de-reservas.md:"
PREFIX_SALIDA = "docs/lista-salida-produccion.md:"
LOCAL = (
    PREFIX_LABEL + "L8-U1",
    PREFIX_LABEL + "L9-U1",
    PREFIX_QA + "L11-U1",
    PREFIX_QA + "L13-U1",
    PREFIX_QA + "L15-U1",
    PREFIX_QA + "L3-U1",
    PREFIX_QA + "L3-U2",
    PREFIX_QA + "L3-U3",
    PREFIX_QA + "L3-U4",
    PREFIX_RESERVA + "B01",
    PREFIX_RESERVA + "B04",
)
WORLD = {
    PREFIX_QA + "L9-U1": "independent QA and actual authenticated GitHub receipts are not locally attestable",
    PREFIX_RESERVA + "B02": "CI/review veto is local, but proof of absence of pushes requires an authenticated, complete event history",
    PREFIX_SALIDA + "L83-U1": "real offsite 3-2-1-1-0 and RPO/RTO require owner-approved provider and restore",
    PREFIX_SALIDA + "L83-U2": "offline fixtures do not attest an actual restore or retention",
    PREFIX_SALIDA + "L84-U1": "protected Factory@v1 publication requires OWNER gate, authorized version/SHA and live evidence",
}
POLICY = {
    PREFIX_SALIDA + "L7-U1": "readiness status criteria are documentary, not a release engine",
    PREFIX_SALIDA + "L7-U2": "epics and roadmap not sufficient is a documentary authority rule",
    PREFIX_SALIDA + "L79-U1": "historical note about issues not created has no runnable mechanism",
    PREFIX_SALIDA + "L8-U1": "SIN_COBERTURA/DEL_DUEÑO/NO_APLICA definitions are policy classifications",
}
MISSING: dict[str, str] = {}
ALL = frozenset(LOCAL) | frozenset(WORLD) | frozenset(POLICY)


def archive(manifest: object = None, *, name: str = "lease-audit-evidence.json") -> tuple[bytes, bytes]:
    raw = json.dumps(
        MANIFEST if manifest is None else manifest,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, raw)
    return stream.getvalue(), raw


def phase_input(count: int = 100, *, interval_minutes: int = 15,
                release: bool = False) -> tuple[list[dict], list[dict], list[dict]]:
    """Fabricated, non-GitHub receipts: never make them real attestation."""
    at = datetime(2026, 9, 1, tzinfo=timezone.utc)
    manifests: list[dict] = []
    receipts: list[dict] = []
    qa: list[dict] = []
    for n in range(count):
        ident = 40001 + n
        row = dict(ROW)
        if release and n == 0:
            row.update(action="release", reason="inactive_after_recovery_grace",
                       activity_age_minutes=45, activity_source="reservation_marker")
            qa.append({"run_id": ident, "issue": 21, "verdict": "correct",
                       "evidence_ref": "fixture-1816-qa/release-1"})
        manifests.append({
            **MANIFEST, "run_id": str(ident),
            "valid_observations": 1, "issues": [row],
        })
        receipts.append({
            **META, "id": ident,
            "artifact_attested": True,  # fictional assertion for the pure evaluator
            "completed_at": (at + timedelta(minutes=interval_minutes * n))
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return manifests, receipts, qa


class _NoPort:
    def __getattr__(self, name):
        raise AssertionError("no port may be accessed in disabled Phase A")


class CoberturaFactory25Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        """AC-01: exact behavioral assertions for all 11 local subcontracts."""
        self.assertEqual((20, 11, 5, 4, 0),
                         (len(ALL), len(LOCAL), len(WORLD), len(POLICY), len(MISSING)))
        catalogs = load_catalogs(ROOT)
        es, en = catalogs["es"], catalogs["en"]
        # label-color L8: the actual parity validator accepts canonical catalogs.
        self.assertIsNone(validate_catalog_parity(es, en))
        self.assertEqual(
            {r["key"]: r["color"] for r in es},
            {r["key"]: r["color"] for r in en},
        )
        # label-color L9: planning never creates/renames/deletes missing labels.
        sample = es[0]
        snapshots = [{"name": sample["name"], "color": "FFFFFF"},
                     {"name": "fixture:unmanaged", "color": "AAAAAA"}]
        plan = plan_repository(REPO, snapshots, catalogs)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action"], "update_color")
        self.assertEqual(plan[0]["label"], sample["name"])
        self.assertEqual(plan[0]["color_before"], "FFFFFF")
        self.assertEqual(plan[0]["color_after"], sample["color"])
        self.assertEqual(
            set(plan[0]), {"action", "repository", "label", "color_before", "color_after"},
        )
        self.assertIsNone(assert_safe_plan(plan))
        self.assertEqual(len(REPOSITORIES), 7)

        blob, raw = archive()
        # QA L3-U1: the real inspector consumes bytes in memory, not an endpoint.
        inspection = inspect_artifact(blob, dict(META))
        self.assertEqual(inspection["status"], "MATCHED_CANDIDATE")
        self.assertEqual((inspection["repository"], inspection["run_id"]),
                         (REPO, META["id"]))
        # QA L3-U2: the identity is exact, schedule/completed/success only.
        self.assertEqual(inspection["head_sha"], SHA)
        # QA L3-U3 / L15: real inspector cannot authorize any mutation/release.
        self.assertEqual(
            {key: inspection[key] for key in
             ("artifact_attested", "terminal_certified", "release_authorized", "mutations")},
            {"artifact_attested": False, "terminal_certified": False,
             "release_authorized": False, "mutations": 0},
        )
        # QA L3-U4: hash the original JSON bytes, do not reserialize/reformat them.
        self.assertEqual(inspection["sha256_json"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(inspection["valid_observations"], 1)

        manifests, receipts, reviews = phase_input(release=True)
        outcome = evaluate_phase_a_candidate(
            manifests, receipts, reviews, repository=REPO)
        # QA L11/L13: synthetic 100 cycles spanning >24h + one individually
        # reviewed hypothetical release only yield a CANDIDATE, never authority.
        self.assertEqual(outcome.status, "candidate_only")
        self.assertEqual(outcome.valid_cycles, 100)
        self.assertGreaterEqual(outcome.observed_minutes, 1440)
        self.assertEqual((outcome.hypothetical_releases, outcome.qa_correct), (1, 1))
        self.assertIs(outcome.release_authorized, False)

        # Reservas B01: production function disabled by default; never access
        # any Port or release a reservation while merely observing Phase A.
        disabled = run_cycle([18, 19], _NoPort())
        self.assertEqual(disabled.state, "feature_disabled")
        self.assertEqual([r.action for _, r in disabled.results], ["wait", "wait"])
        denied = run_cycle([18], _NoPort(), feature_enabled=True,
                           dry_run=False, mutations_authorized=False)
        self.assertEqual(denied.state, "mutation_gate_off")
        self.assertEqual(denied.results[0][1].action, "wait")
        # Reservas B04: evaluator requires each individual hypothetical QA.
        missing_qa = evaluate_phase_a_candidate(
            manifests, receipts, [], repository=REPO)
        self.assertEqual(missing_qa.status, "qa_incomplete")
        self.assertFalse(missing_qa.release_authorized)

    def test_falla_cerrado(self) -> None:
        """AC-02: missing/forged/unsafe input cannot enable colors or phase B."""
        catalogs = load_catalogs(ROOT)
        for bad in (
            {**catalogs, "en": [dict(x) for x in catalogs["en"][:-1]]},
            {**catalogs, "en": [
                {**x, "color": "FFFFFF"} if i == 0 else dict(x)
                for i, x in enumerate(catalogs["en"])
            ]},
        ):
            with self.assertRaises(SyncError):
                validate_catalog_parity(bad["es"], bad["en"])
        for malicious in ("create", "delete", "rename", "update"):
            with self.subTest(action=malicious):
                with self.assertRaises(SyncError):
                    assert_safe_plan([{
                        "action": malicious, "repository": REPO,
                        "label": "fixture", "color_before": "FFFFFF",
                        "color_after": "AABBCC",
                    }])
        with self.assertRaises(SyncError):
            plan_repository("pl0n3r/forbidden", [], catalogs)

        blob, raw = archive()
        for bad_blob, bad_meta in (
            (b"not-a-zip", META),
            (archive(name="../lease-audit-evidence.json")[0], META),
            (blob, {**META, "event": "pull_request"}),
            (blob, {**META, "head_sha": "b" * 40}),
            (archive({**MANIFEST, "terminal_certified": True})[0], META),
            (archive({**MANIFEST, "mutations": 1})[0], META),
            (archive({**MANIFEST, "issues": [{**ROW, "release_authorized": True}]})[0], META),
        ):
            with self.subTest(kind=str(bad_meta)[:50]):
                with self.assertRaises(ArtifactQAError):
                    inspect_artifact(bad_blob, bad_meta)
        self.assertNotEqual(inspection := inspect_artifact(blob, META)["sha256_json"], "")
        self.assertEqual(inspection, hashlib.sha256(raw).hexdigest())

        manifests, receipts, qa = phase_input(release=True)
        for receipt_change in (
            {"event": "pull_request"}, {"conclusion": "failure"},
            {"artifact_attested": False}, {"head_sha": "b" * 40},
        ):
            trial = deepcopy(receipts)
            trial[0].update(receipt_change)
            self.assertEqual(
                evaluate_phase_a_candidate(manifests, trial, qa, repository=REPO).status,
                "invalid_evidence",
            )
        self.assertEqual(evaluate_phase_a_candidate(
            *phase_input(count=99), repository=REPO).status, "insufficient_observation")
        self.assertEqual(evaluate_phase_a_candidate(
            *phase_input(interval_minutes=10), repository=REPO).status,
            "insufficient_observation")
        false_qa = [{**qa[0], "verdict": "incorrect"}]
        self.assertEqual(evaluate_phase_a_candidate(
            manifests, receipts, false_qa, repository=REPO).status, "false_positive")
        self.assertFalse(evaluate_phase_a_candidate(
            manifests, receipts, false_qa, repository=REPO).release_authorized)
        bad_manifest = deepcopy(manifests)
        bad_manifest[0]["issues"][0]["mutations"] = 1
        self.assertEqual(evaluate_phase_a_candidate(
            bad_manifest, receipts, qa, repository=REPO).status, "invalid_evidence")
        self.assertEqual(run_cycle([18, 18], _NoPort()).state, "invalid_batch")
        self.assertEqual(run_cycle([True], _NoPort()).state, "invalid_batch")

    def test_sin_datos_reales(self) -> None:
        """AC-03: no network, remote writes, real receipts, tokens or PII."""
        blob, _ = archive()
        with mock.patch.object(urllib.request, "urlopen",
                               side_effect=AssertionError("external call")), \
             mock.patch.object(socket, "create_connection",
                               side_effect=AssertionError("network")), \
             mock.patch.object(subprocess, "run",
                               side_effect=AssertionError("shell command")):
            got = inspect_artifact(blob, META)
            manifests, receipts, qa = phase_input(count=2)
            phase = evaluate_phase_a_candidate(manifests, receipts, qa, repository=REPO)
            skipped = run_cycle([18], _NoPort())
        self.assertEqual(got["status"], "MATCHED_CANDIDATE")
        self.assertEqual(phase.status, "insufficient_observation")
        self.assertEqual(skipped.state, "feature_disabled")
        self.assertFalse(got["artifact_attested"])
        self.assertFalse(got["release_authorized"])
        self.assertFalse(phase.release_authorized)


if __name__ == "__main__":
    unittest.main()
