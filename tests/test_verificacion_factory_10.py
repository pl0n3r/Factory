"""Factory #2026: 70 testigos reales y trazabilidad fail-closed del lote 10/18.

Se ejecutan testigos de código existentes con datos sintéticos. Ningún testigo
local convierte evidencia de GitHub, reglas administrativas o deploy en GREEN.
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/verificacion/verificacion-10.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
ROWS = (
    ("docs/pr-label-governance.md:L33-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGLA_Y_EVIDENCIA_EXTERNA", "target = branch enforcement = active"),
    ("docs/pr-label-governance.md:L34-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGLA_Y_EVIDENCIA_EXTERNA", "refname.include = ~defaultbranch"),
    ("docs/pr-label-governance.md:L35-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGLA_Y_EVIDENCIA_EXTERNA", "check etiquetas del github actions app integrationid=15368"),
    ("docs/pr-label-governance.md:L36-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGLA_Y_EVIDENCIA_EXTERNA", "strictrequiredstatuscheckspolicy = false y ningún bypass actor."),
    ("docs/pr-label-governance.md:L38-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGLA_Y_EVIDENCIA_EXTERNA", "aplicación administrativa solo por el dueño y después de revisar el payload:"),
    ("docs/pr-label-governance.md:L50-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_uniform_ruleset_payload_and_owner_commands", "REGLA_Y_EVIDENCIA_EXTERNA", "nunca se reemplaza a ciegas."),
    ("docs/pr-label-governance.md:L54-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_audit_classifies_required_etiquetas_or_unknown", "REGLA_Y_EVIDENCIA_EXTERNA", "aplicar etiquetas a un pr usa el endpoint de issues y no requiere pull-requests: write."),
    ("docs/pr-label-governance.md:L54-U2", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_audit_classifies_required_etiquetas_or_unknown", "REGLA_Y_EVIDENCIA_EXTERNA", "como los siete repos de la fábrica son públicos el sweep consulta check-runs por rest público sin token vali"),
    ("docs/pr-label-governance.md:L56-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_audit_classifies_required_etiquetas_or_unknown", "REGLA_Y_EVIDENCIA_EXTERNA", "un pr sin estado recibe estado: en revisión"),
    ("docs/pr-label-governance.md:L57-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_audit_classifies_required_etiquetas_or_unknown", "REGLA_Y_EVIDENCIA_EXTERNA", "si contiene una única referencia closes/fixes/resolves #n tipo y prioridad faltantes se heredan del issue se"),
    ("docs/pr-label-governance.md:L58-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_audit_handles_visible_sources_and_rejects_malformed_evidence", "REGLA_Y_EVIDENCIA_EXTERNA", "etiquetas ambiguas o incompletas fallan cerrado"),
    ("docs/pr-label-governance.md:L59-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_owner_commands_and_audit_document_fail_closed", "REGLA_Y_EVIDENCIA_EXTERNA", "no se escriben contenidos checks actions ni secretos."),
    ("docs/pr-label-governance.md:L63-U1", "tests/test_pr_label_governance.py::PrLabelGovernanceTests::test_merged_pr_with_failed_etiquetas_emits_single_alert", "REGLA_Y_EVIDENCIA_EXTERNA", "si el último check terminal no es success el workflow publica un solo comentario en el pr con marker factory"),
    ("docs/preview-preproduccion.md:L9-U1", "tests/test_cobertura_factory_37.py::CoberturaFactory37Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/build"),
    ("docs/preview-preproduccion.md:L10-U1", "tests/test_cobertura_factory_37.py::CoberturaFactory37Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/backup"),
    ("docs/preview-preproduccion.md:L11-U1", "tests/test_cobertura_factory_37.py::CoberturaFactory37Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/migrate"),
    ("docs/preview-preproduccion.md:L12-U1", "tests/test_cobertura_factory_37.py::CoberturaFactory37Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/deploy"),
    ("docs/preview-preproduccion.md:L13-U1", "tests/test_cobertura_factory_37.py::CoberturaFactory37Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/rollback"),
    ("docs/preview-preproduccion.md:L15-U1", "tests/test_cobertura_factory_37.py::CoberturaFactory37Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "la diferencia es el contexto: durante preview factory crea un directorio temporal y expone únicamente las va"),
    ("docs/preview-preproduccion.md:L17-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "PREVIEW_LOCAL_NO_DEPLOY", "los adapters del proyecto deben ramificar explícitamente por factorypreview=1 y operar solo dentro de factor"),
    ("docs/preview-preproduccion.md:L29-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/preview-health: confirma versión sha y schema cuando aplica."),
    ("docs/preview-preproduccion.md:L30-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/preview-smoke: valida las superficies críticas del artifact preview."),
    ("docs/preview-preproduccion.md:L31-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "ops/factory/preview-e2e: ejecuta el recorrido sintético mínimo."),
    ("docs/preview-preproduccion.md:L37-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "un gate final validar depende de ambos"),
    ("docs/preview-preproduccion.md:L37-U2", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "PREVIEW_LOCAL_NO_DEPLOY", "en push el preview queda skipped mientras que en pullrequest debe terminar success."),
    ("docs/principios-construccion.md:L3-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "no habilita por sí solo acciones coordinación merges ni releases."),
    ("docs/principios-construccion.md:L7-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "serializar solo por dependencia real de datos colisión real de archivos o gate de autoridad vigente."),
    ("docs/principios-construccion.md:L7-U2", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "maximizar paralelismo demostrable nunca inferido de que dos tareas son conceptualmente distintas."),
    ("docs/principios-construccion.md:L11-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "una cola con cero hojas disponible en los siete repositorios exige inventario completo y escalera no ociosa"),
    ("docs/principios-construccion.md:L11-U2", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "no da permiso de convertir bloqueos en trabajo listo."),
    ("docs/principios-construccion.md:L11-U3", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "diferenciar disponible reservado en revisión bloqueado y planificado"),
    ("docs/principios-construccion.md:L11-U4", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "todo bloqueo lleva causa y condición verificable de salida."),
    ("docs/principios-construccion.md:L11-U5", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "el catálogo oficial incluye además estado: requiere recuperación / status: recovery required como sexto esta"),
    ("docs/principios-construccion.md:L11-U6", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "mientras #1098/#1100 solo admitan cinco estados un snapshot con recovery falla cerrado"),
    ("docs/principios-construccion.md:L15-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "un módulo puro build-ahead con fakes deterministas permite preparación offline cuando un gate operativo impi"),
    ("docs/principios-construccion.md:L19-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "una lease activa sobre un directorio no se ignora por prometer editar archivos distintos: el árbitro necesit"),
    ("docs/principios-construccion.md:L19-U2", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "si el diff está ausente truncado stale ambiguo o cambió el sha falla cerrado."),
    ("docs/principios-construccion.md:L19-U3", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "ni siquiera hunks distintos del mismo archivo permiten paralelismo automático."),
    ("docs/principios-construccion.md:L23-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "planificado ≠ bloqueado y available ≠ ready si faltan tandas dependencias reserva o autoridad."),
    ("docs/principios-construccion.md:L23-U2", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "unknown nunca equivale a green."),
    ("docs/principios-construccion.md:L23-U3", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "verificar evidencia terminal exact-head"),
    ("docs/principios-construccion.md:L23-U4", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "para puertas d-043 exigir validatedinproduction sha e identidad sin pendientes."),
    ("docs/principios-construccion.md:L27-U1", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "construccion permite preparar trabajo reversible y offline dentro de d-068"),
    ("docs/principios-construccion.md:L27-U2", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "d-063 exige atestación válida para excepciones informativas"),
    ("docs/principios-construccion.md:L27-U3", "tests/test_cobertura_factory_38.py::CoberturaFactory38Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "factory@v1 mantiene su puerta vigente exact-sha mientras no se integre otro contrato: factory #1080"),
    ("docs/principios-construccion.md:L31-U1", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_contrato_principal", "NORMA_Y_GUARDA_LOCAL", "ac-nn debe señalar unittest existente/implementable o check real nunca un nombre ficticio."),
    ("docs/principios-construccion.md:L35-U1", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "verificar ratelimit y conservar capacidad para reparaciones"),
    ("docs/principios-construccion.md:L35-U2", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "autenticación compartida no garantiza 5.000 solicitudes disponibles en el instante."),
    ("docs/principios-construccion.md:L39-U1", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_sin_datos_reales", "NORMA_Y_GUARDA_LOCAL", "nunca fabricar approved health actividad throughput o readiness."),
    ("docs/principios-construccion.md:L43-U1", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "reportar por repositorio y global conteos separados de disponible reservado en revisión bloqueado y planific"),
    ("docs/principios-construccion.md:L43-U2", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "identificar causa y fuente de cada bloqueo."),
    ("docs/principios-construccion.md:L43-U3", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "el estado: requiere recuperación / status: recovery required es un sexto estado canónico que no es disponibl"),
    ("docs/principios-construccion.md:L43-U4", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "contarlo por separado solo tras integrar el contrato de factory #1102"),
    ("docs/principios-construccion.md:L43-U5", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "antes rechazar snapshots que no puedan representar recovery sin fabricar green o queueempty. utilización = a"),
    ("docs/principios-construccion.md:L43-U6", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "sin evidencia autenticada de agentes activos capacidad heartbeat y frescura marcar unknown / no calculable n"),
    ("docs/principios-construccion.md:L47-U1", "tests/test_cobertura_factory_39.py::CoberturaFactory39Tests::test_falla_cerrado", "NORMA_Y_GUARDA_LOCAL", "esta documentación no cambia coordinación no autoriza merges releases tags ejecución github live gasto ni pr"),
    ("docs/project-dna.md:L9-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "el descubridor recibe señales explícitas y no secretas:"),
    ("docs/project-dna.md:L11-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "rutas relativas del repositorio"),
    ("docs/project-dna.md:L12-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "presencia de manifests conocidos"),
    ("docs/project-dna.md:L13-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "estructura declarada de esos manifests"),
    ("docs/project-dna.md:L14-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "capacidades declaradas por un caller confiable."),
    ("docs/project-dna.md:L26-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "frameworks"),
    ("docs/project-dna.md:L30-U1", "tests/test_project_dna.py::ProjectDnaTests::test_integration_detection_requires_explicit_signal", "DESCUBRIMIENTO_LOCAL", "integrations"),
    ("docs/project-dna.md:L31-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "capabilities"),
    ("docs/project-dna.md:L33-U1", "tests/test_project_dna.py::ProjectDnaTests::test_discovers_stack_and_surfaces_from_repository_signals", "DESCUBRIMIENTO_LOCAL", "extensions"),
    ("docs/project-dna.md:L34-U1", "tests/test_project_dna.py::ProjectDnaTests::test_fingerprint_is_deterministic_and_versioned", "DESCUBRIMIENTO_LOCAL", "fingerprint."),
    ("docs/project-dna.md:L37-U1", "tests/test_project_dna.py::ProjectDnaTests::test_unknown_capabilities_are_explicit_not_invented", "DESCUBRIMIENTO_LOCAL", "no se sustituye por una conjetura."),
    ("docs/project-dna.md:L48-U1", "tests/test_project_dna.py::ProjectDnaTests::test_schema_is_extensible_without_breaking_base_fields", "DESCUBRIMIENTO_LOCAL", "las capacidades futuras deben añadirse"),
    ("docs/project-dna.md:L50-U1", "tests/test_project_dna.py::ProjectDnaTests::test_schema_is_extensible_without_breaking_base_fields", "DESCUBRIMIENTO_LOCAL", "un cambio incompatible de los campos base requiere una nueva versión"),
    ("docs/provisioning.md:L5-U1", "tests/test_cobertura_factory_40.py::CoberturaFactory40Tests::test_falla_cerrado", "PROVISIONAMIENTO_LOCAL", "el destino permitido es pl0n3r/<repo>"),
)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[`*_\[\]";,()]', "", text.lower())).strip()


def report_rows(text: str) -> list[tuple[str, str, str, str, str]]:
    result = []
    for line in text.splitlines():
        if not line.startswith("| `docs/"):
            continue
        columns = [part.strip() for part in line.strip("|").split("|")]
        if len(columns) != 5:
            raise ValueError("An ambiguous evidence table is not permitted")
        key, witness, mode, anchor, status = columns
        if not (key.startswith("`") and key.endswith("`")
                and witness.startswith("`") and witness.endswith("`")
                and anchor.startswith("`") and anchor.endswith("`")):
            raise ValueError("Missing provenance delimiter")
        result.append((key[1:-1], witness[1:-1], mode, anchor[1:-1], status))
    if len(result) != 70 or len({x[0] for x in result}) != 70:
        raise ValueError("Missing, duplicate, or extra rows")
    if [x[:4] for x in result] != list(ROWS):
        raise ValueError("Evidence mapping changed without contract revision")
    if any(row[4] != "NO_VERIFICABLE" for row in result):
        raise ValueError("Local evidence cannot certify external readiness")
    return result


class VerificacionFactory10Tests(unittest.TestCase):
    def test_70_filas_exactas_y_sin_promociones(self):
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({row[0] for row in ROWS}), 70)
        report = REPORT.read_text(encoding="utf-8")
        self.assertEqual(len(report_rows(report)), 70)
        self.assertIn("0 promociones", report)
        self.assertIn("docs/matriz-cobertura.md", report)
        self.assertIn("evidencia externa", report.lower())

    def test_cada_unidad_existe_en_fuente_y_matriz(self):
        matrix = MATRIX.read_text(encoding="utf-8").splitlines()
        inventory = {}
        for line in matrix:
            match = re.match(r"^\| `(docs/[^\u0060]+:L\d+-U\d+)` \| ([^|]+) \| (NO_VERIFICABLE|SIN_COBERTURA) \|", line)
            if match:
                inventory[match.group(1)] = (match.group(2), match.group(3))
        sources = {}
        for key, ref, mode, anchor in ROWS:
            with self.subTest(unit=key):
                match = re.fullmatch(r"(docs/[\w.-]+\.md):L(\d+)-U(\d+)", key)
                self.assertIsNotNone(match)
                path, line_number, _unit_number = match.groups()
                if path not in sources:
                    sources[path] = (ROOT / path).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(int(line_number), len(sources[path]))
                line = sources[path][int(line_number) - 1]
                self.assertIn(normalized(anchor), normalized(line))
                self.assertIn(key, inventory)
                unit, status = inventory[key]
                self.assertEqual(status, "NO_VERIFICABLE")
                self.assertIn(normalized(anchor), normalized(unit))
                self.assertIn(mode, {
                    "REGLA_Y_EVIDENCIA_EXTERNA", "PREVIEW_LOCAL_NO_DEPLOY",
                    "NORMA_Y_GUARDA_LOCAL", "DESCUBRIMIENTO_LOCAL",
                    "PROVISIONAMIENTO_LOCAL",
                })
                filename, cls, method = ref.split("::")
                self.assertTrue(filename.startswith("tests/test_"))
                self.assertTrue(filename.endswith(".py"))
                self.assertRegex(method, r"^test_[a-z0-9_]+$")

    def test_testigos_ejecutables_sobre_codigo_existente(self):
        """Un nombre de método falso no basta: ejecutar todos los testigos únicos."""
        refs = sorted({ref for _, ref, _, _ in ROWS})
        self.assertGreaterEqual(len(refs), 10)
        for ref in refs:
            with self.subTest(witness=ref):
                filename, cls, method = ref.split("::")
                modname = "_factory_verify10_" + Path(filename).stem
                if modname not in sys.modules:
                    spec = importlib.util.spec_from_file_location(modname, ROOT / filename)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[modname] = module
                    spec.loader.exec_module(module)
                suite = unittest.TestLoader().loadTestsFromName(
                    cls + "." + method, sys.modules[modname],
                )
                stream = io.StringIO()
                result = unittest.TextTestRunner(
                    stream=stream, verbosity=0,
                ).run(suite)
                self.assertEqual(result.testsRun, 1, ref + ": " + stream.getvalue())
                self.assertTrue(result.wasSuccessful(), ref + ": " + stream.getvalue())

    def test_rechaza_retiro_duplicacion_y_falsos_verdes(self):
        baseline = REPORT.read_text(encoding="utf-8")
        lines = baseline.splitlines()
        row_line = next(x for x in lines if x.startswith("| `docs/"))
        self.assertEqual(len(report_rows(baseline)), 70)
        variants = [
            baseline.replace(row_line + "\n", "", 1),
            baseline.replace(row_line, row_line + "\n" + row_line, 1),
            baseline.replace(row_line, row_line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            baseline.replace(row_line, row_line.replace(ROWS[0][3], "evidencia-inventada"), 1),
            baseline.replace(row_line, row_line.replace(ROWS[0][0], "docs/falso.md:L1-U1"), 1),
        ]
        for text in variants:
            with self.subTest(mutation=text.count("\n")):
                with self.assertRaises(ValueError):
                    report_rows(text)


if __name__ == "__main__":
    unittest.main()
