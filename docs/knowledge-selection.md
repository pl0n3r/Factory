# Knowledge Selection v1

Este slice adapta Knowledge Item Contract v1 al **Context Compiler existente**. No crea un buscador, motor de memoria ni almacén nuevo.

## Misión cerrada

La misión declara:

- `project` y `domain` exactos;
- `tags` relevantes;
- categorías admitidas por Context Compiler: `decision|lesson|constraint|evidence`;
- `require_current`;
- `max_items` (máximo 12);
- `now_at` para evaluar freshness con Knowledge Lifecycle.

La selección valida cada Knowledge Item mediante `knowledge.contract` y usa `knowledge_item_status()`. Solo items con estado efectivo `active/current` pueden convertirse en contexto.

## Selección

No existe score mágico. El algoritmo:

1. exige scope exacto `project + domain`;
2. filtra categoría y, cuando existen, tags de misión;
3. descarta items no-current;
4. rechaza conocimiento con sensibilidad distinta de `normal`;
5. ordena determinísticamente por categoría + `item_id`;
6. aplica el límite explícito de la misión.

Si `require_current=true` y no queda conocimiento compatible/current, falla cerrado. Stale/deprecated/archived nunca se presenta como current.

## Adapter a Context Compiler

`context_items` contiene **solo** los cuatro campos admitidos por Context Compiler:

- `category`;
- `source`;
- `text`;
- `tags`.

Provenance, authority y estado se conservan sin modificación en `bindings` paralelos de trazabilidad. El adapter no concede authority ni ejecuta Context Compiler.

## Boundary del DAG

- #320: semántica de postmortem verificable.
- #321: selección scoped/current para Context Compiler.
- #322: E2E Knowledge Operations con lifecycle/context/pruning/guardrails.

Fuera de alcance: embeddings, vector DB, búsqueda externa, scheduler, polling, store documental, mutaciones de Knowledge Items o un Knowledge Engine paralelo.
