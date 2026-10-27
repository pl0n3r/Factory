#!/usr/bin/env python3
"""Factory #1570: integridad del contraste de 189 cláusulas."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/matriz-cobertura.md"
DOCUMENT = ROOT / "docs/contraste-factory_resto_2.md"
SOURCES = {
    "docs/cumplimiento-datos-licencias.md": (13, "seguridad/cumplimiento.py", "seguridad/test_cumplimiento.py"),
    "docs/derived-views.md": (21, "intelligence/derived_views.py", "tests/test_derived_views.py"),
    "docs/dod-compiler.md": (24, "intelligence/dod_compiler.py", "tests/test_dod_compiler.py"),
    "docs/evaluacion-agentes.md": (17, "metricas/evaluar_agentes.py", "metricas/test_evaluar_agentes.py"),
    "docs/evolution-engine.md": (10, "evolution/engine.py", "tests/test_evolution_engine.py"),
    "docs/experience-guardrails.md": (22, "evolution/experience_guardrails.py", "tests/test_experience_guardrails.py"),
    "docs/f2-caller-migration.md": (8, "scripts/f2_caller_preflight.py", "tests/test_f2_caller_preflight.py"),
    "docs/factory-queue.md": (20, "scripts/work_origin.py", "tests/test_factory_queue_e2e.py"),
    "docs/feedback-mesh-e2e.md": (18, "feedback/data/feedback-mesh-e2e.json", "tests/test_feedback_mesh_e2e.py"),
    "docs/fitness-engine.md": (15, "evolution/fitness.py", "tests/test_fitness_engine.py"),
    "docs/growth-pruning.md": (21, "evolution/growth.py", "tests/test_growth_pruning.py"),
}
STATES = {"CUBIERTO", "NO_VERIFICABLE", "SIN_COBERTURA", "DESCARTADO", "NO_APLICA"}


def rows(document: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for line in document.splitlines():
        matched = re.match(r"^\| \x60([^\x60]+)\x60 \| ", line)
        if matched is None:
            continue
        key = matched[1]
        if not any(key.startswith(source + ":") for source in SOURCES):
            continue
        if key in found:
            raise ValueError("Fila duplicada: " + key)
        cols = [cell.strip() for cell in re.split(r"(?<!\\)\|", line)]
        if len(cols) < 7 or cols[3] not in STATES:
            raise ValueError("Fila sin estado válido: " + key)
        found[key] = {"line": line, "state": cols[3]}
    return found


class ContrasteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = MATRIX.read_text(encoding="utf-8")
        cls.document = DOCUMENT.read_text(encoding="utf-8")
        cls.expected = rows(cls.matrix)
        cls.actual = rows(cls.document)

    def test_cada_fila_tiene_veredicto(self) -> None:
        self.assertEqual(189, len(self.expected))
        self.assertEqual(set(self.expected), set(self.actual))
        self.assertEqual(
            Counter(key.split(":")[0] for key in self.actual),
            Counter({source: count for source, (count, _, _) in SOURCES.items()}),
        )
        for key, row in self.actual.items():
            self.assertIn(row["state"], STATES, key)
            self.assertIn("[fuente](" + Path(key.split(":")[0]).name + ")", row["line"], key)

    def test_cubierto_enlaza_prueba_existente(self) -> None:
        for source, (_, implementation, test) in SOURCES.items():
            with self.subTest(source=source):
                self.assertTrue((ROOT / source).is_file())
                self.assertTrue((ROOT / implementation).is_file())
                self.assertTrue((ROOT / test).is_file())
        for key, row in self.actual.items():
            if row["state"] != "CUBIERTO":
                continue
            evidence = re.search(
                r"((?:tests|metricas|seguridad)/[\w/.-]+\.py)::([A-Za-z_]\w*)::(test_[A-Za-z_]\w*)",
                row["line"],
            )
            self.assertIsNotNone(evidence, key)
            test_path = ROOT / evidence[1]
            self.assertTrue(test_path.is_file(), key)
            self.assertIn("def " + evidence[3] + "(", test_path.read_text(encoding="utf-8"), key)
            self.assertRegex(row["line"], r"github\.com/pl0n3r/Factory/pull/\d+")

    def test_faltante_tiene_issue(self) -> None:
        for key, row in self.actual.items():
            if row["state"] == "SIN_COBERTURA":
                self.assertRegex(row["line"], r"github\.com/pl0n3r/Factory/issues/\d+")
                self.assertNotIn("issues/1570", row["line"], key)
        fake = "| " + chr(96) + "docs/dod-compiler.md:L1-U1" + chr(96) + " | X | INVALIDO | c | t | prueba |"
        with self.assertRaises(ValueError):
            rows(fake)
        valid = fake.replace("INVALIDO", "NO_VERIFICABLE")
        with self.assertRaises(ValueError):
            rows(valid + "\n" + valid)

    def test_matriz_actualizada(self) -> None:
        self.assertIn("## Contraste Factory, bloque 2 (#1570)", self.matrix)
        self.assertIn("main@8088e66c2366f2483d5229fc6fda8718f1ab46a0", self.matrix)
        self.assertEqual(set(self.expected), set(self.actual))
        for key, info in self.actual.items():
            source = self.expected[key]
            self.assertEqual(info["state"], source["state"], key)
            self.assertIn("contraste-factory_resto_2.md", source["line"], key)


if __name__ == "__main__":
    unittest.main()
