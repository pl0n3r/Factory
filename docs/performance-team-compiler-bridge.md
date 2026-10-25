# Puente de triage profesional a Team Compiler (#1504, epico #304)

El adaptador performance.team_compiler_bridge.compile_performance_team consume una deteccion validada de Performance Contract v1 con **evaluated_at UTC obligatorio**, para reevaluar freshness frente al instante actual, no solo el estado historico CURRENT. Reutiliza triage_performance y el Team Compiler real scripts.roles_kit.compile_team, con el catalogo de roles existente.

Para PERF_DEGRADATION o PERF_INCIDENT con evidencia CURRENT devuelve TEAM_RECOMMENDED, primary, roles, review, compiler_primary y referencias saneadas. Las descripciones para Team Compiler son areas a investigar, no rutas de codigo ni causas comprobadas. PERF_INFO produce NO_ASSIGNMENT; stale/UNKNOWN, catalogos incompletos o adulterados y tiempos no validos fallan cerrado.

Limite duro: composicion NO equivale a asignacion por Dispatcher ni a WorkItem creado en Factory Queue #269. No prueba el E2E productivo AC-11 de #304 ni habilita AUTO_REPAIR. Conserva authority=unchanged, execute_actions=false, create_work_item=false, dispatch=false. Las acciones reales necesitan autoridad, readiness, V3, claims y CI propios. No modifica presupuestos, releases o tag Factory@v1.

Test: python3 -m unittest discover -s tests -p 'test_performance_team_compiler_bridge.py' -v.
