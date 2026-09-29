# Knowledge Operations Contract v1

Factory no crea un **Knowledge Engine** nuevo. Esta capa normaliza metadata operativa
para ADRs, decisiones, runbooks, postmortems y otras piezas de conocimiento, y
reutiliza contratos que ya existen.

## Fuentes canónicas

- **Knowledge Lifecycle** (`evolution/knowledge_lifecycle.py`) conserva provenance,
  scope, timestamps, review/expiry, confidence, evidence class, state e history.
- **Context Compiler** seleccionará en #321 el mínimo conocimiento relevante para
  una misión.
- **Experience Guardrails / pruning** continúan siendo responsables de candidatos
  y consolidación. Este contrato no implementa esas capacidades otra vez.

## Knowledge Item v1

Cada item declara metadata cerrada:

- `item_id` e `item_class`;
- `title`, `summary` y `tags` acotados;
- `owner_ref`;
- `authority_class`, usando el catálogo canónico Capability × Authority;
- `sensitivity`: `normal | personal_data | sensitive_data`;
- `related_refs`;
- relaciones `supersedes` / `superseded_by`;
- `lifecycle`, validado íntegramente por Knowledge Lifecycle v1.

Clases soportadas:

`decision`, `adr`, `runbook`, `postmortem`, `architecture_invariant`,
`product_rule`, `operational_procedure`, `troubleshooting`,
`known_limitation`, `experiment_result`, `lesson_guardrail_candidate`.

`item_id` debe coincidir con `lifecycle.knowledge_id` y `item_class` con
`lifecycle.knowledge_type`. Supersession no admite autorreferencias ni relaciones
contradictorias.

## Freshness y lifecycle

`knowledge_item_status()` no calcula una segunda freshness. Delega en
`effective_state()` del Knowledge Lifecycle y solo considera `current=true`
cuando el estado efectivo es `active`.

Así, un item `candidate`, `needs_review`, `deprecated` o `archived` nunca se
presenta como conocimiento vigente. History/provenance permanecen append-only
según el lifecycle existente.

## Authority y sensitivity

`authority_class` describe la clase de autoridad relacionada con el conocimiento,
pero el item **no concede autoridad**. Clases reservadas (`money`, `legal`,
`personal_data`, `irreversible_delete`, `authority_expansion`) conservan sus
puertas humanas y provenance autenticada en Capability × Authority.

`sensitivity` también es metadata descriptiva. El contrato no permite incluir
PII, secretos, tokens, emails, teléfonos o IPs dentro de title/summary/refs. #321
decidirá qué items son elegibles para Context Compiler y debe fallar cerrado ante
conocimiento no apto para contexto.

## Límites

- sin I/O ni store;
- sin búsqueda vectorial;
- sin scheduler;
- sin delete;
- sin mutar Knowledge Lifecycle;
- sin ampliar autonomy/authority;
- sin convertir README en almacén documental.

README permanece una portada derivada: puede enlazar/resumir conocimiento, pero
la documentación profunda vive fuera de README.
