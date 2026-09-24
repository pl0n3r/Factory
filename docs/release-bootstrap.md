# Release protegido de Factory v1.x

Factory distribuye el kit mediante el canal mayor `v1` y releases semánticos (`v1.0.0`, `v1.0.1`, …). Los workflows con capacidad de escritura ejecutan únicamente el kit ya publicado y no aceptan una referencia dinámica del candidato.

## Frontera de seguridad

`.github/workflows/release.yml` hace checkout fijo de `pl0n3r/factory@v1`. No existe un `inputs.kit_ref` para release; un caller con escritura no puede seleccionar una rama o commit alternativo del kit.

## Ciclo de vida de puertas humanas

- `release-1.0.0`: únicamente para el primer release, cuando `v1.0.0` todavía no existe.
- `factory-release`: obligatoria para cualquier mantenimiento posterior de la major `v1`, cuando `v1.0.0` ya existe.

El preflight detecta la existencia real de `v1.0.0` y falla cerrado si se usa la categoría equivocada.

En ambos casos, el Issue debe estar cerrado por el dueño y un comentario suyo debe contener exactamente:

    <!-- factory-release-approval {"sha":"<SHA exacto aprobado>"} -->

El marker autoriza únicamente ese SHA.

## Primer release v1.0.0

El primer release ya se publicó mediante el bootstrap protegido. Se conserva compatibilidad con la puerta `release-1.0.0` para que la historia y las regresiones del bootstrap inicial sigan verificables.

Antes del primer release se exigieron #1–#14, #54 y #83 cerrados, CI del template, ruleset activo del canal mayor, SHA exacto de `main` y aprobación humana explícita.

## Mantenimiento v1.x

Para publicar un patch/minor posterior dentro de la major `v1`:

1. Integrar el cambio en `main` con la versión semántica nueva en `config/version.json`.
2. Revalidar CI de `main` y fijar el SHA exacto candidato.
3. Crear una puerta humana `factory-release` para ese SHA. El default seguro es **no publicar**.
4. Tras la aprobación explícita, el dueño mueve manualmente el tag mayor `v1` al SHA aprobado. El workflow nunca crea ni mueve `v1`.
5. Ejecutar **Release Factory v1.x** (`.github/workflows/release-bootstrap.yml`) desde `main` con `expected_sha=<SHA aprobado>` y `gate_issue=<Issue de puerta>`.
6. El preflight ejecuta CI reusable sobre `template/`, verifica #1–#14/#54/#83, SHA/HEAD/`v1`, puerta/aprobación y el ruleset actual.
7. El ruleset debe estar activo, incluir `refs/tags/v1` y proteger `creation`, `update` y `deletion`; #83 conserva la evidencia administrativa de bypass.
8. Solo si todo coincide, `release.yml@v1` crea/verifica el tag anotado semántico y la GitHub Release.
9. Después se ejecuta un self-test consumidor mediante `ci.yml@v1` sobre `template/`.

Cambiar `main`, mover `v1` a otro SHA, usar una puerta de otra categoría o reutilizar una aprobación para un SHA distinto hace fallar cerrado el preflight.

## Estado actual

- `v1.0.0`: publicado y validado.
- `v1`: canal mayor protegido.
- Los cambios posteriores solo llegan a consumidores de `@v1` después de una puerta `factory-release` y una publicación protegida.
