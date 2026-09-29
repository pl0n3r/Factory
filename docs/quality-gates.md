# Quality Gates: integración Risk + Definition of Done

#345 conecta Quality Contract con los compiladores existentes. No crea un motor nuevo.

## Trust boundary

Project DNA puede declarar `extensions.quality_contract` desde #344. Risk y DoD solo consumen el Quality Contract fuente cuando:

1. el contrato valida con #343;
2. su versión coincide;
3. su fingerprint coincide con el declarado por Project DNA.

Si falta el contrato fuente, hay mismatch o la tarea toca una superficie no declarada, la compilación falla cerrado.

## Risk

La criticidad de una superficie Quality solo puede **elevar** el riesgo calculado. Nunca reduce señales, blast radius ni controles existentes.

- `low → low`
- `medium → medium`
- `high|critical → high`

La trazabilidad se registra como `quality_contract.surfaces.<surface>.criticality`.

## Definition of Done

Los `required_gates` de cada superficie se añaden a la evidencia ya derivada por Factory. Se deduplican y siguen siendo machine-verifiable.

Quality no elimina:

- invariantes Factory;
- profiles por change type;
- profiles por risk;
- profiles por surface;
- SAFE_FALLBACK ante contexto incompleto.

## Compatibilidad

Project DNA sin extensión Quality conserva exactamente el flujo histórico: no requiere Quality Contract y no aparecen dimensiones/campos Quality nuevos en Risk/DoD.

## Boundary

Performance (#304) y Recovery (#305) permanecen dimensiones externas referenciadas por Quality Contract. #345 no recalcula sus budgets, estados o algoritmos.

No hay score único, scheduler, backlog, ejecución de gates ni pipeline paralelo.
