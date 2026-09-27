# {{project.name}}

> {{project.tagline}}

**Rol en la fábrica:** {{project.role}} · **Fase:** {{project.phase}} · **Roadmap:** {{project.roadmap}}

## Operational Cockpit

<!-- factory:status:start -->
| Señal | Estado |
| --- | --- |
| main SHA | UNKNOWN |
| versión | UNKNOWN |
| CI | UNKNOWN |
| release | UNKNOWN |
| health | UNKNOWN |
| smoke/observer | UNKNOWN |
| quality/security | UNKNOWN |
| Issue activo | UNKNOWN |
| PR activo | UNKNOWN |
| último release | UNKNOWN |
<!-- factory:status:end -->

> Este bloque es derivado. UNKNOWN/PENDING significa que falta evidencia canónica; nunca debe sustituirse por GREEN sin evidencia.

## Work Queue

- **NOW:** enlazar el trabajo activo canónico.
- **NEXT:** enlazar el siguiente trabajo ready.
- **LATER:** enlazar la planificación posterior.
- **BLOCKED:** enlazar bloqueos vigentes.

Esta vista resume; no duplica el Roadmap ni actúa como changelog.

## Qué hace el producto

Describe capacidades permanentes y el problema que resuelve. Los detalles efímeros pertenecen al PR, Release o Roadmap.

## Arquitectura en 60 segundos

```mermaid
flowchart LR
    U[Usuario / agente] --> P[{{project.name}}]
    P --> F[Factory contracts]
```

Mantén aquí solo los límites y dependencias que un lector necesita para orientarse.

## Stack e infraestructura

**Stack declarado:** {{project.stack}}

Documenta runtime, backend/frontend cuando apliquen, datos, hosting, observabilidad y storage desde metadata estable.

## Ciclo de entrega

Issue → reserva → branch → PR → Factory CI → review → merge → release → deploy → smoke → GREEN.

## Calidad y seguridad

Enlaza gates, definición de salud, política de secretos, backup, migraciones y rollback. No publiques secretos ni evidencia sensible.

## Roadmap y fuentes de verdad

- Roadmap: {{project.roadmap}}
- Decisiones: `decisiones.yml`
- Contrato local: `AGENTES.md` / `AGENTS.md`
- Especificaciones y documentación profunda: `docs/`

El README enlaza estas fuentes; no las copia.

## Desarrollo local

Documenta únicamente comandos reales y reproducibles de install, test, build, análisis estático y desarrollo.

## Mapa de la fábrica

- **Factory:** governance/kit.
- **ControlBot:** control plane privado.
- **FactoryRunner:** execution plane.
- **Condor / GrindFlow / BRVTAL:** productos.
- **AutoFactory:** herramienta local/manual.

Destaca el repositorio actual sin alterar estas responsabilidades.
