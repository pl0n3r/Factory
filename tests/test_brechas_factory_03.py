"""Factory #1621: pruebas sintéticas de contratos Recovery y aceptación.

Un descriptor VERIFIED o un HEALTHY de fixtures NO prueban backup, restore
offsite, RPO/RTO reales ni permiso para activar producción.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import unittest

from recovery.adapters import build_adapter_descriptor, supported_providers, RecoveryAdapterError
from recovery.contract import validate_recovery_manifest, RecoveryContractError
from recovery.pipeline import build_backup_pipeline, verify_backup_evidence, RecoveryPipelineError
from recovery.drill import build_restore_drill_plan, evaluate_restore_drill, RecoveryDrillError
from recovery.status import derive_recovery_health, project_recovery_readiness, WORK_ITEM_CLASSES
from scripts.aceptacion_kit import parse_contract, AcceptanceError, REQUIRED_HEADINGS

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = tuple(f"ISSUE-305:AC-{n:02d}" for n in (2, 3, 4, 5, 6, 7, 8, 10, 11, 12))
DOC = "docs/aceptacion-ejecutable.md"
DOCUMENT = tuple(f"{DOC}:L{n}-U1" for n in (12, 14, 15, 16, 17, 18))
IDS = RECOVERY + DOCUMENT
UNKNOWN = "UNKNOWN"
GAPS = {"ISSUE-305:AC-12": "UNKNOWN: la simulación no ejecuta copias, offsite ni restores reales"}


def manifest():
    return {
        "version": 1, "project": "ejemplo-sintetico",
        "target": {"rpo_minutes": 15, "rto_minutes": 60},
        "protection": {"copies": 3, "media_types": 2, "offsite_copies": 1,
                       "immutable_copies": 1, "undetected_restore_failures": 0},
        "retention": {"hourly": 24, "daily": 7, "weekly": 8, "monthly": 12},
        "sources": {"database": "REQUIRED", "media": "NOT_APPLICABLE",
                    "repository": "REQUIRED"},
        "offsite": {"object_storage": "REQUIRED", "cold_copy": "google_drive"},
        "encryption": {"required": True, "key_material": "EXTERNAL_ONLY"},
        "restore_drill": {"cadence_days": 7},
    }


def synthetic_flow():
    m = manifest()
    request = {
        "source": "database", "backup_id": "backup:001", "snapshot_ref": "snapshot:001",
        "encrypted_ref": "encrypted:001", "object_storage_ref": "object:001",
        "cold_copy_ref": "drive:001", "checksum_sha256": "a" * 64,
        "idempotency_key": "backup:001",
    }
    plan = build_backup_pipeline(m, request)
    evidence = {
        "backup_id": "backup:001", "source": "database", "checksum_sha256": "a" * 64,
        "encrypted": True, "primary_verified": True, "primary_ref": "object:001",
        "immutable_version_ref": "version:001", "cold_copy_verified": True,
        "cold_copy_ref": "drive:001", "created_at": "2026-09-29T01:20:00Z",
        "verified_at": "2026-09-29T01:21:00Z",
        "evidence_refs": ["run:backup:001", "offsite:drive:001"],
    }
    backup = verify_backup_evidence(m, plan, evidence)
    restore = build_restore_drill_plan(
        m, backup, {"kind": "disposable", "target_ref": "sandbox:001"}
    )
    result = evaluate_restore_drill(m, restore, backup, {
        "backup_id": "backup:001", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": "2026-09-29T01:25:00Z",
        "started_at": "2026-09-29T01:26:00Z",
        "completed_at": "2026-09-29T01:31:00Z",
        "evidence_refs": ["drill:001", "health:001", "smoke:001", "integrity:001"],
    })
    return m, request, plan, evidence, backup, restore, result


def issue_body():
    sections = {
        "### Contexto": "Contexto aislado.",
        "### Alcance": "Contrato verificable.",
        "### Fuera de alcance": "Producción y clientes.",
        "### Criterios de aceptación": "- [ ] [AC-01] Criterio de prueba.",
        "### Contrato ejecutable": (
            '<!-- factory-acceptance {"version":1,"criteria":'
            '[{"id":"AC-01","kind":"check","target":"Tests de scripts"}]} -->'
        ),
    }
    return "\n\n".join(h + "\n\n" + v for h, v in sections.items())


def matrix_rows(raw):
    if not isinstance(raw, str):
        raise ValueError("Matriz ausente")
    result = {}
    for line in raw.splitlines():
        cols = tuple(x.strip() for x in line.strip().strip("|").split("|"))
        key = cols[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in result or len(cols) != 5 or not all(cols[:4]):
            raise ValueError("Fila ambigua")
        if cols[2] != "NO_VERIFICABLE":
            raise ValueError("Cobertura no acreditada")
        result[key] = cols
    if set(result) != set(IDS):
        raise ValueError("Fila ausente")
    return result


def assess(matrix, evidence):
    verdict = {unit: UNKNOWN for unit in IDS}
    try:
        matrix_rows(matrix)
    except ValueError:
        return verdict
    if type(evidence) is not dict or set(evidence) != set(IDS):
        return verdict
    if any(type(value) is not bool for value in evidence.values()):
        return verdict
    return {
        unit: "OFFLINE_VERIFIED" if evidence[unit] and unit not in GAPS else UNKNOWN
        for unit in IDS
    }


def recovery_evidence():
    m, req, plan, proof, backup, restore, drill = synthetic_flow()
    normalized = validate_recovery_manifest(m)
    exact_protection = tuple(normalized["protection"][k] for k in (
        "copies", "media_types", "offsite_copies", "immutable_copies",
        "undetected_restore_failures",
    )) == (3, 2, 1, 1, 0)
    ac02 = (exact_protection and normalized["target"] == m["target"]
            and normalized["retention"] == m["retention"]
            and normalized["sources"]["media"] == "NOT_APPLICABLE")

    def rejected(fn, error):
        try:
            fn()
        except error:
            return True
        return False

    extra = dict(m, unexpected="field")
    wrong_destination = deepcopy(m)
    wrong_destination["offsite"]["object_storage"] = "OPTIONAL"
    secret_request = dict(req, backup_id="ghp_" + "Z" * 24)
    missing_immutable = dict(proof)
    del missing_immutable["immutable_version_ref"]
    ac03 = all((
        rejected(lambda: validate_recovery_manifest(extra), RecoveryContractError),
        rejected(lambda: validate_recovery_manifest(wrong_destination), RecoveryContractError),
        rejected(lambda: build_backup_pipeline(m, secret_request), RecoveryPipelineError),
        rejected(lambda: verify_backup_evidence(m, plan, missing_immutable), RecoveryPipelineError),
    ))
    descriptor_req = {
        "provider": "object_storage", "operation": "upload",
        "object_ref": "object:001", "checksum_sha256": "a" * 64,
        "idempotency_key": "upload:001",
    }
    adapter = build_adapter_descriptor(m, descriptor_req)
    different = build_adapter_descriptor(m, dict(descriptor_req, idempotency_key="upload:002"))
    ac04 = (adapter == build_adapter_descriptor(m, descriptor_req)
            and adapter["descriptor_id"] != different["descriptor_id"]
            and adapter["checksum_sha256"] == "a" * 64
            and adapter["execute"] is False
            and set(supported_providers()) == {"object_storage", "google_drive"}
            and rejected(lambda: build_adapter_descriptor(
                m, dict(descriptor_req, provider="icloud")), RecoveryAdapterError))
    ac05 = (
        [x["kind"] for x in plan["steps"]] == [
            "snapshot", "checksum", "encrypt", "upload_primary",
            "verify_primary", "cold_copy", "record_evidence",
        ] and [x["provider"] for x in plan["destinations"]]
        == ["object_storage", "google_drive"] and plan["pipeline_state"] == "PLANNED"
        and plan["execute"] is False
    )
    ac06 = (backup["status"] == "VERIFIED" and backup["encrypted"] is True
            and bool(backup["evidence_refs"])
            and rejected(lambda: verify_backup_evidence(
                m, plan, dict(proof, encrypted=False)), RecoveryPipelineError))
    ac07 = (restore["target"]["kind"] == "disposable"
            and {"validate_checksum", "decrypt", "restore", "health",
                 "smoke", "integrity"}.issubset(x["kind"] for x in restore["steps"])
            and drill["status"] == "PASSED"
            and drill["observed"]["rto_seconds"] == 300
            and drill["checks"] == {"health": True, "smoke": True, "integrity": True})
    ac08 = (rejected(lambda: build_restore_drill_plan(
        m, backup, {"kind": "production", "target_ref": "prod:001"}), RecoveryDrillError)
        and all(row["authority"] == "unchanged" and row["execute"] is False
                for row in (plan, backup, restore, drill)))
    missing = derive_recovery_health(m, None, None, observed_at="2026-09-29T01:34:00Z")
    no_drill = derive_recovery_health(m, backup, None,
                                     observed_at="2026-09-29T01:34:00Z")
    ac10 = (
        set(WORK_ITEM_CLASSES) == {"backup_missing", "backup_stale", "offsite_missing",
                                  "checksum_failed", "restore_drill_failed",
                                  "rpo_breached", "rto_breached", "retention_drift"}
        and set(missing["work_item_classes"]).issubset(WORK_ITEM_CLASSES)
        and set(no_drill["work_item_classes"]).issubset(WORK_ITEM_CLASSES)
    )
    ac11 = all(
        row["state"] in {"BLOCKED", "UNKNOWN"}
        and project_recovery_readiness(row, critical=True)["ready"] is False
        and project_recovery_readiness(row, critical=True)["recovery_health"] == row["state"]
        for row in (missing, no_drill)
    )
    # AC-12 queda UNKNOWN: el flujo sintético no produce recibos de proveedores.
    ac12 = (backup["source"] == "database" and drill["status"] == "PASSED"
            and "snapshot_ref" not in backup and "encrypted_ref" not in backup
            and drill["observed"]["rpo_seconds"] == 300)
    return dict(zip(RECOVERY, (ac02, ac03, ac04, ac05, ac06, ac07,
                                ac08, ac10, ac11, ac12), strict=True))


def document_evidence():
    doc = (ROOT / DOC).read_text(encoding="utf-8")
    valid = issue_body()
    passed = len(parse_contract(valid)) == 1
    checks = {}
    for heading in REQUIRED_HEADINGS:
        absent = valid.replace(heading, "### Otro", 1)
        duplicate = valid + "\n\n" + heading + "\n\nDuplicada."
        start = valid.index(heading + "\n\n") + len(heading) + 2
        end = valid.find("\n\n### ", start)
        if end < 0:
            end = len(valid)
        empty = valid[:start] + valid[end:]
        failures = 0
        for mutated in (absent, duplicate, empty):
            try:
                parse_contract(mutated)
            except AcceptanceError:
                failures += 1
        checks[heading] = failures == 3 and heading in doc
    return dict(zip(DOCUMENT, (
        passed and len(REQUIRED_HEADINGS) == 5 and all(checks.values()),
        *(checks[name] for name in REQUIRED_HEADINGS),
    ), strict=True))


class BrechasFactory03Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        rows = matrix_rows(matrix)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(rows), 16)
        evidence = {**recovery_evidence(), **document_evidence()}
        self.assertEqual(set(evidence), set(IDS))
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertEqual(rows[unit][2], "NO_VERIFICABLE")
                self.assertTrue(evidence[unit], unit)
        results = assess(matrix, evidence)
        self.assertEqual({x for x in IDS if results[x] == UNKNOWN}, set(GAPS))

    def test_falla_cerrado(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        line = next(x for x in matrix.splitlines() if chr(96)+IDS[0]+chr(96) in x)
        for broken in (None, "", matrix.replace(line, "", 1),
                       matrix + "\n" + line,
                       matrix.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO", 1))):
            with self.subTest(case=str(broken)[:30]):
                with self.assertRaises(ValueError):
                    matrix_rows(broken)
                self.assertEqual(set(assess(broken, {x: True for x in IDS}).values()),
                                 {UNKNOWN})
        for invalid in (None, {}, {IDS[0]: True}, {x: 1 for x in IDS},
                        {**{x: True for x in IDS}, "extra": True}):
            self.assertEqual(set(assess(matrix, invalid).values()), {UNKNOWN})

    def test_sin_datos_reales(self):
        source = (ROOT / "tests/test_brechas_factory_03.py").read_text(encoding="utf-8")
        imports = {name.name.split(".")[0] for node in ast.walk(ast.parse(source))
                   if isinstance(node, ast.Import) for name in node.names}
        self.assertFalse(imports & {"requests", "socket", "subprocess", "urllib"})
        self.assertTrue(all(x.startswith("UNKNOWN:") for x in GAPS.values()))
        self.assertEqual(len(set(IDS)), 16)
        m, _, plan, _, backup, restore, result = synthetic_flow()
        self.assertEqual(m["encryption"]["key_material"], "EXTERNAL_ONLY")
        self.assertTrue(all(x["execute"] is False for x in (plan, backup, restore, result)))

    def test_estados_unknown_explicitos(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        evidence = {**recovery_evidence(), **document_evidence()}
        states = assess(matrix, evidence)
        self.assertEqual(states["ISSUE-305:AC-12"], UNKNOWN)
        for unit in IDS:
            with self.subTest(unit=unit):
                self.assertNotEqual(states[unit], "PRODUCTION_GREEN")
                self.assertEqual(assess(matrix, {**evidence, unit: False})[unit], UNKNOWN)
                self.assertEqual(assess(matrix, {unit: True})[unit], UNKNOWN)
        m, _, _, _, backup, _, drill = synthetic_flow()
        health = derive_recovery_health(
            m, backup, drill, observed_at="2026-09-29T01:34:00Z",
            drill_observed_at="2026-09-29T01:32:00Z")
        self.assertEqual(health["state"], "HEALTHY")
        self.assertIs(health["execute"], False)


if __name__ == "__main__":
    unittest.main()
