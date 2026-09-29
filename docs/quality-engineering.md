# Quality Engineering E2E

#348 cierra el core local de Quality Engineering componiendo, sin motor nuevo, los contratos #343–#347:

```text
Quality Contract
→ Project DNA (source_ref + fingerprint)
→ Risk/DoD
→ gate evidence + Regression Intelligence
→ Performance #304 + Recovery #305
→ Quality Health
→ Readiness #293
→ clase correctiva
→ WorkItem v1 + Factory Queue #269 / Dispatcher V2
```

## Happy path

El escenario sano define un Quality Contract por superficie, lo adjunta a Project DNA por referencia y fingerprint, y usa esa misma evidencia autenticada para compilar Risk/DoD. Los gates exigidos por DoD se presentan como evidencia current y una regresión ya verificada no degrada el resultado.

Performance #304 y Recovery #305 se consumen como dimensiones externas. Quality Health las integra **sin recalcular** sus algoritmos. Con toda la evidencia current el estado es `PASS` y Readiness #293 reutiliza exactamente ese estado con `recalculated=false`.

## Fallo crítico y trabajo correctivo

Un gate requerido que falla sobre una superficie `critical` produce `BLOCKED`. El estado conserva la clase `quality_gate_failed`; el E2E demuestra que esa clase puede materializarse mediante WorkItem v1 y entrar al Dispatcher V2 existente.

No existe segunda cola. Factory Queue #269 sigue siendo la única semántica de readiness/dispatch para el trabajo correctivo.

## Evidencia incompleta o inestable

- evidencia stale o UNKNOWN → Quality Health `UNKNOWN` → no ready;
- regresión FLAKY → nunca `PASS`; permanece degradación explícita;
- un blocker crítico nunca se diluye con gates menores verdes.

Todo artefacto Quality conserva `authority=unchanged`, `execute_actions=false` y `parallel_queue=false`.

## Límites

Este E2E opera con fixtures deterministas y APIs puras del repositorio. Funciona **sin scheduler**, **sin backlog**, sin Quality Engine paralelo, sin red, sin producción, sin creación automática de Issues/PRs/WorkItems y sin ejecutar remediaciones.

Performance #304 y Recovery #305 mantienen sus contratos y autoridad propios; Quality solo consume sus proyecciones. Readiness #293 y Factory Queue #269 tampoco se reimplementan ni reciben una fórmula competidora.

El rollout a Condor, GrindFlow, BRVTAL, ControlBot, AutoFactory y FactoryRunner requiere evidencia propia por proyecto y no forma parte de #348.
