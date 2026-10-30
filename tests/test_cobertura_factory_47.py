"""Factory #1838: adaptadores de recuperación comprobados con código real.

Solo fakes y contratos declarativos. No interpreta el historial de Issues como
prueba de un sistema live, ni consulta la matriz de cobertura.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest

from recovery.adapters import (
    RecoveryAdapterError, build_adapter_descriptor,
    canonical_adapter_descriptor, supported_providers,
)

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = "docs/recovery-adapters.md:"

# Las diez unidades de contrato funcional están en el alcance de tests.
OFFLINE = frozenset(RECOVERY + key for key in (
    "L13-U1", "L15-U1", "L17-U1", "L18-U1", "L19-U1", "L25-U1",
    "L7-U1", "L7-U2", "L8-U1", "L9-U1",
))

# Históricos/afirmaciones editoriales sin función actual que pueda probarse.
POLICY = {
    "docs/readme-contract.md:B04": "La prohibición de mover main es una regla operativa; un test offline no valida workflows remotos.",
    "docs/reconciliacion-issues-20261024.md:L20-U1": "Ocho Issues son un recuento histórico, no comportamiento del runtime.",
    "docs/reconciliacion-issues-20261024.md:L20-U2": "Cero cierres del corte histórico es evidencia documental, no un algoritmo de aceptación actual.",
    "docs/reconciliacion-issues-20261024.md:L20-U3": "La prohibición de cerrar por commits parciales es política de coordinación.",
    "docs/reconciliacion-issues-20261024.md:L21-U1": "No publicar v1 ni activar leases es límite de autoridad humana, no acto testable con fixtures.",
    "docs/reconciliacion-issues-20261024.md:L21-U2": "La ruta reclamada de aquella hoja es un dato de coordinación histórico.",
    "docs/reconciliacion-issues-20261024.md:L22-U1": "La obligación de releer fuentes exactas es un procedimiento, no una prueba de su ejecución.",
    "docs/reconciliacion-issues-20261024.md:L22-U2": "El documento no acredita estados posteriores a su corte histórico.",
    "docs/reconciliacion-issues-20261024.md:L5-U1": "El cierre integral de un Issue requiere recibos reales, no un test sintético.",
}
EXTERNAL = {
    "docs/readme-progress-readiness.md:B04":
        "GREEN de los siete productos exige evidencia real y fresca por producto, inaccesible desde este test offline.",
}


def support():
    """Carga fixtures sintéticos existentes sin ejecutar ningún transporte."""
    p = ROOT / "tests" / "test_recovery_adapters.py"
    spec = importlib.util.spec_from_file_location("factory47_recovery_support", p)
    if spec is None or spec.loader is None:
        raise AssertionError("Falta test_recovery_adapters.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(test_name):
    """Ejecuta la regresión previa, con sus aserciones de comportamiento."""
    mod = support()
    suite = unittest.TestLoader().loadTestsFromName(
        f"RecoveryAdaptersTests.{test_name}", mod
    )
    result = unittest.TestResult()
    suite.run(result)
    if result.testsRun != 1 or not result.wasSuccessful():
        raise AssertionError(
            f"Regresión real {test_name}: {result.testsRun}, "
            f"{result.failures!r}, {result.errors!r}"
        )


class CoberturaFactory47Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: diez predicados reales y diez límites B/C explícitos."""
        self.assertEqual((len(OFFLINE), len(POLICY), len(EXTERNAL)), (10, 9, 1))
        self.assertEqual(len(OFFLINE | POLICY.keys() | EXTERNAL.keys()), 20)
        mod = support()
        primary = build_adapter_descriptor(mod.manifest(), mod.request())
        self.assertEqual(primary["role"], "primary_offsite")
        self.assertEqual(primary["provider"], "object_storage")
        self.assertEqual(primary["project"], "condor")
        self.assertEqual(primary["authority"], "unchanged")
        self.assertIs(primary["execute"], False)
        self.assertEqual(primary["operation"], "upload")
        self.assertEqual(primary["checksum_sha256"], "a" * 64)
        self.assertEqual(primary["idempotency_key"], "backup:condor:001")
        self.assertEqual(primary["object_ref"], "backup:20260928:001")
        self.assertEqual(primary["namespace"], "recovery:condor")
        self.assertEqual(len(primary["descriptor_id"]), 64)
        self.assertEqual(
            canonical_adapter_descriptor(mod.manifest(), mod.request()),
            canonical_adapter_descriptor(mod.manifest(), copy.deepcopy(mod.request())),
        )

        cold = build_adapter_descriptor(
            mod.manifest(), mod.request(provider="google_drive", operation="verify")
        )
        self.assertEqual((cold["role"], cold["provider"]), ("cold_copy", "google_drive"))
        self.assertEqual(supported_providers(), ("google_drive", "object_storage"))
        self.assertNotIn("icloud", supported_providers())

        for test in (
            "test_object_storage_and_google_drive_cold_copy_are_opaque_idempotent_and_checksum_aware",
            "test_object_storage_remains_primary_and_icloud_is_not_supported",
            "test_adapter_contract_is_declarative_external_io_free_and_non_authorizing",
        ):
            with self.subTest(regression=test):
                exercise(test)

    def test_falla_cerrado(self):
        """AC-02: forma cerrada, providers, referencias y checksum seguros."""
        mod = support()
        baseline = mod.request()
        invalid = (
            {**baseline, "provider": "icloud"},
            {**baseline, "operation": "delete"},
            {**baseline, "object_ref": "../out"},
            {**baseline, "object_ref": "https://invalid.test/x"},
            {**baseline, "checksum_sha256": "NOT_SHA"},
            {**baseline, "idempotency_key": "../unsafe"},
            {**baseline, "extra": "unexpected"},
        )
        for bad in invalid:
            with self.subTest(fields=sorted(bad)):
                with self.assertRaises(RecoveryAdapterError):
                    build_adapter_descriptor(mod.manifest(), bad)
        with self.assertRaises(RecoveryAdapterError):
            build_adapter_descriptor(
                mod.manifest("NOT_APPLICABLE"),
                mod.request(provider="google_drive"),
            )
        exercise("test_invalid_sensitive_or_unsafe_adapter_input_fails_closed_without_echo")

    def test_sin_datos_reales(self):
        """AC-03: fixture documental sin red ni payload de cliente/credencial."""
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("import" + " requests", source)
        self.assertNotIn("import" + " urllib", source)
        self.assertNotIn("url" + "open(", source)
        self.assertNotIn("token=" + "supersecretvalue", source)
        self.assertTrue(all("test_recovery_adapters.py" != s for s in EXTERNAL))
        self.assertFalse(OFFLINE & POLICY.keys())
        self.assertFalse(OFFLINE & EXTERNAL.keys())
        self.assertFalse(POLICY.keys() & EXTERNAL.keys())


if __name__ == "__main__":
    unittest.main()
