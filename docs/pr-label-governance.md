# Gobernanza del check `Etiquetas`

Factory#795 separa dos responsabilidades: los agentes reparan la clasificación segura de PRs y detectan merges que escaparon al gate; **solo el dueño** administra rulesets/protección de ramas.

## Auditoría read-only · 2026-10-02

La evidencia se obtuvo con la API autenticada de GitHub. `UNKNOWN` es intencional cuando branch protection devolvió `403 Resource not accessible by integration`; ausencia de un ruleset visible no se interpreta como ausencia de protección.

| Repo | Ruleset visible | Checks visibles | Branch protection | Resultado |
| --- | --- | --- | --- | --- |
| Factory | `factory-v1-trust-root` (`tag`, no `main`) | ninguno para `main` | UNKNOWN (403) | **UNKNOWN** |
| Condor | `Protección main (V 0.1.0)` | `Validar`, `SonarCloud Code Analysis` | UNKNOWN (403) | **UNKNOWN** |
| GrindFlow | `main-required-checks` | `Etiquetas`, `validate`, Factory policy, SonarCloud | no necesaria para demostrar el gate | **REQUIRED** |
| brvtal | sin rulesets visibles | — | UNKNOWN (403) | **UNKNOWN** |
| ControlBot | sin rulesets visibles | — | UNKNOWN (403) | **UNKNOWN** |
| AutoFactory | sin rulesets visibles | — | UNKNOWN (403) | **UNKNOWN** |
| FactoryRunner | sin rulesets visibles | — | UNKNOWN (403) | **UNKNOWN** |

Caso que motivó el guard: FactoryRunner PR #82 se fusionó en `2fd240f570c41e21f8089bcc0862c363695c11bb` con `validar-pr / Labels = failure` y sin éxito posterior sobre ese HEAD.

## Ruleset uniforme owner-only

El payload canónico crea un ruleset dedicado que **solo añade** `Etiquetas` como required status check sobre la rama por defecto. No reemplaza ni relaja checks existentes de otros rulesets ni activa sincronización strict de rama.

```bash
python3 scripts/pr_label_governance.py ruleset-payload > /tmp/factory-required-labels.json
cat /tmp/factory-required-labels.json
```

El JSON emitido fija:

- `name = factory-required-labels`;
- `target = branch`, `enforcement = active`;
- `ref_name.include = ["~DEFAULT_BRANCH"]`;
- check `Etiquetas` del GitHub Actions App (`integration_id=15368`);
- `strict_required_status_checks_policy = false` y ningún bypass actor.

Aplicación administrativa, **solo por el dueño** y después de revisar el payload:

```bash
gh api --method POST repos/pl0n3r/Factory/rulesets --input /tmp/factory-required-labels.json
gh api --method POST repos/pl0n3r/Condor/rulesets --input /tmp/factory-required-labels.json
# GrindFlow ya acredita Etiquetas como required; no necesita un segundo ruleset mientras siga así.
gh api --method POST repos/pl0n3r/brvtal/rulesets --input /tmp/factory-required-labels.json
gh api --method POST repos/pl0n3r/ControlBot/rulesets --input /tmp/factory-required-labels.json
gh api --method POST repos/pl0n3r/AutoFactory/rulesets --input /tmp/factory-required-labels.json
gh api --method POST repos/pl0n3r/FactoryRunner/rulesets --input /tmp/factory-required-labels.json
```

`scripts/pr_label_governance.py owner-commands` emite esa misma lista de seis repos faltantes más el comando para generar el payload; GrindFlow queda excluido por defecto. Los agentes **no ejecutan** esos comandos. Si GitHub responde que ya existe una regla equivalente, se relee la configuración antes de cualquier cambio; nunca se reemplaza a ciegas.

## Reparación segura de etiquetas del PR

El workflow `Etiquetas` conserva el envelope histórico de mínimo privilegio (`contents: read`, `issues: write`, `pull-requests: read`). Aplicar etiquetas a un PR usa el endpoint de Issues y no requiere `pull-requests: write`. Como los siete repos de la fábrica son públicos, el sweep consulta `check-runs` por REST público sin token, valida el SHA antes de construir la URL y mantiene el barrido acotado a 25 PRs; así no añade `checks: read` al token reusable. El plan de `labels_kit.py` conserva la regla existente:

1. un PR sin estado recibe `estado: en revisión`;
2. si contiene una única referencia `Closes/Fixes/Resolves #N`, tipo y prioridad faltantes se heredan del Issue servidor-side;
3. etiquetas ambiguas o incompletas fallan cerrado;
4. no se escriben contenidos, checks, Actions ni secretos.

## Alerta de merge con `Etiquetas` no verde

Durante el sweep programado se revisan hasta 25 PRs fusionados recientes. Para cada HEAD se inspecciona el check de etiquetas (`Etiquetas`, `Labels` o `*/ Labels`). Si el último check terminal no es `success`, el workflow publica **un solo comentario** en el PR con marker `factory-pr-label-governance-alert` y evidencia de HEAD/check. Runs posteriores ven el marker y no duplican la alerta.

La alerta no revierte merges, no administra rulesets y no convierte un `skipped` o una lectura ausente en verde.
