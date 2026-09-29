# Quality Contract v1

#343 define el contrato canónico de calidad por proyecto. No ejecuta gates ni crea un scheduler/backlog.

Cada proyecto declara sus propias superficies, criticidad, invariantes, gates requeridos, compatibilidad, accessibility, migración, smoke y freshness. No existe un score único ni defaults globales ocultos.

Performance (#304) y Recovery (#305) son dimensiones externas: el contrato guarda `required` + `source_ref` y nunca copia budgets, estado o lógica de esos sistemas.

Ausencia, stale o evidencia inválida se interpreta aguas abajo como **UNKNOWN**; UNKNOWN no equivale a PASS.

Este slice no modifica Project DNA, Risk/DoD, Queue #269 ni Readiness #293. Esas integraciones pertenecen a #344–#348.
