# Factory Lab v1

Factory Lab es el entorno de **shadow mode** para evaluar evoluciones antes de
que puedan afectar `stable`.

## Regla principal

El laboratorio no muta repositorios, producción, Issues, releases ni
infraestructura externa. Su salida es evidencia, no una acción.

Todo resultado declara:

- `mode=shadow`;
- `mutation_allowed=false`;
- `external_writes=[]`;
- baseline llamado exactamente `stable`;
- candidate identificado por SHA exacto;
- comparación Fitness completa;
- validación Constitution del candidato.

## Comparación candidate vs stable

`evaluate_shadow()` exige dos SHAs distintos y dos vectores de métricas.
Fitness siempre recibe:

- baseline = métricas de stable;
- candidate = métricas del candidato.

El resultado conserva fingerprints deterministas de ambos vectores y del
candidato constitucional. No existe modo de evaluar un candidato sin baseline
stable explícito.

## Evidencia causal

Una mejora de Fitness no prueba causalidad por sí sola. Para convertir una
mejora observada en candidata a promoción, `evaluate_experiment_evidence()`
exige una declaración cerrada con:

- baseline y treatment explícitos, cada uno ligado a su SHA exacto;
- métricas protegidas;
- clase de evidencia: `observational`, `quasi_experimental` o
  `controlled_shadow`;
- impacto `low|medium|high`;
- tamaño de muestra de baseline y treatment;
- confounders conocidos;
- cambios simultáneos.

El mínimo de muestra crece con el impacto: 2 para low, 4 para medium y 8 para
high. La fuerza causal requerida también aumenta: observational solo alcanza
low, quasi-experimental puede alcanzar medium y controlled/shadow es necesario
para high. Cualquier confounder o cambio simultáneo reduce un nivel la fuerza de
la conclusión.

Cuando la muestra o la fuerza causal no alcanzan el mínimo, el resultado es
`insufficient_evidence`. Ese estado es de primera clase: no inventa ganador,
no imputa faltantes y no colapsa Fitness a un score único.

## Promoción segura

Factory Lab solo marca `promotion.ready=true` cuando:

1. Constitution valida el candidato;
2. Fitness declara `improved`;
3. no hay regresiones protegidas;
4. no faltan dimensiones de Fitness.

Ese estado sigue siendo insuficiente para afirmar causalidad.
`causal_promotion_contract()` revalida primero el contrato de promoción
existente y después exige evidencia causal reproducible con
`promotion_allowed=true`, verificando que los SHA declarados para baseline y
treatment correspondan exactamente al par stable/candidate evaluado. Una
observación aislada o evidencia causal débil no
puede promover un cambio de alto impacto.

Incluso con evidencia causal suficiente, el contrato conserva
`requires_human_or_authorized_promotion=true` y
`execution=not-performed`. El laboratorio nunca ejecuta la promoción.

## Workflow

`.github/workflows/evolution-lab.yml` usa exclusivamente `contents: read`,
checkout fijado a SHA y `persist-credentials: false`. No usa secretos, tokens
de escritura ni permisos sobre Issues, PRs, deployments, packages o actions.

El workflow ejecuta las suites del contrato shadow y de evidencia causal.

## Fuera de alcance

- deploy productivo;
- mutación de stable;
- modificación de Constitution;
- creación de releases;
- escritura en servicios externos;
- ampliación de autoridad.
