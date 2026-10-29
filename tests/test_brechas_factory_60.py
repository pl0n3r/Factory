"""Factory #1678: 16 brechas Recovery; pruebas exclusivamente sintéticas.

No acreditan backup, restore, servicio remoto, aprobación live ni PR fusionado.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
import re
import unittest

from recovery.drill import build_restore_drill_plan, evaluate_restore_drill
from recovery.pipeline import (
    RecoveryPipelineError, build_backup_pipeline, verify_backup_evidence,
)
from recovery.status import (
    WORK_ITEM_CLASSES, derive_recovery_health, project_recovery_readiness,
    recovery_work_item_classes,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
LOCAL = "CONTRATO_LOCAL"
MATRIX = "docs/matriz-cobertura.md"
E2E = "docs/recovery-e2e.md"
PIPE = "docs/recovery-pipeline.md"
STATUS = "docs/recovery-status.md"
CLAUSES = {
    "docs/recovery-e2e.md:L18-U2": (E2E, "consume solo el artefacto verificado/offsite"),
    "docs/recovery-e2e.md:L21-U1": (E2E, "backup fresco + drill PASSED"),
    "docs/recovery-e2e.md:L22-U1": (E2E, "drill vigente con RPO/RTO excedidos"),
    "docs/recovery-e2e.md:L22-U2": (E2E, "un recovery point stale"),
    "docs/recovery-pipeline.md:L5-U1": (PIPE, "Flujo canónico"),
    "docs/recovery-pipeline.md:L7-U1": (PIPE, "Object storage siempre"),
    "docs/recovery-pipeline.md:L7-U2": (PIPE, "Google Drive solo"),
    "docs/recovery-pipeline.md:L9-U1": (PIPE, "verify_backup_evidence()"),
    "docs/recovery-status.md:L13-U2": (STATUS, "La comprobación es determinista"),
    "docs/recovery-status.md:L13-U3": (STATUS, "Esos recibos siguen pendientes"),
    "docs/recovery-status.md:L15-U1": (STATUS, "El payload incluye razones explicables"),
    "docs/recovery-status.md:L17-U1": (STATUS, "Para recovery crítico"),
    "docs/recovery-status.md:L21-U1": (STATUS, "Un fixture válido mantiene"),
    "docs/recovery-status.md:L21-U2": (STATUS, "no acredita backup real ni restore"),
    "docs/recovery-status.md:L6-U1": (STATUS, "HEALTHY"),
    "docs/recovery-status.md:L7-U1": (STATUS, "DEGRADED"),
}
IDS = tuple(CLAUSES)
PATHS = frozenset({MATRIX, E2E, PIPE, STATUS})
GAPS = frozenset({
    "docs/recovery-status.md:L13-U2",
    "docs/recovery-status.md:L13-U3",
    "docs/recovery-status.md:L21-U2",
})


def read_sources() -> dict[str, str]:
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in PATHS}


def matrix_rows(text: str) -> dict[str, tuple[str, ...]]:
    if type(text) is not str or not text.strip():
        raise ValueError("UNKNOWN: matriz ausente")
    rows: dict[str, tuple[str, ...]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = tuple(x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        if not cells:
            continue
        key = cells[0].strip("`")
        if key not in CLAUSES:
            continue
        if (key in rows or len(cells) != 5 or not all(cells[:4])
                or cells[2] != "NO_VERIFICABLE"):
            raise ValueError("UNKNOWN: fila duplicada/inválida " + key)
        rows[key] = cells
    if set(rows) != set(IDS):
        raise ValueError("UNKNOWN: filas ausentes")
    return rows


def doc_matches(key: str, data: dict[str, str]) -> bool:
    if key not in CLAUSES:
        return False
    path, phrase = CLAUSES[key]
    src = data.get(path)
    match = re.search(r":L([1-9]\d*)-U[1-9]\d*$", key)
    if type(src) is not str or not match:
        return False
    number = int(match.group(1))
    lines = src.splitlines()
    if len(lines) < number:
        return False
    return phrase.casefold() in lines[number - 1].casefold()


def manifest() -> dict:
    return {
        "version": 1, "project": "factory",
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


def backup_bundle() -> tuple[dict, dict]:
    m = manifest()
    pipeline = build_backup_pipeline(m, {
        "source": "database", "backup_id": "backup:synthetic:001",
        "snapshot_ref": "snapshot:synthetic:001",
        "encrypted_ref": "encrypted:synthetic:001",
        "object_storage_ref": "object:synthetic:001",
        "cold_copy_ref": "drive:synthetic:001",
        "checksum_sha256": "a" * 64,
        "idempotency_key": "backup:synthetic:001",
    })
    backup = verify_backup_evidence(m, pipeline, {
        "backup_id": "backup:synthetic:001", "source": "database",
        "checksum_sha256": "a" * 64, "encrypted": True,
        "primary_verified": True, "primary_ref": "object:synthetic:001",
        "immutable_version_ref": "version:synthetic:001",
        "cold_copy_verified": True, "cold_copy_ref": "drive:synthetic:001",
        "created_at": "2026-09-29T01:20:00Z",
        "verified_at": "2026-09-29T01:21:00Z",
        "evidence_refs": ["run:synthetic:001", "offsite:synthetic:001"],
    })
    return pipeline, backup


def drill_bundle(backup: dict, breached: bool = False) -> tuple[dict, dict]:
    m = manifest()
    restore = build_restore_drill_plan(m, backup, {
        "kind": "disposable", "target_ref": "sandbox:synthetic:001",
    })
    observed = {
        "backup_id": "backup:synthetic:001", "checksum_sha256": "a" * 64,
        "health_ok": True, "smoke_ok": True, "integrity_ok": True,
        "incident_at": "2026-09-29T01:25:00Z",
        "started_at": "2026-09-29T01:26:00Z",
        "completed_at": "2026-09-29T01:31:00Z",
        "evidence_refs": ["drill:synthetic:001"],
    }
    if breached:
        observed.update({
            "incident_at": "2026-09-29T01:36:00Z",
            "started_at": "2026-09-29T01:37:00Z",
            "completed_at": "2026-09-29T02:40:00Z",
        })
    return restore, evaluate_restore_drill(m, restore, backup, observed)


def behavioral_evidence() -> dict[str, bool]:
    m = manifest()
    pipe, backup = backup_bundle()
    restore, drill = drill_bundle(backup)
    _, breached = drill_bundle(backup, breached=True)
    healthy = derive_recovery_health(
        m, backup, drill,
        observed_at="2026-09-29T01:34:00Z",
        drill_observed_at="2026-09-29T01:32:00Z",
    )
    degraded = derive_recovery_health(
        m, backup, breached,
        observed_at="2026-09-29T02:42:00Z",
        drill_observed_at="2026-09-29T02:41:00Z",
    )
    retention = derive_recovery_health(
        m, backup, drill,
        observed_at="2026-09-29T01:34:00Z",
        drill_observed_at="2026-09-29T01:32:00Z",
        retention_drift=True,
    )
    missing = derive_recovery_health(
        m, None, None, observed_at="2026-09-29T01:34:00Z",
    )
    invalid = deepcopy(backup)
    invalid["destinations"] = []
    blocked = derive_recovery_health(
        m, invalid, drill,
        observed_at="2026-09-29T01:34:00Z",
        drill_observed_at="2026-09-29T01:32:00Z",
    )
    bad_unicode = deepcopy(backup)
    bad_unicode["evidence_refs"] = ["run:synthetic:001", "ref:" + chr(0xD800)]
    invalid_utf8 = derive_recovery_health(
        m, bad_unicode, drill,
        observed_at="2026-09-29T01:34:00Z",
        drill_observed_at="2026-09-29T01:32:00Z",
    )
    wrong_pipeline = deepcopy(pipe)
    wrong_pipeline["checksum_sha256"] = "b" * 64
    try:
        verify_backup_evidence(m, wrong_pipeline, {})
    except (RecoveryPipelineError, ValueError):
        fail_closed = True
    else:
        fail_closed = False
    roles = [(d["provider"], d["role"]) for d in pipe["destinations"]]
    order = [step["kind"] for step in pipe["steps"]]
    projected = project_recovery_readiness(healthy, critical=True)
    unknown_projected = project_recovery_readiness(missing, critical=True)
    blocked_projected = project_recovery_readiness(blocked, critical=True)
    degraded_projected = project_recovery_readiness(degraded, critical=True)
    checks = (
        restore["target"]["kind"] == "disposable"
        and "snapshot_ref" not in backup and "encrypted_ref" not in backup
        and restore["execute"] is False,
        healthy["state"] == "HEALTHY" and drill["status"] == "PASSED"
        and projected["recovery_health"] == "HEALTHY"
        and projected["recalculated"] is False,
        degraded["state"] == "DEGRADED"
        and {"rpo_breached", "rto_breached"} <= set(degraded["work_item_classes"]),
        degraded["state"] == "DEGRADED"
        and "backup_stale" in degraded["work_item_classes"],
        order == ["snapshot", "checksum", "encrypt", "upload_primary",
                  "verify_primary", "cold_copy", "record_evidence"]
        and pipe["pipeline_state"] == "PLANNED" and pipe["execute"] is False,
        ("object_storage", "primary_offsite") in roles
        and pipe["requirements"]["primary_offsite_required"] is True,
        ("google_drive", "cold_copy") in roles
        and pipe["requirements"]["cold_copy_required"] is True,
        backup["status"] == "VERIFIED"
        and backup["authority"] == "unchanged" and fail_closed,
        "La comprobación es determinista y declarativa" in
        (ROOT / STATUS).read_text(encoding="utf-8"),
        "Esos recibos siguen pendientes" in
        (ROOT / STATUS).read_text(encoding="utf-8"),
        set(recovery_work_item_classes(degraded)) <= WORK_ITEM_CLASSES
        and {"backup_stale", "rpo_breached", "rto_breached"}
        <= set(recovery_work_item_classes(degraded)),
        unknown_projected["ready"] is False
        and blocked_projected["ready"] is False
        and degraded_projected["recovery_health"] == "DEGRADED"
        and degraded_projected["recalculated"] is False,
        healthy["state"] == "HEALTHY" and invalid_utf8["state"] == "BLOCKED"
        and invalid_utf8["execute"] is False,
        "no acredita backup real ni restore" in
        (ROOT / STATUS).read_text(encoding="utf-8"),
        backup["status"] == "VERIFIED" and healthy["state"] == "HEALTHY"
        and drill["status"] == "PASSED",
        retention["state"] == "DEGRADED"
        and "retention_drift" in retention["work_item_classes"],
    )
    return dict(zip(IDS, checks, strict=True))


def local_verdict(data: object, key: str) -> str:
    """No reutiliza pruebas obsoletas tras modificar fuentes."""
    if type(data) is not dict or set(data) != PATHS or key not in CLAUSES:
        return UNKNOWN
    if any(type(v) is not str or not v for v in data.values()):
        return UNKNOWN
    try:
        matrix_rows(data[MATRIX])
        if not doc_matches(key, data) or key in GAPS:
            return UNKNOWN
        # Solo contratos locales: jamás una afirmación de backup o restore real.
        return LOCAL if behavioral_evidence()[key] else UNKNOWN
    except (ValueError, KeyError, TypeError, IndexError, OSError):
        return UNKNOWN


def remote_verdict(_key: str) -> str:
    """Sin recibos auténticos de proveedores, RPO/RTO o autorización live."""
    return UNKNOWN


class BrechasFactory60Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = read_sources()

    def test_contrato_principal(self):
        rows, checks = matrix_rows(self.data[MATRIX]), behavioral_evidence()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(checks), set(IDS))
        for key in IDS:
            with self.subTest(key=key):
                self.assertTrue(doc_matches(key, self.data))
                self.assertTrue(checks[key], "brecha sin aserción: " + key)
                self.assertEqual("NO_VERIFICABLE", rows[key][2])
                self.assertEqual(UNKNOWN if key in GAPS else LOCAL,
                                 local_verdict(self.data, key))

    def test_falla_cerrado(self):
        original = self.data[MATRIX]
        line = next(x for x in original.splitlines()
                    if x.startswith("| `" + IDS[0] + "` |"))
        for mutated in (
            None, "", original.replace(line, "", 1),
            original + "\n" + line,
            original + "\n  " + line,
            original.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO")),
            original.replace(line, "| `" + IDS[0] + "` |"),
        ):
            with self.subTest(mutated=str(mutated)[-40:]):
                with self.assertRaises(ValueError):
                    matrix_rows(mutated)
        for key in IDS:
            bad = dict(self.data)
            bad[CLAUSES[key][0]] = ""
            self.assertEqual(UNKNOWN, local_verdict(bad, key))
        self.assertEqual(UNKNOWN, local_verdict({}, IDS[0]))
        self.assertEqual(UNKNOWN, local_verdict(self.data, "id:not-known"))

    def test_sin_datos_reales(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {n.module.split(".")[0] for n in ast.walk(tree)
                   if isinstance(n, ast.ImportFrom) and n.module}
        imports |= {alias.name.split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.Import) for alias in n.names}
        self.assertFalse(imports & {
            "requests", "httpx", "socket", "urllib", "subprocess", "boto3",
        })
        self.assertNotIn("-----BEGIN " + "PRIVATE KEY-----", source)
        self.assertNotRegex(source, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
        self.assertEqual(set(read_sources()), PATHS)
        _, b = backup_bundle()
        self.assertFalse(b["execute"])
        self.assertEqual(b["authority"], "unchanged")

    def test_estados_unknown_explicitos(self):
        rows = matrix_rows(self.data[MATRIX])
        self.assertEqual(len(GAPS), 3)
        for key in IDS:
            with self.subTest(key=key):
                self.assertEqual("NO_VERIFICABLE", rows[key][2])
                self.assertEqual(UNKNOWN, remote_verdict(key))
                if key in GAPS:
                    self.assertEqual(UNKNOWN, local_verdict(self.data, key))
        self.assertFalse(project_recovery_readiness(
            derive_recovery_health(
                manifest(), None, None, observed_at="2026-09-29T01:34:00Z",
            ), critical=True,
        )["ready"])


if __name__ == "__main__":
    unittest.main()
