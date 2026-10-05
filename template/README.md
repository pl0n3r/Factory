# Proyecto Factory

> Plantilla mínima para consumir `pl0n3r/factory@v1`.

**Rol en la fábrica:** producto consumidor · **Fase:** construction · **Roadmap:** GitHub Issues

## Operational Cockpit

### Estado vivo

- **CI de `main`:** [GitHub Actions](../../actions).
- **Releases:** [GitHub Releases](../../releases).
- **Producción:** añadir una insignia de `/health` únicamente cuando exista un endpoint público real para este proyecto.
- **Detalle operativo:** [Orquestador de ControlBot](https://control.condorapp.com.co/).

El bootstrap del repositorio sustituye estos enlaces por las insignias concretas del workflow/release cuando conoce sus rutas. Si una fuente no existe, se omite: no se rellena con estados sintéticos y no se crean commits periódicos para refrescar el README.

## Work Queue

- **NOW:** enlaza el trabajo activo canónico.
- **NEXT:** enlaza el siguiente trabajo ready.
- **LATER:** enlaza planificación posterior.
- **BLOCKED:** enlaza bloqueos vigentes.

Esta vista resume; no duplica roadmap ni changelog.

## Qué hace el producto

Describe en pocas líneas qué resuelve el producto y sus capacidades permanentes.

## Arquitectura en 60 segundos

```mermaid
flowchart LR
    P[Proyecto consumidor] --> K[pl0n3r/factory@v1]
    K --> C[CI / coordinación / políticas]
```

Factory aporta contratos y automatización reutilizable; el proyecto conserva su producto y su estado.

## Stack e infraestructura

**Stack declarado:** PHP 8.3 + Factory Kit.

Documenta solo runtime, datos, hosting y storage estables. El estado cambiante se consulta en las fuentes vivas.

## Ciclo de entrega

Issue → reserva → branch → PR → Factory CI → review → merge → release → deploy → smoke.

## Calidad y seguridad

`public/health.php` puede comenzar como stub explícito de construcción. Una insignia de producción solo se añade cuando existe un `/health` público que entregue evidencia real. El README no es autoridad de readiness.

## Roadmap y fuentes de verdad

- Roadmap: GitHub Issues.
- Decisiones: `decisiones.yml`.
- Contrato local: `AGENTES.md`.
- Especificaciones: `docs/`.
- Estado vivo: GitHub Actions, GitHub Releases, `/health` público cuando exista y ControlBot.

El README enlaza estas fuentes; no las copia ni calcula progreso.

## Desarrollo local

Usa únicamente comandos reales definidos por el proyecto para install, test, build y análisis estático.

## Mapa de la fábrica

- **Factory:** governance/kit.
- **ControlBot:** control plane privado.
- **FactoryRunner:** execution plane.
- **Condor / GrindFlow / BRVTAL:** productos.
- **AutoFactory:** herramienta local/manual.

Este template es un consumidor de Factory y no altera esas responsabilidades.
