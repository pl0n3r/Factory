# Release protegido de Factory v1.x

Factory distribuye el kit mediante el canal mayor `v1` y releases semánticos (`v1.0.0`, `v1.0.1`, …). Los workflows con capacidad de escritura ejecutan únicamente el kit ya publicado y no aceptan una referencia dinámica del candidato.

## Frontera de seguridad

`.github/workflows/release.yml` hace checkout fijo de `pl0n3r/factory@v1`. No existe un `inputs.kit_ref` para release; un caller con escritura no puede seleccionar una rama o commit alternativo del kit.

## Ciclo de vida de puertas humanas

- `release-1.0.0`: únicamente para el primer release, cuando `v1.0.0` todavía no existe.
- `factory-release`: obligatoria para cualquier mantenimiento posterior de la major `v1`, cuando `v1.0.0` ya existe.

El preflight detecta la existencia real de `v1.0.0` y falla cerrado si se usa la categoría equivocada.

Para puertas nuevas `factory-release`, la vía canónica es responder con un comando exacto del OWNER:

    /decidir A

o:

    /decidir B

`/decidir A` solo materializa la elección; no publica por sí mismo. Seguridad escribe un único journal `factory-human-decision` v2 ligado al fingerprint del gate normalizado y cierra el Issue mediante `github-actions[bot]`. El preflight de release recalcula ese fingerprint, exige que el contexto del gate contenga un único `main@<SHA>` igual a `expected_sha`, conserva `safe_default=B` y exige que el label normalizado de la opción A empiece por `Publicar` como verbo positivo. Labels negados como `No publicar` o frases que solo contienen la palabra `publicar` fallan cerrado.

Las puertas históricas siguen siendo compatibles con el transporte legacy: Issue cerrado por el dueño + comentario OWNER con exactamente:

    <!-- factory-release-approval {"sha":"<SHA exacto aprobado>"} -->

Ese marker autoriza únicamente ese SHA y se mantiene solo para compatibilidad histórica. No debe usarse para puertas nuevas.

## Primer release v1.0.0

El primer release ya se publicó mediante el bootstrap protegido. Se conserva compatibilidad con la puerta `release-1.0.0` para que la historia y las regresiones del bootstrap inicial sigan verificables.

Antes del primer release se exigieron #1–#14, #54 y #83 cerrados, CI del template, ruleset activo del canal mayor, SHA exacto de `main` y aprobación humana explícita.

## Mantenimiento v1.x

Para publicar un patch/minor posterior dentro de la major `v1`:

1. Integrar el cambio en `main` con la versión semántica nueva en `config/version.json`.
2. Revalidar CI de `main` y fijar el SHA exacto candidato.
3. Crear una puerta humana `factory-release` para ese SHA. El default seguro es **no publicar**.
4. El OWNER responde explícitamente `/decidir A` para publicar o `/decidir B` para no publicar. Texto libre o `sigue` no cuentan como decisión.
5. Con A materializada y la puerta cerrada, ejecutar una **primera pasada** de **Release Factory v1.x** (`.github/workflows/release-bootstrap.yml`) desde `main` con `expected_sha=<SHA aprobado>` y `gate_issue=<Issue de puerta>`, mientras `v1` permanece en el último SHA estable.
6. El preflight ejecuta CI reusable sobre `template/`, verifica #1–#14/#54/#83, exactitud `expected_sha == github.sha == HEAD`, puerta/aprobación, ruleset y compatibilidad de consumidores. En mantenimiento, el SHA estable previo de `v1` es válido durante esta fase y no expone el candidato.
7. Solo si esos gates pasan, `release.yml@v1` —el trust root ya publicado— crea o verifica de forma idempotente el **release semántico** (tag anotado + GitHub Release) para el SHA candidato. El workflow nunca crea ni mueve `v1`.
8. El job read-only `channel-ready` relee `refs/tags/v1`. Si el canal aún apunta al SHA estable anterior, falla cerrado y la validación final del canal no se ejecuta.
9. Después de la publicación semántica, el dueño mueve manualmente el tag mayor `v1` al SHA exacto aprobado. Esta sigue siendo una acción administrativa/humana.
10. El dueño reejecuta de forma **idempotente** el mismo bootstrap con el mismo `expected_sha` y la misma puerta. La release semántica ya existente se verifica, `channel-ready` confirma que `v1` coincide y entonces `ci.yml@v1` ejecuta el self-test sobre `template/`.
11. La publicación se considera completa únicamente cuando ese self-test del canal publicado termina correctamente.

El ruleset debe estar activo, incluir `refs/tags/v1` y proteger `creation`, `update` y `deletion`. La comprobación runtime es **solo estructural**; #83 conserva la evidencia administrativa de bypass.

Cambiar `main`, mover `v1` a un SHA distinto del aprobado, usar una puerta de otra categoría o reutilizar una aprobación para un SHA distinto hace fallar cerrado. Que `v1` permanezca en el SHA estable anterior durante la primera pasada de mantenimiento es el estado esperado hasta `channel-ready`; nunca equivale a publicar el candidato.
## Ventana de release y freeze exact-SHA

Para evitar que una aprobación válida caduque porque `main` sigue moviéndose, Factory usa una ventana de release con TTL (60 minutos por defecto) gobernada por `scripts/release_window.py` y `.github/workflows/release-window.yml`.

Orden canónico:

`candidato exact-SHA → freeze → puerta factory-release → decisión OWNER → bootstrap → mover v1 → re-bootstrap → marker factory-release-executed → unfreeze`.

Mientras exista una puerta vigente o una decisión A exact-SHA todavía no ejecutada, los PR normales quedan congelados. El único bypass permitido es un repair crítico con Issue de prioridad crítica y el marker explícito:

    <!-- factory-release-freeze-exception {"version":1,"reason":"critical-repair","issue":<N>} -->

La excepción habilita exclusivamente el repair indicado; no publica una release, no crea una decisión humana y no transporta autoridad entre SHAs.

Si el TTL vence, el freeze deja de bloquear merges, pero la decisión A previa continúa ligada únicamente a su SHA original. Si `main` cambió, `release-window.yml` rearma de forma idempotente una nueva puerta `factory-release` sobre el HEAD vigente con `safe_default=B`; nunca copia el journal A anterior.

Una release solo se considera ejecutada cuando el workflow `Release Factory v1.x` termina con éxito y la puerta exact-SHA recibe un marker `factory-release-executed` coincidente. Hasta entonces el resumen diario/nocturno debe mantener visible “release aprobada sin ejecutar”.

## Rollback tras startup_failure

Si una publicación de `Factory@v1` provoca `startup_failure` en consumidores, aplica el runbook fail-closed [`docs/reusable-release-rollback.md`](reusable-release-rollback.md). Detectar o recomendar rollback no autoriza a mover `v1`; la acción sigue siendo humana/administrativa y exige evidencia nueva de recuperación en un consumidor real.

## Estado actual

- `v1.0.0`: publicado y validado.
- `v1`: canal mayor protegido.
- Los cambios posteriores solo llegan a consumidores de `@v1` después de una puerta `factory-release` y una publicación protegida.
