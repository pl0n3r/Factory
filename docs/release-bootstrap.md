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

1. Issues **#1–#14 cerrados**, incluido el épico #13, y **#54 cerrado**.
2. Template validado por el CI reusable del candidato.
3. Puerta humana explícita de categoría **`release-1.0.0`** resuelta por el dueño.
4. HEAD exacto de `main` revalidado sin cambios posteriores.
5. Ningún secreto, PII ni dato real de clientes incorporado a la evidencia del release.

Si cualquiera falta, el default seguro es **no publicar**.

## Bootstrap inicial

La primera publicación sigue requiriendo una decisión humana explícita, pero el camino técnico ya no se improvisa. El workflow **Bootstrap release Factory v1.0.0** (`.github/workflows/release-bootstrap.yml`) es el único caller manual del primer release.

1. Revalidar todos los gates anteriores y fijar el **SHA exacto aprobado** de Factory.
2. Crear o usar un Issue de puerta humana con categoría `release-1.0.0`. Tras la decisión del dueño, el Issue debe estar cerrado por el dueño y un comentario suyo debe contener:

   ```html
   <!-- factory-release-approval {"sha":"<SHA exacto aprobado>"} -->
   ```

3. Resolver #83 y proteger el canal mayor; después **Crear manualmente el tag mayor** `v1` apuntando al SHA exacto aprobado. El bootstrap no crea ni mueve `v1`.
4. Ejecutar **Bootstrap release Factory v1.0.0** desde `main` con inputs `expected_sha=<SHA>` y `gate_issue=<número>`.
5. El caller ejecuta primero el CI reusable local sobre `template/` con el SHA candidato, luego verifica #1–#14/#54, puerta/aprobación, HEAD de `main`, `v1` y el **ruleset actual**. La revalidación exige un ruleset de tags con `enforcement: active`, inclusión explícita de `refs/tags/v1` y reglas `creation`, `update` y `deletion`.
6. La comprobación runtime del ruleset es **solo estructural** y read-only: **#83 sigue siendo obligatorio** para aportar la evidencia administrativa de qué actor puede hacer `bypass` y demostrar que un actor no autorizado no puede crear, mover ni borrar `v1`. El bootstrap no infiere `bypass_actors` cuando el token lector no los expone.
7. Solo si todo coincide, el job con escritura invoca `pl0n3r/factory/.github/workflows/release.yml@v1` y crea/verifica el tag anotado `v1.0.0` + GitHub Release.
8. Después ejecuta un **self-test** consumidor mediante `pl0n3r/factory/.github/workflows/ci.yml@v1` sobre `template/`. Un fallo mantiene la adopción TANDA 2 bloqueada.

El marker de aprobación autoriza únicamente el SHA indicado; cambiar `main`, mover `v1` o usar otra puerta hace fallar cerrado el preflight.
Para releases posteriores dentro de la misma major, `v1` se actualiza únicamente mediante el proceso humano/autorizado definido para el canal mayor, nunca por inferencia de un agente.

El merge de esta preparación no crea ningún tag automáticamente. El caller existe, pero solo `workflow_dispatch` del dueño y todos los gates satisfechos pueden ejecutar la publicación.
