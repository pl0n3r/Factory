---
name: factory-issue-to-merge
description: Lleva un Issue de la fábrica pl0n3r desde la reserva hasta el PR fusionado y el cierre. Úsala cuando el usuario pida tomar, implementar, entregar o fusionar un Issue/PR de Factory, Condor, GrindFlow, brvtal, ControlBot, AutoFactory o FactoryRunner.
---

# Issue → merge

`PLAN-AGENTES.md` manda sobre esta skill; si discrepan, gana el plan. Un solo Issue a la vez hasta merge o condición de parada legítima (sección «Persistencia ante límites»).

## Flujo

1. **Kill switch.** Lee `https://api.github.com/repos/pl0n3r/Factory/issues/767` (el hook SessionStart ya lo informa). Si no es `RUNNING`, responde `PAUSADO: kill switch global no está en RUNNING (<razón>).` y detente. Nunca edites el marker.
2. **Entender.** `gh issue view N -R pl0n3r/<repo> --json state,labels,body,comments`. Estados: `estado: disponible` → reservable; `reservado` con lease ajena vigente → no invadir (siguiente candidato); `bloqueado` → mira causa y condición de desbloqueo. Dependencias: `depends_on` del marker `factory-plan-task` y `blockedBy`; si alguna sigue abierta, trabaja solo la preparación offline permitida o escoge otro Issue.
3. **Preflight exact-main.** Antes de implementar, comprueba contra el SHA actual de `main` que el contrato no esté ya cubierto (`git fetch && git log origin/main -- <paths>`). Si ya está cubierto, no reabras ni tomes: publica la reconciliación con SHA/PR.
4. **Contrato.** En Factory valida el body con `python3 scripts/issue_contract_preflight.py < body.md`. Sin criterios verificables, escríbelos en el Issue.
5. **Reserva.** Comenta `/tomar`, espera el UUID del bot, nunca repitas `/tomar` sobre una reserva activa. Trabaja solo en `trabajo/issue-N` y dentro de las rutas reclamadas. TTL y traspasos: skill `factory-agent-coordination`.
6. **Implementar** en pasos pequeños (≤ ~400 líneas por PR; si más, parte). Reutiliza antes de escribir; imita el estilo del repo.
7. **Probar** localmente con la matriz de `factory-test-matrix`; autorrevisión de la sección 2 del plan (vacíos, concurrencia, secretos, rollback, test que falle si se revierte).
8. **PR** con la plantilla de la sección 5 (Qué y por qué, Rol(es), `Closes #N · Reserva: <UUID>`, criterios con evidencia, riesgo y reversión, fuera de alcance), etiquetas tipo+prioridad+estado y `rol:`.
9. **CI**: una lectura terminal al final; nada de polling. Si falla → `factory-ci-unblock`, sobre el mismo Issue.
10. **Revisión final.** CodeRabbit se solicita UNA vez, solo con PR definitivo y CI totalmente verde (el hook `factory_guard.py` lo impone). Con rate-limit auténtico aplica D-070 de `construccion`; no programes reintentos por cuota.
11. **Merge** squash propio solo si: reserva V3 válida, PR no draft, HEAD reconciliado con `main`, sin conflictos, `Validar` verde en ese HEAD exacto, sin hallazgos high/critical, fase `construccion` (en `live` no hay auto-merge) y sin freeze #921. Jamás `--admin`. Merges de varios PRs: en serie (ver `factory-agent-coordination`).
12. **Cerrar**: verifica que el Issue se cerró con el merge, libera/cierra la reserva, deja lección de 3 líneas si algo costó, y vuelve al despacho.

## Paradas legítimas (cítalas con evidencia y plan de retry)
Dinero/gasto, datos reales, borrado irreversible, deploy/go-live, kill switch, freeze, falta de autoridad, dependencia real abierta, reserva perdida. «CI rojo» o «CodeRabbit rate-limited» solos no lo son.
