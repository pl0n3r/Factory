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

## Promoción segura

Factory Lab solo marca `promotion.ready=true` cuando:

1. Constitution valida el candidato;
2. Fitness declara `improved`;
3. no hay regresiones protegidas;
4. no faltan dimensiones de Fitness.

Incluso entonces, `promotion_contract()` devuelve
`requires_human_or_authorized_promotion=true` y `execution=not-performed`.
El laboratorio nunca ejecuta la promoción.

## Workflow

`.github/workflows/evolution-lab.yml` usa exclusivamente `contents: read`,
checkout fijado a SHA y `persist-credentials: false`. No usa secretos, tokens
de escritura ni permisos sobre Issues, PRs, deployments, packages o actions.

El workflow ejecuta únicamente validación local del contrato.

## Fuera de alcance

- deploy productivo;
- mutación de stable;
- modificación de Constitution;
- creación de releases;
- escritura en servicios externos;
- ampliación de autoridad.
