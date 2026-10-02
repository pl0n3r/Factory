# Sincronización de colores de labels

`#874` gobierna una sincronización limitada exclusivamente al color de labels ya existentes en los siete repos canónicos.

## Alcance

- Fuente canónica: `labels/es.json` para Factory, Condor, GrindFlow, ControlBot, AutoFactory y FactoryRunner; `labels/en.json` para BRVTAL.
- Los catálogos deben mantener el mismo color por `key`.
- El reconciliador solo genera operaciones `update_color` para labels existentes.
- No crea, borra, renombra ni reasigna labels, y no cambia descripciones.
- BRVTAL conserva sus nombres en inglés.

## Operación

En `Factory#874`, únicamente el owner del repositorio puede crear uno de estos comentarios exactos:

- `/sync-label-colors dry-run`
- `/sync-label-colors apply`

El primer comando ejecuta `python3 scripts/sync_label_colors.py --dry-run` sin credencial cross-repo y reporta únicamente deriva real como `repo + label + color_actual -> color_canónico`.

El segundo comando requiere `FACTORY_PROVISION_TOKEN`, reutiliza esa credencial solo en el paso de apply y ejecuta `python3 scripts/sync_label_colors.py --apply`. El script hace `PATCH` únicamente del campo `color` de cada label existente y después vuelve a medir. La ejecución falla si la verificación post-apply no termina en `0 drifts`.

No se introduce ningún secreto nuevo. El token no se imprime ni se incluye en excepciones o salida del plan.

## Reversión

El dry-run deja visibles los pares `color_before -> color_after`. Para revertir una aplicación, se usan esos valores anteriores como evidencia y se restauran únicamente los colores afectados; no se requiere rename/create/delete ni cambios de asignaciones.

Ante catálogo inválido, repo fuera de allowlist, snapshot ambiguo, falta de token en apply, respuesta ilegible de GitHub o deriva residual, el reconciliador falla cerrado.
