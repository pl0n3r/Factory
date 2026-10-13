# Diagnóstico de auto-merge en construcción (Factory #1143 y #1295)

## Estado y autoridad

Este tramo es un **observador dry-run** previo al gobierno (#1144) y a la integración (#1145). El evaluador puro `scripts/automerge_construccion.py` devuelve **candidaturas diagnósticas**, no permisos de merge. Factory #1295 reduce las señales de calidad que bloquearían un merge durante `construccion` sin autorizar cambios a `main`, al workflow real de CI ni al canal de publicación. La fase `live`, Factory@v1 y cualquier go-live conservan sus puertas.

## Frontera de confianza

- Fuente: evidencia de GitHub API autenticada y completa, con repositorio, número de PR, HEAD, base y main exactos; se vuelve a leer antes del informe. Rechazar identidades duplicadas, paginación incompleta, deriva de SHA y registros malformados.
- Gates en `construccion`: el check de CI `validate`/`Validar` debe estar terminal `success`, con HEAD exacto; la evidencia de seguridad y las puertas duras siguen obligatorias. Aceptación, coordinación, claims V3 de *informe* (no la autoridad de reserva), rondas CodeRabbit/Policy, `CHANGES_REQUESTED` no grave e hilos no graves pasan a informativos. No se exige `APPROVED` independiente. Los hallazgos graves —bugs o vulnerabilidades `high`/`critical` en código nuevo de SonarCloud, CodeQL o CodeRabbit— bloquean; hallazgos menores se documentan como deuda.
- Estado global: leer Factory#767 al comenzar y al terminar la captura, con un único marker válido `RUNNING` y owner autorizado; `PAUSED` o `UNKNOWN` invalida el resultado. Kill switch `RUNNING` no salta límites 4B.
- Seguridad: el `freeze` activo, el kill switch distinto de RUNNING, permisos, reservas V3 de escritura inválidas, branch protection, gasto, datos reales, deploy, release, mover `v1`, borrado destructivo y go-live deniegan. Las rutas sensibles siguen en revisión protectora del diagnóstico; cuota insuficiente, fuente de calidad incompleta o desfasada, snapshot parcial o datos vencidos implican `eligible=false` o `UNKNOWN`. Ningún aviso bajo de Sonar permite neutralizar un finding grave.
- Los datos de entrada no se consideran confiables por venir de un evento de PR. El observador no ejecuta código del HEAD del PR ni acepta snapshots suministrados por el autor como autoridad.

## Contrato operativo del dry-run

1. Ejecutar solo con evento de PR **no privilegiado**, permisos de lectura mínimos, timeout y concurrencia acotados; nada de `pull_request_target`, `workflow_run`, `issue_comment` o `repository_dispatch` para ejecutar código del PR.
2. Recopilar evidencia completa sin registrar cuerpos de comentarios, tokens, cabeceras de autorización, secretos, correos, contenido de Issues ni datos reales. Fallar cerrado ante 403/429, incertidumbre o presupuestos desconocidos; no reintentar en bucle.
3. Alimentar al evaluador solo si se demuestra identidad exact-SHA y frescura. Un resultado `eligible_diagnostic_only` **jamás** llama a `merge`, `enablePullRequestAutoMerge`, `update-branch` ni escribe en Issues/PRs/checks.
4. Emitir reporte JSON acotado con `repository`, `pr_number`, `head_sha`, `eligible` y `reason` de vocabulario fijo. Ante entrada no verificable, usar `eligible=false`, `reason=incomplete_evidence` sin volcar el payload de la excepción.
5. Volver a validar kill switch e identidades antes de mostrar un diagnóstico positivo. Si alguna lectura falla, emitir únicamente resultado denegado y salir sin side effects.

## Validación y reversión

Los cinco tests `AutoMergeWorkflowTests::test_*` del Issue #1143 deben reproducir casos positivos y negativos **sin red**, incluidos doble evento, SHA cambiado, reviews revocadas, hilos abiertos, permisos excesivos, freeze, quota y payloads corruptos. La evidencia de CI debe ser terminal sobre el HEAD exacto del PR y registrar los roles QA/seguridad. Un revisor independiente `APPROVED` no es requisito general en construcción; findings graves sí son veto.

Para deshacer esta entrega se revierte el PR que agrega el workflow observador, la documentación y sus tests; no existe migración, credencial, regla de protección, auto-merge habilitado ni estado productivo que restaurar. La integración funcional de autofusión pertenece a hojas posteriores con sus propias reservas y puertas.

## Rollout operativo pendiente y deuda antes del go-live

**Diagnóstico no es enforcement.** Los workflows existentes `.github/workflows/factory-ci.yml` y `.github/workflows/politica.yml`, la protección de rama que exige `Validar`, y los callers consumidores no se modifican en #1295. Si el actual `Validar` agregado depende de aceptación/coordinación, un fallo sigue bloqueando la fusión real hasta que un cambio autorizado y probado reconcilie el CI con la nueva política. No usar `--admin`, checks viejos, otro contexto ni re-etiquetado para saltarlo.

La evidencia de severidad debe ser completa, autenticada, exact-HEAD y cubrir SonarCloud, CodeQL y CodeRabbit. Si falta, está rate-limited, incompleta o tiene tipos inválidos, el diagnóstico falla cerrado; no se puede traducir silencio en «cero hallazgos». Las revisiones informativas y observaciones menores se anotan en el PR o backlog de deuda técnica, sin crear un Issue por cada sugerencia.

**Deuda pre-live obligatoria:** antes de cualquier decisión de go-live, revisar y limpiar la deuda pendiente de Sonar y CodeRabbit y volver a ejecutar todos los gates de la fase `live`; no hay auto-merge en live. Se conserva siempre la decisión humana de despliegue/release, el freeze exact-SHA, dinero, datos reales y borrado irreversible.
