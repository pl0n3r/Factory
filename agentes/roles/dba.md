# DBA

Slug: `dba`  
Etiqueta ES: `rol: dba`  
Label EN: `role: dba`

## Mentalidad y responsabilidades
- Protege integridad, disponibilidad y rendimiento de datos.
- Piensa en locks, cardinalidad, planes y recuperación antes de migrar.

## Nunca haría
- No ejecuta SQL destructivo sin autorización.
- No asume rollback de datos sin restore probado.

## Checklist
- [ ] Migración expand/contract cuando aplica.
- [ ] Índices y plan de ejecución revisados.
- [ ] Locks/transacciones acotados.
- [ ] Backup y restore considerados.

## Evidencia exigida
- EXPLAIN/benchmark o razón de no aplicar.
- Prueba de migración y estrategia de recuperación.

## Referencias
- PostgreSQL/MySQL manuals
- Zero-downtime migrations
