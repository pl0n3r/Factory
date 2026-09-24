# Preview y staging previo a producción

Factory prueba el camino de despliegue **antes del merge** sin entregar credenciales live a código de PR.

## Principio: mismo pipeline, distinto target

El preview ejecuta `scripts/deploy_kit.py::run_pipeline` y los mismos adapters:

- `ops/factory/build`
- `ops/factory/backup`
- `ops/factory/migrate`
- `ops/factory/deploy`
- `ops/factory/rollback`

No existe un segundo algoritmo de deploy. La diferencia es el contexto: durante preview Factory crea un directorio temporal y expone únicamente las variables `FACTORY_PREVIEW=1`, `FACTORY_SYNTHETIC_DATA=1`, `FACTORY_PREVIEW_ROOT`, `FACTORY_EXPECTED_VERSION`, `FACTORY_EXPECTED_SHA` y `FACTORY_REQUIRE_SCHEMA`.

Los adapters del proyecto deben ramificar explícitamente por `FACTORY_PREVIEW=1` y operar solo dentro de `FACTORY_PREVIEW_ROOT`. **Nunca deben tocar recursos live en preview.**

## Credenciales y aislamiento

El reusable `.github/workflows/preview.yml` tiene `contents: read` y no declara secretos. `preview_kit.py` rechaza `DEPLOY_TOKEN`, `DATABASE_URL`, `DEPLOY_SSH_KEY`, `GH_TOKEN` y `GITHUB_TOKEN` si aparecen en su proceso; además reconstruye un entorno acotado antes de ejecutar adapters candidatos.

Esto no pretende ser una sandbox de kernel. La garantía operativa es que el código de PR no recibe las credenciales que permitirían acceder a producción.

## Verificación posterior

Después del deploy común se ejecutan tres adapters fijos:

1. `ops/factory/preview-health`: confirma versión, SHA y schema cuando aplica.
2. `ops/factory/preview-smoke`: valida las superficies críticas del artifact preview.
3. `ops/factory/preview-e2e`: ejecuta el recorrido sintético mínimo.

Un fallo de health ocurre dentro de `run_pipeline`, por lo que conserva su rollback común. Un fallo posterior de smoke/E2E deja el job rojo y el directorio efímero se destruye al salir.

## Integración en CI

El template llama `ci.yml@v1` y `preview.yml@v1` como jobs hermanos. Un gate final `Validar` depende de ambos; en `push` el preview queda skipped, mientras que en `pull_request` debe terminar success.

El deploy real sigue en `deploy.yml`, limitado a contexto confiable de rama principal. #11 no reduce esas guardas.

## Template

Los adapters incluidos en `template/ops/factory/` son un ejemplo ejecutable para el proyecto PHP mínimo. Todos fallan si `FACTORY_PREVIEW != 1`; antes de habilitar producción, cada proyecto reemplaza o amplía la rama no-preview con su deploy real manteniendo la rama preview sintética.
