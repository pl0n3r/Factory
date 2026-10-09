# Deduplicación global de NO_WORK

Factory#904 define un único sink canónico para el estado global NO_WORK:

- Issue: `pl0n3r/Factory#904`.
- La decisión es pura y vive en `scripts/no_work_dedup.py`.
- El caller sigue siendo responsable de leer inventario vivo, recheck final y GitHub.
- Este contrato no altera ranking, readiness, kill switch, D-068 ni puertas humanas.

## Huella del inventario

La huella SHA-256 usa exclusivamente:

1. estado del kill switch;
2. hojas `available` / `estado: disponible`;
3. hojas de recovery;
4. reservas vivas;
5. bloqueos;
6. número, estado y HEAD de PRs abiertos;
7. los siete repos canónicos: Factory, Condor, GrindFlow, brvtal, ControlBot,
   AutoFactory y FactoryRunner.

Campos incidentales como timestamps de observación, títulos de PR o texto de UI no
cambian la huella. Un repo faltante hace fallar el cálculo en vez de permitir un
NO_WORK parcial.

## Metadatos de observación anidados (Factory#1065)

Al construir la huella, las entradas de `reservations` y `blockers` pueden
llevar `observed_at`, `fetched_at` y `captured_at` como timestamps
**exclusivamente observacionales**. Se omiten de la proyección, sin cambiar el
objeto original del caller. Una misma `reservation_id`, dueño, rama, issue,
claims y estado conserva la misma huella aunque otro agente capture después.

Si el productor necesita etiquetar `updated_at` como hora de observación,
debe usar el namespace explícito `observation_metadata: {updated_at: ...}`.
Solo admite `observed_at`, `fetched_at`, `captured_at` y `updated_at`
con valores temporales válidos: epoch Unix como entero no negativo o cadena
ISO 8601 con zona horaria explícita. Se rechazan cadenas arbitrarias,
fechas sin zona y tipos ambiguos. Un `updated_at` ordinario fuera de
ese namespace **se conserva como material**: puede representar un cambio de
reserva o bloqueo y nunca se descarta por heurística.

Los campos desconocidos de la entrada también permanecen en la huella, para
no ocultar cambios materiales. Una metadata declarada como observacional
pero ambigua o con claves no permitidas falla cerrado con
`NoWorkInventoryError`: nunca se omiten campos desconocidos de una supuesta
observación. Cambios de `reservation_id`, `owner`, `issue`, `branch`,
`active`, `claims` o del motivo/condición de los `blockers` cambian
la huella. Las reservas inactivas continúan excluidas como antes. El normalizado
de PR (número, estado abierto, HEAD exacto) no cambia.

## Tiempo de observación vs. tiempo de publicación

`observed_at` identifica cuándo se tomó la fotografía del inventario. Es distinto
de `published_at`, que identifica cuándo el estado canónico fue escrito en GitHub.
La huella sigue dependiendo solo del inventario autorizado y nunca del timestamp.

Para compatibilidad, callers existentes que no informan `observed_at` usan el
momento de decisión/publicación como observación. Los estados históricos sin ese
campo se normalizan con `observed_at = published_at`.

## Decisión create | update | omit

Dado el snapshot actual y el estado del comentario canónico:

| Condición | Acción |
| --- | --- |
| No existe comentario canónico previo | `create` una vez en Factory#904 |
| La huella cambió | `update` del mismo comment_id |
| Huella idéntica y han pasado < 30 min | `omit` |
| Huella idéntica y han pasado >= 30 min | `update` del mismo comment_id |

Después de la creación inicial, la política nunca requiere crear otro comentario
para NO_WORK. Un incidente como Factory#860 no es un sink alternativo.

## Revalidación justo antes de escribir

Una decisión calculada no autoriza por sí sola el overwrite. Inmediatamente antes
de `create` o `update`, el caller debe releer el estado canónico y ejecutar
`revalidate_no_work_application(decision, current)`.

La precondición es fail-closed:

- `apply`: el comentario/fingerprint esperado siguen vigentes y la observación
  canónica no es más nueva que la decisión;
- `omit`: la decisión original ya era un no-op;
- `recompute`: cambió `comment_id`, cambió el fingerprint esperado, apareció o
  desapareció el comentario concurrentemente, o el canónico contiene una
  observación más nueva.

Ante `recompute`, el caller no debe escribir con la decisión vieja: debe volver a
leer inventario vivo, recalcular la decisión y repetir la revalidación. Esto evita
la carrera A/B donde B observa primero, se demora y luego intenta reemplazar el
estado publicado por A con evidencia más reciente.

## Baseline y métrica

Factory#904 describía el episodio como “decenas de comentarios” entre
aproximadamente 22:50 y 00:00 UTC. La relectura reproducible del feed global de
comentarios de GitHub mostró un desfase horario en esa descripción: esa ventana
exacta contiene 0 comentarios NO_WORK, mientras el burst observable anterior sí
puede medirse sin inferencia.

Entre **20:00:19Z** y **22:46:22Z** del 2026-10-02, la API devuelve
**119 comentarios** NO_WORK nuevos, todos en Factory#860. Son 166.05 minutos y
equivalen a **43.0 comentarios nuevos/h**. Este es el baseline verificable usado
por la regresión; no se extrapola desde la palabra “decenas”.

Con la política nueva:

- primera observación sin comentario canónico: máximo **1 creación total**;
- después de existir el comentario: máximo **0 comentarios nuevos/h** por
  inventario idéntico;
- con huella idéntica, como máximo **2 updates in-place/h** (intervalo 30 min);
- un cambio real de inventario puede actualizar inmediatamente el mismo
  comentario, pero no crea uno nuevo.

La métrica primaria es `new_no_work_comments_per_hour`; la secundaria es
`canonical_no_work_updates_per_hour`. El objetivo no es esconder cambios, sino
hacer que un cambio real sea visible sin multiplicar comentarios equivalentes.

## Reversión

Revertir el PR restaura la conducta previa del despachador. No modifica reservas,
Issues de trabajo, kill switch ni producción.
