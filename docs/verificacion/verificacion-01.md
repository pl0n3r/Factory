# Factory #2017 — verificación del lote 01/18 (70 filas)

**Corte:** 5-nov-2026; fuente `docs/matriz-cobertura.md`; épica #304;
reserva V3 `2d8c8a81-c8d3-456e-b906-06563d65f6ae`; fase `construccion`.
Solo archivos `docs/verificacion/verificacion-01.md` y `tests/test_verificacion_factory_01.py`.

## Alcance, código real y límites

Se contrastan exactamente **70/70** unidades de nueve documentos de Factory.
Las 66 referencias `LNN-Ux` conservan un ancla reproducible en la línea
de origen, y las cuatro referencias sintéticas `Bxx` contrastan un ancla
real del mismo documento, sin suponer que una síntesis sea prueba completa.

`tests/test_verificacion_factory_01.py` inspecciona cada entrada, cada
fuente y la matriz, ejecuta métodos reales de regresión en los contratos
locales de aceptación, orquestación adaptativa, staff, AI Gateway,
arquitectura, autonomía, autoridad, compilación de contexto y conversación.
Rechaza filas ausentes, duplicadas, extra, alteradas y promociones sin
prueba causal. Los testigos solo acreditan subcontratos de código local:
no demuestran permisos vigentes de GitHub, integraciones de consumidores,
consentimiento, publicación de tag, recuperación productiva ni decisiones
humanas. **0 promociones**; las 70 filas quedan `NO_VERIFICABLE`
hasta completar la evidencia externa e integral y la consolidación #2035.

| Clase | Subcontrato local que se ejecuta | Evidencia que todavía falta |
| --- | --- | --- |
| ACCEPTANCE_LOCAL | parser de criterios y checks éxito/fallo | integración y gates exactos de consumidores |
| ADAPTIVE_LOCAL | replan, fencing y fallos cerrados | sesiones remotas y runtime observado |
| STAFF_AUTHORITY_PARTIAL | superficie de administración y límites | adapters reales de cada producto |
| AI_GATEWAY_LOCAL | atribución y gobernanza del adapter | proveedores/credenciales y ejecución real |
| ARCHITECTURE_POLICY | guardas del kit y release | deploy, rulesets y roles reales |
| AUTONOMY_LOCAL | niveles y degradación de autonomía | evidencia productiva por capability |
| CAPABILITY_LOCAL | grants exactos y provenance | autoridad distribuida real |
| CONTEXT_LOCAL | contexto determinista y límites | contexto real de consumidores |
| COMMUNICATION_POLICY | obligaciones de comunicación | práctica/observación en sesiones reales |

## Trazabilidad de las 70 unidades

| Fila exacta | Testigo de código | Alcance | Ancla real normalizada | Resultado |
| --- | --- | --- | --- | --- |
| `docs/aceptacion-ejecutable.md:L5-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `gates genéricos como lint tests globales coordinación codeql y sonar` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L6-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `criterios específicos del issue definidos como ac nn y verificados por el j` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L8-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `un pr no está hecho si solo pasa la primera capa` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L12-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `el issue debe contener exactamente una sección no vacía para` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L14-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `contexto` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L15-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `alcance` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L16-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `fuera de alcance` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L17-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `criterios de aceptación` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L18-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `contrato ejecutable` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L22-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `ac 01 descripción verificable` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L37-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `los ids del marker deben coincidir exactamente con los ids humanos` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L41-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `solo acepta un target con forma` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L45-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_contract_rejects_missing_sections_and_mismatch` | ACCEPTANCE_LOCAL | `la ruta debe vivir en un directorio de tests permitido tests metricas segur` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L49-U2` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_check_must_exist_and_be_success` | ACCEPTANCE_LOCAL | `nunca cuenta como éxito` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L49-U3` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_check_must_exist_and_be_success` | ACCEPTANCE_LOCAL | `un check completed solo satisface el criterio con conclusion success` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L51-U1` | `tests/test_aceptacion_kit.py::AcceptanceContractTests::test_check_must_exist_and_be_success` | ACCEPTANCE_LOCAL | `validar y criterios de aceptación no pueden referenciarse como evidencia pa` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L57-U1` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired` | ACCEPTANCE_LOCAL | `lint tests coordinación criterios de aceptación validar` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L59-U1` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_readiness_does_not_repeat_contract_tests` | ACCEPTANCE_LOCAL | `la espera solo vuelve a leer check runs no vuelve a ejecutar workflows jobs` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L59-U2` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_readiness_does_not_repeat_contract_tests` | ACCEPTANCE_LOCAL | `un fallo terminal distinto de evidencia pendiente aborta de inmediato y el ` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L61-U1` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired` | ACCEPTANCE_LOCAL | `los criterios kind test no se ejecutan durante ese preflight` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L67-U1` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired` | ACCEPTANCE_LOCAL | `github issue template trabajo yml exige las cinco secciones y config yml de` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L71-U1` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired` | ACCEPTANCE_LOCAL | `los pr históricos abiertos deberán migrar su issue al contrato cuando vuelv` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L71-U2` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired` | ACCEPTANCE_LOCAL | `no se fabrican criterios retrospectivos` | NO_VERIFICABLE |
| `docs/aceptacion-ejecutable.md:L71-U3` | `tests/test_aceptacion_workflow_contract.py::AcceptanceWorkflowContractTests::test_issue_form_and_required_gate_are_wired` | ACCEPTANCE_LOCAL | `al retomar cada issue se documenta el comportamiento que realmente debe pro` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L6-U1` | `tests/test_adaptive_replan.py::AdaptiveReplanTests::test_incident_replans_immediately_and_unknown_fails_closed` | ADAPTIVE_LOCAL | `puede continuar paralelizar o debe fallar cerrado controlbot o el runtime` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L12-U1` | `tests/test_adaptive_replan.py::AdaptiveReplanTests::test_incident_replans_immediately_and_unknown_fails_closed` | ADAPTIVE_LOCAL | `una session solo cuenta como` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L33-U1` | `tests/test_adaptive_replan.py::AdaptiveReplanTests::test_incident_replans_immediately_and_unknown_fails_closed` | ADAPTIVE_LOCAL | `pura entre keep replan y fail closed` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L41-U1` | `tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_stale_generation_fails_closed` | ADAPTIVE_LOCAL | `el fence exige coincidencia exacta antes de consultar` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L47-U1` | `tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown` | ADAPTIVE_LOCAL | `solo retiene replans no críticos` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L49-U1` | `tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown` | ADAPTIVE_LOCAL | `replan no equivale a preemption pause allowed solo es true cuando el` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L56-U1` | `tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown` | ADAPTIVE_LOCAL | `siguiente e2e del épico 260 debe componer presence replan fencing usando` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L63-U1` | `tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown` | ADAPTIVE_LOCAL | `presence y fencing únicamente aportan razones de readiness y metadata atrib` | NO_VERIFICABLE |
| `docs/adaptive-orchestration.md:L67-U1` | `tests/test_adaptive_fencing.py::AdaptiveFencingTests::test_noncritical_rebalance_respects_cooldown` | ADAPTIVE_LOCAL | `una presence unknown o stale o un fencing fail closed excluye candidatos an` | NO_VERIFICABLE |
| `docs/admin-staff-api.md:B04` | `tests/test_admin_staff_contract.py::AdminStaffContractTests::test_documented_api_is_staff_only_and_fail_closed` | STAFF_AUTHORITY_PARTIAL | `el adapter debe hacer cumplir ese límite también en su capa de dominio servicio` | NO_VERIFICABLE |
| `docs/ai-gateway.md:L13-U1` | `tests/test_ai_gateway.py::AIGatewayTests::test_execution_evidence_is_attributable` | AI_GATEWAY_LOCAL | `cada éxito registra provider model executor venture project costo evidence ` | NO_VERIFICABLE |
| `docs/ai-gateway.md:L15-U2` | `tests/test_ai_gateway.py::AIGatewayTests::test_coding_adapter_is_governed_not_parallel` | AI_GATEWAY_LOCAL | `así codex cli sigue siendo un adapter gobernado de factory factoryrunner nu` | NO_VERIFICABLE |
| `docs/ai-gateway.md:L17-U1` | `tests/test_ai_gateway.py::AIGatewayTests::test_execution_evidence_is_attributable` | AI_GATEWAY_LOCAL | `credenciales deberán entrar únicamente por el execution plane autorizado` | NO_VERIFICABLE |
| `docs/arquitectura-tecnica.md:B02` | `tests/test_kit_security_boundaries.py::KitSecurityBoundaryTests::test_write_capable_workflows_execute_published_kit` | ARCHITECTURE_POLICY | `permissions por job tokens efímeros sin pat personales acciones fijadas a sha` | NO_VERIFICABLE |
| `docs/arquitectura-tecnica.md:B03` | `tests/test_kit_security_boundaries.py::KitSecurityBoundaryTests::test_template_health_never_fakes_release_evidence` | ARCHITECTURE_POLICY | `deploy con backup migración health y rollback` | NO_VERIFICABLE |
| `docs/arquitectura-tecnica.md:B04` | `tests/test_kit_security_boundaries.py::KitSecurityBoundaryTests::test_write_capable_workflows_execute_published_kit` | ARCHITECTURE_POLICY | `control plane y workspace operativo decide trabajo prioridad scheduler reservas políticas estado durable y ux del dueño` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L17-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder` | AUTONOMY_LOCAL | `una promoción exige` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L19-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder` | AUTONOMY_LOCAL | `fitness completo sin dimensiones faltantes ni regresiones protegidas` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L20-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder` | AUTONOMY_LOCAL | `claim equal o improved` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L21-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder` | AUTONOMY_LOCAL | `risk con contexto crítico completo` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L22-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder` | AUTONOMY_LOCAL | `evidencia no vacía` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L24-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_capability_progresses_through_evidence_ladder` | AUTONOMY_LOCAL | `el nivel autonomous no se concede con riesgo high` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L28-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy` | AUTONOMY_LOCAL | `los fallos nunca se esconden` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L31-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy` | AUTONOMY_LOCAL | `major baja dos niveles` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L32-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy` | AUTONOMY_LOCAL | `critical revoca hasta observe` | NO_VERIFICABLE |
| `docs/autonomy-engine.md:L34-U1` | `tests/test_autonomy_engine.py::AutonomyEngineTests::test_failures_reduce_or_revoke_autonomy` | AUTONOMY_LOCAL | `la historia previa no se modifica` | NO_VERIFICABLE |
| `docs/capability-authority.md:L16-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority` | CAPABILITY_LOCAL | `disparar menos autonomía o revocación nunca más permisos` | NO_VERIFICABLE |
| `docs/capability-authority.md:L18-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority` | CAPABILITY_LOCAL | `cuando una acción recibe varios grants scopes y targets agregados son solo` | NO_VERIFICABLE |
| `docs/capability-authority.md:L21-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority` | CAPABILITY_LOCAL | `el resumen como un producto cartesiano authorize evalúa siempre el grant` | NO_VERIFICABLE |
| `docs/capability-authority.md:L22-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_matrix_preserves_exact_bindings_without_cartesian_authority` | CAPABILITY_LOCAL | `exacto y falla cerrado ante combinaciones no concedidas` | NO_VERIFICABLE |
| `docs/capability-authority.md:L26-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_grants_and_revocations_require_trusted_provenance` | CAPABILITY_LOCAL | `los grants y revocaciones se aceptan únicamente desde` | NO_VERIFICABLE |
| `docs/capability-authority.md:L39-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_grants_and_revocations_require_trusted_provenance` | CAPABILITY_LOCAL | `capabilityauthorityregistry autonomy scope acepta únicamente los niveles` | NO_VERIFICABLE |
| `docs/capability-authority.md:L42-U1` | `tests/test_capability_authority.py::CapabilityAuthorityTests::test_grants_and_revocations_require_trusted_provenance` | CAPABILITY_LOCAL | `nunca agregan permisos` | NO_VERIFICABLE |
| `docs/context-compiler.md:L4-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context` | CONTEXT_LOCAL | `project dna ya validado la tarea actual y decisiones lecciones previamente` | NO_VERIFICABLE |
| `docs/context-compiler.md:L11-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context` | CONTEXT_LOCAL | `project dna validado` | NO_VERIFICABLE |
| `docs/context-compiler.md:L12-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context` | CONTEXT_LOCAL | `una task cerrada con id título objetivo y tags` | NO_VERIFICABLE |
| `docs/context-compiler.md:L13-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context` | CONTEXT_LOCAL | `context relevante con categoría fuente texto y tags` | NO_VERIFICABLE |
| `docs/context-compiler.md:L14-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context` | CONTEXT_LOCAL | `límites explícitos` | NO_VERIFICABLE |
| `docs/context-compiler.md:L15-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_mission_package_contains_only_relevant_context` | CONTEXT_LOCAL | `fingerprint sha 256 determinista` | NO_VERIFICABLE |
| `docs/context-compiler.md:L32-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic` | CONTEXT_LOCAL | `máximo 12 piezas de contexto` | NO_VERIFICABLE |
| `docs/context-compiler.md:L33-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic` | CONTEXT_LOCAL | `máximo 1200 caracteres por texto` | NO_VERIFICABLE |
| `docs/context-compiler.md:L34-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic` | CONTEXT_LOCAL | `máximo 12000 caracteres para el paquete serializado` | NO_VERIFICABLE |
| `docs/context-compiler.md:L35-U1` | `tests/test_context_compiler.py::ContextCompilerTests::test_package_is_bounded_and_deterministic` | CONTEXT_LOCAL | `sin i o sin mutación del proyecto y sin decisión de riesgo` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L11-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones` | COMMUNICATION_POLICY | `encontré que el fallo viene del wiring de test no del transporte productivo` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L11-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones` | COMMUNICATION_POLICY | `ahora valido el contenedor en app env test` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L12-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones` | COMMUNICATION_POLICY | `backend y validar ya están verdes` | NO_VERIFICABLE |

## Validación y reversión

`python3 -m unittest -v tests.test_verificacion_factory_01` y
`Tests de scripts` / `Validar` sobre HEAD exacto del PR.
La matriz `docs/matriz-cobertura.md` se deja intacta; el consolidado
#2035 permanece bloqueado por las otras hojas del DAG, no se infiere
`CUBIERTO` de tener un PR. Sin secretos, red externa, datos reales,
gasto, producción, releases, cambios de permisos o go-live.
Reversión: squash revert.
