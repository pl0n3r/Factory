# Sincronización de colores de labels

`#874` gobierna una sincronización limitada exclusivamente al color de labels ya existentes en los siete repos canónicos.

## Alcance

- Fuente canónica: `labels/es.json` para Factory, Condor, GrindFlow, ControlBot, AutoFactory y FactoryRunner; `labels/en.json` para BRVTAL.
- Los catálogos deben mantener el mismo color por `key`.
- El reconciliador solo genera operaciones `update_color` para labels existentes.
- No crea, borra, renombra ni reasigna labels, y no cambia descripciones.
- BRVTAL conserva sus nombres en inglés.

## Estado planificado

`Factory#1048` añade una distinción semántica que no existía en el vocabulario anterior:

- `estado: bloqueado` / `status: blocked`: trabajo que sí está detenido por una dependencia, fallo o condición real pendiente;
- `estado: planificado` / `status: planned`: plan, épica o roadmap no ejecutable por diseño. No está atascado, no entra al despacho y no debe contarse como bloqueo operativo.

Ambos catálogos usan la key semántica `state_planned` y el mismo color canónico. La exclusividad de la dimensión `state_` se conserva: un Issue no puede ser simultáneamente `planificado` y `bloqueado`, `disponible`, `reservado`, `en revisión`, `requiere recuperación`, `completado` o `cancelado`.

La clasificación a `planificado` debe ser conservadora. Nunca se usa para esconder una hoja ejecutable ni una dependencia abierta real. La migración de Issues existentes se prepara primero como `--dry-run`, es idempotente y solo puede aplicarse después de publicar el kit compatible en `v1` y sincronizar los labels en los consumidores siguiendo `Factory#994`. `Factory#1048` no mueve `v1` ni aplica esa migración.

ControlBot adopta el nuevo estado en una hoja separada (`ControlBot#752`) para que el Orquestador lo muestre aparte de los bloqueos reales. Esa adopción permanece bloqueada hasta completar el orden kit → publicación autorizada → sincronización de labels.

## Operación offline tras F2A

**El trigger remoto está desactivado.** F2A eliminó `.github/workflows/sync-label-colors.yml`; publicar comentarios `/sync-label-colors dry-run` o `/sync-label-colors apply` en Factory #874 **ya no ejecuta** la sincronización. Estos comandos de comentario se conservan aquí solo como referencia histórica, no como instrucciones operativas.

El motor `scripts/sync_label_colors.py` permanece disponible para pruebas offline y para generar un plan de lectura `python3 scripts/sync_label_colors.py --dry-run` en un entorno autorizado. Las pruebas de paridad y reconciliación siguen cubriendo el contrato de actualizar únicamente colores de labels existentes.

**No ejecutar `--apply` ni usar `FACTORY_PROVISION_TOKEN` sin una autorización explícita independiente.** El motor conserva controles de fail-closed, pero la baja del workflow no aplica cambios a etiquetas reales. No hay disparador nuevo, publicación ni escritura remota por comentarios.

## Reversión

El dry-run deja visibles los pares `color_before -> color_after`. Para revertir una aplicación, se usan esos valores anteriores como evidencia y se restauran únicamente los colores afectados; no se requiere rename/create/delete ni cambios de asignaciones.

Ante catálogo inválido, repo fuera de allowlist, snapshot ambiguo, falta de token en apply, respuesta ilegible de GitHub o deriva residual, el reconciliador falla cerrado.
