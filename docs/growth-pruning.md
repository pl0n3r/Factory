# Growth + Pruning v1

Growth y Pruning modelan dos mecanismos complementarios del Living Software:
crear capacidades que realmente faltan y retirar entropía demostrada sin borrar
historia ni tocar controles protegidos.

## Growth

`detect_capability_gap()` compara una capacidad requerida contra el inventario
existente usando un identificador canónico conservador. Solo normaliza
mayúsculas, acentos, puntuación y espacios; no inventa equivalencias semánticas.

Si existe una capacidad equivalente, devuelve `gap=false` y señala
`reuse=<capability>`. En ese caso `compile_growth_candidate()` devuelve
`None`: Factory reutiliza en vez de duplicar.

Un gap real puede producir un candidato Constitution-valid bajo
`evolution_state.heuristics.capability_<hash>`. El candidato conserva:

- capacidad requerida;
- valor esperado;
- fingerprint del gap;
- evidencia origen;
- rollback reversible.

Growth no instala ni promociona la capacidad.

## Pruning

`evaluate_pruning()` exige evidencia medible:

- uso <= 1;
- edad >= 90 días;
- valor <= 0.25;
- al menos 2 referencias de evidencia.

Solo si las cuatro condiciones se cumplen se marca `eligible=true`.

`compile_pruning_candidate()` no borra la capacidad ni su historia. Emite un
candidato `prune-candidate` bajo `evolution_state.heuristics`, con rollback
`restore_baseline` y linaje que conserva:

- parent fingerprint;
- fingerprint de la evaluación;
- evidencia;
- `history_preserved=true`.

La ejecución real debe atravesar Evolution Engine y Factory Lab.

## Capacidades protegidas

Nunca pueden podarse las dimensiones constitucionales:

`security`, `privacy`, `traceability`, `reversibility`, `authority`.

También se protegen explícitamente `constitution`, `human-gates`,
`rollback` y `audit-trail`. El caller puede marcar además cualquier capacidad
como `protected=true`.

Pruning falla cerrado antes de evaluar uso/edad/valor para cualquiera de ellas.

## Fuera de alcance

- borrar historia;
- retirar Constitution o controles protegidos;
- mutar stable;
- promover candidatos automáticamente.
