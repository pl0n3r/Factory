# Sonar Watch v1

**Estado post-F1C (#1308 / PR #1309): Sonar Watch no se ejecuta automáticamente.** Se eliminó el cron cada seis horas y `workflow_dispatch` al retirar `.github/workflows/sonar-watch.yml`. Los Issues `[AUTO] Sonar` (#1052/#1053) **no se refrescan automáticamente**. El motor offline `scripts/sonar-watch.py` y la proyección `quality.sonar` permanecen disponibles solo para ejecuciones expresamente autorizadas.

## Runtime versionado

La configuración versionada para ejecución manual/offline es `quality/sonar-watch-config.json`; el motor no depende de `SONAR_WATCH_CONFIG_JSON`. No hay scheduler activo.

El contrato versionado histórico proviene de la **Opción C aprobada en #516**; no implica ejecución automática vigente:

| Proyecto | Sonar key | GitHub | Método | Freshness | Vulnerabilities / Bugs |
| --- | --- | --- | --- | ---: | ---: |
| brvtal | `pl0n3r_brvtal` | `pl0n3r/brvtal` | automatic | 48 h | 0 / 18 |
| condor | `pl0n3r_Condor` | `pl0n3r/Condor` | automatic | 48 h | 0 / 0 |
| controlbot | `pl0n3r_factory-control` | `pl0n3r/ControlBot` | ci | 48 h | 0 / 1 |
| factory | `pl0n3r_factory` | `pl0n3r/Factory` | ci | 48 h | 0 / 0 |
| factoryrunner | `pl0n3r_FactoryRunner` | `pl0n3r/FactoryRunner` | automatic | 7 d | 0 / 0 |
| grindflow | `pl0n3r_GrindFlow` | `pl0n3r/GrindFlow` | automatic | 48 h | 8 / 0 |

Campos comunes: `expected_visibility=public`, `max_organization_line_usage_percent=80`, `max_open_hotspots=0` y `max_debt_age_days=30`.

Los topes escalonados son techo productivo explícito, no un waiver oculto: ControlBot bugs baja de 1 a 0 al cerrar ControlBot #559; GrindFlow vulnerabilities baja de 8 a 0 al cerrar GrindFlow #195; BRVTAL bugs baja de 18 a 0 al cerrar BRVTAL #808. Esos descensos se materializan actualizando este contrato versionado; no requieren reinterpretar observación runtime como política.

Migrar `analysis_method` de un proyecto requiere nueva decisión del dueño.

## Autenticación y fail-closed

`SONAR_TOKEN` es opcional cuando todos los contratos versionados esperan visibilidad pública.

Antes de cualquier request Sonar, el runtime inspecciona localmente los seis `contract.sonar.expected_visibility`. Si alguno exige `private` y no existe `SONAR_TOKEN`, aborta sin tocar la red.

Después, el preflight observa visibilidad mediante `GET /api/components/show`. Payload ausente o ambiguo falla cerrado. La visibilidad observada se normaliza después contra el Quality Contract; no se convierte en política implícita.

## Solo lectura de Sonar

El cliente Sonar está marcado read-only y rechaza cualquier método distinto de `GET`. No usa `/api/autoscan/activation`.

El método de análisis se observa exclusivamente con:

`GET /api/settings/values?component=<key>&keys=sonar.autoscan.enabled`

El parser exige exactamente un setting `sonar.autoscan.enabled` con valor textual `true` o `false`, normalizado a `automatic` o `ci`. Ausencia, duplicidad, key inesperada o cualquier otro valor falla cerrado.

## Ejecución manual/offline (scheduler desactivado)

Después de F1C **no existe** `.github/workflows/sonar-watch.yml`; el cron cada seis horas (`schedule`) y `workflow_dispatch` están **desactivados**. Se conservan `scripts/sonar-watch.py`, `quality/sonar-watch-config.json` y `tests/test_sonar_watch.py` para análisis y pruebas offline. El entrypoint histórico es `python3 scripts/sonar-watch.py`; esto **no autoriza ejecutarlo** ni sincronizar Issues reales. El antiguo job tenía `contents: read` e `issues: write`, pero ya no está activo.

Los checks **Sonar CI-based** (`sonar.yml`) y **CodeQL** siguen como validadores CI de PR y **no sustituyen** la sincronización periódica Sonar→GitHub Issues.

## Idempotencia y evidencia

Cada señal usa un marker estable `project + signal -> fingerprint`. Existe como máximo un Issue administrado por proyecto/señal. `FAIL`, `UNKNOWN` o `STALE` actualizan/reabren el mismo Issue; un `PASS` solo lo cierra con freshness `CURRENT`. Una señal `NOT_APPLICABLE` no abre Issue: si existe uno abierto del mismo marker, Sonar Watch añade una sola explicación con razón/source_ref y lo cierra; ejecuciones posteriores no vuelven a comentar ni reabrirlo.

Todo Issue abierto que administra el watcher se crea o reconcilia con `tipo: calidad`, `prioridad: media` y `estado: bloqueado`. Las alertas son observaciones, **no hojas ejecutables**: el cuerpo explica que solo un `PASS/CURRENT` o un `NOT_APPLICABLE` canónico puede desbloquearlas. En cierre verificado, el estado de GitHub pasa a `closed` y la etiqueta a `estado: completado`; el contenido histórico no se reescribe como PASS. Se preservan etiquetas fuera de las familias tipo/prioridad/estado y se rechazan clasificaciones gobernadas contradictorias antes de mutar. Las alertas históricas sin etiquetas se reparan idempotentemente en su próxima observación; no hay backfill manual ni inferencia de HEALTH.

El cuerpo conserva estado, razón, freshness, referencias opacas y un origen validado `https://sonarcloud.io/project/overview?id=<sonar_key>`.

Quality Gate incluye condiciones fallidas; CE task conserva `error_message` saneado; deuda histórica pagina issues y hotspots con límites seguros.

La política productiva #516 declara `organization_line_usage=not_applicable` para los seis proyectos públicos. También declara `coverage=not_applicable` para BRVTAL, Condor, FactoryRunner y GrindFlow por usar Automatic Analysis. ControlBot y Factory usan CI: cobertura ausente sigue siendo un FAIL real y sus Issues no se cierran como N/A. Cambiar método o visibilidad exige actualizar el contrato; el desvío observado frente a la política continúa siendo FAIL.

## Límites

Sonar Watch no corrige findings, no modifica configuración Sonar, no relaja gates ni cambia planes. Si falta configuración, el contrato es ambiguo, una respuesta no respeta su shape o la proyección difiere de la evidencia normalizada, falla cerrado.
