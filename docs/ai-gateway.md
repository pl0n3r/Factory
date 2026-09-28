# AI Gateway / Model Router — Phase 0

## Límite arquitectónico

Factory conserva la única cola, readiness, prioridad, reservas y autoridad. El AI Gateway **no selecciona qué WorkItem va primero**: recibe un WorkItem ya elegible y resuelve qué executor puede satisfacer una capability solicitada.

```text
ControlBot / Venture / Institution
        ↓
Factory WorkItem → Dispatcher V2
        ↓ (WorkItem ya seleccionado)
AI Gateway → executor/provider/model
        ↓
evidence + cost + execution feedback
        ↓
Factory feedback → ControlBot
```

Provider/model/executor son metadata de ejecución. El WorkItem sigue declarando `requested_capabilities`, no nombres de modelos.

## Phase 0

La primera fase es deliberadamente local y sin APIs pagas:

- executor manual (humano + ChatGPT web) y adapters API simulados comparten el mismo contrato;
- policy evalúa capability, costo máximo, clasificación de datos, authority, calidad y seguridad mínimas;
- los adapters no reciben secretos desde WorkItems;
- unavailable/rate-limit pueden producir fallback solo si el siguiente adapter sigue cumpliendo todos los mínimos;
- `max_attempts` limita intentos y evita loops;
- cada resultado conserva provider/model/executor, venture/project, costo estimado/real, ruta de fallback y evidence refs;
- el feedback emitido usa el contrato existente de `producto.feedback.validate_execution_feedback`.

## Selección determinista

Entre adapters elegibles se prioriza menor costo estimado, menor latencia, mayor calidad, mayor seguridad y finalmente identificadores estables. La política puede excluir providers completos. Si ningún adapter cumple todos los gates, el router falla cerrado.

Esta selección **no es una prioridad de trabajo**; solo decide cómo ejecutar el WorkItem que Factory ya seleccionó.

## Seguridad y autoridad

- WorkItem, policy y adapter rechazan campos con forma de secretos.
- Un adapter debe soportar explícitamente el `authority_level` del WorkItem.
- La clasificación de datos requerida nunca puede superar la admitida por el adapter.
- Budget, calidad y seguridad son mínimos duros.
- Un adapter `codex` requiere `governed_by_factory=true` y `workspace_ref` igual al repositorio del WorkItem.
- Elegir un modelo más capaz nunca amplía authority.

## Fallback

Fallback solo aplica a fallos transitorios declarados (`unavailable`, `rate_limited`) y cuando el adapter permite fallback. Errores no transitorios fallan cerrado. Todos los intentos quedan en `route_trace`.

## Evolución

Phase 1 podrá reemplazar un adapter simulado por un provider API real sin cambiar el WorkItem ni el contrato de evidencia. Las credenciales deberán vivir fuera del repositorio/WorkItem y entrar únicamente mediante el execution plane autorizado.

Codex/CLI y futuros coding agents pertenecen a FactoryRunner como adapters de ejecución gobernados; nunca crean un canal `ControlBot → shell/model` paralelo a Factory.
