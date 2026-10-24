# Observador de CI FactoryRunner — entrada GET-only al Performance Loop

**Parent:** Factory #304, AC-02/03/06/10. **Pendiente:** AC-11 real.

\`performance.github_actions_ci.evaluate_factoryrunner_ci_run\` transforma un snapshot **completo** del endpoint autenticado \`GET /repos/pl0n3r/FactoryRunner/actions/runs/{id}\` en una observación v1 del contrato vigente \`performance/contracts/factoryrunner.json\`. Reutiliza el detector, triage, status y la proyección de Readiness canónicos; **no implementa un scheduler, una cola ni un clasificador paralelo**.

## Autoridad y procedencia

El caller debe obtener el JSON desde GitHub autenticado y vincularlo al run exacto que consultó: el adaptador **no verifica firmas, credenciales ni transportes**. Rechaza otra identidad de repositorio, workflow distinto de \`CI\`, eventos que no sean \`push\`, ramas distintas a \`main\`, runs incompletos, en curso u omitidos, SHA y timestamps inválidos y duraciones no positivas o imposibles. Otras propiedades no se vuelven a publicar para no filtrar nombres de usuarios, secrets ni rutas de jobs. Reintentos válidos quedan ligados a \`run_attempt\` en \`evidence_ref\`.

El tiempo computado es \`updated_at - run_started_at\` según la superficie contractual actual; incluye overhead de Actions y **no** es duración por caso de prueba ni latencia del producto. Con una sola muestra solo se clasifica la métrica contractual cuyo mínimo es uno. No se estima P95 desde esa muestra, no se diagnostica el testcase ni se atribuye el cuello sin perfilado: \`bottleneck=unknown\`, \`operational_impact=false\`, severidad operativa \`medium\`.

Con evidencia exacta, el run \`40012602637\` midió **167 s** y \`40029930158\` **182 s**, frente a budget **≤120 s**. Ambos son \`PERF_DEGRADATION/DEGRADED\` mientras la evidencia esté fresca; no demuestran reparación ni mejora. Ante evidencia caducada, la proyección es \`UNKNOWN\`; una entrada inválida genera error explícito, nunca \`HEALTHY\`.

La salida conserva \`authority=unchanged\`, \`execute_actions=false\`, \`create_work_item=false\`, \`candidate_terminal=false\`. El contrato de FactoryRunner solo concede \`observe\`, \`diagnose\`, \`benchmark\`: no autoriza crear WorkItems, alterar tests de FactoryRunner, tocar su pipeline, cambiar budgets, ejecutar deploy ni salir a live.

## AC-11 restante

La clasificación GET-only es un **prerrequisito de observación**, no el E2E de remediación. Hace falta triage y benchmark causal del runner, hoja correctiva autorizada con V3 en el repositorio competente, PR/CI y CodeRabbit FINAL, medidas \`push/main\` **antes y después** con identidad/release, decisión \`ADOPT/REVERT\` y nueva baseline/Readiness. Mantener Factory #304 abierto hasta esa evidencia. No publicar \`Factory@v1\` por esta hoja.
