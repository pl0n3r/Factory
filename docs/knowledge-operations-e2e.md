# Knowledge Operations — E2E v1

#322 demuestra el loop integrado; no añade runtime ni otro motor.

## Ciclo verificado

Knowledge Item Contract (#319) → Selection (#321) → Context Compiler conserva scope, provenance y authority sin cambios. Postmortem (#320) con causa conocida y evidencia → lesson canónica → Experience Guardrails puede producir únicamente un candidate. Root cause unknown no produce lesson ni guardrail.

Knowledge Lifecycle sigue siendo la única fuente de freshness. Items stale/deprecated no entran como current; propose_pruning_candidates() solo genera propuestas revisables con delete=false e history_preserved=true.

## Invariantes

- No promoción automática de guardrails.
- No delete físico durante pruning.
- No store, red, scheduler, polling, vector DB ni embeddings.
- No WorkItems ni cambios de authority en este slice.
- Context Compiler recibe únicamente category/source/text/tags.
- Provenance permanece en bindings/artefactos canónicos, no se inventa.

README permanece como portada operativa derivada: el detalle de root cause, lifecycle, guardrails y pruning vive en estos artefactos/docs, no en README.\n\nEste E2E cierra el DAG local de #307: Contract → Postmortem/Selection → Context/Guardrail/Pruning. No crea un Knowledge Engine paralelo.
