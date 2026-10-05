# {{project.name}}

> {{project.tagline}}

**Rol en la fábrica:** {{project.role}} · **Fase:** {{project.phase}} · **Roadmap:** {{project.roadmap}}

## Operational Cockpit

### Estado vivo

[![CI main](https://img.shields.io/github/actions/workflow/status/pl0n3r/{{project.name}}/{{live.ci_workflow}}?branch=main&label=CI%20main)](https://github.com/pl0n3r/{{project.name}}/actions)
[![Release](https://img.shields.io/github/v/release/pl0n3r/{{project.name}}?display_name=tag&label=release)](https://github.com/pl0n3r/{{project.name}}/releases/latest)

- **Producción:** si el proyecto expone un `/health` público, su migración v2 añade una insignia dinámica que consulta ese endpoint. Si no existe una fuente pública real, la señal se omite.
- **Detalle operativo:** [Orquestador de ControlBot](https://control.condorapp.com.co/).

Las insignias se actualizan desde sus fuentes al consultar el README. No hay commits periódicos de refresco y la ausencia de una señal no se convierte en progreso, readiness ni estado sintético.

## Work Queue

- **NOW:** enlazar el trabajo activo canónico.
- **NEXT:** enlazar el siguiente trabajo ready.
- **LATER:** enlazar la planificación posterior.
- **BLOCKED:** enlazar bloqueos vigentes.

Esta vista resume; no duplica el Roadmap ni actúa como changelog.

## Qué hace el producto

Describe en pocas líneas las capacidades permanentes y el problema que resuelve. El detalle efímero pertenece a Issues, PRs, Releases o al Orquestador.

## Arquitectura en 60 segundos

```mermaid
flowchart LR
    U[Usuario / agente] --> P[{{project.name}}]
    P --> F[Factory contracts]
```

Mantén solo los límites y dependencias necesarios para orientarse.

## Stack e infraestructura

**Stack declarado:** {{project.stack}}

Resume runtime, datos, hosting y storage estables. El estado operativo vivo pertenece a sus fuentes.

## Ciclo de entrega

Issue → reserva → branch → PR → Factory CI → review → merge → release → deploy → smoke.

## Calidad y seguridad

Enlaza gates, política de secretos, backup, migraciones y rollback. No publiques secretos ni conviertas ausencia de evidencia en una afirmación de salud.

## Roadmap y fuentes de verdad

- Roadmap: {{project.roadmap}}
- Decisiones: `decisiones.yml`
- Contrato local: `AGENTES.md` / `AGENTS.md`
- Especificaciones: `docs/`
- Estado vivo: GitHub Actions, GitHub Releases, `/health` público cuando exista y ControlBot.

El README enlaza estas fuentes; no las copia ni calcula progreso.

## Desarrollo local

Documenta solo comandos reales y reproducibles de install, test, build, análisis estático y desarrollo.

## Mapa de la fábrica

- **Factory:** governance/kit.
- **ControlBot:** control plane privado.
- **FactoryRunner:** execution plane.
- **Condor / GrindFlow / BRVTAL:** productos.
- **AutoFactory:** herramienta local/manual.

Destaca el repositorio actual sin alterar estas responsabilidades.
