"""Factory #1566: contraste por comportamientos, no por frases aisladas."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/contraste-matriz-puertas_revisor.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
SOURCES = ["docs/puertas-humanas.md","docs/politica-revisor-externo.md","docs/immune-repair.md","docs/quality-health.md","AGENTES.md"]
COUNTS = {"docs/puertas-humanas.md":57,"docs/politica-revisor-externo.md":53,"docs/immune-repair.md":34,"docs/quality-health.md":32,"AGENTES.md":51}
COVERED = {"docs/puertas-humanas.md:B04":{"code":"template/.github/workflows/seguridad.yml","test":"tests/test_template_security_workflow_contract.py","pr":891,"sha":"4f042ae0044444f46d926543d86008258c977264"},"docs/immune-repair.md:B01":{"code":"evolution/immune.py","test":"tests/test_immune_repair.py","pr":214,"sha":"35c65b3c8553b7f7fb62361b8fc189971bdb0681"},"docs/immune-repair.md:B02":{"code":"evolution/repair.py","test":"tests/test_immune_repair.py","pr":214,"sha":"35c65b3c8553b7f7fb62361b8fc189971bdb0681"}}
ALLOWED = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "NO_APLICA", "DESCARTADO"}


def rows_from(doc: str) -> dict[str, list[str]]:
    rows = {}
    for line in doc.splitlines():
        if not line.startswith("| `") or ":B" not in line:
            continue
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            raise AssertionError("Fila requiere ocho columnas")
        key = cells[0].strip("`")
        if key in rows or cells[3] not in ALLOWED or not cells[2]:
            raise AssertionError("ID duplicado o estado inválido: " + key)
        if cells[1] != "`" + key.rsplit(":B", 1)[0] + "`":
            raise AssertionError("Identidad documental inconsistente")
        rows[key] = cells
    return rows


def require_canonical_leaf(row: list[str]) -> None:
    if row[3] == "SIN_COBERTURA":
        raise AssertionError("SIN_COBERTURA requiere hoja canónica auténtica, no épico")


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC.read_text(encoding="utf-8")
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.rows = rows_from(cls.doc)

    def test_cada_documento_tiene_veredicto(self) -> None:
        self.assertEqual(len(self.rows), 22)
        for source in SOURCES:
            with self.subTest(source=source):
                actual = [k for k in self.rows if k.startswith(source + ":B")]
                self.assertEqual(sorted(actual), [f"{source}:B{x:02}" for x in range(1, 7 if source == "docs/puertas-humanas.md" else 5)])
                self.assertTrue((ROOT / source).is_file())
        self.assertEqual(Counter(row[3] for row in self.rows.values()), Counter({"CUBIERTO": 3, "NO_VERIFICABLE": 19}))

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        actual = {key for key, row in self.rows.items() if row[3] == "CUBIERTO"}
        self.assertEqual(actual, set(COVERED), "Promoción sin PR y prueba verificados")
        for key, info in COVERED.items():
            with self.subTest(key=key):
                row = self.rows[key]
                self.assertTrue((ROOT / info["code"]).is_file())
                self.assertTrue((ROOT / info["test"]).is_file())
                self.assertIn(info["code"], row[4])
                self.assertIn(info["test"], row[5])
                self.assertIn(f"/pull/{info['pr']}", row[6])
                self.assertIn(info["sha"], row[6])
        for key, row in self.rows.items():
            if row[3] == "NO_VERIFICABLE":
                self.assertEqual(row[6], "—")
                self.assertGreater(len(row[7]), 30)

    def test_faltante_tiene_issue(self) -> None:
        for row in self.rows.values():
            require_canonical_leaf(row)
        with self.assertRaisesRegex(AssertionError, "hoja canónica"):
            require_canonical_leaf(["", "", "", "SIN_COBERTURA", "—", "—", "—", "#1082"])
        self.assertIn("Ninguna ausencia fue demostrada", self.doc)
        self.assertNotIn("Sin cobertura verificada en producción", self.doc)

    def test_puertas_y_revisor_no_omiten_excepciones(self) -> None:
        safe = self.rows["docs/puertas-humanas.md:B05"][2]
        privacy = self.rows["docs/puertas-humanas.md:B06"][2]
        rerun = self.rows["docs/politica-revisor-externo.md:B03"][2]
        for fragment in ("safe_default", "segura", "reversible"):
            self.assertIn(fragment, safe)
        for fragment in ("D-063", "nothing_live=true",
                         "no_real_customer_data=true", "bloquea"):
            self.assertIn(fragment, privacy)
        for fragment in ("SHA-less", "rerun", "OWNER",
                         "timeline REST autenticada"):
            self.assertIn(fragment, rerun)

    def test_credenciales_historicas_no_se_sobreatribuyen(self) -> None:
        for key in ("docs/immune-repair.md:B03",
                    "docs/immune-repair.md:B04",
                    "docs/quality-health.md:B02"):
            with self.subTest(key=key):
                self.assertEqual(self.rows[key][3], "NO_VERIFICABLE")
                self.assertEqual(self.rows[key][6], "—")
                self.assertNotIn(key, COVERED)
                self.assertIn("no acredita", self.rows[key][7])

    def test_matriz_actualizada(self) -> None:
        for source in SOURCES:
            self.assertIn(f"| `{source}` | {COUNTS[source]} |", self.matrix)
            self.assertFalse(any(line.startswith(f"| `{source}:L") for line in self.matrix.splitlines()))
        for key, row in self.rows.items():
            marker = f"| `{key}` |"
            matches = [line for line in self.matrix.splitlines() if line.startswith(marker)]
            self.assertEqual(len(matches), 1, key)
            self.assertIn(f"| {row[3]} |", matches[0])
        self.assertIn("## Contraste de comportamientos #1566", self.matrix)
        self.assertEqual(self.matrix.count("## Filas de cobertura"), 1)

if __name__ == "__main__":
    unittest.main()
