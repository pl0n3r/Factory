# Evidencia de consumidores para Factory@v1 — solo lectura

**Hoja:** [Factory #2093](https://github.com/pl0n3r/Factory/issues/2093), épico [#1080](https://github.com/pl0n3r/Factory/issues/1080).

**Autoridad:** el propietario decidió A en [#2075](https://github.com/pl0n3r/Factory/issues/2075#issuecomment-6713206181), con journal bot v2/A #6713215649, para desarrollar y probar una futura política. No aprobó publicar o mover Factory@v1 ni cambiar permisos, gates o la identidad del dueño.

## Problema y modelo de confianza

El preflight [#2084](release-auto-candidate-preflight.md) conserva como UNKNOWN la compatibilidad de los consumidores y el watchdog. Un CI verde en el main de Condor o GrindFlow, por ejemplo, **no demuestra** compatibilidad con un SHA nuevo de Factory que todavía no se distribuye. No se debe inferir GO ni READY a partir de la etiqueta, de un check verde o de booleanos aportados por un caller.

El nuevo módulo scripts/release_auto_consumer_gate.py ofrece dos contratos diferentes:

1. collect_consumer_ci(get=...) consulta, como máximo, doce endpoints GitHub REST GET: ramas main y check-runs exactos del HEAD observado en los seis consumidores. Exige branch protegida, SHA de 40 hex, un solo check llamado Validar o validate, resultado terminal success e identidad de la aplicación GitHub Actions id=15368. Una fuente ausente, ambigua o roja produce BLOCKED. **Incluso seis CIs exitosos producen BLOCKED / candidate_compatibility_and_watchdog_unknown**, porque faltan evidencias sobre el candidato Factory.
2. evaluate_fixture(snapshot, synthetic=True) comprueba en pruebas exclusivamente sintéticas que existen seis registros sin duplicados, cada uno correlacionado con el mismo SHA candidato, y un registro independiente de watchdog exact-SHA. Rechaza fuentes, run IDs, estados o SHAs inválidos. Su mejor resultado es REVIEW_ONLY con synthetic=true y evidence_authenticated=false. En una llamada normal sin synthetic=True, **siempre BLOCKED**.

Los valores source=independent de los fixtures son declaraciones del caller, no pruebas de autenticación: la función pura no verifica firmas ni la procedencia real. REVIEW_ONLY sintético tampoco es readiness ni prueba de que el workflow haya validado el candidato.

## Matriz de observación

| Consumidor | Fuente GET | Límite de la evidencia |
| --- | --- | --- |
| pl0n3r/Condor | main protegido + check exact-HEAD | No acredita compatibilidad candidata |
| pl0n3r/GrindFlow | main protegido + check exact-HEAD | No acredita compatibilidad candidata |
| pl0n3r/brvtal | main protegido + check exact-HEAD | No acredita compatibilidad candidata |
| pl0n3r/ControlBot | main protegido + check exact-HEAD | No acredita compatibilidad candidata |
| pl0n3r/AutoFactory | main protegido + check exact-HEAD | No acredita compatibilidad candidata |
| pl0n3r/FactoryRunner | main protegido + check exact-HEAD | No acredita compatibilidad candidata |

La función _get utiliza gh api -X GET con allowlist de rutas REST, sin shell, salida acotada y timeout. Un mock GET solo sirve para QA. La integración futura debe verificar una prueba genuina de compatibilidad contra el **mismo SHA candidato de Factory**, la identidad del workflow/producto y un recibo independiente auténtico de watchdog. Esta hoja no integra esos recibos, ni edita el preflight de #2084, ni elimina la decisión humana vigente para publicar cada versión.

## Reversión, seguridad y aceptación

Los resultados contienen siempre authorizes_release=false, evidence_authenticated=false, mutations=0, tag_writes=0 y release_writes=0. No hay llamadas HTTP mutantes, nuevos workflows, tareas programadas, secretos, datos personales ni acceso a hosting. No se modifican release.yml, release-window.yml, permisos, rulesets, etiquetas, versionado o consumidores.

Pruebas reproducibles:

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_release_auto_consumer_gate

Reversión: revertir el squash y retirar estos tres archivos. Esta hoja es una preparación reversible, **no cumple por sí sola AC-01..03** de #1080 ni permite release o go-live.
