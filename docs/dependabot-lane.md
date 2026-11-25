# Carril protegido de Dependabot, Factory #2184


### Reusable propio con `actions: write` (#2222)

GitHub valida los permisos de **todos** los jobs de un reusable al cargarlo, aunque el caller solo ejecute uno. Por eso los jobs que despachan CI exact-main tras el squash (`actions: write`, #2212) viven en `.github/workflows/dependabot.yml`, no en `coordinacion.yml`: así los callers de coordinación (`/tomar`, etiquetas, PR, sweep) mantienen su envelope sin `actions`. Los consumidores cuyo carril ya llama `coordinacion.yml` con `operation: dependabot` siguen funcionando sin dispatch; solo un consumidor allowlisted para dispatch (hoy GrindFlow) debe llamar `pl0n3r/factory/.github/workflows/dependabot.yml@v1` y conceder `actions: write` únicamente en esos dos jobs.

## Comportamiento y límites

Factory sólo activa su llamador en `main` tras CI `CI factory` concluido. El evento `workflow_run` debe ser `pull_request`, `success`, del mismo repositorio, actor Dependabot autenticado, con **un único PR** cuyo HEAD coincida exactamente con el HEAD del run. Un barrido diario (`29 10 * * *` UTC) recupera PRs cuyo payload no contenga asociación PR; el barrido no inventa un HEAD.

El llamador utiliza el reusable `coordinacion.yml` desde el árbol **protegido**, nunca checkout del código del PR con token privilegiado. La operación `dependabot` valida nuevamente identidad, firma, diff, semver, repo, HEAD, estado del interruptor global #767, ausencia de carreras y checks terminales, incluido `Validar` emitido por GitHub Actions. El permiso `contents: write` se limita a los jobs `dependabot` y `dependabot-sweep` del reusable y de cada caller; los demás jobs conservan sus permisos. No se usa `--admin` ni se modifica la protección de ramas.

**Política de merge actual (Factory#2172):** patch/minor de manifiestos o lockfiles, con checks exigidos realmente en verde, se fusiona por `PUT /merge` **squash exact-SHA** usando las protecciones normales de GitHub. No se limita a encender una preferencia de auto-merge diferida. Versiones **major**, cambios a pins de workflows, código de aplicación o PRs estancados siguen el proceso manual con issue de seguimiento idempotente; el workflow no los fusiona. Un run success aislado nunca basta. Las fases `live` deben respetar adicionalmente sus puertas de no auto-merge.

## Caller propio de Factory

El archivo `.github/workflows/dependabot-lane.yml` llama `./.github/workflows/dependabot.yml` para usar el reusable del mismo commit de `main`. El checkout del kit dentro de `dependabot` continúa anclado a `Factory@v1`, no a ramas de Dependabot. El código publicado en `v1` debe conservar la lógica de clasificación segura.

## YAML exacto para consumidores (copiar como `.github/workflows/dependabot-lane.yml`)

Cada ejemplo utiliza el nombre del workflow CI verificable en el propio repositorio. La protección de rama y el gate `Validar` deben seguir habilitados. BRVTAL está en fase `live`: en su ejemplo **ambos jobs están desactivados** (`false` / `if: false`); no activarlos sin autorización humana específica y garantías de esa fase. Los otros consumidores se mantienen en `construccion` según los contratos observados. **No añadir `pull_request_target` ni ejecutar el HEAD del PR con `contents:write`.**

### pl0n3r/BRVTAL

```yaml
name: Dependabot protegido
on:
  workflow_run:
    workflows: ['BRVTAL CI']
    types: [completed]
  schedule:
    - cron: '29 10 * * *'
permissions:
  contents: read
concurrency:
  group: dependabot-${{ github.repository_id }}-${{ github.event_name }}
  cancel-in-progress: false
jobs:
  dependabot:
    # BRVTAL phase=live: D-069 prohibe auto-merge hasta autorizacion independiente.
    if: >-
      false &&
      github.event_name == 'workflow_run' &&
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      github.event.workflow_run.actor.login == 'dependabot[bot]' &&
      github.event.workflow_run.actor.id == 49699333 &&
      github.event.workflow_run.pull_requests[0].number > 0 &&
      github.event.workflow_run.pull_requests[1] == null &&
      github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot
      pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}
      head_sha: ${{ github.event.workflow_run.head_sha }}
  dependabot-sweep:
    # Prohibido reconciliar PRs automaticamente durante fase live.
    if: false
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot-sweep
```

### pl0n3r/GrindFlow

```yaml
name: Dependabot protegido
on:
  workflow_run:
    workflows: ['GrindFlow CI']
    types: [completed]
  schedule:
    - cron: '29 10 * * *'
permissions:
  contents: read
concurrency:
  group: dependabot-${{ github.repository_id }}-${{ github.event_name }}
  cancel-in-progress: false
jobs:
  dependabot:
    if: >-
      github.event_name == 'workflow_run' &&
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      github.event.workflow_run.actor.login == 'dependabot[bot]' &&
      github.event.workflow_run.actor.id == 49699333 &&
      github.event.workflow_run.pull_requests[0].number > 0 &&
      github.event.workflow_run.pull_requests[1] == null &&
      github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot
      pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}
      head_sha: ${{ github.event.workflow_run.head_sha }}
  dependabot-sweep:
    if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot-sweep
```

### pl0n3r/Condor

```yaml
name: Dependabot protegido
on:
  workflow_run:
    workflows: ['CI Condor (V 0.1.0)']
    types: [completed]
  schedule:
    - cron: '29 10 * * *'
permissions:
  contents: read
concurrency:
  group: dependabot-${{ github.repository_id }}-${{ github.event_name }}
  cancel-in-progress: false
jobs:
  dependabot:
    if: >-
      github.event_name == 'workflow_run' &&
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      github.event.workflow_run.actor.login == 'dependabot[bot]' &&
      github.event.workflow_run.actor.id == 49699333 &&
      github.event.workflow_run.pull_requests[0].number > 0 &&
      github.event.workflow_run.pull_requests[1] == null &&
      github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot
      pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}
      head_sha: ${{ github.event.workflow_run.head_sha }}
  dependabot-sweep:
    if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot-sweep
```

### pl0n3r/ControlBot

```yaml
name: Dependabot protegido
on:
  workflow_run:
    workflows: ['CI ControlBot']
    types: [completed]
  schedule:
    - cron: '29 10 * * *'
permissions:
  contents: read
concurrency:
  group: dependabot-${{ github.repository_id }}-${{ github.event_name }}
  cancel-in-progress: false
jobs:
  dependabot:
    if: >-
      github.event_name == 'workflow_run' &&
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      github.event.workflow_run.actor.login == 'dependabot[bot]' &&
      github.event.workflow_run.actor.id == 49699333 &&
      github.event.workflow_run.pull_requests[0].number > 0 &&
      github.event.workflow_run.pull_requests[1] == null &&
      github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot
      pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}
      head_sha: ${{ github.event.workflow_run.head_sha }}
  dependabot-sweep:
    if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot-sweep
```

### pl0n3r/FactoryRunner

```yaml
name: Dependabot protegido
on:
  workflow_run:
    workflows: ['CI']
    types: [completed]
  schedule:
    - cron: '29 10 * * *'
permissions:
  contents: read
concurrency:
  group: dependabot-${{ github.repository_id }}-${{ github.event_name }}
  cancel-in-progress: false
jobs:
  dependabot:
    if: >-
      github.event_name == 'workflow_run' &&
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      github.event.workflow_run.actor.login == 'dependabot[bot]' &&
      github.event.workflow_run.actor.id == 49699333 &&
      github.event.workflow_run.pull_requests[0].number > 0 &&
      github.event.workflow_run.pull_requests[1] == null &&
      github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot
      pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}
      head_sha: ${{ github.event.workflow_run.head_sha }}
  dependabot-sweep:
    if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot-sweep
```

### pl0n3r/AutoFactory

```yaml
name: Dependabot protegido
on:
  workflow_run:
    workflows: ['Validate']
    types: [completed]
  schedule:
    - cron: '29 10 * * *'
permissions:
  contents: read
concurrency:
  group: dependabot-${{ github.repository_id }}-${{ github.event_name }}
  cancel-in-progress: false
jobs:
  dependabot:
    if: >-
      github.event_name == 'workflow_run' &&
      github.event.workflow_run.event == 'pull_request' &&
      github.event.workflow_run.conclusion == 'success' &&
      github.event.workflow_run.head_repository.full_name == github.repository &&
      github.event.workflow_run.actor.login == 'dependabot[bot]' &&
      github.event.workflow_run.actor.id == 49699333 &&
      github.event.workflow_run.pull_requests[0].number > 0 &&
      github.event.workflow_run.pull_requests[1] == null &&
      github.event.workflow_run.pull_requests[0].head.sha == github.event.workflow_run.head_sha
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot
      pr_number: ${{ github.event.workflow_run.pull_requests[0].number }}
      head_sha: ${{ github.event.workflow_run.head_sha }}
  dependabot-sweep:
    if: github.event_name == 'schedule' && github.ref == 'refs/heads/main'
    permissions:
      contents: write
      checks: read
      issues: write
      pull-requests: write
    uses: pl0n3r/factory/.github/workflows/coordinacion.yml@v1
    with:
      operation: dependabot-sweep
```

## Evidencia y activación

La CI de este issue valida permisos, evento, PR/HEAD, cron y copia documental sin red. Tras fusionar el cambio de Factory a `main`, el workflow aparece en Actions, pero la demostración real de un PR **patch/minor de manifiesto** requiere un bot oficial con `Validar` y los checks terminales verdes en su SHA; registrar el enlace del run y del merge si lo hay. El PR `Factory#2107` modifica pins de workflows, por tanto es **manual** y jamás sirve como prueba positiva de auto-merge. No declarar AC-02 observada por una prueba sintética.
