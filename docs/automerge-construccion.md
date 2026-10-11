# Simulación de auto-merge en construcción (Factory #1143)

## Estado y autoridad

Este tramo es un **observador dry-run** previo al gobierno (#1144) y a la integración (#1145). El evaluador puro `scripts/automerge_construccion.py` devuelve **candidaturas diagnósticas**, no permisos de merge. Un job verde no aprueba un PR, no desbloquea release y no certifica producción. La fase `live`, Factory@v1 y cualquier go-live conservan sus puertas.

## Frontera de confianza

- Fuente: evidencia de GitHub API autenticada y completa, con repositorio, número de PR, HEAD, base y main exactos; se vuelve a leer antes del informe. Rechazar identidades duplicadas, paginación incompleta, deriva de SHA y registros malformados.
- Gates: checks requeridos con identidad/conclusión/HEAD terminal; aceptación, coordinación, seguridad y review independiente vigente. `COMMENTED`, `DISMISSED`, `CHANGES_REQUESTED`, hilos abiertos y evidencia de historial ambiguo **no** sustituyen `APPROVED`.
- Estado global: leer Factory#767 al comenzar y al terminar la captura, con un único marker válido `RUNNING` y owner autorizado; `PAUSED` o `UNKNOWN` invalida el resultado. Kill switch `RUNNING` no salta límites 4B.
- Seguridad: `freeze` activo, fase `live`, rutas de política/release/seguridad, permisos desconocidos, cuota insuficiente, snapshot parcial y datos vencidos implican `eligible=false` o `UNKNOWN`.
- Los datos de entrada no se consideran confiables por venir de un evento de PR. El observador no ejecuta código del HEAD del PR ni acepta snapshots suministrados por el autor como autoridad.

## Contrato operativo del dry-run

1. Ejecutar solo con evento de PR **no privilegiado**, permisos de lectura mínimos, timeout y concurrencia acotados; nada de `pull_request_target`, `workflow_run`, `issue_comment` o `repository_dispatch` para ejecutar código del PR.
2. Recopilar evidencia completa sin registrar cuerpos de comentarios, tokens, cabeceras de autorización, secretos, correos, contenido de Issues ni datos reales. Fallar cerrado ante 403/429, incertidumbre o presupuestos desconocidos; no reintentar en bucle.
3. Alimentar al evaluador solo si se demuestra identidad exact-SHA y frescura. Un resultado `eligible_diagnostic_only` **jamás** llama a `merge`, `enablePullRequestAutoMerge`, `update-branch` ni escribe en Issues/PRs/checks.
4. Emitir reporte JSON acotado con `repository`, `pr_number`, `head_sha`, `eligible` y `reason` de vocabulario fijo. Ante entrada no verificable, usar `eligible=false`, `reason=incomplete_evidence` sin volcar el payload de la excepción.
5. Volver a validar kill switch e identidades antes de mostrar un diagnóstico positivo. Si alguna lectura falla, emitir únicamente resultado denegado y salir sin side effects.

## Validación y reversión

Los cinco tests `AutoMergeWorkflowTests::test_*` del Issue #1143 deben reproducir casos positivos y negativos **sin red**, incluidos doble evento, SHA cambiado, reviews revocadas, hilos abiertos, permisos excesivos, freeze, quota y payloads corruptos. La evidencia de CI debe ser terminal sobre el HEAD exacto del PR y contar con QA/seguridad independientes antes de integrar.

Para deshacer esta entrega se revierte el PR que agrega el workflow observador, la documentación y sus tests; no existe migración, credencial, regla de protección, auto-merge habilitado ni estado productivo que restaurar. La integración funcional de autofusión pertenece a hojas posteriores con sus propias reservas y puertas.
