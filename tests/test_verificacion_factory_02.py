"""Factory #2018: verificar 70 filas exactas del lote 02, sin promoción externa.

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
REPORT = ROOT / "docs/verificacion/verificacion-02.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
ROWS = tuple(tuple(row) for row in json.loads(r'''[["docs/conversacion-agentes.md:L12-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio","COMUNICACION_LOCAL","solo falta playwright"],["docs/conversacion-agentes.md:L12-U3","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio","COMUNICACION_LOCAL","mientras corre reviso el flujo nuevo para detectar fallos lógicos"],["docs/conversacion-agentes.md:L13-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio","COMUNICACION_LOCAL","el enfoque a falló por x"],["docs/conversacion-agentes.md:L13-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio","COMUNICACION_LOCAL","cambio al enfoque b porque evita y"],["docs/conversacion-agentes.md:L15-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio","COMUNICACION_LOCAL","prohibidas sigo revisando déjame pensar estoy trabajando en eso y repeti"],["docs/conversacion-agentes.md:L39-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial","COMUNICACION_LOCAL","debe conservar objetivo repo issue pr branch y sha decisiones tomadas ha"],["docs/conversacion-agentes.md:L43-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial","COMUNICACION_LOCAL","no reexplicar lo ya presente en issue pr lecciones"],["docs/conversacion-agentes.md:L44-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial","COMUNICACION_LOCAL","buscar primero"],["docs/conversacion-agentes.md:L44-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial","COMUNICACION_LOCAL","abrir solo fragmentos relevantes"],["docs/conversacion-agentes.md:L45-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial","COMUNICACION_LOCAL","agrupar lecturas independientes en paralelo"],["docs/conversacion-agentes.md:L46-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial","COMUNICACION_LOCAL","sin polling una lectura terminal de ci y más solo ante fallo o transició"],["docs/conversacion-agentes.md:L47-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_estado_compacto_canonico_y_por_hitos","COMUNICACION_LOCAL","resultado primero detalle después"],["docs/conversacion-agentes.md:L47-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_estado_compacto_canonico_y_por_hitos","COMUNICACION_LOCAL","hitos en 3 7 líneas salvo petición"],["docs/conversacion-agentes.md:L48-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_estado_compacto_canonico_y_por_hitos","COMUNICACION_LOCAL","no duplicar en el chat lo registrado en github"],["docs/conversacion-agentes.md:L57-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","lo de la segunda fila no se resuelve solo con instrucciones si la integr"],["docs/conversacion-agentes.md:L65-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","no es un fallo no reenviar el mensaje no abrir otro chat y no cancelar m"],["docs/conversacion-agentes.md:L65-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","una sola espera luego continuar"],["docs/conversacion-agentes.md:L66-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","reducir disparadores pedir una sola tarea acotada por turno"],["docs/conversacion-agentes.md:L66-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","no pegar secretos tokens ni volcados grandes de logs salida resumir y ci"],["docs/conversacion-agentes.md:L66-U3","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","no encadenar ejecuciones de código innecesarias"],["docs/conversacion-agentes.md:L66-U4","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","describir la finalidad defensiva operativa de cualquier comando de segur"],["docs/conversacion-agentes.md:L67-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo","COMUNICACION_LOCAL","si se repite en el mismo chat escribir una nota state continuar en un ch"],["docs/conversacion-agentes.md:L69-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones","COMUNICACION_LOCAL","requiere issue propio"],["docs/conversacion-agentes.md:L73-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones","COMUNICACION_LOCAL","tests test conversacion agentes py comprueba que trae todos los campos y"],["docs/coordinacion-pr-validation.md:L5-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","la coordinación valida cada pr mientras está abierto rama canónica relac"],["docs/coordinacion-pr-validation.md:L8-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","closes n github puede cerrar el issue antes de que una revalidación tard"],["docs/coordinacion-pr-validation.md:L9-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","volver a exigir entonces que el issue siga abierto produce un falso rojo"],["docs/coordinacion-pr-validation.md:L16-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","el caller canónico conserva pull request closed porque pr event todavía"],["docs/coordinacion-pr-validation.md:L17-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","debe reconciliar la reserva y el estado"],["docs/coordinacion-pr-validation.md:L18-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","el caller usa validar pr evento como precondición ese job solo completa"],["docs/coordinacion-pr-validation.md:L19-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","cuando github event pull request merged true validar pr conserva"],["docs/coordinacion-pr-validation.md:L21-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","llega a invocar operation validate"],["docs/coordinacion-pr-validation.md:L22-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","el reusable aplica la misma defensa una llamada validate originada por u"],["docs/coordinacion-pr-validation.md:L24-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","un cierre sin merge tiene merged false y no recibe esta excepción"],["docs/coordinacion-pr-validation.md:L27-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","mantener la forma legacy de validar pr"],["docs/coordinacion-pr-validation.md:L29-U1","tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral","COORDINACION_LOCAL","closed por sí solo nunca se convierte en autoridad para saltarse validac"],["docs/coordinacion-pr-validation.md:L33-U1","tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation","COORDINACION_LOCAL","la neutralidad post merge no cambia validate pull"],["docs/coordinacion-pr-validation.md:L34-U1","tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation","COORDINACION_LOCAL","siga abierto el coordinador conserva el comportamiento fail closed exist"],["docs/coordinacion-pr-validation.md:L35-U1","tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation","COORDINACION_LOCAL","el issue debe estar abierto la branch debe ser trabajo issue n la reserv"],["docs/coordinacion-pr-validation.md:L36-U1","tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation","COORDINACION_LOCAL","su identidad deben ser válidas la relación de cierre debe corresponder y"],["docs/coordinacion-pr-validation.md:L40-U1","tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation","COORDINACION_LOCAL","issue n debe estar abierto durante el pr"],["docs/coordinacion-pr-validation.md:L47-U1","tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate","COORDINACION_LOCAL","tests test coordinacion reusable contract py t test merged pr validation"],["docs/coordinacion-pr-validation.md:L48-U1","tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate","COORDINACION_LOCAL","tests test consumer coordination template py consumercoordinationtemplat"],["docs/coordinacion-pr-validation.md:L49-U1","tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate","COORDINACION_LOCAL","tests test coordinar trabajo py coordinaciontests test open pr with clos"],["docs/coordinacion-pr-validation.md:L52-U1","tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation","COORDINACION_LOCAL","la reversión es un revert de estos cambios declarativos y no requiere mi"],["docs/costos-presupuestos.md:L5-U1","metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok","COSTOS_LOCAL_NO_TELEMETRIA","el agente que abre un pr declara únicamente métricas numéricas y clasifi"],["docs/costos-presupuestos.md:L13-U1","metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok","COSTOS_LOCAL_NO_TELEMETRIA","mientras tokens minutos de ci minutos de agente o rondas solo estén auto"],["docs/costos-presupuestos.md:L15-U1","metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok","COSTOS_LOCAL_NO_TELEMETRIA","ok reservado para una evaluación completamente observada y por debajo de"],["docs/costos-presupuestos.md:L15-U2","metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok","COSTOS_LOCAL_NO_TELEMETRIA","con la telemetría actual no se emite a partir de datos autodeclarados"],["docs/costos-presupuestos.md:L16-U1","metricas/test_costos.py::CostTests::test_near_limit_warns_and_over_limit_soft_blocks","COSTOS_LOCAL_NO_TELEMETRIA","warning al menos una dimensión está entre 80 y 100"],["docs/costos-presupuestos.md:L17-U1","metricas/test_costos.py::CostTests::test_near_limit_warns_and_over_limit_soft_blocks","COSTOS_LOCAL_NO_TELEMETRIA","soft block falta medición o alguna dimensión supera 100"],["docs/costos-presupuestos.md:L19-U1","metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent","COSTOS_LOCAL_NO_TELEMETRIA","un marker malformado falla cerrado"],["docs/costos-presupuestos.md:L19-U2","metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent","COSTOS_LOCAL_NO_TELEMETRIA","un pr dentro de límites pero con dimensiones solo declaradas permanece e"],["docs/costos-presupuestos.md:L19-U3","metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent","COSTOS_LOCAL_NO_TELEMETRIA","así no se confunde una estimación con costo observado"],["docs/costos-presupuestos.md:L27-U1","metricas/test_costos.py::CostTests::test_ci_trend_rejects_duplicate_run_ids","COSTOS_LOCAL_NO_TELEMETRIA","un run id duplicado falla cerrado para evitar doble conteo"],["docs/costos-presupuestos.md:L29-U1","metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent","COSTOS_LOCAL_NO_TELEMETRIA","f1f no acredita ningún informe mensual nuevo ni ahorro cuantificado de a"],["docs/cumplimiento-datos-licencias.md:L7-U1","seguridad/test_cumplimiento.py::PrivacyTests::test_valid_record","CUMPLIMIENTO_LOCAL_NO_LEGAL","el script seguridad cumplimiento py comprueba que un producto tenga un i"],["docs/cumplimiento-datos-licencias.md:L15-U1","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","evidence exige siete referencias no sensibles a evidencias revisadas pri"],["docs/cumplimiento-datos-licencias.md:L15-U2","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","el validador rechaza campos adicionales y revisiones con más de 365 días"],["docs/cumplimiento-datos-licencias.md:L17-U1","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","importante exception for legal review solo deja constancia de que una ex"],["docs/cumplimiento-datos-licencias.md:L17-U2","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","el responsable debe contrastar evidencias y hechos del producto antes de"],["docs/cumplimiento-datos-licencias.md:L21-U1","seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock","CUMPLIMIENTO_LOCAL_NO_LEGAL","el cli no acepta rutas arbitrarias"],["docs/cumplimiento-datos-licencias.md:L21-U2","seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock","CUMPLIMIENTO_LOCAL_NO_LEGAL","la evidencia de privacidad entra por stdin por lo que su ubicación priva"],["docs/cumplimiento-datos-licencias.md:L36-U1","seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock","CUMPLIMIENTO_LOCAL_NO_LEGAL","las pruebas propias son pythonpath seguridad python3 m unittest discover"],["docs/cumplimiento-datos-licencias.md:L37-U1","seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock","CUMPLIMIENTO_LOCAL_NO_LEGAL","seguridad yml ya ejecuta unittest discover s seguridad p test py"],["docs/cumplimiento-datos-licencias.md:L37-U2","seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock","CUMPLIMIENTO_LOCAL_NO_LEGAL","al integrar este slice las regresiones de cumplimiento quedan dentro de "],["docs/cumplimiento-datos-licencias.md:L38-U1","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","cada proyecto debe aportar al menos una evidencia documentada y verifica"],["docs/cumplimiento-datos-licencias.md:L38-U2","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","un fixture de tests no es prueba de cumplimiento de ningún producto"],["docs/cumplimiento-datos-licencias.md:L39-U1","seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails","CUMPLIMIENTO_LOCAL_NO_LEGAL","cierre de 12 requiere ci y evidencia de la revisión material no únicamen"],["docs/derived-views.md:L3-U1","tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed","VISTAS_DERIVADAS_LOCAL","una vista derivada nunca es una fuente de verdad"]]'''))
MODES = {
    "COMUNICACION_LOCAL", "COORDINACION_LOCAL", "COSTOS_LOCAL_NO_TELEMETRIA",
    "CUMPLIMIENTO_LOCAL_NO_LEGAL", "VISTAS_DERIVADAS_LOCAL",
}


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


class VerificacionFactory02Tests(unittest.TestCase):
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
                modname = "_factory02_" + file.parent.name + "_" + file.stem
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
        path = "docs/conversacion-agentes.md"
        original = (ROOT / path).read_text(encoding="utf-8")
        target = original.splitlines()[11]
        with self.assertRaises(ValueError):
            validate_sources(source_overrides={path: original.replace(target, "fuente alterada", 1)})
        matrix = MATRIX.read_text(encoding="utf-8")
        line = next(x for x in matrix.splitlines() if x.startswith("| `" + ROWS[0][0] + "` |"))
        with self.assertRaises(ValueError):
            validate_sources(matrix_override=matrix.replace(line, line.replace("solo falta Playwright.", "fuente alterada"), 1))


if __name__ == "__main__":
    unittest.main()
