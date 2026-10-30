#!/usr/bin/env python3
"""Factory #1793: conducta offline de Performance/Recovery sin datos reales.

A acredita solamente código local; B/C requiere autoridad, observación externa
o una norma no reducible a un test. Nunca afirma producción ni backup real.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import runpy
import unittest

from performance.detector import PerformanceDetectionError, detect_performance
from performance.remediation import PerformanceRemediationError, evaluate_before_after, plan_remediation
from performance.status import derive_performance_status, readiness_projection
from performance.team_compiler_bridge import compile_performance_team
from performance.triage import triage_performance
from recovery.contract import RecoveryContractError, validate_recovery_manifest
from recovery.drill import RecoveryDrillError, build_restore_drill_plan, evaluate_restore_drill
from recovery.pipeline import RecoveryPipelineError, build_backup_pipeline, verify_backup_evidence
from recovery.status import WORK_ITEM_CLASSES, derive_recovery_health, project_recovery_readiness, recovery_work_item_classes

ROOT = Path(__file__).resolve().parents[1]

def fixtures(filename):
    """Reutilizar solo entradas sintéticas de los tests del kit ya ejecutados."""
    return runpy.run_path(str(ROOT / "tests" / filename))

A = frozenset({
    "ISSUE-304:AC-02", "ISSUE-304:AC-03", "ISSUE-304:AC-04",
    "ISSUE-304:AC-05", "ISSUE-304:AC-06", "ISSUE-304:AC-09",
    "ISSUE-304:AC-10",
    "ISSUE-305:AC-01", "ISSUE-305:AC-02", "ISSUE-305:AC-03",
    "ISSUE-305:AC-04", "ISSUE-305:AC-05", "ISSUE-305:AC-06",
    "ISSUE-305:AC-08", "ISSUE-305:AC-10",
})
B = {
    "ISSUE-304:AC-07": "crear WorkItem real en Factory Queue requiere GitHub autenticado",
    "ISSUE-304:AC-08": "ejecución de un fix y rollback real requiere autoridad y entorno",
    "ISSUE-304:AC-11": "E2E before/after de producción requiere observador autenticado",
    "ISSUE-305:AC-07": "restauración y RPO/RTO reales requieren backup y destino autorizado",
}
C = {"ISSUE-304:AC-12": "ausencia de scheduler paralelo es política arquitectónica"}

class CoberturaFactory02Tests(unittest.TestCase):
    """Pruebas sobre funciones reales, no el estado declarado en matriz."""

    def test_contrato_principal(self):
        self.assertEqual((len(A), len(B), len(C)), (15, 4, 1))
        self.assertEqual(len(A | B.keys() | C.keys()), 20)
        self.assertFalse((A & B.keys()) or (A & C.keys()) or (B.keys() & C.keys()))

        pd = fixtures("test_performance_detector.py")
        pr = fixtures("test_performance_remediation.py")
        rc = fixtures("test_cobertura_factory_48.py")
        contract = pd["contract"]()
        at = "2026-09-28T20:06:00Z"
        degraded = detect_performance(contract, pd["observation"](), evaluated_at=at)
        normal = detect_performance(contract, pd["observation"](value=220), evaluated_at=at)
        stale = detect_performance(
            contract, pd["observation"](observed_at="2026-09-28T19:00:00Z"), evaluated_at=at)
        team = compile_performance_team(degraded, evaluated_at=at)
        proposed = plan_remediation(pr["finding"](), pr["triage"](), pr["proposal"]())
        escalation = plan_remediation(pr["finding"](), pr["triage"](),
                                      pr["proposal"](triggered_conditions=["cost_change"]))
        before = pr["finding"]()
        after = pr["finding"](
            classification="PERF_INFO", breach=False,
            observed={**before["observed"], "value": 220, "observed_at": at},
            identity={"sha": "b" * 40, "release": "v1.2.4"}, evidence_ref="run:3")
        compared = evaluate_before_after(before, after)
        status = derive_performance_status(degraded)
        stale_status = derive_performance_status(stale)
        projection = readiness_projection(status)

        m = rc["manifest"]()
        pipeline = build_backup_pipeline(m, rc["backup_request"]())
        backup = verify_backup_evidence(m, pipeline, rc["backup_receipt"]())
        restore = build_restore_drill_plan(
            m, backup, {"kind": "disposable", "target_ref": "sandbox:synthetic"})
        drill = evaluate_restore_drill(m, restore, backup, rc["drill_receipt"]())
        health = derive_recovery_health(
            m, backup, drill, observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z")
        missing = derive_recovery_health(
            m, None, None, observed_at="2026-09-29T01:34:00Z")
        damaged = deepcopy(backup)
        damaged["checksum_sha256"] = "b" * 64
        blocked = derive_recovery_health(
            m, damaged, drill, observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z")

        proof = {
            "ISSUE-304:AC-02": (degraded["breach"] is True and
                                degraded["delta"] == 120 and
                                normal["classification"] == "PERF_INFO"),
            "ISSUE-304:AC-03": (team["decision"] == "TEAM_RECOMMENDED"
                                and team["primary"] == "dba"
                                and "qa" in team["roles"] and team["dispatch"] is False),
            "ISSUE-304:AC-04": (compared["decision"] == "ADOPT"
                                and compared["improved"] is True and compared["delta"] == -80),
            "ISSUE-304:AC-05": (proposed["decision"] == "AUTO_REPAIR"
                                and proposed["execute_actions"] is False
                                and proposed["work_item"]["work_id"] == "perf-condor-inventory-1"),
            "ISSUE-304:AC-06": (stale["evidence_state"] == "STALE"
                                and stale_status["status"] == "UNKNOWN"),
            "ISSUE-304:AC-09": (escalation["decision"] == "ESCALATE"
                                and escalation["human_gate_required"]
                                and escalation["reasons"] == ["cost_change"]),
            "ISSUE-304:AC-10": (status["status"] == "DEGRADED"
                                and projection["status"] == status["status"]
                                and projection["evidence_state"] == status["evidence_state"]),
            "ISSUE-305:AC-01": validate_recovery_manifest(m)["version"] == 1,
            "ISSUE-305:AC-02": (validate_recovery_manifest(m)["protection"]
                                == {"copies": 3, "media_types": 2, "offsite_copies": 1,
                                    "immutable_copies": 1, "undetected_restore_failures": 0}),
            "ISSUE-305:AC-03": (backup["encrypted"] is True
                                and backup["checksum_sha256"] == "a" * 64),
            "ISSUE-305:AC-04": ([d["provider"] for d in pipeline["destinations"]]
                                == ["object_storage", "google_drive"]
                                and pipeline["execute"] is False),
            "ISSUE-305:AC-05": ([s["kind"] for s in pipeline["steps"]]
                                == ["snapshot", "checksum", "encrypt", "upload_primary",
                                    "verify_primary", "cold_copy", "record_evidence"]),
            "ISSUE-305:AC-06": (backup["status"] == "VERIFIED"
                                and bool(backup["evidence_refs"])
                                and backup["immutable_version_ref"] == "version:synthetic"),
            "ISSUE-305:AC-08": (restore["execute"] is False
                                and restore["authority"] == "unchanged"
                                and health["execute"] is False
                                and project_recovery_readiness(missing, critical=True)["ready"] is False),
            "ISSUE-305:AC-10": (set(recovery_work_item_classes(blocked)) <= set(WORK_ITEM_CLASSES)
                                and blocked["state"] == "BLOCKED"
                                and project_recovery_readiness(blocked, critical=True)["ready"] is False),
        }
        self.assertEqual(set(A), set(proof))
        for row, valid in proof.items():
            with self.subTest(row=row):
                self.assertTrue(valid, "no se acreditó comportamiento ejecutable")

    def test_falla_cerrado(self):
        pd = fixtures("test_performance_detector.py")
        pr = fixtures("test_performance_remediation.py")
        rc = fixtures("test_cobertura_factory_48.py")
        for bad in (
            {"sample_count": 1}, {"window_seconds": 1},
            {"observed_at": "2026-09-28T19:00:00Z"},
        ):
            with self.subTest(evidence=bad):
                result = detect_performance(
                    pd["contract"](), pd["observation"](**bad),
                    evaluated_at="2026-09-28T20:06:00Z")
                self.assertNotEqual(result["evidence_state"], "CURRENT")
                self.assertEqual(result["classification"], "PERF_REVIEW")
        with self.assertRaises(PerformanceDetectionError):
            detect_performance(
                pd["contract"](), pd["observation"](evidence_ref="user@example.test"),
                evaluated_at="2026-09-28T20:06:00Z")
        with self.assertRaises(PerformanceRemediationError):
            plan_remediation(pr["finding"](), pr["triage"](),
                             pr["proposal"](triggered_conditions=[["cost_change"]]))
        self.assertEqual(
            plan_remediation(pr["finding"](), pr["triage"](),
                             pr["proposal"](within_authority=False))["decision"],
            "ESCALATE")

        m = rc["manifest"]()
        malformed = deepcopy(m)
        malformed["unknown"] = True
        with self.assertRaises(RecoveryContractError):
            validate_recovery_manifest(malformed)
        pipeline = build_backup_pipeline(m, rc["backup_request"]())
        bad_receipt = rc["backup_receipt"]()
        bad_receipt["encrypted"] = False
        with self.assertRaises(RecoveryPipelineError):
            verify_backup_evidence(m, pipeline, bad_receipt)
        good = verify_backup_evidence(m, pipeline, rc["backup_receipt"]())
        with self.assertRaises(RecoveryDrillError):
            build_restore_drill_plan(
                m, good, {"kind": "production", "target_ref": "prod:forbidden"})
        self.assertEqual("UNKNOWN", derive_recovery_health(
            m, None, None, observed_at="2026-09-29T01:34:00Z")["state"])

    def test_sin_datos_reales(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        modules = {node.module.split(".")[0] for node in ast.walk(tree)
                   if isinstance(node, ast.ImportFrom) and node.module}
        modules |= {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
        self.assertFalse(modules & {
            "requests", "httpx", "urllib", "socket", "subprocess",
            "playwright", "selenium", "psycopg2", "pymysql",
        })
        self.assertEqual(len(A | B.keys() | C.keys()), 20)
        self.assertTrue(all("requiere" in reason or "requieren" in reason
                            for reason in B.values()))
        m = fixtures("test_cobertura_factory_48.py")["manifest"]()
        self.assertEqual(m["project"], "synthetic-factory")
        self.assertEqual(m["encryption"]["key_material"], "EXTERNAL_ONLY")
        exported = json.dumps(m)
        self.assertNotIn("-----BEGIN", exported)
        self.assertNotIn("Bearer ", exported)

if __name__ == "__main__":
    unittest.main()
