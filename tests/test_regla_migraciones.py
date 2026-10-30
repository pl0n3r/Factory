#!/usr/bin/env python3
"""Contrato offline de migraciones; jamás usa bases de datos ni red (#1955)."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unittest
from pathlib import Path

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PROJECTS = frozenset({"Condor", "GrindFlow", "brvtal", "ControlBot"})


def _object(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name}: se requiere objeto")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: cadena no vacía requerida")
    return value.strip()


def _count(value: object, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name}: entero no negativo requerido")
    return value


def validate_migration_description(value: object) -> dict[str, object]:
    """Valida evidencia estructural, NO acredita autenticidad de recibos reales."""
    data = _object(value, "migración")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("schema_version debe ser 1")
    if data.get("project") not in PROJECTS:
        raise ValueError("project fuera de los cuatro productos")
    migration_id = _text(data.get("migration_id"), "migration_id")

    backup = _object(data.get("verified_backup"), "verified_backup")
    receipt = _text(backup.get("receipt_id"), "verified_backup.receipt_id")
    digest = backup.get("sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("verified_backup.sha256: digest de 64 hex minúsculas requerido")
    if backup.get("verified") is not True:
        raise ValueError("verified_backup.verified debe ser true")
    _text(backup.get("verified_at_utc"), "verified_backup.verified_at_utc")

    rehearsal = _object(data.get("local_rehearsal"), "local_rehearsal")
    if rehearsal.get("environment") != "isolated_local_copy":
        raise ValueError("local_rehearsal.environment debe ser isolated_local_copy")
    _text(rehearsal.get("copy_id"), "local_rehearsal.copy_id")
    before = _count(rehearsal.get("rows_before"), "local_rehearsal.rows_before")
    after = _count(rehearsal.get("rows_after"), "local_rehearsal.rows_after")
    if before != after:
        _text(rehearsal.get("row_count_justification"), "local_rehearsal.row_count_justification")
    if rehearsal.get("passed") is not True:
        raise ValueError("local_rehearsal.passed debe ser true")

    rollback = _object(data.get("rollback_plan"), "rollback_plan")
    if rollback.get("backup_receipt_id") != receipt:
        raise ValueError("rollback_plan.backup_receipt_id no coincide con copia verificada")
    _text(rollback.get("trigger"), "rollback_plan.trigger")
    _text(rollback.get("restore_method"), "rollback_plan.restore_method")
    steps = rollback.get("steps")
    if not isinstance(steps, list) or not steps or any(
        not isinstance(step, str) or not step.strip() for step in steps
    ):
        raise ValueError("rollback_plan.steps: pasos no vacíos requeridos")
    verification = _object(rollback.get("verification"), "rollback_plan.verification")
    if _count(verification.get("expected_rows"), "rollback_plan.verification.expected_rows") != before:
        raise ValueError("rollback_plan.verification.expected_rows debe coincidir con rows_before")
    _text(verification.get("method"), "rollback_plan.verification.method")

    return {"migration_id": migration_id, "project": data["project"],
            "receipt_id": receipt, "rows_before": before, "rows_after": after,
            "result": "CONTRATO_OFFLINE_COMPLETO"}


def example() -> dict[str, object]:
    """Fixture sintética; el recibo y el checksum NO son reales."""
    return {
        "schema_version": 1, "project": "Condor", "migration_id": "fixture-1955",
        "verified_backup": {
            "receipt_id": "fixture-backup-001", "sha256": "a" * 64,
            "verified": True, "verified_at_utc": "2026-10-30T00:00:00Z",
        },
        "local_rehearsal": {
            "environment": "isolated_local_copy", "copy_id": "fixture-copy-001",
            "rows_before": 12, "rows_after": 14, "passed": True,
            "row_count_justification": "dos registros añadidos en fixture",
        },
        "rollback_plan": {
            "backup_receipt_id": "fixture-backup-001",
            "trigger": "fallo de integridad o error de migración",
            "restore_method": "restaurar copia verificada en entorno aislado",
            "steps": ["detener escrituras", "restaurar respaldo", "verificar integridad"],
            "verification": {"expected_rows": 12, "method": "conteo e integridad"},
        },
    }


class ReglaMigracionesTests(unittest.TestCase):
    def test_criterio_principal(self):
        for project in sorted(PROJECTS):
            with self.subTest(project=project):
                data = example()
                data["project"] = project
                self.assertEqual("CONTRATO_OFFLINE_COMPLETO", validate_migration_description(data)["result"])
        for missing in ("verified_backup", "local_rehearsal", "rollback_plan"):
            with self.subTest(missing=missing):
                data = example()
                del data[missing]
                with self.assertRaisesRegex(ValueError, missing):
                    validate_migration_description(data)

    def test_rechaza_copia_no_verificada_o_digest_invalido(self):
        for field, invalid in (("verified", False), ("verified", "true"),
                               ("sha256", "bad"), ("receipt_id", ""),
                               ("verified_at_utc", None)):
            with self.subTest(field=field, invalid=invalid):
                data = example()
                data["verified_backup"][field] = invalid
                with self.assertRaises(ValueError):
                    validate_migration_description(data)

    def test_rechaza_ensayo_no_aislado_o_conteos_invalidos(self):
        for field, invalid in (("environment", "production"), ("rows_before", True),
                               ("rows_after", -1), ("rows_after", "14"),
                               ("passed", False), ("copy_id", "")):
            with self.subTest(field=field, invalid=invalid):
                data = example()
                data["local_rehearsal"][field] = invalid
                with self.assertRaises(ValueError):
                    validate_migration_description(data)

    def test_conteo_distinto_exige_justificacion_y_cuando_igual_no(self):
        data = example()
        del data["local_rehearsal"]["row_count_justification"]
        with self.assertRaisesRegex(ValueError, "row_count_justification"):
            validate_migration_description(data)
        data["local_rehearsal"]["row_count_justification"] = "   "
        with self.assertRaisesRegex(ValueError, "row_count_justification"):
            validate_migration_description(data)
        data["local_rehearsal"]["rows_after"] = data["local_rehearsal"]["rows_before"]
        self.assertEqual("CONTRATO_OFFLINE_COMPLETO", validate_migration_description(data)["result"])

    def test_rechaza_plan_ausente_o_incompatible(self):
        for field, invalid in (("backup_receipt_id", "otro"), ("trigger", ""),
                               ("restore_method", None), ("steps", []),
                               ("steps", [""]), ("verification", {"expected_rows": 13, "method": "conteo"})):
            with self.subTest(field=field, invalid=invalid):
                data = example()
                data["rollback_plan"][field] = invalid
                with self.assertRaises(ValueError):
                    validate_migration_description(data)

    def test_validacion_no_muta_entrada(self):
        data = example()
        original = copy.deepcopy(data)
        validate_migration_description(data)
        self.assertEqual(original, data)
        for bad in (None, "", [], {}, {"schema_version": True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_migration_description(bad)

    def test_documento_cubre_cuatro_productos_y_limites(self):
        doc = (Path(__file__).resolve().parents[1] / "docs/regla-migraciones-datos.md").read_text(encoding="utf-8")
        for token in (*sorted(PROJECTS), "verified_backup", "local_rehearsal", "rollback_plan",
                      "rows_before", "rows_after", "--check-json", "NO ACREDITA"):
            with self.subTest(token=token):
                self.assertIn(token, doc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight offline de descripción de migración JSON")
    parser.add_argument("--check-json", metavar="RUTA", required=True)
    args = parser.parse_args()
    try:
        path = Path(args.check_json)
        if path.stat().st_size > 131072:
            raise ValueError("descripción excede 128 KiB")
        record = json.loads(path.read_text(encoding="utf-8"))
        result = validate_migration_description(record)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"RECHAZADO: {exc}", file=sys.stderr)
        return 1
    print("CONTRATO_OFFLINE_COMPLETO: " + result["project"] + " / " + result["migration_id"])
    return 0


if __name__ == "__main__":
    if "--check-json" in sys.argv:
        raise SystemExit(main())
    unittest.main()
