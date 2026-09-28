# AI Gateway / Model Router — Phase 0

Factory conserva la única cola, readiness, prioridad, reservas y autoridad. El AI Gateway recibe un WorkItem **ya despachado** y resuelve qué executor satisface una `requested_capability`; provider/model nunca forman parte de la prioridad del WorkItem.

```text
Factory WorkItem → Dispatcher V2 → AI Gateway → executor → evidence/cost → Factory feedback
```

Phase 0 no usa APIs pagas ni secretos. Executor manual, API simulada y Codex simulado comparten contrato. La policy aplica provider permitido, costo máximo, clasificación de datos, authority, calidad y seguridad mínimas. Si ningún adapter cumple todo, falla cerrado.

Fallback solo ocurre ante `unavailable` o `rate_limited`, queda registrado en `route_trace` y está limitado por `max_attempts`. Un fallback nunca puede saltarse budget, quality, security, data policy o authority.

Cada éxito registra provider/model/executor, venture/project, costo, evidence refs y un payload compatible con `producto.feedback.validate_execution_feedback`.

Un adapter `codex` exige `governed=true` y workspace igual a `repository_ref`. Así Codex/CLI sigue siendo un adapter gobernado de Factory/FactoryRunner, nunca un canal paralelo `ControlBot → shell/model`.

Phase 1 podrá sustituir adapters simulados por providers reales sin cambiar WorkItem ni feedback; credenciales deberán entrar únicamente por el execution plane autorizado.
