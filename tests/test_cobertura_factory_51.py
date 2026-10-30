"""Factory #1842: prueba las reglas ejecutables de resiliencia sin I/O remoto.

Las acciones de incidente/restore en proveedores son procedimientos operativos;
ningún fixture offline las hace pasar por evidencia de producción. No se lee la
matriz: este test permanece válido cuando una fila pasa a CUBIERTO.
"""
from __future__ import annotations

import copy
import io
import json
import socket
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from seguridad import resiliencia


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
CHECKS = ("repo_backup", "secrets_escrow", "token_rotation", "restore_drill")


def manifest_v2() -> dict[str, object]:
    """Prueba solo formato/vigencia; las referencias son ficticias."""
    return {
        "version": 2,
        "project": "fixture/resiliencia",
        "execution_mechanisms": {
            "ci": "github-token:ephemeral",
            "observer": "github-token:ephemeral",
            "deploy": "hostinger:git",
        },
        "cross_repo_write": {"required_mechanism": "github-app"},
        "checks": {
            name: {
                "verified_at": "2026-10-29T11:00:00Z",
                "evidence_ref": f"fixture/synthetic-{name}",
            }
            for name in CHECKS
        },
    }


def manifest_v1() -> dict[str, object]:
    """Fixture de diagnóstico histórico, nunca configuración de ejecución."""
    v2 = manifest_v2()
    return {
        "version": 1,
        "project": v2["project"],
        "identities": {
            "ci": "github-app:synthetic-ci",
            "deploy": "github-app:synthetic-deploy",
            "observer": "github-app:synthetic-observer",
        },
        "checks": v2["checks"],
    }


class CoberturaFactory51Tests(unittest.TestCase):
    def test_contrato_principal(self) -> None:
        # resiliencia-fabrica L7/L9, L24, L25 y L28: capacidades concretas,
        # tokens efímeros por trabajo y GitHub App como frontera cross-repo.
        operative = manifest_v2()
        self.assertIsNone(resiliencia.validate_manifest(operative, now=NOW))
        self.assertEqual(
            operative["execution_mechanisms"],
            {"ci": "github-token:ephemeral", "observer": "github-token:ephemeral", "deploy": "hostinger:git"},
        )
        self.assertEqual(operative["cross_repo_write"], {"required_mechanism": "github-app"})

        # L30-U1/U2: ejercer el límite de antigüedad, no solo la presencia de
        # campos. Un registro fechado exactamente hace 90 días es válido.
        boundary = copy.deepcopy(operative)
        boundary["checks"]["repo_backup"]["verified_at"] = (
            NOW - timedelta(days=90)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertIsNone(resiliencia.validate_manifest(boundary, now=NOW))
        self.assertCountEqual(operative["checks"].keys(), CHECKS)

        # L34-U1/U2 y L36: el parser v1 solo diagnostica datos históricos.
        legacy = manifest_v1()
        self.assertIsNone(resiliencia.validate_legacy_manifest(legacy, now=NOW))
        with self.assertRaisesRegex(resiliencia.ValidationError, "migrar a v2"):
            resiliencia.validate_manifest(legacy, now=NOW)

        # El CLI real prohíbe usar legacy como gate operativo.
        with patch.object(resiliencia.sys, "argv", ["resiliencia.py", "--manifest-stdin"]), \
             patch.object(resiliencia.sys, "stdin", io.StringIO(json.dumps(legacy))), \
             patch.object(resiliencia.sys, "stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as exited:
                resiliencia.main()
        self.assertEqual(exited.exception.code, 1)

    def test_falla_cerrado(self) -> None:
        base = manifest_v2()
        # Tokens persistentes, PATs, permisos excesivos o formato cross-repo
        # ambiguo no sustituyen el mecanismo aprobado (L24/L25/L28).
        cases = (
            {"execution_mechanisms": {**base["execution_mechanisms"], "ci": "github-token:persistent"}},
            {"execution_mechanisms": {**base["execution_mechanisms"], "observer": "personal-pat"}},
            {"execution_mechanisms": {**base["execution_mechanisms"], "deploy": "personal-pat"}},
            {"execution_mechanisms": {**base["execution_mechanisms"], "unknown": "github-token:ephemeral"}},
            {"cross_repo_write": {"required_mechanism": "github-token"}},
            {"cross_repo_write": {"required_mechanism": "personal-pat"}},
            {"cross_repo_write": {}},
            {"checks": {}},
            {"project": "owner/repo/subdir"},
            {"version": True},
            {"extra": "campo-no-autorizado"},
        )
        for change in cases:
            with self.subTest(change=change):
                doc = copy.deepcopy(base)
                doc.update(change)
                with self.assertRaises(resiliencia.ValidationError):
                    resiliencia.validate_manifest(doc, now=NOW)

        # L30: cada evidencia obligatoria es UTC estricto, no futura, no vieja,
        # con referencia sintética no sensible y estructura exacta.
        bad_check_values = (
            {"verified_at": "2026-10-29", "evidence_ref": "fixture/test"},
            {"verified_at": "2026-10-29T12:00:01Z", "evidence_ref": "fixture/test"},
            {"verified_at": "2026-07-31T11:59:59Z", "evidence_ref": "fixture/test"},
            {"verified_at": "2026-10-29T11:00:00+00:00", "evidence_ref": "fixture/test"},
            {"verified_at": "2026-10-29T11:00:00Z", "evidence_ref": "Bearer secret"},
            {"verified_at": "2026-10-29T11:00:00Z"},
        )
        for item in bad_check_values:
            with self.subTest(item=item):
                doc = copy.deepcopy(base)
                doc["checks"]["token_rotation"] = item
                with self.assertRaises(resiliencia.ValidationError):
                    resiliencia.validate_manifest(doc, now=NOW)

        with self.assertRaises(resiliencia.ValidationError):
            resiliencia.validate_manifest(base, now=datetime(2026, 10, 29, 12))
        with self.assertRaises(resiliencia.ValidationError):
            resiliencia.validate_legacy_manifest(manifest_v2(), now=NOW)
        legacy = manifest_v1()
        legacy["identities"]["observer"] = legacy["identities"]["ci"]
        with self.assertRaises(resiliencia.ValidationError):
            resiliencia.validate_legacy_manifest(legacy, now=NOW)

        # El auditor preventivo real impide escalada de permisos y eventos
        # privilegiados sin suponer que el CI en producción haya sucedido.
        safe = "name: Fixture\non: push\npermissions: read-all\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        self.assertIsNone(resiliencia.audit_workflow(safe))
        for bad in (
            "on: pull_request_target\n",
            "permissions: write-all\n",
            "permissions:\n  contents: write\n",
            "permissions: {contents: write}\n",
            "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n",
        ):
            with self.subTest(workflow=bad):
                with self.assertRaises(resiliencia.ValidationError):
                    resiliencia.audit_workflow(bad)

    def test_sin_datos_reales(self) -> None:
        # Los fixtures solo son JSON sintético, no se consulta hosting, secretos,
        # backups, red ni archivos de producción (L3, L62).
        with patch.object(socket, "socket", side_effect=AssertionError("red prohibida")):
            self.assertIsNone(resiliencia.validate_manifest(manifest_v2(), now=NOW))
            self.assertIsNone(resiliencia.validate_legacy_manifest(manifest_v1(), now=NOW))
            with patch.object(resiliencia, "_utc_now", return_value=NOW), \
                 patch.object(resiliencia.sys, "argv", ["resiliencia.py", "--manifest-stdin"]), \
                 patch.object(resiliencia.sys, "stdin", io.StringIO(json.dumps(manifest_v2()))), \
                 patch.object(resiliencia.sys, "stdout", new_callable=io.StringIO) as captured:
                self.assertEqual(resiliencia.main(), 0)
            self.assertIn("evidencia de recuperación validada", captured.getvalue())
        self.assertEqual(manifest_v2()["project"], "fixture/resiliencia")


if __name__ == "__main__":
    unittest.main()
