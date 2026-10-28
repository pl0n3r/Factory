---
name: factory-ci-unblock
description: Diagnostica y resuelve CI en rojo, checks fallidos o cancelados, conflictos de merge, ramas desactualizadas, dependencias rotas y fallos transitorios en PRs de la fábrica pl0n3r. Úsala cuando un PR no pasa `Validar` o el usuario diga "arregla el CI", "desbloquea el PR" o "conflicto".
---

# Desbloquear CI

Objetivo: dejar el MISMO Issue/PR en verde sobre un HEAD nuevo, sin relajar checks (plan §3 y «CI y revisión»).

1. **Estado.** `gh pr view N --json headRefOid,mergeable,mergeStateStatus,statusCheckRollup` y `gh run list --branch trabajo/issue-N -L 5`. Una lectura terminal, sin polling.
2. **Rama desactualizada/conflicto.** `git fetch origin && git merge origin/main` (o rebase si el repo lo prefiere); resuelve conflictos conservando ambos intents, nunca borres cambios ajenos. En worktrees gestionados por la app usa su sincronización con la base.
3. **Clasifica cada check fallido:** `gh run view <run> --log-failed | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ci_triage.py"` → `transient | conflict | dependency | config | test | unknown`.
   - `transient` (red, 5xx, runner cancelado): UN `gh run rerun --failed`. Si repite el mismo fallo, ya no es transitorio.
   - `dependency`: arregla `composer.lock`/`package-lock.json` con la herramienta del repo; no fijes versiones por encima de lo que el repo ya usa sin motivo.
   - `config`: corrige el workflow/permisos; las acciones de terceros van fijadas a SHA.
   - `test`: reproduce localmente, corrige la **causa**; jamás silencies, saltes ni borres el test (anti-patrón §8).
   - `unknown`: lee el log completo antes de actuar.
4. **Verifica antes de empujar** con la matriz local (`factory-test-matrix`), commit pequeño, push, y una lectura terminal posterior. El éxito se confirma por `Validar` en el HEAD exacto, no por un check viejo.
5. **Reglas de intentos:** máximo 2 del mismo enfoque; al tercero cambia de enfoque dentro del mismo Issue (formato `⛔ BLOQUEADO` solo si cita una condición de parada real). Si un check requerido falta por contrato, no uses `--admin`.
