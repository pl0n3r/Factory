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


## Integración canónica al protocolo

Living Software ya tiene una arquitectura conectada al protocolo Factory. Esta sección define el **handoff entre componentes**, no una nueva fuente de autoridad.

Flujo canónico:

1. **Project DNA** → huella verificable del software y unknowns explícitos.
2. **Context Compiler** → briefing mínimo, trazable y privado.
3. **Definition-of-Done Compiler** → evidencia dinámica y verificable.
4. **Risk Compiler** → dimensiones de riesgo, blast radius y controles monotónicos.
5. **Fitness Engine** → comparación multidimensional candidate vs baseline.
6. **Evolution Engine** → lifecycle append-only.
7. **Autonomy Engine** → escalera de supervisión solo para authority class `operational`.
8. **Factory Lab** → shadow candidate vs `stable`, sin mutación.
9. **Experience Guardrails** → patrones repetidos convertidos en candidatos.
10. **Growth/Pruning** → capacidad faltante o entropía convertidas en candidatos con linaje.
11. **Immune/Repair** → incidentes convertidos en reparación reversible e inmunización candidata.

El ciclo operativo resumido es:

`observe → learn → experiment → adopt_or_reject → measure → prune`

y se expande al lifecycle constitucional:

`observe → remember → learn → propose → shadow → experiment → validate → promote_or_reject → measure → prune → rollback`.

`adopt_or_reject` es lenguaje operativo; el estado máquina sigue llamándose `promote_or_reject`.

### Evidencia y autoridad

La evidencia derivada no se autocertifica cuando existe un productor canónico. Autonomy, por ejemplo, revalida Fitness y Risk desde inputs fuente antes de ganar nivel. Una evolución solo puede operar dentro de la autoridad estable ya existente.

Living Software no concede dinero, autoridad legal, acceso a datos personales, borrado irreversible ni permiso de publicar/pasar a live. Esas fronteras siguen gobernadas por PLAN-AGENTES, decisiones.yml y el registro canónico de puertas humanas.

## Hardening de fronteras de evidencia completado

El DAG de #143 y sus hardenings posteriores de evidencia están cerrados en el alcance estructural previsto:

- **#209 — Autonomy authority + canonical evidence:** cerrado. Autonomy separa capability/authority class y revalida Fitness/Risk desde inputs fuente.
- **#211 — Factory Lab promotion provenance:** cerrado. Factory Lab revalida provenance antes de considerar una decisión de promoción.
- **#213 — Growth/Pruning source evidence:** cerrado. Growth/Pruning recompone evidencia fuente antes de producir candidatos confiables.
- **#215 — Repair human authority + immunity provenance:** cerrado. Repair/Immune validan scope, integridad e historia.
- **#221 — deterministic renewal retry:** cerrado. La renovación v2 deriva un successor estable y revalida acceptance/task/HEAD.
- **#223 — trusted Repair/Immune provenance:** cerrado. La autoridad destructiva y los incidentes se resuelven mediante fuentes confiables/append-only; hashes del caller no sustituyen provenance.

### Qué significa cerrar #143

Cerrar #143 declara **arquitectura/protocolo Living Software integrado y endurecido**. Es un cierre estructural del contrato y sus fronteras de evidencia, **no una concesión de producción autónoma irrestricta**.

En particular:

1. Living Software sigue sin concederse autoridad nueva;
2. Promotion no publica ni despliega por sí sola;
3. Repair conserva `automatic_execution_allowed=false` y `execution=not-performed`;
4. dinero, legal, datos reales/personales, borrado irreversible y publicación/live conservan sus puertas humanas vigentes;
5. cualquier fuente no confiable, evidencia inconsistente o conflicto de autoridad continúa fallando cerrado.
