---
name: factory-documentation
description: Mantiene README, AGENTES.md/CLAUDE.md, arquitectura, contratos, decisiones técnicas, runbooks y procedimientos de la fábrica pl0n3r, actualizando lo existente sin duplicar. Úsala cuando un cambio altere comportamiento, contratos, comandos o procedimientos, o al pedir documentar.
---

# Documentación

1. **Busca primero** (`grep -ril` en `docs/`, README, AGENTES.md/AGENTS.md, `decisiones.yml`): actualiza el documento dueño del tema; nunca crees un segundo.
2. **Qué actualizar según el cambio:** comando o flujo → README/runbook; contrato → doc del contrato + prueba; decisión de arquitectura → `decisiones.yml`/doc de decisión; dato personal o proveedor → `datos.yml` en el mismo PR (Ley 1581); lección costosa → `lecciones/` en 3 líneas (qué pasó, por qué, cómo evitarlo).
3. **CLAUDE.md:** archivo corto que importa `@AGENTES.md` (o `@AGENTS.md`) y enlaza a `PLAN-AGENTES.md`; no repitas reglas del plan, enlázalas. Idioma: español (BRVTAL conserva su convención de etiquetas en inglés).
4. Estilo: resultado primero, tablas en vez de párrafos, rutas y comandos verificados (ejecútalos o cítalos de scripts reales). No documentes lo que no probaste.
5. El PR de documentación pasa los mismos checks; los enlaces relativos deben resolver.
