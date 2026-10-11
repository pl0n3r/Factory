# Orquestador único de la fábrica

Factory convierte un épico estructurado en un DAG de Issues ejecutables antes de que dos agentes empiecen a trabajar.

## Contrato del épico

El Issue épico declara un único marker factory-plan con version=1 y una lista tasks.
Cada tarea exige key, title, owner, paths y depends_on.

- key: identificador estable.
- title: una línea.
- owner: login GitHub responsable.
- paths: archivos exactos o prefijos de directorio terminados en /; no acepta glob, traversal ni rutas absolutas.
- depends_on: keys del mismo plan.

Los roles no se escriben a mano: se derivan del clasificador profesional de #2 usando título, tipo del épico y paths.

## /planificar

Un actor OWNER, MEMBER o COLLABORATOR comenta /planificar en el épico.

El workflow valida esquema, límites y DAG; rechaza ciclos; detecta claims de paths solapados; crea o actualiza Issues hijos idempotentes; asigna owner, roles y etiquetas; materializa dependencias como números de Issue; y publica un grafo + tabla de ejecución en un único comentario del bot.

Si dos tareas reclaman rutas solapadas, el plan solo es válido cuando una depende transitivamente de la otra. Una tarea ya activa no puede cambiar su marker y una tarea materializada no puede desaparecer del plan.

## Claims derivados allowlisted

Antes de materializar cada `factory-plan-task`, Factory expande claims deterministas
con contexto del repositorio y vuelve a validar colisiones. La primera regla está
cerrada a `pl0n3r/Condor`: un task que reclama exactamente `datos.yml` reclama
también `tests/php/Privacy/PrivacyAsCodeTest.php` y los documentos canónicos bajo
`docs/privacidad/` (aviso, canal de derechos, política de tratamiento, registro de
tratamientos, retención y términos/condiciones).

La expansión es estable, idempotente y no se aplica a otros repositorios.
`config/version.php` no se deriva de `datos.yml`: debe aparecer explícitamente
cuando una hoja cambie versión. Si una tarea ya activa conserva un marker anterior
con claims menores, el resync falla cerrado; la ampliación requiere el flujo
explícito de renovación del contrato en vez de mutar silenciosamente la lease.

## Enforcement antes de /tomar

Cada Issue hijo lleva un marker factory-plan-task. El coordinador lo lee antes de crear o recuperar una reserva:

- el actor debe coincidir con el owner planificado;
- todas las dependencias deben estar cerradas;
- ninguna otra tarea planificada en estado reservado, revisión o recuperación puede reclamar un path solapado, incluso si pertenece a otro épico.

Los Issues históricos sin marker siguen usando el flujo normal. El validador de PR conserva su detección de colisiones exactas como segunda barrera.

## Garantía verificable

Una tarea planificada no entra a /tomar si una dependencia o claim de archivos la hace incompatible con trabajo activo. El objetivo es prevenir la colisión antes de escribir código, no descubrirla al final del PR.

## Bootstrap de coordinación en consumidores existentes

Cuando un repositorio `pl0n3r/*` existente no puede usar `/tomar` porque todavía no contiene el caller de coordinación, Factory no crea una excepción manual ni escribe en `main`. El owner ejecuta `bootstrap-coordination.yml` desde la rama por defecto con `target_repository`, `target_issue`, `expected_main_sha`, `governance_ref=pl0n3r/factory@v1` e `idempotency_key`.

El workflow reutiliza únicamente `FACTORY_PROVISION_TOKEN`, valida owner, Issue abierto y SHA exacto, y genera una rama `factory/bootstrap-coordination-<issue>` con PR a `main`. El request externo sigue cerrado: no acepta patches, comandos, rutas ni contenido arbitrario.

La preparación del consumidor ocurre en un checkout fijado a `expected_main_sha` con `persist-credentials: false` y **sin** `FACTORY_PROVISION_TOKEN`. Para consumidores con contrato adicional, Factory usa adapters internos allowlisted. El primer adapter es `pl0n3r/GrindFlow`: exige paridad entre `config/version.php`, `package.json` y las dos versiones raíz de `package-lock.json`, calcula solo patch +1 y ejecuta el updater canónico `scripts/readme-dashboard.py --update` antes de serializar la entrega.

El step privilegiado no ejecuta scripts del consumidor. Solo consume el JSON preparado, verifica identidad, SHA del patch, tamaño, ausencia de traversal/symlinks y una allowlist cerrada. Para GrindFlow esa allowlist contiene exactamente seis rutas: `.github/workflows/work-coordination.yml`, `tests/test_factory_coordination_adoption.py`, `config/version.php`, `package.json`, `package-lock.json` y `README.md`. Los consumidores sin adapter continúan con el bootstrap mínimo; si se detecta un contrato estricto conocido por estructura pero no soportado, el proceso falla antes del primer write.

Nunca copia `coordinar_trabajo.py`: el caller consume `pl0n3r/factory/.github/workflows/coordinacion.yml@v1` con perfil `es`.

Un retry con la misma intención converge sobre la misma rama/PR. Si cambian la intención, `main`, el owner, el Issue o aparece un path/symlink fuera de la allowlist, el bootstrap falla cerrado. El merge del PR no sustituye la evidencia del consumidor: después del merge, `/tomar` debe funcionar en el Issue objetivo antes de considerar restaurada la coordinación.

## Incidentes con validación post-merge

La relación normal entre una rama reservada y su Issue sigue siendo `Closes #N`,
`Fixes #N` o `Resolves #N`. Esa es la opción por defecto y permite que GitHub
cierre el trabajo al integrar el PR.

Una excepción cerrada existe **solo para incidentes** que necesitan evidencia
productiva del SHA fusionado antes de poder declararse resueltos. En ese caso el
PR no usa una keyword de cierre y declara exactamente un marker:

```html
<!-- factory-issue-lifecycle {"version":1,"issue":739,"mode":"post_merge_validation"} -->
```

El coordinador acepta el marker únicamente cuando `issue` coincide con el Issue
derivado de la rama reservada y ese Issue tiene `tipo: incidente` o
`type: incident`. JSON inválido, campos extra, markers duplicados, otro número,
un Issue que no sea incidente, una reserva inválida o mezclar el marker con una
keyword de cierre fallan cerrado.

El incidente **permanece abierto** tras el merge hasta que su contrato específico
obtenga la evidencia post-merge requerida, por ejemplo health/smoke exact-main.
Esta relación no relaja reservas, aceptación, colisiones, permisos ni gates y
**no amplía autoridad** para cerrar el incidente o mutar producción.



## Evidencia de archivos exact-HEAD (Factory #1081)

La coordinación distingue entre **claims declarados** (contrato del Issue/lease) y **archivos cambiados** (diff auténtico de un PR). La función pura `verified_changed_file_overlap` modela la segunda distinción, pero no concede ni mueve reservas; requiere SHA completos estables, un conjunto de archivos completo, paths canónicos y UUID identificable de la otra lease.

La puerta de **validación de PR** consulta `GitHub.pull_files_exact_head`, que exige `changed_files` (0–3000), lee todas las páginas de 100 archivos de la API autenticada, incluye origen y destino de `renamed`, rechaza filas/paths ilegibles o duplicados, y revalida HEAD/BASE después de leerlos. `collision_validation_errors` usa esa evidencia y reconfirma los HEAD/BASE de cada PR antes de comparar archivos. Cambios concurrentes o datos incompletos son **errores**, nunca permiso para ignorar una colisión.

**Análisis restringido de `/tomar` (sin concesión por solapamiento):** `reserve_work` compara primero los claims fijados por una reserva V3. Si hay solapamiento con un directorio amplio, puede estudiar como evidencia diagnóstica un candidato cuyos claims sean **archivos exactos**, cuando la otra reserva tiene un PR **abierto en el mismo repositorio**, un diff completo y autenticado, y un HEAD de rama que coincida con la evidencia. Antes de publicar la nueva lease vuelve a leer el contrato, las reservas y los HEAD/BASE; cualquier cambio hace rollback de la rama nueva. Una reserva V1/V2 sin `task_paths`, un PR sin diff verificable o un directorio declarado por el candidato **siguen bloqueados**. Un PR **draft** puede aportar evidencia si su diff autenticado está completo; el draft por sí solo no invalida la lectura. La comprobación previa vuelve a comparar tanto el fingerprint de aceptación como el marker de tarea. **Exclusividad vigente:** incluso con diff disjunto, `/tomar` nunca concede claims solapados mientras el titular amplio pueda editar esos archivos en pushes futuros. Es necesario enforcement de claims durante la lease o merge-train verificable antes de habilitar una excepción.

**Validación provisional en cada push de PR interno:** el job `claims-pr / Validar claims V3 del PR` corre en eventos `opened`, `synchronize`, `reopened` y `edited`, con token de **solo lectura**, y compara todos los archivos del diff paginado exact-HEAD (incluidos ambos nombres de un rename) con los `task_paths` confiables de la reserva V3. Rechaza archivos fuera del alcance, pruebas incompletas, pérdida de la lease y carreras HEAD/BASE. El job no hace checkout ni ejecuta código del PR: usa exclusivamente el runner y la API de GitHub para leer claims y evidencia, con credenciales de solo lectura. Mientras la definición del workflow no esté en `main` como autoridad protegida, **no constituye enforcement independiente de confianza**, pues el autor del PR puede modificar esa definición. Para proteger merges, publicarla desde una base confiable, exigir ese check desde las reglas de rama/repositorio y conservar revisión independiente. Hasta entonces, AC-01 de directorios solapados permanece **FAIL-CLOSED**.

**Archivos compartidos obligatorios:** `config/version.php`, `README.md`, `package-lock.json` y archivos fuente iguales siguen siendo colisiones reales, incluso si los cambios afectan líneas distintas. Para evitar falsas independencias entre Linux y sistemas de archivos insensibles a mayúsculas/normalización, las pruebas de colisión comparan identidades conservadoras Unicode NFC + `casefold` por componente: `src/Cache.php` y `src/cache.php`, o nombres equivalentes con acentos compuestos/descompuestos, se tratan como el mismo archivo; duplicados por alias dentro de un diff fallan cerrado. La comparación conservadora no modifica nombres reales ni autoriza claims solapados. Una excepción por merge-train, bump serializado o rebase de hunks requiere una implementación específica con evidencia atómica en cada integración; no se habilita automáticamente mediante la función pura.

**Comprobación de regresión:** `tests/test_parallel_coordination.py` cubre seis criterios de conflictos y denegación; `tests/test_coordinar_trabajo.py::ExactHeadPullFileEvidenceTests` y `ExactHeadPullCollisionIntegrationTests` ejercitan paginación, el borde de 100 archivos, renombrados, SHA obsoleto y denegación de PR. El `Validar` agregado exact-HEAD y la revisión independiente siguen siendo obligatorios para fusionar esta capacidad.
