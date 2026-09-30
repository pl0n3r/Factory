# Sonar Watch v1

Factory ejecuta una vigilancia Sonar centralizada para Condor, GrindFlow, BRVTAL, Factory, FactoryRunner y ControlBot. El watcher **lee** Sonar, normaliza la evidencia mediante `quality.sonar` (#490), la proyecta por Quality Health (#491) y mantiene Issues `[AUTO]` en el repositorio Factory.

## Contrato operativo

El workflow `.github/workflows/sonar-watch.yml` admite `schedule` y `workflow_dispatch`. Su token GitHub solo necesita `contents: read` e `issues: write`; no dispone de permisos de código, Actions, deployments ni administración. Sonar se consume exclusivamente mediante GET. Security Hotspots se leen desde su endpoint dedicado; no se infieren desde `/api/issues/search`.

La configuración runtime vive en `SONAR_WATCH_CONFIG_JSON` y debe cubrir exactamente estos seis identificadores: `brvtal`, `condor`, `controlbot`, `factory`, `factoryrunner`, `grindflow`. Cada entrada declara su `sonar_key`, `github_repo` y Quality Contract completo, incluidos los thresholds Sonar. El secreto `SONAR_TOKEN` es solo de lectura.

## Idempotencia

Cada señal usa un marker estable:

`project + signal -> fingerprint`

Por eso existe como máximo un Issue administrado por cada proyecto y señal. Mientras el estado siga en `FAIL`, `UNKNOWN` o `STALE`, el mismo Issue se actualiza/reabre. Un `PASS` solo cierra el Issue de esa misma señal cuando su freshness es `CURRENT`.

La concurrencia del workflow está serializada y el sincronizador falla cerrado si detecta más de un Issue con el mismo marker. La búsqueda de Issues pagina hasta encontrar una página terminal y falla cerrado si excede el límite seguro; no trunca silenciosamente repositorios grandes. Los reintentos no crean un segundo Issue.

## Evidencia y remediación

El cuerpo del Issue conserva estado, razón, freshness, referencias opacas y origen. Además:

- Quality Gate incluye la condición fallida con actual/threshold;
- CE task incluye `error_message` ya saneado por el normalizador, incluido un line-limit;
- deuda histórica pagina `/api/issues/search` y `/api/hotspots/search?status=TO_REVIEW` hasta `paging.total` (máximo 10.000 por fuente), y agrupa bugs, vulnerabilidades y hotspots por `type/severity`, antigüedad y umbrales excedidos;
- las clases correctivas provienen de la proyección Quality Health existente; el watcher no amplía WorkItem ni Dispatcher.

No se guardan URLs Sonar, credenciales, tokens ni payloads raw en los Issues. Las escrituras GitHub envían JSON explícito con `Content-Type: application/json`.

`organization_line_usage` queda deliberadamente `UNKNOWN` en este watcher porque las lecturas Sonar usadas en v1 no aportan una fuente canónica de uso/límite de organización. El estado UNKNOWN es fail-closed: no se presenta como cobertura observada ni como PASS.

## Límites

Sonar Watch no arregla findings, no modifica configuración Sonar, no relaja gates ni coverage y no toca AutoFactory. Si falta configuración, un payload es ambiguo o la proyección no coincide con la evidencia normalizada, falla cerrado.
