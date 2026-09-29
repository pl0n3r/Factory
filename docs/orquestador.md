# Orquestador único de la fábrica

Factory convierte un épico estructurado en un DAG de Issues ejecutables antes de que dos agentes empiecen a trabajar.

## Contrato del épico

El Issue épico declara un único marker factory-plan con version=1 y una lista tasks.
Cada tarea exige key, title, owner, paths y depends_on.

- key: identificador estable.
- title: una línea.
- owner: login GitHub responsable.
- paths: archivos exactos o prefijos de directorio terminados en /; no acepta glob, traversal ni rutas absolutas.
- depends_on: keys del mismo plan.

Los roles no se escriben a mano: se derivan del clasificador profesional de #2 usando título, tipo del épico y paths.

## /planificar

Un actor OWNER, MEMBER o COLLABORATOR comenta /planificar en el épico.

El workflow valida esquema, límites y DAG; rechaza ciclos; detecta claims de paths solapados; crea o actualiza Issues hijos idempotentes; asigna owner, roles y etiquetas; materializa dependencias como números de Issue; y publica un grafo + tabla de ejecución en un único comentario del bot.

Si dos tareas reclaman rutas solapadas, el plan solo es válido cuando una depende transitivamente de la otra. Una tarea ya activa no puede cambiar su marker y una tarea materializada no puede desaparecer del plan.

## Enforcement antes de /tomar

Cada Issue hijo lleva un marker factory-plan-task. El coordinador lo lee antes de crear o recuperar una reserva:

- el actor debe coincidir con el owner planificado;
- todas las dependencias deben estar cerradas;
- ninguna otra tarea planificada en estado reservado, revisión o recuperación puede reclamar un path solapado, incluso si pertenece a otro épico.

Los Issues históricos sin marker siguen usando el flujo normal. El validador de PR conserva su detección de colisiones exactas como segunda barrera.

## Garantía verificable

Una tarea planificada no entra a /tomar si una dependencia o claim de archivos la hace incompatible con trabajo activo. El objetivo es prevenir la colisión antes de escribir código, no descubrirla al final del PR.

## Bootstrap de coordinación en consumidores existentes

Cuando un repositorio `pl0n3r/*` existente no puede usar `/tomar` porque todavía no contiene el caller de coordinación, Factory no crea una excepción manual ni escribe en `main`. El owner ejecuta `bootstrap-coordination.yml` desde la rama por defecto con `target_repository`, `target_issue`, `expected_main_sha`, `governance_ref=pl0n3r/factory@v1` e `idempotency_key`.

El workflow reutiliza únicamente `FACTORY_PROVISION_TOKEN`, valida owner, Issue abierto y SHA exacto, y genera una rama `factory/bootstrap-coordination-<issue>` con PR a `main`. El patch está limitado a `.github/workflows/work-coordination.yml`, `tests/test_factory_coordination_adoption.py` y, solo cuando sea necesario, `AGENTS.md`. Nunca copia `coordinar_trabajo.py`: el caller consume `pl0n3r/factory/.github/workflows/coordinacion.yml@v1` con perfil `es`.

Un retry con la misma intención converge sobre la misma rama/PR. Si cambian la intención, `main`, el owner, el Issue o aparece un path/symlink fuera de la allowlist, el bootstrap falla cerrado. El merge del PR no sustituye la evidencia del consumidor: después del merge, `/tomar` debe funcionar en el Issue objetivo antes de considerar restaurada la coordinación.
