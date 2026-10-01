# Sonar Watch v1

Factory ejecuta vigilancia Sonar centralizada para Condor, GrindFlow, BRVTAL, Factory, FactoryRunner y ControlBot. El watcher **solo lee** Sonar, normaliza la evidencia mediante `quality.sonar`, la proyecta por Quality Health y mantiene Issues `[AUTO] Sonar` en Factory.

## Runtime versionado

La fuente canónica es `quality/sonar-watch-config.json`. El workflow no depende de `SONAR_WATCH_CONFIG_JSON`.

La política productiva vigente proviene de la **Opción C aprobada en #516**:

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

## Workflow

`.github/workflows/sonar-watch.yml` conserva `schedule` y `workflow_dispatch`. Ambos ejecutan el mismo entrypoint:

`python3 scripts/sonar-watch.py`

Permisos GitHub: `contents: read` y `issues: write` únicamente en el job que sincroniza Issues. No se concede escritura de código, Actions, deployments ni administración.

## Idempotencia y evidencia

Cada señal usa un marker estable `project + signal -> fingerprint`. Existe como máximo un Issue administrado por proyecto/señal. `FAIL`, `UNKNOWN` o `STALE` actualizan/reabren el mismo Issue; un `PASS` solo lo cierra con freshness `CURRENT`.

El cuerpo conserva estado, razón, freshness, referencias opacas y un origen validado `https://sonarcloud.io/project/overview?id=<sonar_key>`.

Quality Gate incluye condiciones fallidas; CE task conserva `error_message` saneado; deuda histórica pagina issues y hotspots con límites seguros.

`organization_line_usage` permanece `UNKNOWN` mientras no exista una lectura Sonar canónica para uso/límite organizacional. UNKNOWN es fail-closed y nunca se presenta como PASS.

## Límites

Sonar Watch no corrige findings, no modifica configuración Sonar, no relaja gates ni cambia planes. Si falta configuración, el contrato es ambiguo, una respuesta no respeta su shape o la proyección difiere de la evidencia normalizada, falla cerrado.
