# Experience Guardrail Compiler v1

Experience Guardrail Compiler convierte **patrones demostrados** de lecciones en
candidatos de prevención ejecutable. Nunca promueve una regla directamente a
stable y nunca modifica las lecciones históricas.

## Entrada

Consume el formato canónico de `lecciones/memoria.py`:

- `what`: qué ocurrió;
- `why`: causa;
- `prevention`: prevención esperada;
- `source`: Issue/PR con evidencia;
- además de id, proyecto, kind y timestamp.

Las lecciones se validan con el validador existente antes de agruparlas.

## Patrón equivalente

Dos lecciones son equivalentes cuando coinciden en:

- proyecto;
- causa normalizada;
- prevención normalizada.

La normalización solo elimina diferencias de mayúsculas, acentos, puntuación y
espacios. No intenta inferir equivalencias semánticas sin evidencia.

## Umbral anti-burocracia

Por defecto se requieren al menos **2 lecciones** y **2 fuentes distintas**.
Una anécdota aislada, o dos registros que apuntan a la misma fuente, no generan
candidato.

El compilador acepta hasta 32 lecciones por llamada y el umbral nunca puede bajar
de 2.

## Salida

Cada patrón suficiente produce un único candidato con:

- fingerprint determinista del patrón;
- ids y fuentes de todas las lecciones origen;
- prevención esperada;
- ocurrencias;
- candidato constitucional bajo
  `evolution_state.heuristics.guardrail_<fingerprint>`;
- rollback `revert`;
- fingerprint validado por Constitution.

El valor del cambio conserva `origins` completos y `status=candidate`. La
promoción posterior debe recorrer Evolution Engine / Factory Lab; este componente
no puede convertir el candidato en autoridad estable.

## Fuera de alcance

No reescribe historia, no modifica políticas estables, no ejecuta guardrails y no
amplía autoridad.
