---
name: factory-cross-repo-contracts
description: Vigila dependencias y contratos entre repos de la fábrica pl0n3r (Factory, AutoFactory, ControlBot, FactoryRunner, productos) - contratos de API, cambios incompatibles y versionado de `Factory@vN`. Úsala al cambiar un workflow reusable, un endpoint `/ops`, un schema compartido o al planear cambios que afecten a otro repo.
---

# Contratos entre repos

Responsabilidades (plan §0/§7): Factory gobierna el kit y se consume como `@v1`; ControlBot es el control plane (`/ops/staff`, D-060; `openapi/`); FactoryRunner es el execution plane; AutoFactory es herramienta local/manual; Condor, GrindFlow y brvtal son productos.

1. Antes de cambiar, localiza consumidores: `gh search code "pl0n3r/Factory/.github/workflows/<archivo>" --owner pl0n3r` y los contratos en `docs/`, `openapi/`, `config/` y `scripts/` del repo.
2. Clasifica: **aditivo** (campo/input opcional nuevo) vs **incompatible** (renombrar/quitar input, cambiar forma o semántica, endurecer validación). Incompatible ⇒ versión mayor (`vN.M.P`, consumidores en `@vN`) y migración de consumidores en PRs separados, uno por repo.
3. Mover o publicar `Factory@v1` es puerta dura (release #921): nunca lo hagas por iniciativa propia.
4. Verifica con la prueba del contrato (unittest del kit, `openapi/` lint, tests de ControlBot/FactoryRunner). Si no existe una, añade una que falle si el contrato se rompe.
5. Documenta el contrato en el repo dueño (no lo copies a los consumidores); consumidores enlazan.
