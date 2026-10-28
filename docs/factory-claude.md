# factory-claude: skills y hooks de Claude Code para la fábrica

Plugin propio, versionado en este repo (`claude/factory-claude/`) y publicado por el marketplace `factory` (`.claude-plugin/marketplace.json`). `PLAN-AGENTES.md` sigue siendo la autoridad; el plugin no crea otro orquestador: usa `/tomar`, `/liberar`, `/transferir`, el orquestador y la coordinación de Factory.

## Contenido

| Skill | Cubre |
| --- | --- |
| `factory-issue-to-merge` | Issue → reserva → PR → CI → revisión → merge → cierre |
| `factory-ci-unblock` | Diagnóstico de CI (`scripts/ci_triage.py`), conflictos, dependencias, transitorios |
| `factory-agent-coordination` | Reservas, TTL, claims, worktrees, tope de 4 agentes, merges en serie |
| `factory-test-matrix` | Detección del stack (`scripts/detect_stack.py`) y matriz de pruebas |
| `factory-deploy-rollback` | Predeploy, migraciones, health/SHA, rollback; sin deploy autónomo |
| `factory-security-audit` | Auth, multiempresa, inyección, XSS/CSRF, secretos, dependencias |
| `factory-cross-repo-contracts` | Contratos Factory/ControlBot/FactoryRunner/AutoFactory y versionado `@vN` |
| `factory-documentation` | README, AGENTES/CLAUDE.md, contratos, decisiones, runbooks |

## Hooks (ejecutables, con tests en `tests/test_factory_claude.py`)

| Hook | Script | Efecto |
| --- | --- | --- |
| SessionStart | `kill_switch.py` | Informa el estado de Factory#767; `UNKNOWN`/`PAUSED` ⇒ aviso `PAUSADO:`. Nunca edita el marker |
| PreToolUse Bash | `factory_guard.py` | Deniega `gh pr merge --admin`, merge sin `Validar` verde (o con estado UNKNOWN), CodeRabbit prematuro o repetido, push directo/forzado a `main` |
| PreToolUse Edit/Write | `reservation_guard.py` | En `trabajo/issue-N` deniega si el Issue está cerrado o sin reserva; avisa en `main` o si no puede verificar |
| PostToolUseFailure | `log_failure.py` | Registra errores en `.claude/factory-claude/errores.jsonl` (idempotente, acotado, sin salida) |

Los hooks ignoran entradas ilegibles y no producen salida salvo para denegar/avisar, así que no bloquean operaciones legítimas ni crean bucles.

## Distribución e instalación

Sin copiar skills a mano: cada repo consumidor declara el marketplace y el plugin en `.claude/settings.json`.

```bash
python3 claude/install_factory_claude.py <ruta-repo>          # perfil por nombre de repo
python3 claude/install_factory_claude.py <ruta-repo> --check  # exit 1 si falta algo (CI/auditoría)
```

Es idempotente y fusiona sin pisar permisos existentes. Actualizar = subir `version` en `plugin.json` y `marketplace.json` (el test exige que coincidan); los consumidores reciben la nueva versión con `/plugin marketplace update factory`.

## Plugins: decisión (verificada en `anthropics/claude-plugins-official`, 2026-10-28)

| Plugin | Alcance | Decisión |
| --- | --- | --- |
| `factory-claude@factory` | los 7 repos (repo) | Propio |
| `superpowers`, `skill-creator`, `context7`, `security-guidance`, `code-simplifier`, `claude-md-management`, `pr-review-toolkit` | globales de usuario (`/plugin install <n>@claude-plugins-official`; superpowers en el marketplace oficial por URL/SHA) | Recomendados |
| `php-lsp` | Condor, ControlBot, GrindFlow | Por repo |
| `laravel-boost` | GrindFlow | Por repo; requiere paquete `laravel/boost` en el proyecto |
| `playwright`, `frontend-design` | brvtal | Por repo |
| `github` | — | Descartado: requiere token PAT en MCP y `gh` ya autenticado cubre el flujo exigido por el plan |
| `serena` | — | Descartado: solapa con LSP, requiere `uv` y consume contexto |

Los plugins globales se instalan por usuario (no se versionan en repos). Claude Code no permite instalarlos desde un script del repo: se hace con `/plugin install` en una sesión.
