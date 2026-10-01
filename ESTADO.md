# Estado derivado de la fábrica

> Vista generada y no autoritativa. GitHub y los health/smoke reales siguen
> siendo la fuente operativa. Si esta vista deriva o queda vieja, falla cerrado
> y debe regenerarse desde evidencia canónica.

- **TANDA 1:** COMPLETADA
- **TANDA 2:** COMPLETADA
- **TANDA 3:** ACTIVA
- **Freshness de evidencia:** `2026-09-30T17:03:36Z` (máximo `updated_at` del snapshot)
- **Snapshot SHA-256:** `3e9c6224d7afe9e74c6779d61c69154e20a1cd0aa27ca5b1c43894c680a0e8a4`

## Evidencia canónica de TANDA 2

| Proyecto | Épico | Estado normalizado | updated_at | Fuente |
| --- | --- | --- | --- | --- |
| Condor | Condor#192 | COMPLETADO | `2026-09-26T20:01:32Z` | [https://github.com/pl0n3r/Condor/issues/192](https://github.com/pl0n3r/Condor/issues/192) |
| GrindFlow | GrindFlow#129 | COMPLETADO | `2026-09-30T17:03:36Z` | [https://github.com/pl0n3r/GrindFlow/issues/129](https://github.com/pl0n3r/GrindFlow/issues/129) |
| BRVTAL | brvtal#630 | COMPLETADO | `2026-09-30T13:42:20Z` | [https://github.com/pl0n3r/brvtal/issues/630](https://github.com/pl0n3r/brvtal/issues/630) |
| FactoryRunner | FactoryRunner#1 | COMPLETADO | `2026-09-29T05:02:05Z` | [https://github.com/pl0n3r/FactoryRunner/issues/1](https://github.com/pl0n3r/FactoryRunner/issues/1) |

## Semántica fail-closed

TANDA 3 solo figura ACTIVA cuando los cuatro épicos canónicos están presentes,
cerrados, con razón `completed` y etiqueta de completado coherente. Evidencia
faltante, abierta, contradictoria, no terminal o de otra URL produce TANDA 2
UNKNOWN y mantiene TANDA 3 BLOQUEADA.
