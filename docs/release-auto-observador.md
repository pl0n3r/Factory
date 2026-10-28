# Observador manual y read-only de release

Hoja Factory #1616, autorizada únicamente como preparación por el OWNER en #1615 (journal v2/A).
**No es un mecanismo de publicación**, ni reemplaza una decisión por SHA de tipo factory-release.

## Ejecución y fuentes

- Workflow `release-auto-observador.yml`, únicamente `workflow_dispatch`, solicitado por OWNER desde `main`.
- Token del job restringido a `contents:read`, `checks:read` e `issues:read`.
- La ejecución comprueba el actor original y el iniciador de reejecuciones (`github.actor` y `github.triggering_actor`), así como el ref completo `refs/heads/main` antes del checkout. Consulta el commit protegido de `main`, el ref ligero `v1`, el Issue release elegido, sus comentarios, el kill switch #767, cuota y check-runs del HEAD exacto.
- Se usan exclusivamente `gh api -X GET` sobre rutas predefinidas, nunca una URL aportada por el Issue ni un archivo secreto.
- El reporte JSON contiene `state`, `reason`, `repository`, `authorizes_release`, `mutations` y `tag_writes`. `authorizes_release=false` y las mutaciones/escrituras son siempre cero; no incluye bodies, correos, tokens ni payloads de comentarios.

## Confianza y bloqueo explícito

- Los bytes de GitHub llegan al contexto del job; el evaluador Python no verifica firmas criptográficas de origen independiente.
- Se exige repo exacto, branch protegido, checkout SHA idéntico, tag `v1` tipo commit, saldo verificable y kill switch RUNNING.
- La puerta proporcionada debe ser `factory-release`, cerrada y de SHA idéntico; se comprueban voto aislado OWNER y marker del bot, pero el simple marker no es prueba por sí solo de seguridad general.
- Los check-runs deben tener cobertura completa, ID positivo no repetido, nombre **exacto** (`Validar`, `SonarCloud Code Analysis`, `CodeQL`), SHA exacto y GitHub App esperada (slug + ID numérico: GitHub Actions `15368`, SonarQube Cloud `12526`, GitHub Advanced Security `57789`). `CodeQL Actions SARIF` no reemplaza a `CodeQL`. Los reruns con ID distinto se contrastan por ID máximo. Si cambia la identidad de una App, bloquear hasta volver a verificarla con fuente autenticada. Un `success` de Actions no acredita ausencia de hallazgos graves.
- Deliberadamente `v1_tag_protected`, `freeze_active` y `security_veto` permanecen UNKNOWN en el preflight: **BLOCKED** hasta que una verificación distinta y autorizada pruebe esas condiciones. Un hipotético `REVIEW_ONLY` tampoco publicaría.
- El observador no escribe comentario, Issue, branch, tag, release o credenciales; no hace pairing, no muta producción y no cambia el estado de go-live.

## Regresión, riesgo y reversión

Suite `python3 -m unittest tests.test_release_auto_observer -v`, con cuatro AC específicos y casos negativos; CI global/aceptación y revisión de seguridad exact-HEAD son independientes.
Revertir el squash deshabilita la herramienta manual. La publicación real conserva su workflow y aprobación exact-SHA separados.
