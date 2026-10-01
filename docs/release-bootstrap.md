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

`/decidir A` solo materializa la elección; no publica por sí mismo. Seguridad escribe un único journal `factory-human-decision` v2 ligado al fingerprint del gate normalizado y cierra el Issue mediante `github-actions[bot]`. El preflight de release recalcula ese fingerprint, exige que el contexto del gate contenga un único `main@<SHA>` igual a `expected_sha`, conserva `safe_default=B` y comprueba que la opción A sea inequívocamente de publicación.

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
5. Solo si A quedó materializada con journal v2 válido y gate cerrado, el dueño mueve manualmente el tag mayor `v1` al SHA exacto aprobado. El workflow nunca crea ni mueve `v1`.
6. Ejecutar **Release Factory v1.x** (`.github/workflows/release-bootstrap.yml`) desde `main` con `expected_sha=<SHA aprobado>` y `gate_issue=<Issue de puerta>`.
7. El preflight ejecuta CI reusable sobre `template/`, verifica #1–#14/#54/#83, SHA/HEAD/`v1`, puerta/aprobación y el ruleset actual.
8. El ruleset debe estar activo, incluir `refs/tags/v1` y proteger `creation`, `update` y `deletion`. La comprobación runtime es **solo estructural**; #83 conserva la evidencia administrativa de bypass.
9. Solo si todo coincide, `release.yml@v1` crea/verifica el tag anotado semántico y la GitHub Release.
10. Después se ejecuta un self-test consumidor mediante `ci.yml@v1` sobre `template/`.

Cambiar `main`, mover `v1` a otro SHA, usar una puerta de otra categoría o reutilizar una aprobación para un SHA distinto hace fallar cerrado el preflight.

## Estado actual

- `v1.0.0`: publicado y validado.
- `v1`: canal mayor protegido.
- Los cambios posteriores solo llegan a consumidores de `@v1` después de una puerta `factory-release` y una publicación protegida.
