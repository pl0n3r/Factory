# Quality Gates: Risk + Definition of Done

#345 conecta Quality Contract con los compiladores existentes. No crea un motor nuevo.

## Trust boundary

Risk y DoD consumen Quality Contract solo si:
1. valida con #343;
2. versión y fingerprint coinciden con `Project DNA.extensions.quality_contract`;
3. cada superficie de la tarea está declarada.

Falta de contrato fuente, mismatch o superficie desconocida falla cerrado.

## Risk

La criticidad Quality solo puede elevar riesgo:
`low→low`, `medium→medium`, `high|critical→high`.

Nunca reduce señales, blast radius ni controles existentes. La trazabilidad usa
`quality_contract.surfaces.<surface>.criticality`.

## Definition of Done

Los `required_gates` se añaden y deduplican sobre la evidencia ya derivada. No eliminan invariantes Factory, profiles por cambio/risk/surface ni SAFE_FALLBACK.

Project DNA sin extensión Quality conserva el comportamiento histórico.

## Boundary

Performance (#304) y Recovery (#305) permanecen dimensiones externas. #345 no recalcula sus budgets, estados o algoritmos.

No hay score único, scheduler, backlog, ejecución de gates ni pipeline paralelo.
