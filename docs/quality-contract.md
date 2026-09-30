# Quality Contract v1

#343 define el contrato canónico de calidad por proyecto. No ejecuta gates ni crea un scheduler/backlog.

Cada proyecto declara sus propias superficies, criticidad, invariantes, gates requeridos, compatibilidad, accessibility, migración, smoke y freshness. No existe un score único ni defaults globales ocultos.

Performance (#304) y Recovery (#305) son dimensiones externas: el contrato guarda `required` + `source_ref` y nunca copia budgets, estado o lógica de esos sistemas.

## Sonar monitoring opcional

La clave `sonar` es una extensión opcional y cerrada del mismo Quality Contract; no crea un pipeline de calidad paralelo ni llama APIs de Sonar.

Cuando está presente, el proyecto declara **todos** sus umbrales de forma explícita:

- `expected_visibility`: `public|private`;
- `analysis_method`: `automatic|ci`;
- `max_analysis_age_seconds`: freshness máxima del análisis;
- `max_organization_line_usage_percent`: porcentaje máximo de uso de líneas de la organización antes de degradar la señal;
- `max_open_vulnerabilities`, `max_open_bugs` y `max_open_hotspots`: deuda abierta máxima permitida;
- `max_debt_age_days`: antigüedad máxima permitida para deuda abierta.

No existen defaults Sonar implícitos. Si `sonar` está ausente, el significado es **“Sonar monitoring no configurado”**: aguas abajo no se aplican thresholds Sonar y esa ausencia nunca debe reinterpretarse como PASS.

Ausencia, stale o evidencia inválida se interpreta aguas abajo como **UNKNOWN**; UNKNOWN no equivale a PASS.

Este slice no modifica Project DNA, Risk/DoD, Queue #269 ni Readiness #293. Esas integraciones pertenecen a #344–#348. La captura/normalización de evidencia Sonar y su proyección a Quality Health pertenecen a los leafs posteriores de #487.
