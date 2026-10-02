# Archivo histórico de PLAN-AGENTES — TANDAS 1 y 2

> **ARCHIVADO · ya cumplido · no aplicar.**
>
> Este documento conserva el texto histórico que guio TANDA 1 y TANDA 2.
> No es backlog vigente ni autoriza reabrir Issues, PRs o tareas aquí citadas.
> Para el estado actual usa `ESTADO.md`, la sección 6 de `PLAN-AGENTES.md`
> y la evidencia canónica de GitHub/health/smoke.

## TANDA 1

### Condor: producción en verde
- Crítico: PR #205 (backup previo por PDO, Closes #200) destraba las migraciones de D-054 que dejaron `/`, `/health`, `/marcela-arias-tienda` y el centro de control en 500. Termínalo e intégralo; no abras otro frente sobre el backup.
- Tras el deploy, verifica los 5 puntos de VERDE, incluyendo `/marcela-arias-tienda` y el centro de control.
- Al terminar: comenta "🟢 PRODUCCIÓN EN VERDE" en Condor#1 con la evidencia de los 5 puntos y detente.

### GrindFlow: producción en verde
- Crítico: el Production Smoke (#121, #73). El usuario sintético ya se aprovisiona (#130, #132); termina el PR #133 (bootstrap OIDC) o el arreglo que falte hasta que el smoke pase. Si falta una variable en el `.env` de producción, documéntala en el PR y en #121.
- Al terminar: comenta "🟢 PRODUCCIÓN EN VERDE" en GrindFlow#2 con la evidencia y detente.

### BRVTAL: production green (English)
- Production health is already OK; confirm the 5 GREEN points. The authenticated production smoke currently shows *skipped*: make it actually run and pass.
- Finish #623 / PR #626 (slow DISCADMIN) if still open: release the PHP session lock on read-only requests, one shared `/auth`, memoized `information_schema` checks, paginated listings; record before/after dashboard timing.
- When done: comment "🟢 PRODUCTION GREEN" on brvtal#533 with the evidence and stop.

### factory: construir el kit
- Orden: #14 arranque → #1 kit v1 completo (ci, deploy con rollback, release, observar, coordinación, etiquetas es/en, política con `decisiones.yml` y tope de 3 rondas) → #2 roles → #3 orquestador → #4 especificaciones ejecutables → #5 evaluación de agentes → #7 costos → #8 memoria (`lecciones/`) → #9 puertas humanas → #6, #10, #11, #12 → `template/`.
- **Extrae de lo que ya funciona en pl0n3r/Condor** en vez de inventar. Todo configurable por inputs: stack (Symfony, Laravel, PHP plano), dominio, fuente de versión, idioma de etiquetas y fase `construccion|live`.
- Acciones fijadas a SHA, mínimo privilegio, `concurrency` y filtros `if:`.
- Mantén el README al día: la tabla "Estado actual" refleja lo que ya existe.
- Publica `v1.0.0` cuando #1 a #14 estén cerrados y el template pase su propio CI.
- **Paralelismo en factory:** no hay un cupo fijo de “segundo agente”. El trabajo no planificado conserva una sola línea activa; las tareas materializadas por el orquestador pueden coexistir únicamente con dependencias satisfechas y claims de paths disjuntos, y cada agente debe reevaluar el DAG si pierde una carrera de reserva.
- Al terminar: comenta la guía de adopción del kit v1.0.0 en Condor#192, GrindFlow#129 y brvtal#630, y detente.

---

## TANDA 2: adoptar el kit (Condor, GrindFlow, BRVTAL y FactoryRunner)

Guía: el comentario de adopción en tu épico (Condor#192, GrindFlow#129, brvtal#630 y **FactoryRunner#1**).

**FactoryRunner** adopta Factory v1 desde su primer PR funcional: Node.js 24/TypeScript, CI `stack: node`, coordinación, etiquetas, aceptación, roles, política, privacidad y release. ControlBot y AutoFactory también permanecen elegibles para la cola automática, aunque no formen parte del gate histórico de adopción de estos cuatro productos.

1. Reemplaza CI, coordinación, etiquetas, release, observador/smoke y deploy locales por reusable workflows del kit (`uses: pl0n3r/factory/...@v1`) cuando la superficie exista. Elimina copias locales divergentes.
2. Crea `decisiones.yml` con la lista de la sección 7.
3. Adopta el núcleo común de AGENTES.md del kit y conserva solo la capa propia del proyecto.
4. En Condor, GrindFlow y BRVTAL activa deploy con rollback, merge queue/auto-merge, métricas y monitoreo. En FactoryRunner activa CI Node, coordinación, release, métricas y health del runner; no inventes deploy de browser/runtime hasta que exista un target ejecutable.
5. Cierra como resueltos por el kit: Condor #188 y #190; GrindFlow #123, #124 y #125; brvtal #624, #625 y #627; FactoryRunner #1 cuando su bootstrap y CI exacto estén integrados.
6. Valida con un PR de prueba que pase el CI del kit y se integre. Condor, GrindFlow y BRVTAL deben terminar en producción validada o rollback automático. FactoryRunner debe terminar con CI Node exact-main, tests/build reproducibles, release versionada y cero incidentes; cuando tenga runtime desplegado, añade health/smoke exactos.

Los cuatro productos solo terminan su adopción con evidencia publicada en su Roadmap/Issue canónico.

---
