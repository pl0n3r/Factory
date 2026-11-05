"""Factory #2017: 70 contratos documentales con testigos reales y negativos.

Prueba solo comportamiento offline de Factory; no certifica operación externa.
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
REPORT = ROOT / "docs/verificacion/verificacion-01.md"
MATRIX = ROOT / "docs/matriz-cobertura.md"
ROWS = tuple(tuple(v) for v in json.loads(r'''[["docs/aceptacion-ejecutable.md:L5-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","gates genéricos como lint tests globales coordinación codeql y sonar"],["docs/aceptacion-ejecutable.md:L6-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","criterios específicos del issue definidos como ac nn y verificados por el j"],["docs/aceptacion-ejecutable.md:L8-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","un pr no está hecho si solo pasa la primera capa"],["docs/aceptacion-ejecutable.md:L12-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","el issue debe contener exactamente una sección no vacía para"],["docs/aceptacion-ejecutable.md:L14-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","contexto"],["docs/aceptacion-ejecutable.md:L15-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","alcance"],["docs/aceptacion-ejecutable.md:L16-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","fuera de alcance"],["docs/aceptacion-ejecutable.md:L17-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","criterios de aceptación"],["docs/aceptacion-ejecutable.md:L18-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","contrato ejecutable"],["docs/aceptacion-ejecutable.md:L22-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","ac 01 descripción verificable"],["docs/aceptacion-ejecutable.md:L37-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","los ids del marker deben coincidir exactamente con los ids humanos"],["docs/aceptacion-ejecutable.md:L41-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","solo acepta un target con forma"],["docs/aceptacion-ejecutable.md:L45-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch","ACCEPTANCE_LOCAL","la ruta debe vivir en un directorio de tests permitido tests metricas segur"],["docs/aceptacion-ejecutable.md:L49-U2","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_check_must_exist_and_be_success","ACCEPTANCE_LOCAL","nunca cuenta como éxito"],["docs/aceptacion-ejecutable.md:L49-U3","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_check_must_exist_and_be_success","ACCEPTANCE_LOCAL","un check completed solo satisface el criterio con conclusion success"],["docs/aceptacion-ejecutable.md:L51-U1","tests/test_aceptacion_kit.py::AcceptanceContractTests::test_check_must_exist_and_be_success","ACCEPTANCE_LOCAL","validar y criterios de aceptación no pueden referenciarse como evidencia pa"],["docs/aceptacion-ejecutable.md:L57-U1","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired","ACCEPTANCE_LOCAL","lint tests coordinación criterios de aceptación validar"],["docs/aceptacion-ejecutable.md:L59-U1","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_readiness_does_not_repeat_contract_tests","ACCEPTANCE_LOCAL","la espera solo vuelve a leer check runs no vuelve a ejecutar workflows jobs"],["docs/aceptacion-ejecutable.md:L59-U2","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_readiness_does_not_repeat_contract_tests","ACCEPTANCE_LOCAL","un fallo terminal distinto de evidencia pendiente aborta de inmediato y el "],["docs/aceptacion-ejecutable.md:L61-U1","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired","ACCEPTANCE_LOCAL","los criterios kind test no se ejecutan durante ese preflight"],["docs/aceptacion-ejecutable.md:L67-U1","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired","ACCEPTANCE_LOCAL","github issue template trabajo yml exige las cinco secciones y config yml de"],["docs/aceptacion-ejecutable.md:L71-U1","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired","ACCEPTANCE_LOCAL","los pr históricos abiertos deberán migrar su issue al contrato cuando vuelv"],["docs/aceptacion-ejecutable.md:L71-U2","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired","ACCEPTANCE_LOCAL","no se fabrican criterios retrospectivos"],["docs/aceptacion-ejecutable.md:L71-U3","tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired","ACCEPTANCE_LOCAL","al retomar cada issue se documenta el comportamiento que realmente debe pro"],["docs/adaptive-orchestration.md:L6-U1","tests/test_adaptive_replan.py::AdaptiveReplanTests::test_incident_replans_immediately_and_unknown_fails_closed","ADAPTIVE_LOCAL","puede continuar paralelizar o debe fallar cerrado controlbot o el runtime"],["docs/adaptive-orchestration.md:L12-U1","tests/test_adaptive_replan.py::AdaptiveReplanTests::test_incident_replans_immediately_and_unknown_fails_closed","ADAPTIVE_LOCAL","una session solo cuenta como"],["docs/adaptive-orchestration.md:L33-U1","tests/test_adaptive_replan.py::AdaptiveReplanTests::test_incident_replans_immediately_and_unknown_fails_closed","ADAPTIVE_LOCAL","pura entre keep replan y fail closed"],["docs/adaptive-orchestration.md:L41-U1","tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_stale_generation_fails_closed","ADAPTIVE_LOCAL","el fence exige coincidencia exacta antes de consultar"],["docs/adaptive-orchestration.md:L47-U1","tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown","ADAPTIVE_LOCAL","solo retiene replans no críticos"],["docs/adaptive-orchestration.md:L49-U1","tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown","ADAPTIVE_LOCAL","replan no equivale a preemption pause allowed solo es true cuando el"],["docs/adaptive-orchestration.md:L56-U1","tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown","ADAPTIVE_LOCAL","siguiente e2e del épico 260 debe componer presence replan fencing usando"],["docs/adaptive-orchestration.md:L63-U1","tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown","ADAPTIVE_LOCAL","presence y fencing únicamente aportan razones de readiness y metadata atrib"],["docs/adaptive-orchestration.md:L67-U1","tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown","ADAPTIVE_LOCAL","una presence unknown o stale o un fencing fail closed excluye candidatos an"],["docs/admin-staff-api.md:B04","tests/test_admin_staff_contract.py::AdminStaffContractTests::test_documented_api_is_staff_only_and_fail_closed","STAFF_AUTHORITY_PARTIAL","el adapter debe hacer cumplir ese límite también en su capa de dominio servicio"],["docs/ai-gateway.md:L13-U1","tests/test_ai_gateway.py::AIGatewayTests::test_execution_evidence_is_attributable","AI_GATEWAY_LOCAL","cada éxito registra provider model executor venture project costo evidence "],["docs/ai-gateway.md:L15-U2","tests/test_ai_gateway.py::AIGatewayTests::test_coding_adapter_is_governed_not_parallel","AI_GATEWAY_LOCAL","así codex cli sigue siendo un adapter gobernado de factory factoryrunner nu"],["docs/ai-gateway.md:L17-U1","tests/test_ai_gateway.py::AIGatewayTests::test_execution_evidence_is_attributable","AI_GATEWAY_LOCAL","credenciales deberán entrar únicamente por el execution plane autorizado"],["docs/arquitectura-tecnica.md:B02","tests/test_kit_security_boundaries.py::KitSecurityBoundaryTests::test_write_capable_workflows_execute_published_kit","ARCHITECTURE_POLICY","permissions por job tokens efímeros sin pat personales acciones fijadas a sha"],["docs/arquitectura-tecnica.md:B03","tests/test_kit_security_boundaries.py::KitSecurityBoundaryTests::test_template_health_never_fakes_release_evidence","ARCHITECTURE_POLICY","deploy con backup migración health y rollback"],["docs/arquitectura-tecnica.md:B04","tests/test_kit_security_boundaries.py::KitSecurityBoundaryTests::test_write_capable_workflows_execute_published_kit","ARCHITECTURE_POLICY","control plane y workspace operativo decide trabajo prioridad scheduler reservas políticas estado durable y ux del dueño"],["docs/autonomy-engine.md:L17-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder","AUTONOMY_LOCAL","una promoción exige"],["docs/autonomy-engine.md:L19-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder","AUTONOMY_LOCAL","fitness completo sin dimensiones faltantes ni regresiones protegidas"],["docs/autonomy-engine.md:L20-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder","AUTONOMY_LOCAL","claim equal o improved"],["docs/autonomy-engine.md:L21-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder","AUTONOMY_LOCAL","risk con contexto crítico completo"],["docs/autonomy-engine.md:L22-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder","AUTONOMY_LOCAL","evidencia no vacía"],["docs/autonomy-engine.md:L24-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder","AUTONOMY_LOCAL","el nivel autonomous no se concede con riesgo high"],["docs/autonomy-engine.md:L28-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy","AUTONOMY_LOCAL","los fallos nunca se esconden"],["docs/autonomy-engine.md:L31-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy","AUTONOMY_LOCAL","major baja dos niveles"],["docs/autonomy-engine.md:L32-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy","AUTONOMY_LOCAL","critical revoca hasta observe"],["docs/autonomy-engine.md:L34-U1","tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy","AUTONOMY_LOCAL","la historia previa no se modifica"],["docs/capability-authority.md:L16-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority","CAPABILITY_LOCAL","disparar menos autonomía o revocación nunca más permisos"],["docs/capability-authority.md:L18-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority","CAPABILITY_LOCAL","cuando una acción recibe varios grants scopes y targets agregados son solo"],["docs/capability-authority.md:L21-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority","CAPABILITY_LOCAL","el resumen como un producto cartesiano authorize evalúa siempre el grant"],["docs/capability-authority.md:L22-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority","CAPABILITY_LOCAL","exacto y falla cerrado ante combinaciones no concedidas"],["docs/capability-authority.md:L26-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_grants_and_revocations_require_trusted_provenance","CAPABILITY_LOCAL","los grants y revocaciones se aceptan únicamente desde"],["docs/capability-authority.md:L39-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_grants_and_revocations_require_trusted_provenance","CAPABILITY_LOCAL","capabilityauthorityregistry autonomy scope acepta únicamente los niveles"],["docs/capability-authority.md:L42-U1","tests/test_capability_authority.py::CapabilityAuthorityTests::test_grants_and_revocations_require_trusted_provenance","CAPABILITY_LOCAL","nunca agregan permisos"],["docs/context-compiler.md:L4-U1","tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context","CONTEXT_LOCAL","project dna ya validado la tarea actual y decisiones lecciones previamente"],["docs/context-compiler.md:L11-U1","tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context","CONTEXT_LOCAL","project dna validado"],["docs/context-compiler.md:L12-U1","tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context","CONTEXT_LOCAL","una task cerrada con id título objetivo y tags"],["docs/context-compiler.md:L13-U1","tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context","CONTEXT_LOCAL","context relevante con categoría fuente texto y tags"],["docs/context-compiler.md:L14-U1","tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context","CONTEXT_LOCAL","límites explícitos"],["docs/context-compiler.md:L15-U1","tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context","CONTEXT_LOCAL","fingerprint sha 256 determinista"],["docs/context-compiler.md:L32-U1","tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic","CONTEXT_LOCAL","máximo 12 piezas de contexto"],["docs/context-compiler.md:L33-U1","tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic","CONTEXT_LOCAL","máximo 1200 caracteres por texto"],["docs/context-compiler.md:L34-U1","tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic","CONTEXT_LOCAL","máximo 12000 caracteres para el paquete serializado"],["docs/context-compiler.md:L35-U1","tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic","CONTEXT_LOCAL","sin i o sin mutación del proyecto y sin decisión de riesgo"],["docs/conversacion-agentes.md:L11-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones","COMMUNICATION_POLICY","encontré que el fallo viene del wiring de test no del transporte productivo"],["docs/conversacion-agentes.md:L11-U2","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones","COMMUNICATION_POLICY","ahora valido el contenedor en app env test"],["docs/conversacion-agentes.md:L12-U1","tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones","COMMUNICATION_POLICY","backend y validar ya están verdes"]]'''))
MODES = {
    "ACCEPTANCE_LOCAL", "ADAPTIVE_LOCAL", "STAFF_AUTHORITY_PARTIAL",
    "AI_GATEWAY_LOCAL", "ARCHITECTURE_POLICY", "AUTONOMY_LOCAL",
    "CAPABILITY_LOCAL", "CONTEXT_LOCAL", "COMMUNICATION_POLICY",
}


def normalized(source: str) -> str:
    return re.sub(r"[\W_]+", " ", source.casefold()).strip()


def report_rows(report: str) -> list[tuple[str, str, str, str, str]]:
    result = []
    for line in report.splitlines():
        if not line.startswith("| `docs/"):
            continue
        fields = line.strip("|").strip().split(" | ")
        if len(fields) != 5 or not all(fields[i].startswith("`") and fields[i].endswith("`") for i in (0, 1, 3)):
            raise ValueError("Malformed report evidence")
        key, witness, mode, anchor, status = fields
        result.append((key[1:-1], witness[1:-1], mode, anchor[1:-1], status))
    if len(result) != 70 or len({row[0] for row in result}) != 70:
        raise ValueError("Absent, duplicated or extra row")
    if any(row[:4] != expected for row, expected in zip(result, ROWS)):
        raise ValueError("Unreviewed evidence mapping drift")
    if any(row[4] != "NO_VERIFICABLE" for row in result):
        raise ValueError("Unproven promotion")
    return result


def validate_sources(rows: tuple[tuple[str, str, str, str], ...] = ROWS, *, overrides: dict[str, str] | None = None) -> None:
    inventory = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        matched = re.match(
            r"^\| `([^`]+)` \| (.*?) \| (NO_VERIFICABLE|SIN_COBERTURA|CUBIERTO|NO_APLICA) \|",
            line,
        )
        if matched:
            inventory[matched[1]] = matched[2], matched[3]
    files = {}
    for key, witness, mode, anchor in rows:
        if key not in inventory or inventory[key][1] != "NO_VERIFICABLE":
            raise ValueError("Unverified or absent source unit " + key)
        if mode not in MODES or not anchor or len(anchor) > 160:
            raise ValueError("Invalid source/mode/anchor")
        match = re.fullmatch(r"(docs/[\w.-]+\.md):(L(\d+)-U\d+|B\d+)", key)
        if match is None:
            raise ValueError("Invalid unit reference " + key)
        path, _, number = match.groups()
        if path not in files:
            files[path] = (overrides or {}).get(path, (ROOT / path).read_text(encoding="utf-8"))
        source = files[path].splitlines()
        candidate = source[int(number) - 1] if number else files[path]
        if number and int(number) > len(source):
            raise ValueError("Source line missing")
        if normalized(anchor) not in normalized(candidate):
            raise ValueError("Source anchor changed " + key)
        if number and normalized(anchor) not in normalized(inventory[key][0]):
            raise ValueError("Matrix unit no longer matches source " + key)
        parts = witness.split("::")
        if len(parts) != 3 or not parts[0].startswith("tests/test_") or not parts[0].endswith(".py"):
            raise ValueError("Invalid code witness")


class VerificacionFactory01Tests(unittest.TestCase):
    def test_70_contratos_y_estados_no_inflados(self):
        self.assertEqual(len(ROWS), 70)
        self.assertEqual(len({row[0] for row in ROWS}), 70)
        self.assertEqual(len(report_rows(REPORT.read_text(encoding="utf-8"))), 70)
        self.assertIn("0 promociones", REPORT.read_text(encoding="utf-8"))
        self.assertIn("consolidación #2035", REPORT.read_text(encoding="utf-8"))

    def test_anclas_exactas_en_fuentes_y_matriz(self):
        validate_sources()

    def test_testigos_ejecutan_codigo_real(self):
        refs = sorted({witness for _, witness, _, _ in ROWS})
        self.assertGreaterEqual(len(refs), 10)
        for ref in refs:
            with self.subTest(witness=ref):
                file_path, cls, method = ref.split("::")
                name = "_verify_factory01_" + Path(file_path).stem
                if name not in sys.modules:
                    spec = importlib.util.spec_from_file_location(name, ROOT / file_path)
                    self.assertIsNotNone(spec)
                    self.assertIsNotNone(spec.loader)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    spec.loader.exec_module(module)
                suite = unittest.TestLoader().loadTestsFromName(
                    cls + "." + method, sys.modules[name],
                )
                output = io.StringIO()
                result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
                self.assertEqual(result.testsRun, 1, ref + ": " + output.getvalue())
                self.assertTrue(result.wasSuccessful(), ref + ": " + output.getvalue())

    def test_mutaciones_negativas_rechazan_trazabilidad_falsa(self):
        base = REPORT.read_text(encoding="utf-8")
        row = next(line for line in base.splitlines() if line.startswith("| `docs/"))
        variants = [
            base.replace(row + "\n", "", 1),
            base.replace(row, row + "\n" + row, 1),
            base.replace(row, row.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            base.replace(row, row.replace(ROWS[0][3], "evidencia inventada"), 1),
            base.replace(row, row.replace(ROWS[0][0], "docs/falso.md:L1-U1"), 1),
            base.replace(row, row.replace(ROWS[0][1], "tests/test_fake.py::Fake::test_fake"), 1),
        ]
        for i, modified in enumerate(variants):
            with self.subTest(mutation=i), self.assertRaises(ValueError):
                report_rows(modified)

        path = "docs/aceptacion-ejecutable.md"
        source = (ROOT / path).read_text(encoding="utf-8")
        original = source.splitlines()[4]
        mutated = source.replace(original, "texto invertido por fixture", 1)
        with self.assertRaises(ValueError):
            validate_sources(overrides={path: mutated})


if __name__ == "__main__":
    unittest.main()
