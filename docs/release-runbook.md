# Runbook protegido: publicar Factory v1.x

Este procedimiento documenta el estado comprobable de [release-window.yml](../.github/workflows/release-window.yml), [release-bootstrap.yml](../.github/workflows/release-bootstrap.yml), [release.yml](../.github/workflows/release.yml), [release-bootstrap.md](release-bootstrap.md) y [PLAN-AGENTES.md](../PLAN-AGENTES.md).

**Autoridad:** abrir la ventana, responder la puerta y mover el tag mayor protegido `v1` corresponde al OWNER y al operador administrativo autorizado, no a los agentes. El kill switch Factory #767 y las condiciones de protección no se sustituyen por este documento. Esta guía no ejecuta una publicación.

## 1. Preparar candidato versionado y jurídico

Bajo una reserva V3 auténtica de los paths, preparar una nueva versión semántica `X.Y.Z` en `config/version.json`, añadir la prueba `tests/test_release_candidate_<X_Y_Z>.py` y regenerar `revision-juridica/00-LEEME.md` **y** `revision-juridica/paquete-completo.md`. Si la generación modifica otras copias, incluirlas también en los claims legítimos, nunca ampliarlos silenciosamente. Para revisar el candidato, sin publicar:

~~~bash
python3 -m json.tool config/version.json
python3 scripts/generar_revision_juridica.py
python3 scripts/generar_revision_juridica.py --check
python3 -m unittest discover -s tests -p 'test_release_candidate_*.py'
~~~

Verificar la prueba concreta del nuevo número y todas las fuentes; no tomar un test viejo como aceptación del release nuevo. Fusionar el PR del candidato solo tras `Validar` y seguridad exact-HEAD sobre el SHA definitivo. No crear otro tag con una versión ya publicada.

## 2. Abrir Factory Release Window

En Actions, ejecutar manualmente [Factory Release Window](https://github.com/pl0n3r/Factory/actions/workflows/release-window.yml) sobre `main`, con `version=X.Y.Z` (o dejar vacío para leer la versión de la configuración).

Comando equivalente, **solo OWNER**:

~~~bash
VERSION=X.Y.Z
gh workflow run release-window.yml --repo pl0n3r/Factory --ref main -f version="$VERSION"
~~~

El workflow real está en `.github/workflows/release-window.yml` (no en `factory-release-window.yml`). Revalida para el HEAD exacto: **CI factory** `factory-ci.yml`, **Sonar CI-based** `sonar.yml`, **Evidencia CodeQL** `codeql-evidence.yml`, watchdog de reusables `reusable-release-watchdog.yml` y **Compatibilidad de consumidores**. Ausencia o carrera de resultados termina con `revalidation_required`: completar los gates terminales `success` sobre el mismo SHA y volver a solicitar la ventana, no inventar aprobación.

La puerta `factory-release` caduca y su ventana puede congelar `main`: el check `Ventana de release Factory` puede bloquear PRs hasta que la puerta se decida o expire. No eludir ni desmontar protección; relanzar los checks del PR cuando el freeze esté resuelto.

## 3. Decisión del dueño

En el Issue de la puerta generado por el workflow, responder como OWNER:

~~~text
/decidir A
~~~

La alternativa segura es `/decidir B`, que no publica. Un mensaje libre o `sigue` nunca constituye decisión. Comprobar el journal `factory-human-decision` del bot, la opción A, el SHA y la versión autorizados, la identidad de puerta y su cierre antes del bootstrap. El número de Issue se obtiene del enlace real de la puerta, no se inventa.

Si `main` se movió desde que se abrió la ventana, especialmente por cambios a la maquinaria de release, hay deriva y la puerta debe revalidarse o reabrirse. No transportar la A de una versión/SHA a otro. El árbol de rearmado de puertas tiene límite **64**, y las cadenas cíclicas fallan cerrado.

## 4. Primera ejecución de Release Factory v1.x

Después de una decisión A válida, el OWNER lanza [Release Factory v1.x](https://github.com/pl0n3r/Factory/actions/workflows/release-bootstrap.yml) en `main`:

~~~bash
GATE_ISSUE=<numero_real_de_la_puerta>
gh workflow run release-bootstrap.yml --repo pl0n3r/Factory --ref main \
  -f expected_sha=latest -f gate_issue="$GATE_ISSUE"
~~~

`expected_sha=latest` resuelve el HEAD real en el preflight y comprueba la versión, la puerta, los checks exactos de CI/Sonar/CodeQL/watchdog y la compatibilidad. El workflow actual también admite `expected_sha=<SHA_de_40_hex>`, siempre que concuerde con `main`, `github.sha` y la aprobación. El mensaje `require_exact_main_success: command not found` fue un fallo **histórico** de bootstrap corregido en [#1436](https://github.com/pl0n3r/Factory/issues/1436): nunca afirmarlo como limitación permanente; contrastar ejecución y fuente actuales.

La primera pasada crea o comprueba la GitHub Release semántica y el tag anotado `vX.Y.Z` a través de `release.yml@v1`. El bootstrap **no mueve `v1`**. Mientras el canal `refs/tags/v1` siga en el commit estable anterior, el check `channel-ready` falla cerrado o bloquea el self-test. Eso no equivale a publicar el nuevo kit completamente.

Si el tag `vX.Y.Z` `ya apunta a otro commit`, no forzar, reutilizar ni reescribir un tag semántico: preparar versión nueva y puerta nueva. La aprobación anterior no autoriza un commit diferente.

## 5. Actualizar v1 administrativamente y repetir el bootstrap

Solo el OWNER autorizado puede mover el tag mayor protegido `v1` al SHA exacto aprobado, conforme al ruleset y los permisos vigentes. Para comprobar los objetos antes de la operación:

~~~bash
gh api repos/pl0n3r/Factory/commits/main --jq .sha
gh api repos/pl0n3r/Factory/git/ref/tags/v1 --jq .object.sha
~~~

La actualización de `v1` es un paso administrativo fuera de este PR. No usar `force`, no alterar el ruleset ni intentar bypass. Si GitHub niega el permiso, detenerse: el éxito de la GitHub Release semántica no concede autoridad sobre el tag protegido.

Con `v1` ya apuntando al SHA autorizado, el OWNER relanza el **mismo bootstrap** de forma idempotente:

~~~bash
gh workflow run release-bootstrap.yml --repo pl0n3r/Factory --ref main \
  -f expected_sha=latest -f gate_issue="$GATE_ISSUE"
~~~

La validación terminal exige `channel-ready` y self-test `Validar` del `@v1` publicado sobre el SHA exacto, además de controles de compatibilidad. La presencia de un tag no sustituye el run terminal. Revisar logs de [Actions](https://github.com/pl0n3r/Factory/actions/workflows/release-bootstrap.yml) y [GitHub Releases](https://github.com/pl0n3r/Factory/releases).

## Trampas conocidas y solución comprobable

| Síntoma | Diagnóstico | Acción segura |
| --- | --- | --- |
| `revalidation_required` | CI factory, Sonar CI-based, Evidencia CodeQL, watchdog o compatibilidad no terminales | Revalidar SHA y repetir la solicitud del OWNER cuando haya `success` |
| `Ventana de release Factory` bloquea PRs | Freeze activo de la ventana | Esperar cierre/expiración; revalidar el PR y sus checks |
| `main` cambió desde la puerta | Deriva o modificación de maquinaria de release | Nueva puerta exacta, no heredar autorización |
| `ya apunta a otro commit` | Tag semántico preexistente para otro SHA | Incrementar versión y comenzar con candidato y puerta nuevos |
| `require_exact_main_success: command not found` | Error histórico corregido en #1436 | Releer workflow actual; no prescribir workaround inseguro |
| `channel-ready` rojo | `v1` todavía en SHA previo | Movimiento humano bajo ruleset, después segundo bootstrap |
| Cadena de rearmado supera **64** o forma ciclo | Procedencia incompleta | Fail-closed; crear nueva puerta válida del OWNER |
| Respuestas 403/429 o GitHub API rate-limit | Permiso o cuota insuficiente | Reintentar solo cuando haya reset real; no hacer polling ni omitir gates |

La release [v1.0.39](https://github.com/pl0n3r/Factory/releases/tag/v1.0.39) figura publicada en la evidencia de esta redacción. Para cualquier acción futura, verificar versión actual en `config/version.json` y Releases, nunca reutilizar la decisión A previa.

## Fuentes de verdad

- [Workflow de ventana](../.github/workflows/release-window.yml) y [evaluador](../scripts/release_window.py).
- [Bootstrap](../.github/workflows/release-bootstrap.yml), [reusable release](../.github/workflows/release.yml) y [guía de release](release-bootstrap.md).
- [CI factory](../.github/workflows/factory-ci.yml), [Sonar](../.github/workflows/sonar.yml) y [CodeQL](../.github/workflows/codeql-evidence.yml).
- [Puertas humanas](puertas-humanas.md), [reglas de agentes](../PLAN-AGENTES.md) y [reparación #1436](https://github.com/pl0n3r/Factory/issues/1436).
