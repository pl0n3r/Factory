"""Factory #1953: custodia sin secretos y rotación de claves simuladas."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "custodia-y-rotacion-credenciales.md"

# Patrones reconocibles de credenciales reales, sin incorporar muestras de valores.
SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{12,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?im)^\s*(?:password|access_token|api_key|secret_key)\s*[:=]\s*['\"]?[^\s'\"]{12,}"),
)


class CustodiaRotacionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")

    def test_criterio_principal(self) -> None:
        """AC-01: inventario, rotación y ensayo verificables sin credenciales."""
        self.assertIn("## Inventario de custodia", self.doc)
        self.assertIn("## Procedimiento ante credencial comprometida", self.doc)
        self.assertIn("## Ensayo offline con credenciales ficticias", self.doc)
        for heading in ("Clase de acceso o cuenta", "Custodia (sin valores)", "Última revisión", "Comprobación pendiente"):
            self.assertIn(heading, self.doc)
        for category in ("GitHub App", "GitHub Actions", "Llaves", "Segundo factor (2FA)", "DNS/TLS"):
            self.assertIn(category, self.doc)
        self.assertGreaterEqual(self.doc.count("Pendiente: dueño / live"), 6)
        for verb in ("Contener", "Revocar primero", "Generar nueva", "Actualizar custodia privada", "Verificar funcionamiento y revocación", "Cerrar con evidencia"):
            self.assertIn(verb, self.doc)
        self.assertIn("NAME_FILE", self.doc)
        self.assertIn("No registrar un estado", self.doc)
        self.assertEqual(self.find_sensitive_values(self.doc), [])

    @staticmethod
    def find_sensitive_values(content: str) -> list[str]:
        """Retorna clases detectadas, no valores que puedan filtrarse al CI."""
        return [f"patrón-{index}" for index, p in enumerate(SENSITIVE_PATTERNS, 1) if p.search(content)]

    def test_patrones_no_se_escapan_en_el_inventario(self) -> None:
        """Un cambio que introduzca un secreto plausible debe fallar cerrado."""
        self.assertEqual(self.find_sensitive_values(self.doc), [])
        self.assertTrue(self.find_sensitive_values("password = " + "X" * 22))
        self.assertTrue(self.find_sensitive_values("AKIA" + "Q" * 16))
        self.assertTrue(self.find_sensitive_values("github_pat_" + "Z" * 40))
        self.assertTrue(self.find_sensitive_values("-----BEGIN PRIVATE KEY-----"))

    def test_rotacion_ficticia_revoca_primero(self) -> None:
        """Simulacro aislado: antigua revocada antes de activar la nueva."""
        old, new = "CLAVE_SIMULADA_ANTIGUA", "CLAVE_SIMULADA_NUEVA"
        self.assertIn(old, self.doc)
        self.assertIn(new, self.doc)
        active = {old}
        with tempfile.TemporaryDirectory(prefix="factory-rotacion-simulada-") as temp:
            private_file = Path(temp) / "credencial-simulada.txt"
            active.remove(old)  # Revocación explícita; no usar el valor en logs.
            self.assertNotIn(old, active)
            private_file.write_text(new, encoding="utf-8")
            private_file.chmod(0o600)
            active.add(new)
            self.assertNotIn(old, active)
            self.assertIn(new, active)
            self.assertEqual(private_file.read_text(encoding="utf-8"), new)
            self.assertEqual(private_file.stat().st_mode & 0o777, 0o600)
        self.assertFalse(private_file.exists())

    def test_no_presentar_simulacro_como_evidencia_productiva(self) -> None:
        self.assertIn("no valida el proveedor real", self.doc)
        self.assertIn("no admite rollback a la clave anterior", self.doc)
        self.assertIn("registro privado", self.doc)


if __name__ == "__main__":
    unittest.main()
