# BRVTAL · Performance Contract bootstrap

Este documento materializa la policy específica de BRVTAL que desbloquea la frontera baseline/budget de Factory #304. El productor es `Production Performance` de BRVTAL #819/#820 y usa probes Playwright de laboratorio; este contrato **no** convierte tres corridas lab en datos de campo, CrUX ni p75 de usuarios reales.

## Evidencia comparable

Las tres muestras usan el mismo productor y la misma semántica de observación (`window_seconds=1`, `sample_count=1`):

| Evidencia | Mobile FCP / LCP / CLS | Desktop FCP / LCP / CLS |
| --- | --- | --- |
| BRVTAL `c62baaabc994484d925d11f3625bb12772a8b5cb` · run `36786118661` | 380 ms / 1600 ms / 0 | 456 ms / 1772 ms / 0.005 |
| BRVTAL `7ac39afa8ad205cc3c3668906a6d1ffa873ac1cf` · run `36853443439` · attempt 1 | 468 ms / 1768 ms / 0 | 788 ms / 2352 ms / 0.004 |
| BRVTAL `7ac39afa8ad205cc3c3668906a6d1ffa873ac1cf` · run `36853443439` · attempt 2 | 380 ms / 1624 ms / 0 | 440 ms / 1748 ms / 0.005 |

La baseline bootstrap es la **mediana por superficie y métrica** de esas tres muestras:

- mobile: FCP 380 ms, LCP 1624 ms, CLS 0;
- desktop: FCP 456 ms, LCP 1772 ms, CLS 0.005.

El contrato usa `observed_at=2026-10-01T11:47:55Z`, cierre del attempt 2 más reciente, como timestamp de materialización de esa baseline derivada. La provenance canónica apunta a Factory #304; esta página conserva los runs/attempts que permiten reproducir la derivación.

## Budgets web explícitos

Los budgets son guardrails BRVTAL declarados, no una fórmula global de Factory:

- FCP `<= 1800 ms`, alineado con la referencia pública de web.dev para una puntuación FCP “good”: https://web.dev/articles/fcp
- LCP `<= 2500 ms`, alineado con la referencia pública de web.dev para LCP “good”: https://web.dev/articles/lcp
- CLS `<= 0.1`, alineado con la referencia pública de web.dev para CLS “good”: https://web.dev/articles/cls

Las páginas públicas de web.dev explican esos umbrales en contexto de experiencia de usuario y recomiendan evaluar el percentil 75 de cargas/visitas cuando se dispone de datos de campo. Aquí se reutilizan **solo los valores numéricos como budgets de laboratorio explícitos** para este consumidor. Tres probes Playwright no acreditan p75, CrUX ni Core Web Vitals de campo.

## Ventana, freshness y métricas fuera del contrato

El productor actual emite una observación puntual con `window_seconds=1` y `sample_count=1`. Por eso el bootstrap declara esa ventana mínima y `freshness.max_age_seconds=604800` (7 días). Esto permite clasificar la evidencia reciente sin fingir una distribución estadística.

`dom_content_loaded` y `load_event_end` siguen siendo telemetría útil, pero no tienen budget aprobado. No aparecen en `performance/contracts/brvtal.json`; el detector real debe devolver `PERF_REVIEW` + `UNKNOWN` para ellas, nunca inferir un límite.

## Boundary

Este contrato habilita clasificación determinista de FCP/LCP/CLS y describe acciones de workflow, pero **no concede autoridad** ni ejecuta remediación. No cambia BRVTAL, probes, producción, CDN, caché, DB, costos ni thresholds de otros proyectos. WorkItem/Team Compiler/remediación y before/after pertenecen a slices posteriores de #304.
