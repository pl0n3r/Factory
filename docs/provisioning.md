# Provisión gobernada de repositorios

Factory expone `.github/workflows/provision-project.yml` como la **única ruta soportada** para materializar un repositorio de Proyecto aprobado. `scripts/provision_project.py` es una implementación interna del workflow: ejecutarlo directamente no aplica las comprobaciones de `github.actor`, evento ni rama.

- El destino permitido es `pl0n3r/<repo>`; tanto un repo nuevo como uno adoptado deben ser **privados**.
- La autoridad externa es exclusivamente `FACTORY_PROVISION_TOKEN`; el `GITHUB_TOKEN` del workflow conserva `contents: read`.
- La credencial debe pertenecer a `pl0n3r` y limitarse a las capacidades necesarias para crear un repositorio privado y empujar su commit inicial. Factory valida la identidad autenticada antes de la primera escritura.
- Si la credencial falta, el workflow falla antes del checkout y antes de cualquier escritura remota. Su valor nunca se pega en Issues, chats, URLs remotas ni logs.
- El runtime se descarga desde el SHA exacto que disparó el workflow; la gobernanza se descarga por separado desde `Factory@v1`. El SHA exacto resuelto de esa gobernanza queda registrado en `.factory/provisioning.json`.
- El bootstrap construye localmente `template/ + .factory/provisioning.json`, crea un único root commit en `main` y lo empuja mediante un `GIT_ASKPASS` efímero. No usa Git Database REST para inicializar un repositorio vacío.
- La descripción de recuperación liga un digest SHA-256 de la intención completa, incluida la idempotency key completa y el SHA exacto de gobernanza.
- Un retry con el mismo marker converge sin nuevas escrituras. Un repo preexistente público, no vacío, con identidad distinta o con marker distinto falla cerrado.
