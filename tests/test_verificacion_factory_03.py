"""Factory #2019: verificar 70 filas exactas del lote 02, sin promoción externa.

Tests conductuales existentes de coordinación, costos, cumplimiento y vistas.
"""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-03.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
ROWS = tuple(tuple(row) for row in json.loads(r'''[["docs/derived-views.md:L3-U2","tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views","DERIVED_VIEWS_LOCAL","la vista solo materializa o verifica esa información"],["docs/derived-views.md:L9-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views","DERIVED_VIEWS_LOCAL","view id identificador estable"],["docs/derived-views.md:L10-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views","DERIVED_VIEWS_LOCAL","source fuente canónica y sus referencias"],["docs/derived-views.md:L11-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_declares_canonical_source_and_views","DERIVED_VIEWS_LOCAL","view superficie derivada"],["docs/derived-views.md:L12-U1","tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic","DERIVED_VIEWS_LOCAL","mode generated si existe un generador seguro o regression cuando la fu"],["docs/derived-views.md:L13-U1","tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic","DERIVED_VIEWS_LOCAL","generator función determinista obligatoria para generated"],["docs/derived-views.md:L14-U1","tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic","DERIVED_VIEWS_LOCAL","drift check test guard que impide publicar una vista divergente"],["docs/derived-views.md:L18-U1","tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic","DERIVED_VIEWS_LOCAL","un generador debe ser una función pura sin red reloj aleatoriedad ni e"],["docs/derived-views.md:L18-U2","tests/test_derived_views.py::DerivedViewsTests::test_generation_is_deterministic","DERIVED_VIEWS_LOCAL","la misma instantánea normalizada de la fuente debe producir exactament"],["docs/derived-views.md:L24-U1","tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed","DERIVED_VIEWS_LOCAL","el guard compara la salida esperada con la vista comprometida y falla "],["docs/derived-views.md:L24-U2","tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed","DERIVED_VIEWS_LOCAL","no se debe arreglar la fuente para hacer pasar el check ni aceptar la "],["docs/derived-views.md:L28-U1","tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed","DERIVED_VIEWS_LOCAL","la regresión debe comprobar claims concretos contra la fuente canónica"],["docs/derived-views.md:L28-U2","tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed","DERIVED_VIEWS_LOCAL","esto permite proteger una vista mientras se evita inventar una extracc"],["docs/derived-views.md:L34-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","no debe convertir el readme en fuente de verdad"],["docs/derived-views.md:L38-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","identifique la fuente canónica"],["docs/derived-views.md:L39-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","registre la vista en el manifiesto"],["docs/derived-views.md:L40-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","elija generated solo si puede demostrar determinismo y ausencia de efe"],["docs/derived-views.md:L40-U2","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","de lo contrario use regression"],["docs/derived-views.md:L41-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","añada un drift check determinista"],["docs/derived-views.md:L42-U1","tests/test_derived_views.py::DerivedViewsTests::test_manifest_rejects_self_referential_source","DERIVED_VIEWS_LOCAL","documente el límite y la reversión"],["docs/dod-compiler.md:L3-U1","tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts","DOD_LOCAL","definition of done compiler deriva el contrato de evidencia que debe e"],["docs/dod-compiler.md:L5-U1","tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts","DOD_LOCAL","solo produce requisitos verificables por máquina a partir de la tarea "],["docs/dod-compiler.md:L6-U1","tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts","DOD_LOCAL","project dna validado"],["docs/dod-compiler.md:L12-U1","tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts","DOD_LOCAL","change type code database ci docs security o"],["docs/dod-compiler.md:L14-U1","tests/test_dod_compiler.py::DodCompilerTests::test_different_changes_compile_different_done_contracts","DOD_LOCAL","surfaces superficies afectadas por ejemplo api web"],["docs/dod-compiler.md:L16-U1","tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants","DOD_LOCAL","risk low medium high o unknown"],["docs/dod-compiler.md:L18-U1","tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants","DOD_LOCAL","project dna aporta el fingerprint y el conocimiento verificable del so"],["docs/dod-compiler.md:L24-U1","tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants","DOD_LOCAL","ci requerida"],["docs/dod-compiler.md:L25-U1","tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants","DOD_LOCAL","cero hallazgos de revisión abiertos"],["docs/dod-compiler.md:L26-U1","tests/test_dod_compiler.py::DodCompilerTests::test_every_contract_keeps_factory_invariants","DOD_LOCAL","alcance limitado a rutas reclamadas"],["docs/dod-compiler.md:L34-U1","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","código tests del scope análisis estático"],["docs/dod-compiler.md:L35-U1","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","base de datos verify plan backup y compatibilidad de esquema"],["docs/dod-compiler.md:L36-U1","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","ci validación de workflow ejecución representativa"],["docs/dod-compiler.md:L37-U1","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","docs lint y links"],["docs/dod-compiler.md:L38-U1","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","seguridad scan casos negativos"],["docs/dod-compiler.md:L39-U1","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","riesgo medio alto plan de rollback"],["docs/dod-compiler.md:L39-U2","tests/test_dod_compiler.py::DodCompilerTests::test_evidence_targets_are_machine_verifiable","DOD_LOCAL","riesgo alto añade smoke exact sha"],["docs/dod-compiler.md:L48-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","safe fallback y exige además de las invariantes"],["docs/dod-compiler.md:L50-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","suite completa"],["docs/dod-compiler.md:L51-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","análisis estático"],["docs/dod-compiler.md:L52-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","security scan"],["docs/dod-compiler.md:L53-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","rollback plan"],["docs/dod-compiler.md:L54-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","completar contexto antes de promoción"],["docs/dod-compiler.md:L56-U1","tests/test_dod_compiler.py::DodCompilerTests::test_unknown_context_fails_safe_instead_of_weakening_done","DOD_LOCAL","así ignorancia nunca equivale a menos evidencia"],["docs/evaluacion-agentes.md:L7-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_ranking_is_separate_by_task_type_and_deterministic","AGENTS_EVALUATION_LOCAL","campos obligatorios"],["docs/evaluacion-agentes.md:L13-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_ranking_is_separate_by_task_type_and_deterministic","AGENTS_EVALUATION_LOCAL","el validador rechaza campos desconocidos duplicados por task id número"],["docs/evaluacion-agentes.md:L17-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","una configuración solo entra al ranking al alcanzar la muestra mínima"],["docs/evaluacion-agentes.md:L19-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","mayor tasa de éxito"],["docs/evaluacion-agentes.md:L20-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","menos incidentes posteriores por tarea"],["docs/evaluacion-agentes.md:L21-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","mayor tasa de integración a la primera"],["docs/evaluacion-agentes.md:L22-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","menos commits de retrabajo"],["docs/evaluacion-agentes.md:L23-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","menos rondas de revisión"],["docs/evaluacion-agentes.md:L24-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_insufficient_sample_never_fabricates_recommendation","AGENTS_EVALUATION_LOCAL","menos tokens cuando el dato existe"],["docs/evaluacion-agentes.md:L26-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","solo se publica una recomendación cuando existen al menos dos configur"],["docs/evaluacion-agentes.md:L26-U2","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","tokens solo desempatan cuando todas las tareas de las configuraciones "],["docs/evaluacion-agentes.md:L26-U3","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","telemetría parcial queda como tokens avg null y no se interpreta como "],["docs/evaluacion-agentes.md:L30-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","github workflows metricas yml valida el motor y evalúa el mes utc ante"],["docs/evaluacion-agentes.md:L32-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","el cli del workflow lee únicamente metricas datos jsonl y escribe únic"],["docs/evaluacion-agentes.md:L32-U2","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","no acepta rutas arbitrarias"],["docs/evaluacion-agentes.md:L32-U3","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","con cero datos del periodo la corrida sigue siendo válida pero no reco"],["docs/evaluacion-agentes.md:L34-U1","metricas/test_evaluar_agentes.py::EvaluationTests::test_partial_token_telemetry_never_becomes_zero_cost","AGENTS_EVALUATION_LOCAL","los proyectos que adopten el kit deben producir registros con este con"],["docs/evolution-engine.md:L10-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_candidate_follows_closed_lifecycle","EVOLUTION_LOCAL","observe remember learn propose shadow experiment validate promote or r"],["docs/evolution-engine.md:L12-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_candidate_follows_closed_lifecycle","EVOLUTION_LOCAL","solo se admite la transición a la etapa inmediatamente siguiente"],["docs/evolution-engine.md:L20-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed","EVOLUTION_LOCAL","generation"],["docs/evolution-engine.md:L22-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed","EVOLUTION_LOCAL","parent generation"],["docs/evolution-engine.md:L25-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed","EVOLUTION_LOCAL","la huella del candidato validado por constitution v1"],["docs/evolution-engine.md:L26-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed","EVOLUTION_LOCAL","decision cuando la etapa es promote or reject"],["docs/evolution-engine.md:L27-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_invalid_transition_fails_closed","EVOLUTION_LOCAL","restores generation cuando la etapa es rollback"],["docs/evolution-engine.md:L29-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_lineage_preserves_parent_reason_and_evidence","EVOLUTION_LOCAL","el candidato se valida antes de crear la primera generación"],["docs/evolution-engine.md:L35-U1","tests/test_evolution_engine.py::EvolutionEngineTests::test_lineage_preserves_parent_reason_and_evidence","EVOLUTION_LOCAL","promote or reject exige una decisión explícita adopt o reject"]]'''))
MODES = {"DERIVED_VIEWS_LOCAL", "DOD_LOCAL", "AGENTS_EVALUATION_LOCAL", "EVOLUTION_LOCAL"}


def normalized(value: str) -> str:
    """Fold punctuation and case without losing source semantics."""
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


def report_rows(report: str) -> list[tuple[str, str, str, str, str]]:
    """Read *all* table rows, including malformed or unrecognized additions."""
    parts = report.split("## Trazabilidad de las 70 unidades")
    if len(parts) != 2:
        raise ValueError("Missing or duplicate evidence heading")
    table = parts[1].split("## Validación y reversión")
    if len(table) != 2:
        raise ValueError("Missing evidence table terminator")
    result = []
    for line in table[0].splitlines():
        if not line.startswith("|"):
            continue
        if line.startswith("| Fila exacta |") or line.startswith("| --- |"):
            continue
        fields = line.strip("|").strip().split(" | ")
        if len(fields) != 5 or not all(fields[i].startswith("`") and fields[i].endswith("`") for i in (0, 1, 3)):
            raise ValueError("Malformed or unexpected evidence row")
        key, witness, mode, anchor, status = fields
        if not key.startswith("`docs/"):
            raise ValueError("Unexpected evidence identifier")
        result.append((key[1:-1], witness[1:-1], mode, anchor[1:-1], status))
    if len(result) != 70 or len({row[0] for row in result}) != 70:
        raise ValueError("Missing, duplicate or extra report row")
    if any(item[:4] != expected for item, expected in zip(result, ROWS)):
        raise ValueError("Unauthorized change in evidence mapping")
    if any(item[4] != "NO_VERIFICABLE" for item in result):
        raise ValueError("Invalid promotion to coverage")
    return result


def validate_sources(*, source_overrides: dict[str, str] | None = None, matrix_override: str | None = None) -> None:
    """Check each source line and matrix clause, not just the test name."""
    inventory = {}
    matrix = MATRIX.read_text(encoding="utf-8") if matrix_override is None else matrix_override
    for line in matrix.splitlines():
        matched = re.match(r"^\| `([^`]+)` \| (.*?) \| (NO_VERIFICABLE|SIN_COBERTURA|CUBIERTO|NO_APLICA) \|", line)
        if matched:
            if matched[1] in inventory:
                raise ValueError("Duplicate matrix identifier " + matched[1])
            inventory[matched[1]] = matched[2], matched[3]
    cache = {}
    for key, witness, mode, anchor in ROWS:
        if key not in inventory or inventory[key][1] != "NO_VERIFICABLE":
            raise ValueError("Absent or reclassified inventory row " + key)
        if mode not in MODES or not anchor or len(anchor) > 160:
            raise ValueError("Invalid mode/anchor")
        match = re.fullmatch(r"(docs/[\w.-]+\.md):L(\d+)-U\d+", key)
        if match is None:
            raise ValueError("Malformed unit ID")
        path, linenum = match.groups()
        if path not in cache:
            cache[path] = (source_overrides or {}).get(path, (ROOT / path).read_text(encoding="utf-8")).splitlines()
        lines = cache[path]
        if int(linenum) > len(lines) or normalized(anchor) not in normalized(lines[int(linenum)-1]):
            raise ValueError("Source anchor drift " + key)
        if normalized(anchor) not in normalized(inventory[key][0]):
            raise ValueError("Matrix clause drift " + key)
        parts = witness.split("::")
        if len(parts) != 3 or not parts[0].endswith(".py") or not parts[2].startswith("test_"):
            raise ValueError("Invalid executable witness")


class VerificacionFactory03Tests(unittest.TestCase):
    """Mutation-resistant documentary evidence with executable local witnesses."""

    def test_70_filas_exactas_y_no_promocion(self):
        """Report the source inventory precisely, never synthetic GREEN."""
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({row[0] for row in ROWS}), 70)
        content = REPORT.read_text(encoding="utf-8")
        self.assertEqual(len(report_rows(content)), 70)
        self.assertIn("0 promociones", content)
        self.assertIn("consolidación #2035", content)

    def test_fuentes_y_matriz_reales(self):
        """Every ID belongs to a source line and stays unverified."""
        validate_sources()

    def test_testigos_existentes_ejecutados(self):
        """Run unique real tests, not a string that merely looks like a method."""
        refs = sorted({row[1] for row in ROWS})
        self.assertGreaterEqual(len(refs), 10)
        for name in refs:
            with self.subTest(witness=name):
                filename, cls, method = name.split("::")
                file = ROOT / filename
                self.assertTrue(file.is_file(), filename)
                root = str(file.parent)
                if root not in sys.path:
                    sys.path.insert(0, root)
                modname = "_factory03_" + file.parent.name + "_" + file.stem
                if modname not in sys.modules:
                    spec = importlib.util.spec_from_file_location(modname, file)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[modname] = module
                    spec.loader.exec_module(module)
                suite = unittest.TestLoader().loadTestsFromName(cls + "." + method, sys.modules[modname])
                output = io.StringIO()
                result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
                self.assertEqual(result.testsRun, 1, name + ": " + output.getvalue())
                self.assertTrue(result.wasSuccessful(), name + ": " + output.getvalue())

    def test_mutaciones_rechazadas(self):
        """Reject corrupted report, orphan source and changed matrix clauses."""
        report = REPORT.read_text(encoding="utf-8")
        row = next(line for line in report.splitlines() if line.startswith("| `docs/"))
        variants = [
            report.replace(row + "\n", "", 1),
            report.replace(row, row + "\n" + row, 1),
            report.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            report.replace(row, row.replace(ROWS[0][3], "ancla inventada"), 1),
            report.replace(row, row.replace(ROWS[0][0], "docs/falso.md:L1-U1"), 1),
            report.replace(row, row + "\n| `ruta:falsa` | cualquier dato | extra | sin prueba | NO_VERIFICABLE |", 1),
        ]
        for i, variant in enumerate(variants):
            with self.subTest(mutation=i), self.assertRaises(ValueError):
                report_rows(variant)
        path = "docs/derived-views.md"
        original = (ROOT / path).read_text(encoding="utf-8")
        target = original.splitlines()[2]
        with self.assertRaises(ValueError):
            validate_sources(source_overrides={path: original.replace(target, "fuente alterada", 1)})
        matrix = MATRIX.read_text(encoding="utf-8")
        line = next(x for x in matrix.splitlines() if x.startswith("| `" + ROWS[0][0] + "` |"))
        with self.assertRaises(ValueError):
            validate_sources(matrix_override=matrix.replace(line, line.replace(line.split(" | ")[1], "fuente alterada"), 1))


if __name__ == "__main__":
    unittest.main()
