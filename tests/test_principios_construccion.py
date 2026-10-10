"""AC #1091: regresión sobre documentación y lección reales."""
import json
import re
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs/principios-construccion.md"
LESSON = ROOT / "lecciones/registros/principios-construccion.jsonl"


class PrincipiosConstruccionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOCUMENT.read_text(encoding="utf-8")

    def test_regla_cero_y_ocho_invariantes_con_fuentes(self):
        self.assertRegex(self.doc, r"(?m)^## Regla 0 — diseñar primero para ejecución en paralelo$")
        self.assertEqual([str(i) for i in range(1, 9)],
                         re.findall(r"(?m)^## Principio ([1-8]) — ", self.doc))
        for source in ("Factory/issues/1082", "Factory/issues/1081",
                       "Factory/issues/1080", "Factory/issues/1075",
                       "Factory/issues/1072", "ControlBot/issues/760",
                       "ControlBot/issues/761"):
            self.assertIn("https://github.com/pl0n3r/" + source, self.doc)
        self.assertIn("dependencia real de datos", self.doc)
        self.assertIn("paralelismo **demostrable**", self.doc)

    def test_limites_human_only_y_d068_no_se_relajan(self):
        for term in ("D-068", "D-063", "D-059", "go-live", "gasto",
                     "credenciales/secretos", "datos reales de clientes",
                     "destrucción irreversible", "legal/privacidad",
                     "puerta vigente", "**no** autorización autoejecutable"):
            self.assertIn(term, self.doc)
        self.assertIn("**No elimina aprobación humana**", self.doc)
        self.assertIn("no autoriza merges", self.doc)

    def test_claims_compartidos_y_evidencia_unknown_permanecen_fail_closed(self):
        for term in ("diff exact-SHA", "falla cerrado", "README.md",
                     "config/version.php", "package-lock.json", "lockfiles",
                     "merge-train", "hunks distintos", "UNKNOWN",
                     "VALIDATED_IN_PRODUCTION", "updated_at",
                     "agentes activos verificados / capacidad de agentes disponible verificada"):
            self.assertIn(term, self.doc)
        self.assertIn("no** se excluyen del arbitraje", self.doc)
        self.assertIn("no acreditan que un agente esté activo", self.doc)

    def test_leccion_jsonl_trazable_y_sin_secretos(self):
        lines = LESSON.read_text(encoding="utf-8").splitlines()
        self.assertEqual(1, len(lines))
        item = json.loads(lines[0])
        self.assertEqual({"id", "project", "kind", "occurred_at", "what",
                          "why", "prevention", "source"}, set(item))
        self.assertEqual("pl0n3r/factory", item["project"])
        self.assertEqual("process", item["kind"])
        self.assertEqual("https://github.com/pl0n3r/Factory/issues/1082", item["source"])
        self.assertEqual(0, datetime.fromisoformat(
            item["occurred_at"].replace("Z", "+00:00")).utcoffset().total_seconds())
        for field in ("what", "why", "prevention"):
            self.assertTrue(5 <= len(item[field]) <= 280)
        self.assertLess(len(lines[0]), 2048)
        self.assertNotRegex(lines[0], r"(?i)(?:ghp_|github_pat_|sk-[A-Za-z0-9]{12}|-----BEGIN|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})")


if __name__ == "__main__":
    unittest.main()
