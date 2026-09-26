# Factory Living Software — Constitución v1

Factory Living Software puede aprender, experimentar, reparar y adaptar heurísticas sin ampliar por sí mismo la autoridad de la fábrica. Esta Constitución separa la **capa estable** de la **capa evolutiva** y define el límite que los motores posteriores del DAG #143 deben consumir.

## Contrato vigente

`constitution.version = 1`

`human_gate_registry = seguridad/puertas-humanas.json`

La fuente ejecutable vive en:

- `evolution/constitution.json`: contrato máquina versionado;
- `evolution/constitution.py`: validador fail-closed de Constitución y candidatos.

No existe una segunda lista de categorías de decisión humana dentro de Living Software. Las categorías válidas se delegan al registro canónico indicado arriba.

## Autoridad estable

La autoridad estable no es estado evolutivo y su mutación autónoma está prohibida. Sus fuentes v1 son:

- PLAN-AGENTES.md
- AGENTES.md
- decisiones.yml
- seguridad/puertas-humanas.json
- docs/puertas-humanas.md
- docs/resiliencia-fabrica.md

Una evolución no puede reinterpretar estas fuentes para concederse permisos, eliminar una puerta humana o rebajar una decisión vigente. Un cambio de ese tipo pertenece al mecanismo de gobierno correspondiente, fuera del candidato evolutivo.

## Invariantes protegidos

Los invariantes que v1 prohíbe rebajar autónomamente son exactamente:

- security
- privacy
- traceability
- reversibility
- authority

Cada uno usa la política `must_not_weaken` y `autonomous_mutation = forbidden`. Su fuente está fijada por la Constitución v1; cambiar ese binding exige una nueva versión del contrato, no una mutación evolutiva.

## Estado evolutivo permitido

Un candidato autónomo solo puede cambiar paths bajo estos prefixes:

- evolution_state.observations
- evolution_state.hypotheses
- evolution_state.experiments
- evolution_state.heuristics
- evolution_state.thresholds
- evolution_state.metrics
- evolution_state.autonomy_scores

Todo path fuera de esos namespaces falla cerrado. En particular, `stable_authority.*`, `protected_invariants.*` y `candidate_policy.*` no son superficies de evolución autónoma.

Cada candidato debe declarar:

- `version = 1`;
- entre 1 y 32 cambios;
- evidencia explícita;
- rollback reversible;
- estrategia de rollback `revert` o `restore_baseline`.

El validador devuelve una huella SHA-256 del candidato serializado canónicamente. La misma entrada semántica produce la misma huella independientemente del orden de claves JSON.

## Ciclo Living Software

El lifecycle máquina y documental es exactamente:

observe → remember → learn → propose → shadow → experiment → validate → promote_or_reject → measure → prune → rollback

### 1. observe

Recoger señales verificables de operación, calidad, costo, seguridad, producto o ingeniería. Una observación todavía no es una regla.

### 2. remember

Registrar evidencia en la memoria apropiada sin mezclar conocimiento universal, de fábrica y por proyecto.

### 3. learn

Convertir evidencia repetida en una hipótesis explícita. Aprender no concede autoridad.

### 4. propose

Producir un candidato cerrado con cambios, evidencia y rollback. El candidato debe pasar la Constitución antes de cualquier experimento.

### 5. shadow

Ejecutar o evaluar el candidato sin afectar la ruta estable cuando el riesgo lo requiera.

### 6. experiment

Comparar el candidato contra baseline en un entorno o población acotada. Los motores futuros definirán fitness y métricas; esta Constitución solo fija el límite de autoridad.

### 7. validate

Comprobar evidencia, criterios ejecutables e invariantes protegidos. Un weakening constitucional se rechaza aunque otras métricas mejoren.

### 8. promote_or_reject

Promover únicamente con evidencia reproducible y dentro de la autoridad ya existente. Si la propuesta requiere dinero, legal, datos reales, publicación/live u otra puerta humana vigente, se usa el registro canónico de puertas; Living Software no la sustituye.

### 9. measure

Medir el resultado posterior contra el baseline y conservar trazabilidad de la decisión.

### 10. prune

Retirar hipótesis, reglas o capacidades evolutivas obsoletas cuando la evidencia lo justifique, sin borrar historia necesaria para auditoría.

### 11. rollback

Restaurar el baseline cuando la evolución degrada fitness o rompe una condición de seguridad. La reversibilidad es una invariante, no una preferencia.

## Qué valida Constitution v1

`validate_constitution()` falla cerrado ante versión desconocida, campos extra/faltantes, fuentes no canónicas, weakening de invariantes, prefixes evolutivos distintos, operaciones no previstas o lifecycle divergente.

`validate_candidate()` acepta únicamente cambios en el estado evolutivo permitido. También exige evidencia y rollback reversible. La función no ejecuta el cambio: autoriza estructuralmente un candidato para que motores posteriores puedan evaluarlo.

## Éxito observable

Esta primera hoja del DAG se considera útil cuando:

1. cualquier motor posterior puede importar un único validador reutilizable;
2. un candidato legítimo dentro de `evolution_state.*` obtiene una huella determinista;
3. intentos de modificar seguridad, privacidad, trazabilidad, reversibilidad o autoridad fallan antes de experimentar;
4. documentación y contrato máquina divergen de forma detectable por CI.

## Fuera de alcance

Constitution v1 no implementa Evolution Engine, Fitness Engine, Risk Compiler, Lab, autonomía adaptativa ni promoción a producción. Tampoco modifica decisiones del dueño, crea nuevas categorías de puertas humanas ni publica releases.

Los nodos posteriores #145–#157 deben consumir esta Constitución y extender capacidades alrededor de ella; no deben copiarla ni crear una política paralela.
