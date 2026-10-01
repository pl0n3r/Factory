# Clasificación de envelopes de performance

Factory clasifica evidencia Performance v1 producida por proyectos mediante una sola frontera: `performance.classifier.classify_performance_envelope`. El adaptador valida el envelope y delega cada observación a `performance.detector.detect_performance()`; no implementa otro algoritmo de presupuesto ni clasificación.

El productor debe enviar `version=1`, `classification_authority=factory-performance-v1`, `classification=null`, identidad de proyecto, SHA/release, `evidence_ref`, `observed_at` y una lista acotada de observaciones. Cada observación debe coincidir con el proyecto, SHA/release y `evidence_ref` del envelope. Identidades `surface+metric` duplicadas fallan cerrado.

El CLI `scripts/performance-classify.py` es offline y determinista. Lee contrato y envelope desde archivos locales, exige un `--evaluated-at` explícito y escribe JSON a stdout o a `--output`. No usa red, API de GitHub, escrituras en producción, WorkItems, Team Compiler ni remediación.

BRVTAL es el primer productor real. Sus observaciones FCP, LCP y CLS de Home móvil/escritorio se resuelven contra `performance/contracts/brvtal.json`. `dom_content_loaded` y `load_event_end` permanecen fuera de ese contrato y por eso pasan por el mismo detector como `PERF_REVIEW` con evidencia `UNKNOWN`. El adaptador nunca inventa un budget ni acepta clasificación precalculada por el productor.

Este slice termina en clasificación. Factory #304 todavía requiere una regresión material real antes de que el loop pueda crear un WorkItem, despachar remediación profesional, registrar evidencia before/after y adoptar o revertir un baseline nuevo.
