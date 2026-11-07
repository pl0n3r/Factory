"""Factory #2020: documental verification of 70 clauses with real local witnesses."""
from __future__ import annotations
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unicodedata
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-04.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
IDS = tuple(json.loads(r'''["docs/evolution-engine.md:L41-U1","docs/experience-guardrails.md:L4-U1","docs/experience-guardrails.md:L5-U1","docs/experience-guardrails.md:L11-U1","docs/experience-guardrails.md:L12-U1","docs/experience-guardrails.md:L13-U1","docs/experience-guardrails.md:L14-U1","docs/experience-guardrails.md:L15-U1","docs/experience-guardrails.md:L17-U1","docs/experience-guardrails.md:L24-U1","docs/experience-guardrails.md:L25-U1","docs/experience-guardrails.md:L27-U1","docs/experience-guardrails.md:L32-U1","docs/experience-guardrails.md:L36-U1","docs/experience-guardrails.md:L43-U1","docs/experience-guardrails.md:L44-U1","docs/experience-guardrails.md:L45-U1","docs/experience-guardrails.md:L46-U1","docs/experience-guardrails.md:L47-U1","docs/experience-guardrails.md:L49-U1","docs/experience-guardrails.md:L50-U1","docs/experience-guardrails.md:L53-U1","docs/experience-guardrails.md:L54-U1","docs/f2-caller-migration.md:L3-U1","docs/f2-caller-migration.md:L11-U1","docs/f2-caller-migration.md:L15-U1","docs/f2-caller-migration.md:L15-U2","docs/f2-caller-migration.md:L16-U1","docs/f2-caller-migration.md:L16-U2","docs/f2-caller-migration.md:L17-U1","docs/f2-caller-migration.md:L17-U2","docs/factory-queue.md:L3-U1","docs/factory-queue.md:L35-U1","docs/factory-queue.md:L39-U1","docs/factory-queue.md:L40-U1","docs/factory-queue.md:L41-U1","docs/factory-queue.md:L55-U1","docs/factory-queue.md:L63-U1","docs/factory-queue.md:L64-U1","docs/factory-queue.md:L65-U1","docs/factory-queue.md:L66-U1","docs/factory-queue.md:L67-U1","docs/factory-queue.md:L68-U1","docs/factory-queue.md:L69-U1","docs/factory-queue.md:L70-U1","docs/factory-queue.md:L72-U1","docs/factory-queue.md:L76-U1","docs/factory-queue.md:L76-U2","docs/factory-queue.md:L80-U1","docs/factory-queue.md:L84-U1","docs/factory-queue.md:L88-U1","docs/feedback-mesh-e2e.md:L3-U1","docs/feedback-mesh-e2e.md:L9-U1","docs/feedback-mesh-e2e.md:L10-U1","docs/feedback-mesh-e2e.md:L11-U1","docs/feedback-mesh-e2e.md:L12-U1","docs/feedback-mesh-e2e.md:L12-U2","docs/feedback-mesh-e2e.md:L20-U1","docs/feedback-mesh-e2e.md:L21-U1","docs/feedback-mesh-e2e.md:L22-U1","docs/feedback-mesh-e2e.md:L23-U1","docs/feedback-mesh-e2e.md:L24-U1","docs/feedback-mesh-e2e.md:L25-U1","docs/feedback-mesh-e2e.md:L25-U2","docs/feedback-mesh-e2e.md:L26-U1","docs/feedback-mesh-e2e.md:L27-U1","docs/feedback-mesh-e2e.md:L31-U1","docs/feedback-mesh-e2e.md:L33-U1","docs/feedback-mesh-e2e.md:L39-U1","docs/fitness-engine.md:L20-U1"]'''))
MODES = {"EVOLUCION_LOCAL", "EXPERIENCIA_LOCAL", "F2_LOCAL", "COLA_LOCAL", "FEEDBACK_LOCAL", "FITNESS_LOCAL"}
BT = chr(96)


def normalized(value: str) -> str:
    s = unicodedata.normalize("NFKD", value).casefold()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", s).strip()


def report_rows(text: str) -> list[tuple[str, str, str, str, str]]:
    sections = text.split("## Trazabilidad de las 70 unidades")
    if len(sections) != 2:
        raise ValueError("Invalid report heading")
    blocks = sections[1].split("## Validación y reversión")
    if len(blocks) != 2:
        raise ValueError("Missing report terminator")
    rows = []
    for line in blocks[0].splitlines():
        if not line.startswith("|") or line.startswith("| Fila exacta |") or line.startswith("| --- |"):
            continue
        fields = line.strip("|").strip().split(" | ")
        if len(fields) != 5 or any(not fields[i].startswith(BT) or not fields[i].endswith(BT) for i in (0, 1, 3)):
            raise ValueError("Malformed or unexpected report row")
        key, witness, mode, anchor, status = fields
        rows.append((key[1:-1], witness[1:-1], mode, anchor[1:-1], status))
    if len(rows) != 70 or tuple(r[0] for r in rows) != IDS:
        raise ValueError("Missing, duplicate, reordered or extra report clause")
    if any(r[4] != "NO_VERIFICABLE" for r in rows):
        raise ValueError("Unproven coverage promotion")
    return rows


def validate_sources(*, report_override=None, source_overrides=None, matrix_override=None):
    rows = report_rows(REPORT.read_text(encoding="utf-8") if report_override is None else report_override)
    source_overrides = source_overrides or {}
    matrix = MATRIX.read_text(encoding="utf-8") if matrix_override is None else matrix_override
    pattern = re.compile(r"^\| " + re.escape(BT) + r"([^" + BT + r"]+)" + re.escape(BT) +
                         r" \| (.*?) \| (NO_VERIFICABLE|SIN_COBERTURA|CUBIERTO|NO_APLICA) \|")
    inventory = {}
    for line in matrix.splitlines():
        match = pattern.match(line)
        if match:
            if match[1] in inventory:
                raise ValueError("Duplicate source in matrix")
            inventory[match[1]] = match[2], match[3]
    docs = {}
    witness_re = re.compile(r"tests/test_[\w]+\.py::[A-Za-z_]\w*::test_\w+")
    for key, witness, mode, anchor, status in rows:
        if key not in inventory or inventory[key][1] != status:
            raise ValueError("Missing/reclassified matrix clause " + key)
        if mode not in MODES or not anchor or len(anchor) > 145:
            raise ValueError("Invalid scope or anchor " + key)
        match = re.fullmatch(r"(docs/[\w.-]+\.md):L(\d+)-U\d+", key)
        if not match:
            raise ValueError("Invalid clause ID")
        path, n = match[1], int(match[2])
        if path not in docs:
            docs[path] = source_overrides.get(path, (ROOT / path).read_text(encoding="utf-8")).splitlines()
        if n > len(docs[path]):
            raise ValueError("Missing clause source")
        if normalized(anchor) not in normalized(docs[path][n-1]):
            raise ValueError("Document drift " + key)
        if normalized(anchor) not in normalized(inventory[key][0]):
            raise ValueError("Matrix clause drift " + key)
        if not witness_re.fullmatch(witness) or not (ROOT / witness.split("::")[0]).is_file():
            raise ValueError("False witness " + key)


class VerificacionFactory04Tests(unittest.TestCase):
    def test_70_filas_no_promocion(self):
        report = REPORT.read_text(encoding="utf-8")
        self.assertEqual(len(IDS), 70)
        self.assertEqual(len(set(IDS)), 70)
        self.assertEqual(len(report_rows(report)), 70)
        self.assertIn("0 promociones", report)
        self.assertIn("consolidación #2035", report)

    def test_fuentes_y_matriz_exactas(self):
        validate_sources()

    def test_testigos_conductuales_ejecutados(self):
        rows = report_rows(REPORT.read_text(encoding="utf-8"))
        witnesses = sorted({r[1] for r in rows})
        self.assertGreaterEqual(len(witnesses), 16)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        for ref in witnesses:
            with self.subTest(witness=ref):
                path, cls, method = ref.split("::")
                source = ROOT / path
                name = "_factory_verify04_" + source.stem
                if name not in sys.modules:
                    spec = importlib.util.spec_from_file_location(name, source)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    spec.loader.exec_module(module)
                suite = unittest.TestLoader().loadTestsFromName(cls + "." + method, sys.modules[name])
                output = io.StringIO()
                result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
                self.assertEqual(result.testsRun, 1, ref + ": " + output.getvalue())
                self.assertTrue(result.wasSuccessful(), ref + ": " + output.getvalue())

    def test_mutaciones_negativas(self):
        original = REPORT.read_text(encoding="utf-8")
        row = next(s for s in original.splitlines() if s.startswith("| " + BT + "docs/"))
        variants = (
            original.replace(row + "\n", "", 1),
            original.replace(row, row + "\n" + row, 1),
            original.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            original.replace(row, row.replace(IDS[0], "docs/falso.md:L1-U1"), 1),
            original.replace(row, row.replace("tests/test_", "tests/test_falso_", 1), 1),
            original.replace(row, row + "\n| " + BT + "docs/extra.md:L1-U1" + BT + " | testigo falso | EXTRA | ancla | NO_VERIFICABLE |", 1),
        )
        for n, variant in enumerate(variants):
            with self.subTest(variant=n), self.assertRaises(ValueError):
                validate_sources(report_override=variant)
        doc = "docs/evolution-engine.md"
        old = (ROOT / doc).read_text(encoding="utf-8")
        source_line = old.splitlines()[40]
        with self.assertRaises(ValueError):
            validate_sources(source_overrides={doc: old.replace(source_line, "ancla falsa", 1)})
        matrix = MATRIX.read_text(encoding="utf-8")
        prefix = "| " + BT + IDS[0] + BT + " |"
        line = next(x for x in matrix.splitlines() if x.startswith(prefix))
        with self.assertRaises(ValueError):
            validate_sources(matrix_override=matrix.replace(line, line.replace("Rollback solo es válido", "cláusula alterada"), 1))


if __name__ == "__main__":
    unittest.main()
