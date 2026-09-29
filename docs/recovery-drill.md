# Recovery restore drill v1

#330 demuestra recuperación **sin tocar producción**. `build_restore_drill_plan()` solo acepta backups `VERIFIED` de #329 y targets `disposable`; describe selección, checksum, decrypt, target limpio, restore, migraciones compatibles, health, smoke, integrity y report, siempre con `authority=unchanged` y `execute=false`.

`evaluate_restore_drill()` exige checksum consistente y health/smoke/integrity exitosos. Calcula RPO como distancia entre recovery point e incidente y RTO como duración observada del restore drill. Devuelve `PASSED` si ambos targets del Recovery Manifest se cumplen o `BREACHED` con `RPO_EXCEEDED` / `RTO_EXCEEDED`.

No ejecuta restore, decrypt, migraciones, HTTP, browser smoke, DB/media writes, failover ni cutover. #331 consume el resultado para Recovery Health/Readiness.
