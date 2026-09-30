# Sonar Watch v1

Factory ejecuta una vigilancia Sonar centralizada para Condor, GrindFlow, BRVTAL, Factory, FactoryRunner y ControlBot. El watcher **lee** Sonar, normaliza la evidencia mediante `quality.sonar`, la proyecta por Quality Health y mantiene Issues `[AUTO]` en el repositorio Factory.

## Runtime versionado

La fuente canónica de runtime es `quality/sonar-watch-config.json`. No existe dependencia funcional de `SONAR_WATCH_CONFIG_JSON`.

La configuración cubre exactamente seis proyectos:

| Proyecto | Sonar key | GitHub | Método observado |
| --- | --- | --- | --- |
| brvtal | `pl0n3r_brvtal` | `pl0n3r/brvtal` | automatic |
| condor | `pl0n3r_Condor` | `pl0n3r/Condor` | automatic |
| controlbot | `pl0n3r_factory-control` | `pl0n3r/ControlBot` | ci |
| factory | `pl0n3r_factory` | `pl0n3r/Factory` | ci |
| factoryrunner | `pl0n3r_FactoryRunner` | `pl0n3r/FactoryRunner` | automatic |
| grindflow | `pl0n3r_GrindFlow` | `pl0n3r/GrindFlow` | automatic |

Los métodos anteriores son estado observado mediante `GET /api/settings/values?keys=sonar.autoscan.enabled`; no se infieren a partir de coverage, scanner paths ni Quality Gate.

El contrato versionado exige visibilidad pública y mantiene thresholds explícitos: análisis máximo 24 h, 80 % de líneas de organización, 0 vulnerabilidades, 10 bugs, 0 hotspots y 30 días de antigüedad máxima. Estos valores son política de observación de este runtime, no configuración remota de Sonar.

## Autenticación y fail-closed

`SONAR_TOKEN` es opcional. El watcher realiza primero un preflight de visibilidad mediante `GET /api/components/show` para los seis proyectos.

- Si todos son públicos, continúa sin token.
- Si cualquiera resulta privado y no existe `SONAR_TOKEN`, aborta antes de cualquier otra lectura Sonar.
- Si existe token, se conserva como credencial de lectura y nunca se usa para mutar Sonar.

El workflow mantiene `contents: read` e `issues: write`; no concede permisos de código, Actions, deployments ni administración.

## Solo lectura de Sonar

El cliente HTTP de Sonar está explícitamente marcado como read-only y rechaza cualquier método distinto de `GET`.

El watcher ya no utiliza `/api/autoscan/activation`. El método de análisis se obtiene exclusivamente de:

`GET /api/settings/values?component=<key>&keys=sonar.autoscan.enabled`

El parser exige exactamente un setting con key `sonar.autoscan.enabled` y valor textual `true` o `false`, que se normaliza respectivamente a `automatic` o `ci`. Ausencia, duplicidad, key inesperada o valor ambiguo provocan fallo cerrado.

## Workflow

`.github/workflows/sonar-watch.yml` conserva `schedule` y `workflow_dispatch`. Ambos ejecutan exactamente `python3 scripts/sonar-watch.py` con la misma configuración versionada.

## Idempotencia

Cada señal usa un marker estable:

`project + signal -> fingerprint`

Por eso existe como máximo un Issue administrado por cada proyecto y señal. Mientras el estado siga en `FAIL`, `UNKNOWN` o `STALE`, el mismo Issue se actualiza/reabre. Un `PASS` solo cierra el Issue de esa misma señal cuando su freshness es `CURRENT`.

## Evidencia y remediación

El cuerpo del Issue conserva estado, razón, freshness, referencias opacas y un enlace de origen canónico `https://sonarcloud.io/project/overview?id=<sonar_key>`. La URL se valida contra ese único host/path y no acepta parámetros adicionales.

Además:

- Quality Gate incluye la condición fallida con actual/threshold.
- CE task incluye `error_message` saneado.
- deuda histórica pagina issues y hotspots hasta el total declarado, con límite seguro.
- las clases correctivas provienen de Quality Health; el watcher no crea un pipeline paralelo.

`organization_line_usage` queda deliberadamente `UNKNOWN` porque las lecturas utilizadas no aportan una fuente canónica de uso/límite de organización.

## Límites

Sonar Watch no arregla findings, no modifica configuración Sonar, no relaja gates ni coverage y no toca AutoFactory. Si falta configuración, un payload es ambiguo o la proyección no coincide con la evidencia normalizada, falla cerrado.
