"""Factory #1553: contrato documental de continuidad de proveedores."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/continuidad-caida-proveedores.md"
IDS = {"GH-API", "GH-ACTIONS", "GH-IDENTIDAD", "CG-SESION", "CG-CUENTA", "MIXTO"}


def report():
    if not DOC.is_file():
        raise AssertionError("Falta docs/continuidad-caida-proveedores.md")
    return DOC.read_text(encoding="utf-8")


def table():
    rows = {}
    for line in report().splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] not in IDS:
            continue
        if len(cells) != 5 or cells[0] in rows:
            raise AssertionError("Matriz de escenarios inválida: " + line)
        rows[cells[0]] = cells[1:]
    return rows


class ContinuidadProveedoresTests(unittest.TestCase):
    def test_escenarios_separados(self):
        rows = table()
        self.assertEqual(set(rows), IDS)
        for ident, (scenario, source, state, action) in rows.items():
            with self.subTest(ident=ident):
                self.assertGreater(len(source), 48)
                self.assertEqual(state, "UNKNOWN")
                self.assertEqual(action, "SUSPENDER")
        self.assertIn("GitHub API", rows["GH-API"][0])
        self.assertIn("GitHub Actions", rows["GH-ACTIONS"][0])
        self.assertIn("GitHub App", rows["GH-IDENTIDAD"][0])
        self.assertIn("ChatGPT", rows["CG-SESION"][0])
        self.assertIn("ChatGPT", rows["CG-CUENTA"][0])
        self.assertIn("cuenta", rows["CG-CUENTA"][0])
        self.assertIn("sesión", rows["CG-SESION"][0])
        self.assertIn("simultáneamente", rows["MIXTO"][0])

    def test_fallo_cerrado_mutaciones(self):
        text = report()
        self.assertTrue(all(cells[-2:] == ["UNKNOWN", "SUSPENDER"] for cells in table().values()))
        for token in ("/tomar", "/liberar", "/transferir", "/renovar-contrato",
                      "commits", "push", "Issues/PR/tags", "merge", "rerun",
                      "Factory@v1", "deploy", "go-live", "Ninguna escritura",
                      "no prorrogada", "no autoriza un segundo intento de escritura",
                      "UNKNOWN", "PAUSED", "RECUPERACION_EN_VALIDACION",
                      "sin escritura"):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), text.casefold())
        for n in range(1, 7):
            self.assertIn(f"MESA-{n:02d}", text)
        self.assertRegex(text, r"MESA-01[^\n]*UNKNOWN; SUSPENDER")
        self.assertRegex(text, r"MESA-02[^\n]*UNKNOWN; SUSPENDER")
        self.assertRegex(text, r"MESA-04[^\n]*RECUPERACION_EN_VALIDACION; SUSPENDER")

    def test_reentrada_autenticada(self):
        text = report()
        section = text.split("## Reentrada autenticada: secuencia obligatoria", 1)[1].split("\n## ", 1)[0]
        steps = re.findall(r"(?m)^([1-7])\. \*\*([^\n]+?)\*\*", section)
        self.assertEqual([str(i) for i in range(1, 8)], [number for number, _ in steps])
        titles = [title for _, title in steps]
        for expected, title in zip(("Identidad autorizada", "Factory#767",
                                     "main y HEAD exactos", "reserva V3",
                                     "gates del SHA exacto", "bitácora offline",
                                     "Decidir reentrada"), titles):
            self.assertEqual(expected.casefold(), title.casefold())
        for key in ("autenticada", "RUNNING", "pl0n3r", "único marker v1", "main",
                    "SHA", "UUID", "owner", "fingerprint", "claims disjuntos",
                    "dependencias", "revocación", "Validar", "aceptación",
                    "SonarCloud", "CodeQL", "CodeRabbit", "D-069/D-070",
                    "freeze #921", "RECUPERACION_EN_VALIDACION", "READY_VERIFICADO"):
            with self.subTest(key=key):
                self.assertIn(key.casefold(), section.casefold())
        self.assertIn("no puede recuperarse desde texto guardado", section)
        self.assertRegex(text, r"MESA-06[^\n]*READY_VERIFICADO")

    def test_limites_sin_datos_reales(self):
        text = report()
        for token in ("RTO: UNKNOWN", "RPO: UNKNOWN", "no ejecuta failover automático",
                      "sin red", "custodio", "2FA", "MFA", "no hay medición real",
                      "PII", "datos reales", "secretos", "gastos", "compras",
                      "fuera de alcance", "sin efectos sobre runtime", "Factory@v1"):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), text.casefold())
        self.assertNotRegex(text, r"gh[pousr]_[A-Za-z0-9]{20,}")
        self.assertNotIn("-----BEGIN PRIVATE KEY-----", text)


if __name__ == "__main__":
    unittest.main()
