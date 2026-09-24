# Bootstrap seguro del primer v1

Factory distribuye el kit mediante el canal mayor `v1` y releases semánticos como `v1.0.0`. Los workflows con capacidad de escritura ejecutan únicamente el kit ya publicado; no aceptan una referencia dinámica del candidato.

## Frontera de seguridad

`.github/workflows/release.yml` hace checkout fijo de:

```yaml
repository: pl0n3r/factory
ref: v1
```

No existe un `inputs.kit_ref` para release. Esta restricción evita que un caller con permisos de escritura seleccione una rama o commit alternativo del kit.

## Puertas obligatorias antes del primer tag

La preparación técnica de este documento **no autoriza** crear tags ni releases.

Antes de crear por primera vez `v1` y `v1.0.0` deben cumplirse simultáneamente:

1. Issues **#1–#14 cerrados**, incluido el épico #13.
2. Template validado por el CI reusable del candidato.
3. Puerta humana explícita de categoría **`release-1.0.0`** resuelta por el dueño.
4. HEAD exacto de `main` revalidado sin cambios posteriores.
5. Ningún secreto, PII ni dato real de clientes incorporado a la evidencia del release.

Si cualquiera falta, el default seguro es **no publicar**.

## Bootstrap inicial

La primera publicación requiere una acción humana explícita porque todavía no existe el canal publicado que consume el propio workflow:

1. Revalidar todos los gates anteriores.
2. Fijar el **SHA exacto aprobado** de Factory.
3. Crear manualmente el tag mayor **`v1`** apuntando a ese SHA exacto. No usar una rama flotante.
4. Verificar que `v1` resuelve exactamente al SHA aprobado.
5. Ejecutar el caller normal de release desde un `push` confiable de la rama principal. El reusable ya puede cargar `actions/read-version` desde `v1` y crear/verificar el tag anotado `v1.0.0` y su GitHub Release.
6. Verificar que `v1.0.0` apunta al mismo commit.
7. Ejecutar un self-test consumidor usando `@v1` antes de iniciar TANDA 2.

Para releases posteriores dentro de la misma major, `v1` se actualiza únicamente mediante el proceso humano/autorizado definido para el canal mayor, nunca por inferencia de un agente.

El merge de esta preparación no crea ningún tag automáticamente porque Factory no añade aquí un caller de publicación.
