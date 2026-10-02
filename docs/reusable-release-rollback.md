# Rollback fail-closed de Factory@v1

Usa este procedimiento cuando una publicación de Factory haga que uno o más consumidores de workflows reutilizables terminen en `startup_failure` antes de materializar jobs. El objetivo es restaurar el canal mayor a una versión estable conocida **sin convertir una recomendación automática en autoridad para mover tags**.

## 1. Evidencia mínima antes de actuar

Registra, como mínimo:

- SHA exacto de Factory que está resolviendo `@v1`;
- tag/release semántica asociada al incidente;
- repositorios y workflows consumidores afectados;
- run IDs cuyo resultado sea `startup_failure`;
- SHA/tag estable previo conocido que sí materializaba jobs en consumidores.

Un check verde dentro de Factory no sustituye evidencia de consumidor.

## 2. Elegir el objetivo de rollback

El objetivo debe ser un SHA/tag Factory previamente conocido como estable para los consumidores afectados. No se elige por inferencia ni por “último release verde” si no existe evidencia de consumidor.

Documenta explícitamente:

- `affected_factory_sha=<SHA afectado>`;
- `stable_factory_sha=<SHA estable objetivo>`;
- consumidores que justifican el rollback;
- evidencia que demuestra que el SHA estable había materializado jobs.

## 3. Autoridad administrativa

Detectar o recomendar rollback **no autoriza** a un agente, workflow o sesión automática a mover `refs/tags/v1`.

Mover `v1` sigue siendo una acción humana/administrativa protegida por la puerta vigente de Factory. El OWNER debe ejecutar conscientemente la actualización del tag mayor al SHA estable exacto mediante su canal administrativo autorizado.

La acción administrativa debe equivaler exactamente a mover:

    refs/tags/v1 -> <stable_factory_sha>

No se autoriza mover tags semánticos, publicar una release nueva, cambiar otra referencia ni usar un SHA distinto.

## 4. Verificación posterior obligatoria

Después de restablecer `v1`, genera un evento nuevo en al menos un consumidor afectado y exige evidencia nueva de que:

1. el workflow reutilizable vuelve a **materializar jobs**;
2. el run deja de terminar en `startup_failure`;
3. el workflow usa el `Factory@v1` que resuelve al SHA estable objetivo.

Los runs fallidos previos al rollback **no prueban recuperación**. Solo pueden reintentarse o regenerarse después de restablecer el canal.

Si no existe evidencia nueva de consumidor, el incidente permanece abierto/fail-closed.

## 5. Cierre y seguimiento

Conserva en el incidente:

- SHA afectado;
- SHA estable restaurado;
- repos/workflows afectados;
- run IDs antes y después;
- evidencia de al menos un consumidor recuperado;
- decisión humana/administrativa que movió `v1`.

Después del rollback, la corrección de fondo debe viajar por un PR separado y una nueva puerta de release. Nunca uses el rollback como bypass de compatibilidad reusable↔caller.
