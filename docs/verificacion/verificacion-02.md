# Factory #2018 — verificación lote 02/18 (70 filas)

**Corte:** 5-nov-2026; fuente `docs/matriz-cobertura.md`; épica #304;
reserva V3 `2d534045-0c3e-46fc-bd94-17eea218ea43`; fase `construccion`.
Se mantienen fuera del PR los archivos de la matriz, la producción y los permisos.

## Resultado verificable y límites

**70/70** cláusulas trazadas de conversación de agentes (24), coordinación PR
(21), costos y presupuestos (11), cumplimiento y licencias (13), y vistas
derivadas (1). **0 promociones** a `CUBIERTO`, 0 `SIN_COBERTURA` nuevas:
las 70 cláusulas permanecen `NO_VERIFICABLE` sin evidencia integral externa.

La suite `tests/test_verificacion_factory_02.py` contrasta cada fila con el
inventario y su línea histórica, ejecuta testigos de implementación reales
y rechaza en pruebas negativas borrados, duplicados, filas adicionales mal
formadas, cambios de anclas, testigos falsos y cualquier falsa promoción.
Los métodos existentes de `tests/`, `metricas/` y `seguridad/` ejercen
reglas concretas de coordinación, costo y privacidad mediante fixtures.
No acreditan ejecución de agentes remotos, CI de consumidores, telemetría
externa de gasto, revisión jurídica efectiva ni producción.

| Alcance | Testigo conductual | Brecha que no se promueve |
| --- | --- | --- |
| COMUNICACION_LOCAL | reglas de conversación, STATE y reanudación | comportamiento real de agentes externos |
| COORDINACION_LOCAL | post-merge y preflight de permisos | eventos GitHub/consumidores en producción |
| COSTOS_LOCAL_NO_TELEMETRIA | warnings, límites, marcador y deduplicación | gasto medido de API/CI, informes de ahorro |
| CUMPLIMIENTO_LOCAL_NO_LEGAL | esquema privacidad y CLI fail-closed | revisión humana y cumplimiento efectivo por producto |
| VISTAS_DERIVADAS_LOCAL | determinismo y drift | observación real de las vistas consumidoras |

## Trazabilidad de las 70 unidades

| Fila exacta | Testigo de código | Alcance | Ancla real normalizada | Resultado |
| --- | --- | --- | --- | --- |
| `docs/conversacion-agentes.md:L12-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio` | COMUNICACION_LOCAL | `solo falta playwright` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L12-U3` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio` | COMUNICACION_LOCAL | `mientras corre reviso el flujo nuevo para detectar fallos lógicos` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L13-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio` | COMUNICACION_LOCAL | `el enfoque a falló por x` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L13-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio` | COMUNICACION_LOCAL | `cambio al enfoque b porque evita y` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L15-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_prohibe_progreso_vacio` | COMUNICACION_LOCAL | `prohibidas sigo revisando déjame pensar estoy trabajando en eso y repeti` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L39-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial` | COMUNICACION_LOCAL | `debe conservar objetivo repo issue pr branch y sha decisiones tomadas ha` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L43-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial` | COMUNICACION_LOCAL | `no reexplicar lo ya presente en issue pr lecciones` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L44-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial` | COMUNICACION_LOCAL | `buscar primero` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L44-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial` | COMUNICACION_LOCAL | `abrir solo fragmentos relevantes` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L45-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial` | COMUNICACION_LOCAL | `agrupar lecturas independientes en paralelo` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L46-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_fixture_permite_continuar_sin_historial` | COMUNICACION_LOCAL | `sin polling una lectura terminal de ci y más solo ante fallo o transició` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L47-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_estado_compacto_canonico_y_por_hitos` | COMUNICACION_LOCAL | `resultado primero detalle después` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L47-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_estado_compacto_canonico_y_por_hitos` | COMUNICACION_LOCAL | `hitos en 3 7 líneas salvo petición` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L48-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_estado_compacto_canonico_y_por_hitos` | COMUNICACION_LOCAL | `no duplicar en el chat lo registrado en github` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L57-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `lo de la segunda fila no se resuelve solo con instrucciones si la integr` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L65-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `no es un fallo no reenviar el mensaje no abrir otro chat y no cancelar m` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L65-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `una sola espera luego continuar` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L66-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `reducir disparadores pedir una sola tarea acotada por turno` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L66-U2` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `no pegar secretos tokens ni volcados grandes de logs salida resumir y ci` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L66-U3` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `no encadenar ejecuciones de código innecesarias` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L66-U4` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `describir la finalidad defensiva operativa de cualquier comando de segur` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L67-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_revision_de_plataforma_no_es_fallo` | COMUNICACION_LOCAL | `si se repite en el mismo chat escribir una nota state continuar en un ch` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L69-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones` | COMUNICACION_LOCAL | `requiere issue propio` | NO_VERIFICABLE |
| `docs/conversacion-agentes.md:L73-U1` | `tests/test_conversacion_agentes.py::ConversacionAgentesTests::test_nucleo_define_progreso_solo_en_transiciones` | COMUNICACION_LOCAL | `tests test conversacion agentes py comprueba que trae todos los campos y` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L5-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `la coordinación valida cada pr mientras está abierto rama canónica relac` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L8-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `closes n github puede cerrar el issue antes de que una revalidación tard` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L9-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `volver a exigir entonces que el issue siga abierto produce un falso rojo` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L16-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `el caller canónico conserva pull request closed porque pr event todavía` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L17-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `debe reconciliar la reserva y el estado` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L18-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `el caller usa validar pr evento como precondición ese job solo completa` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L19-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `cuando github event pull request merged true validar pr conserva` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L21-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `llega a invocar operation validate` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L22-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `el reusable aplica la misma defensa una llamada validate originada por u` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L24-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `un cierre sin merge tiene merged false y no recibe esta excepción` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L27-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `mantener la forma legacy de validar pr` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L29-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_merged_pr_validation_is_neutral` | COORDINACION_LOCAL | `closed por sí solo nunca se convierte en autoridad para saltarse validac` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L33-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation` | COORDINACION_LOCAL | `la neutralidad post merge no cambia validate pull` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L34-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation` | COORDINACION_LOCAL | `siga abierto el coordinador conserva el comportamiento fail closed exist` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L35-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation` | COORDINACION_LOCAL | `el issue debe estar abierto la branch debe ser trabajo issue n la reserv` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L36-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation` | COORDINACION_LOCAL | `su identidad deben ser válidas la relación de cierre debe corresponder y` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L40-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation` | COORDINACION_LOCAL | `issue n debe estar abierto durante el pr` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L47-U1` | `tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate` | COORDINACION_LOCAL | `tests test coordinacion reusable contract py t test merged pr validation` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L48-U1` | `tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate` | COORDINACION_LOCAL | `tests test consumer coordination template py consumercoordinationtemplat` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L49-U1` | `tests/test_consumer_coordination_template.py::ConsumerCoordinationTemplateTests::test_merged_pr_does_not_revalidate` | COORDINACION_LOCAL | `tests test coordinar trabajo py coordinaciontests test open pr with clos` | NO_VERIFICABLE |
| `docs/coordinacion-pr-validation.md:L52-U1` | `tests/test_coordinacion_reusable_contract.py::T::test_strict_preflight_rejects_permission_escalation` | COORDINACION_LOCAL | `la reversión es un revert de estos cambios declarativos y no requiere mi` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L5-U1` | `metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok` | COSTOS_LOCAL_NO_TELEMETRIA | `el agente que abre un pr declara únicamente métricas numéricas y clasifi` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L13-U1` | `metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok` | COSTOS_LOCAL_NO_TELEMETRIA | `mientras tokens minutos de ci minutos de agente o rondas solo estén auto` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L15-U1` | `metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok` | COSTOS_LOCAL_NO_TELEMETRIA | `ok reservado para una evaluación completamente observada y por debajo de` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L15-U2` | `metricas/test_costos.py::CostTests::test_declared_usage_never_reports_verified_ok` | COSTOS_LOCAL_NO_TELEMETRIA | `con la telemetría actual no se emite a partir de datos autodeclarados` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L16-U1` | `metricas/test_costos.py::CostTests::test_near_limit_warns_and_over_limit_soft_blocks` | COSTOS_LOCAL_NO_TELEMETRIA | `warning al menos una dimensión está entre 80 y 100` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L17-U1` | `metricas/test_costos.py::CostTests::test_near_limit_warns_and_over_limit_soft_blocks` | COSTOS_LOCAL_NO_TELEMETRIA | `soft block falta medición o alguna dimensión supera 100` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L19-U1` | `metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent` | COSTOS_LOCAL_NO_TELEMETRIA | `un marker malformado falla cerrado` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L19-U2` | `metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent` | COSTOS_LOCAL_NO_TELEMETRIA | `un pr dentro de límites pero con dimensiones solo declaradas permanece e` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L19-U3` | `metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent` | COSTOS_LOCAL_NO_TELEMETRIA | `así no se confunde una estimación con costo observado` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L27-U1` | `metricas/test_costos.py::CostTests::test_ci_trend_rejects_duplicate_run_ids` | COSTOS_LOCAL_NO_TELEMETRIA | `un run id duplicado falla cerrado para evitar doble conteo` | NO_VERIFICABLE |
| `docs/costos-presupuestos.md:L29-U1` | `metricas/test_costos.py::CostTests::test_missing_marker_is_soft_block_not_silent` | COSTOS_LOCAL_NO_TELEMETRIA | `f1f no acredita ningún informe mensual nuevo ni ahorro cuantificado de a` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L7-U1` | `seguridad/test_cumplimiento.py::PrivacyTests::test_valid_record` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `el script seguridad cumplimiento py comprueba que un producto tenga un i` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L15-U1` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `evidence exige siete referencias no sensibles a evidencias revisadas pri` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L15-U2` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `el validador rechaza campos adicionales y revisiones con más de 365 días` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L17-U1` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `importante exception for legal review solo deja constancia de que una ex` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L17-U2` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `el responsable debe contrastar evidencias y hechos del producto antes de` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L21-U1` | `seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `el cli no acepta rutas arbitrarias` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L21-U2` | `seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `la evidencia de privacidad entra por stdin por lo que su ubicación priva` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L36-U1` | `seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `las pruebas propias son pythonpath seguridad python3 m unittest discover` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L37-U1` | `seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `seguridad yml ya ejecuta unittest discover s seguridad p test py` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L37-U2` | `seguridad/test_cumplimiento.py::CliSafetyTests::test_cli_reads_privacy_from_stdin_and_canonical_lock` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `al integrar este slice las regresiones de cumplimiento quedan dentro de ` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L38-U1` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `cada proyecto debe aportar al menos una evidencia documentada y verifica` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L38-U2` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `un fixture de tests no es prueba de cumplimiento de ningún producto` | NO_VERIFICABLE |
| `docs/cumplimiento-datos-licencias.md:L39-U1` | `seguridad/test_cumplimiento.py::PrivacyTests::test_stale_review_fails` | CUMPLIMIENTO_LOCAL_NO_LEGAL | `cierre de 12 requiere ci y evidencia de la revisión material no únicamen` | NO_VERIFICABLE |
| `docs/derived-views.md:L3-U1` | `tests/test_derived_views.py::DerivedViewsTests::test_drift_fails_closed` | VISTAS_DERIVADAS_LOCAL | `una vista derivada nunca es una fuente de verdad` | NO_VERIFICABLE |

## Validación y reversión

`python3 -m unittest -v tests.test_verificacion_factory_02` y luego
`Tests de scripts` / `Validar` terminales sobre el HEAD exacto.
La consolidación #2035 queda pendiente hasta cerrar las otras hojas de su
DAG; este PR no edita `docs/matriz-cobertura.md`, no infiere `GREEN`,
ni publica releases. Sin datos reales, proveedores, secretos, gastos,
rollback de producción o cambios de autoridad. Reversión: squash revert.
