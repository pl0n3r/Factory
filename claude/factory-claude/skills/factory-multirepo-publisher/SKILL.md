---
name: factory-multirepo-publisher
description: Publica el mismo cambio (docs, skills, configuración) en varios repos de la fábrica pl0n3r con un issue canónico, reserva y PR por repo, respetando las reglas de cada uno. Úsala cuando un cambio deba llegar a Condor, GrindFlow, brvtal, Factory, ControlBot, AutoFactory y FactoryRunner.
---

# Publicador multirepo

Cada repo tiene reglas distintas. Hacerlo a mano o improvisar costó horas el 5-nov-2026 (la reserva falló en los 6 repos por un campo `epic` omitido).

## Flujo por repo (en este orden, una fase a la vez)

1. **issue**: crear con `factory-issue-author` (plantilla canónica, `epic` del roadmap padre). Validar con `aceptacion_kit.parse_contract` y `orquestador_kit.parse_task_marker` de Factory.
2. **take**: comentar `/tomar` (en brvtal `/take`). Una sola vez.
3. **reserva**: esperar el comentario `condor-reserva` con `"active":true` (en brvtal, `brvtal-work-reservation`). La cola de GitHub puede tardar minutos. Si el workflow falló, leer `gh run view <id> --log-failed` y buscar `##[error]`: dice qué sección o campo falla; corregir el cuerpo y volver a comentar el comando.
4. **pr**: worktree desde `origin/main`, rama `trabajo/issue-N` (brvtal `work/issue-N`), commit, push y PR.

## Reglas del PR
- Cuerpo con `Closes #N`, `Rol(es):`, `Rol primario:`, `Revisión cruzada:`, `Reservation: <uuid>` y el marcador `<!-- condor-reserva-id: <uuid> -->` (brvtal: `brvtal-reservation-id`). Termina con la línea de Claude Code.
- Commit termina con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Condor y GrindFlow exigen el sufijo de versión en el título, igual a la versión actual: `(V 0.1.198)` y `(V 0.1.225)`. **No subir la versión** si el PR no es un release.
- brvtal no pide subir versión en PRs que no despliegan (#1400).
- ControlBot limita sus PRs a 400 líneas: no sirve para paquetes grandes.
- Nunca `--admin`. Tras abrir cada PR usa las herramientas de PR de la app; no hagas polling manual de CI.

## Qué evitar
- Publicar skills con scripts, hooks o binarios en los repos.
- Marcar un repo como hecho sin ver su PR abierto y con checks en marcha.
- Reservar archivos que choquen con otro issue abierto.

