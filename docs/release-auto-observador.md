# Observador manual y read-only de release

Hoja Factory #1616, autorizada únicamente como preparación por el OWNER en #1615 (journal v2/A).
**No es un mecanismo de publicación**, ni reemplaza una decisión por SHA de tipo factory-release.

## Ejecución y fuentes

- Workflow `release-auto-observador.yml`, únicamente `workflow_dispatch`, solicitado por OWNER desde `main`.
- Token del job restringido a `contents:read`, `checks:read` e `issues:read`.
- La ejecución consulta el commit protegido de `main`, el ref ligero `v1`, el Issue release elegido, sus comentarios, el kill switch #767, cuota y check-runs del HEAD exacto.
- Se usan exclusivamente `gh api -X GET` sobre rutas predefinidas, nunca una URL aportada por el Issue ni un archivo secreto.
- El reporte JSON muestra solo `state`, motivo y contadores inertes, no bodies, correos, tokens ni payloads de comentarios.

## Confianza y bloqueo explícito

- Los bytes de GitHub llegan al contexto del job; el evaluador Python no verifica firmas criptográficas de origen independiente.
- Se exige repo exacto, branch protegido, checkout SHA idéntico, tag `v1` tipo commit, saldo verificable y kill switch RUNNING.
- La puerta proporcionada debe ser `factory-release`, cerrada y de SHA idéntico; se comprueban voto aislado OWNER y marker del bot, pero el simple marker no es prueba por sí solo de seguridad general.
- Los check-runs deben tener cobertura completa, coincidir con el SHA y carecer de duplicados ambiguos. Un `success` de Actions no acredita hallazgos graves inexistentes.
- Deliberadamente `v1_tag_protected`, `freeze_active` y `security_veto` permanecen UNKNOWN en el preflight: **BLOCKED** hasta que una verificación distinta y autorizada pruebe esas condiciones. Un hipotético `REVIEW_ONLY` tampoco publicaría.
- El observador no escribe comentario, Issue, branch, tag, release o credenciales; no hace pairing, no muta producción y no cambia el estado de go-live.

## Regresión, riesgo y reversión

Suite `python3 -m unittest tests.test_release_auto_observer -v`, con cuatro AC específicos y casos negativos; CI global/aceptación y revisión de seguridad exact-HEAD son independientes.
Revertir el squash deshabilita la herramienta manual. La publicación real conserva su workflow y aprobación exact-SHA separados.
