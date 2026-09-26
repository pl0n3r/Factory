# Fitness Engine v1

Fitness Engine compara una evolución candidata contra un baseline como **vector
multidimensional**. No suma dimensiones ni produce un score mágico: cada métrica
conserva su dirección, valor, delta y estado independiente.

## Entrada

Cada vector es un objeto `dimension -> metric`:

```json
{
  "security": {"value": 0.98, "direction": "higher"},
  "latency": {"value": 140, "direction": "lower"},
  "cost": {"value": null, "direction": "lower"}
}
```

`value=null` o una dimensión ausente significa dato desconocido. El motor no
imputa valores. `direction` debe ser `higher` o `lower` y no puede cambiar
entre baseline y candidate.

## Dimensiones protegidas

Por defecto las dimensiones protegidas provienen de
`evolution.constitution.PROTECTED_INVARIANTS`: security, privacy,
traceability, reversibility y authority.

Una regresión en cualquiera de ellas produce `claim=blocked`, aunque otras
dimensiones mejoren. Fitness informa el bloqueo; no modifica Constitución ni
promueve cambios.

## Resultado por dimensión

Cada dimensión queda en uno de cuatro estados:

- `improved`: mejora según su dirección;
- `equal`: no cambia;
- `regressed`: empeora;
- `unknown`: falta baseline o candidate.

El resultado conserva `baseline`, `candidate`, `direction`, `delta` y si
la dimensión es protegida.

## Confianza y claim

La confianza es evidencia observable, no una calidad agregada:
`comparable / total`.

- cualquier regresión protegida → `blocked`;
- cualquier dato faltante → `inconclusive`;
- regresiones no protegidas mezcladas con mejoras → `mixed`;
- una o más mejoras sin regresiones/faltantes → `improved`;
- todo igual → `equal`.

`can_claim_improvement=true` solo para `improved`. Esto impide ocultar
degradaciones o incertidumbre detrás de un promedio.

## Determinismo y límites

Los nombres de dimensión se normalizan por orden, se admiten hasta 64 dimensiones
por vector, se rechazan números no finitos y el resultado incluye un fingerprint
SHA-256 estable. Reordenar las mismas métricas no cambia la comparación ni la
huella.

## Fuera de alcance

El motor no recolecta métricas externas, no decide promoción, no ejecuta cambios
y no concede autoridad. Solo compara evidencia entregada explícitamente.
