# Bootstrap seguro del primer v1

Factory publica el kit reusable mediante tags mayores (`v1`) y releases semánticos (`v1.0.0`). El primer release tiene una condición especial: antes de que exista `v1`, el workflow reusable no puede depender de ese tag para cargar sus propias composite actions.

## Regla de bootstrap

El reusable `.github/workflows/release.yml` mantiene `kit_ref: v1` como valor por defecto para repos consumidores. Para la **primera publicación solamente**, el caller autorizado debe pasar en `kit_ref` una referencia inmutable del propio Factory candidato (idealmente el SHA exacto de `main` que se pretende publicar).

Nunca se usa una rama flotante como `main` para ese bootstrap. El objetivo es que la acción `actions/read-version` provenga exactamente del mismo candidato que se está validando.

## Puertas obligatorias antes de publicar

La preparación técnica de este documento **no autoriza** crear tags ni releases.

Antes de crear `v1.0.0` y el tag mayor `v1` deben cumplirse simultáneamente:

1. Issues **#1–#14 cerrados**, incluido el épico #13.
2. Template validado por el CI reusable del candidato.
3. Puerta humana explícita de categoría **`release-1.0.0`** resuelta por el dueño.
4. HEAD exacto de `main` revalidado sin cambios posteriores.
5. Ningún secreto, PII ni dato real de clientes incorporado a la evidencia del release.

Si cualquiera falta, el default seguro es **no publicar**.

## Orden de la primera publicación

1. Revalidar los gates anteriores.
2. Fijar el SHA exacto candidato.
3. Ejecutar el caller de release desde un evento confiable de `push` en la rama principal, pasando ese SHA como `kit_ref`.
4. Crear/verificar el tag anotado `v1.0.0` y su GitHub Release mediante el reusable.
5. Crear o mover `v1` al mismo commit **solo después** de que `v1.0.0` exista y haya sido verificado.
6. Ejecutar un self-test consumidor usando `@v1` antes de iniciar TANDA 2.

El merge de la corrección de bootstrap no crea ningún tag automáticamente porque Factory no añade aquí un caller de publicación.
