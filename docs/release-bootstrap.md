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
2. Revalidar `main` y confirmar la versión semántica candidata.
3. El OWNER ejecuta manualmente **Factory Release Window** sobre `main`. El workflow revalida exact-main y compatibilidad de consumidores antes de crear una única puerta `factory-release` para el HEAD vigente; el default seguro es **no publicar**.
4. El OWNER responde explícitamente `/decidir A` para publicar o `/decidir B` para no publicar. Texto libre o `sigue` no cuentan como decisión.
5. Con A materializada y la puerta cerrada, ejecutar una **primera pasada** de **Release Factory v1.x** (`.github/workflows/release-bootstrap.yml`) desde `main` con `expected_sha=latest` (recomendado para la aprobación por versión) o con un SHA explícito para compatibilidad histórica, y `gate_issue=<Issue de puerta>`, mientras `v1` permanece en el último SHA estable.
6. El preflight resuelve y registra el SHA candidato, ejecuta CI reusable sobre `template/`, verifica #1–#14/#54/#83, versión, evidencia exact-main, deriva de maquinaria de release, puerta/aprobación, ruleset y compatibilidad de consumidores. En mantenimiento, el SHA estable previo de `v1` es válido durante esta fase y no expone el candidato.
7. Solo si esos gates pasan, `release.yml@v1` —el trust root ya publicado— crea o verifica de forma idempotente el **release semántico** (tag anotado + GitHub Release) para el SHA candidato. El workflow nunca crea ni mueve `v1`.
8. El job read-only `channel-ready` relee `refs/tags/v1`. Si el canal aún apunta al SHA estable anterior, falla cerrado y la validación final del canal no se ejecuta.
9. Después de la publicación semántica, el dueño mueve manualmente el tag mayor `v1` al SHA exacto aprobado. Esta sigue siendo una acción administrativa/humana.
10. El dueño reejecuta de forma **idempotente** el mismo bootstrap con el mismo `expected_sha` y la misma puerta. La release semántica ya existente se verifica, `channel-ready` confirma que `v1` coincide y entonces `ci.yml@v1` ejecuta el self-test sobre `template/`.
11. La publicación se considera completa únicamente cuando ese self-test del canal publicado termina correctamente.

El ruleset debe estar activo, incluir `refs/tags/v1` y proteger `creation`, `update` y `deletion`. La comprobación runtime es **solo estructural**; #83 conserva la evidencia administrativa de bypass.

Cambiar `main`, mover `v1` a un SHA distinto del aprobado, usar una puerta de otra categoría o reutilizar una aprobación para un SHA distinto hace fallar cerrado. Que `v1` permanezca en el SHA estable anterior durante la primera pasada de mantenimiento es el estado esperado hasta `channel-ready`; nunca equivale a publicar el candidato.
## Aprobación por versión y resolución `latest`

Para mantenimiento de la major `v1`, una decisión A puede autorizar una **versión
semántica** en lugar de quedar consumida por el SHA exacto que tenía `main` cuando
se abrió la puerta. La opción A de la puerta debe identificar la versión de forma
inequívoca, por ejemplo `Publicar Factory 1.0.23`. El contexto conserva un único
`main@<SHA>` como **baseline de deriva**; no es una autorización para saltar
validaciones.

El bootstrap acepta dos formas de `expected_sha`:

- un SHA de 40 hex: conserva el contrato histórico exact-SHA;
- `latest`: resuelve una sola vez el HEAD de la rama por defecto al iniciar el
  preflight y registra ese SHA como `approved_sha`.

`latest` falla cerrado salvo que se cumpla todo lo siguiente:

1. `github.sha`, el HEAD de la rama por defecto y el SHA resuelto sean idénticos;
   si `main` se mueve durante el bootstrap, hay que reejecutar;
2. `config/version.json` contenga exactamente la versión autorizada por la puerta;
3. existan ejecuciones `success` sobre ese SHA exacto de **CI factory**,
   **Sonar CI-based**, **Evidencia CodeQL** y **Unattended Watchdog**;
4. el job **Compatibilidad de consumidores** y el CI reusable del candidato
   terminen correctamente dentro del propio bootstrap;
5. al comparar el SHA baseline de la puerta con el HEAD resuelto no haya cambios
   en la maquinaria de release.

Se considera maquinaria de release, como mínimo, cualquier workflow cuyo nombre de
archivo contenga `release`, `scripts/release_bootstrap.py`,
`scripts/reusable_release_preflight.py`, el contrato de permission envelopes,
el validador del ruleset y el workflow de release del template. Si cualquiera de
esas rutas cambió desde la puerta, se exige **una puerta nueva**. Cambios ordinarios
de producto/documentación que hayan pasado los gates exact-main no invalidan por sí
solos la aprobación de la versión.

Las puertas creadas por automatización después de una solicitud explícita del OWNER
siguen necesitando provenance canónico hasta una puerta histórica creada por el
OWNER. La solicitud manual no convierte la decisión A de una versión en autorización
para otra versión o para maquinaria de release modificada. `safe_default=B` y el
journal `factory-human-decision` continúan siendo obligatorios.

Nada de lo anterior mueve `v1` automáticamente. El orden seguro permanece:
bootstrap → release semántico → movimiento administrativo de `v1` por el dueño →
re-bootstrap idempotente.

## Ventana de release y freeze exact-SHA

Para evitar que una aprobación válida caduque porque `main` sigue moviéndose, Factory usa una ventana de release con TTL (60 minutos por defecto) gobernada por `scripts/release_window.py` y `.github/workflows/release-window.yml`.

Orden canónico:

`candidato exact-SHA → freeze → puerta factory-release → decisión OWNER → bootstrap → mover v1 → re-bootstrap → marker factory-release-executed → unfreeze`.

Mientras exista una puerta vigente o una decisión A exact-SHA todavía no ejecutada, los PR normales quedan congelados. El único bypass permitido es un repair crítico con Issue de prioridad crítica y el marker explícito:

    <!-- factory-release-freeze-exception {"version":1,"reason":"critical-repair","issue":<N>} -->

La excepción habilita exclusivamente el repair indicado; no publica una release, no crea una decisión humana y no transporta autoridad entre SHAs.

Si el TTL vence, **solo termina el freeze de merges**; la **hora de expiración** sigue formando parte del diagnóstico cuando un preflight detecta una ventana vencida. Una decisión A v2 válida no caduca por reloj cuando `main` sigue exactamente en el SHA aprobado y la maquinaria de release no derivó; el bootstrap puede reutilizar esa autorización porque el journal continúa ligado al fingerprint del gate y al mismo SHA. Si `main` cambió, la autorización exact-SHA no se transporta y **no se abre ni rearma ninguna puerta automáticamente**. El OWNER debe ejecutar de nuevo `Factory Release Window`; la nueva solicitud se liga al HEAD vigente, revalida exact-main + compatibilidad, retira silenciosamente las puertas stale de la misma versión y vuelve a exigir `/decidir A` o `/decidir B`.

### Confianza de puertas creadas tras solicitud OWNER

Una puerta creada por `github-actions[bot]` **no se vuelve confiable por el nombre del actor**. El bootstrap solo admite esa excepción estrecha cuando la evidencia read-only demuestra simultáneamente que:

- el gate actual contiene exactamente un `factory-release-rearm` y un `factory-release-window` válidos, ambos ligados al mismo `expected_sha`;
- el Issue fue creado dentro de esa ventana; después del vencimiento, el bootstrap solo conserva la autoridad si existe una decisión A v2 válida y el SHA/maquinaria siguen compatibles;
- la cadena `source_issue` es acíclica, tiene como máximo ocho saltos y cada salto intermedio creado por el bot conserva markers canónicos coherentes con el SHA de su propia puerta;
- la cadena termina en una puerta `factory-release` creada por el OWNER del repositorio con `author_association=OWNER`.

El workflow obtiene esa cadena únicamente mediante `issues: read` dentro del mismo repositorio y la entrega al parser puro; no amplía permisos ni confía en datos derivados del título. Marker ausente/duplicado/malformado, SHA incompatible, creación fuera de ventana, deriva de maquinaria, ciclo, profundidad excesiva o una cadena que no termina en el OWNER fallan cerrado. Esto conserva la cadena de provenance sin convertir a `github-actions[bot]` en una identidad globalmente confiable.

Una release solo se considera ejecutada cuando el workflow `Release Factory v1.x` termina con éxito y la puerta exact-SHA recibe un marker `factory-release-executed` coincidente. Hasta entonces el resumen diario/nocturno debe mantener visible “release aprobada sin ejecutar”.

## Rollback tras startup_failure

Si una publicación de `Factory@v1` provoca `startup_failure` en consumidores, aplica el runbook fail-closed [`docs/reusable-release-rollback.md`](reusable-release-rollback.md). Detectar o recomendar rollback no autoriza a mover `v1`; la acción sigue siendo humana/administrativa y exige evidencia nueva de recuperación en un consumidor real.

## Estado actual

- `v1.0.0`: publicado y validado.
- `v1`: canal mayor protegido.
- Los cambios posteriores solo llegan a consumidores de `@v1` después de una puerta `factory-release` y una publicación protegida.

## Puertas bajo demanda

Desde #1016, un `push` a `main` **nunca** abre ni rearma una puerta. Sin petición del OWNER no hay una nueva `decisión: dueño` ni un nuevo freeze de release.

Procedimiento corto:

1. **Pídele a Factory que publique**: el OWNER ejecuta manualmente `Factory Release Window` sobre `main` (`workflow_dispatch`) (versión vacía = `config/version.json`).
2. Factory exige sobre el HEAD vigente **CI factory, Sonar CI-based, Evidencia CodeQL, Unattended Watchdog** y la **Compatibilidad de consumidores**; si falta evidencia, falla cerrado y no crea puerta.
3. **Decide A** o B con `/decidir A` o `/decidir B`. `sigue` y texto libre no autorizan publicar.
4. Con A materializada, **lanza el workflow** `Release Factory v1.x`.
5. Tras crear/verificar el release semántico, el dueño **mueve `v1`** al SHA exacto aprobado y reejecuta el bootstrap idempotente.

Una solicitud nueva cierra silenciosamente las puertas stale de la misma versión y retira su etiqueta `decisión: dueño`; nunca hereda una A anterior.
