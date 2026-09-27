# Proyecto Factory

> Plantilla mínima para consumir `pl0n3r/factory@v1`.

**Rol en la fábrica:** producto consumidor · **Fase:** construction · **Roadmap:** GitHub Issues

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

> Este bloque es derivado. `UNKNOWN`/`PENDING` significa que falta evidencia canónica; nunca se promueve a `GREEN` sin evidencia.

## Work Queue

- **NOW:** enlaza el trabajo activo canónico.
- **NEXT:** enlaza el siguiente trabajo `ready`.
- **LATER:** enlaza planificación posterior.
- **BLOCKED:** enlaza bloqueos vigentes.

Esta vista resume. No duplica roadmap ni changelog.

## Qué hace el producto

Esta plantilla crea un proyecto consumidor del Factory Kit con CI, coordinación, etiquetas, política y release. Deploy y observación se habilitan cuando el proyecto configura su entorno.

## Arquitectura en 60 segundos

```mermaid
flowchart LR
    P[Proyecto consumidor] --> K[pl0n3r/factory@v1]
    K --> C[CI / coordinación / políticas]
```

El proyecto conserva su producto y estado; Factory aporta contratos y automatización reutilizable.

## Stack e infraestructura

**Stack declarado:** PHP 8.3 + Factory Kit.

El deploy usa adapters ejecutables fijos en `ops/factory/{build,backup,migrate,deploy,rollback}`.

## Ciclo de entrega

Issue → reserva → branch → PR → Factory CI → review → merge → release → deploy → smoke → GREEN.

## Calidad y seguridad

`public/health.php` nace como stub explícito de construcción: no inventa SHA ni estado de esquema y expone `evidence=construction-stub`. En fase `live` exige un `RELEASE_SHA` real; `schema_up_to_date` solo refleja `SCHEMA_UP_TO_DATE` cuando el proyecto decide reportarlo.

El README Contract se valida en modo read-only y falla cerrado ante drift o metadata inválida.

## Roadmap y fuentes de verdad

- Roadmap: GitHub Issues.
- Decisiones: `decisiones.yml`.
- Contrato local: `AGENTES.md`.
- Especificaciones profundas: `docs/`.
- Factory Kit: `pl0n3r/factory@v1`.

El README enlaza estas fuentes; no las copia.

## Desarrollo local

Usa únicamente los comandos reales definidos por el proyecto para install, test, build y análisis estático.

## Mapa de la fábrica

- **Factory:** governance/kit.
- **ControlBot:** control plane privado.
- **FactoryRunner:** execution plane.
- **Condor / GrindFlow / BRVTAL:** productos.
- **AutoFactory:** herramienta local/manual.

Este template es un consumidor de Factory y no altera esas responsabilidades.
