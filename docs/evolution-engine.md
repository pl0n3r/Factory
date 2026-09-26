# Evolution Engine

El Evolution Engine ejecuta el ciclo de evolución de Factory sin ampliar
autoridad ni redefinir la Constitución. Su fuente de verdad es
`evolution/constitution.py`: el motor carga el contrato canónico y usa
exactamente su lifecycle versionado.

## Lifecycle

`observe → remember → learn → propose → shadow → experiment → validate → promote_or_reject → measure → prune → rollback`

Solo se admite la transición a la etapa inmediatamente siguiente. Una etapa
desconocida, un salto o una decisión fuera de `promote_or_reject` falla
cerrado.

## Registro append-only

Cada entrada conserva:

- `generation`;
- `stage`;
- `parent_generation`;
- `reason`;
- `evidence`;
- la huella del candidato validado por Constitution v1;
- `decision` cuando la etapa es `promote_or_reject`;
- `restores_generation` cuando la etapa es `rollback`.

El candidato se valida antes de crear la primera generación. El motor no
modifica `stable_authority`, invariantes protegidos ni el contrato
constitucional.

## Decisión

`promote_or_reject` exige una decisión explícita `adopt` o `reject`. Esa
decisión describe el resultado del experimento; no concede permisos ni amplía
la autoridad disponible.

## Rollback

Rollback solo es válido al final del recorrido constitucional. Restaurar una
generación previa **no reescribe ni elimina historia**: agrega una nueva entrada
`rollback`, enlaza su padre con la generación actual y registra
`restores_generation` con la generación restaurada. La historia completa
permanece auditable.

## Límites

Este motor es puro y determinista. No ejecuta producción, no recoge métricas de
fitness, no concede autoridad y no sustituye puertas humanas. Esos componentes
pertenecen a nodos posteriores del roadmap Living Software.
