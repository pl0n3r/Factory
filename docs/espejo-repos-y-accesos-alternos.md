# Espejo independiente de GitHub y accesos alternos — Factory #1960

## Estado y límites

**Diseñado y probado solo con fixtures**. NO se ha creado una cuenta Backblaze B2, no se ha contratado almacenamiento, no se han usado credenciales reales y no se ha ejecutado ninguna exportación real. Esta integración permanece desactivada hasta decisión explícita del dueño en la etapa live (D-066). Código y pruebas no realizan conexiones externas al ejecutarse en CI.

Repositorios canónicos (siete): pl0n3r/Factory, pl0n3r/Condor, pl0n3r/GrindFlow, pl0n3r/brvtal, pl0n3r/ControlBot, pl0n3r/AutoFactory y pl0n3r/FactoryRunner. Todos son públicos; este hecho NO autoriza publicar tokens, expedientes, datos operativos o la copia offsite.

El archivo scripts/espejo_repos.py implementa una preparación reutilizable. Durante una ejecución futura autorizada, para cada repositorio:

1. Clona un espejo git y genera un bundle de todas sus referencias disponibles en el origen (ramas y etiquetas).
2. Obtiene en modo lectura la lista de issues y pull requests (estados abiertos y cerrados), sus comentarios, revisiones y archivos cambiados mediante la API REST de GitHub. La identidad de los objetos queda en JSON para auditoría, sin intentar escribir issues o PRs.
3. Sube tres objetos independientes (repository.bundle, issues.json y pulls.json) al destino compatible con S3 mediante HTTPS y firma AWS SigV4.
4. Calcula SHA-256 y tamaño de cada objeto. Publica manifest.json **al final**, solo cuando los tres objetos anteriores terminaron de cargarse.
5. Devuelve para cada repositorio la ruta del manifiesto y su SHA-256. Ambos deben custodiarse **fuera de GitHub**, junto al registro de recuperación. Si el proceso falla antes del manifiesto, los objetos parciales no representan un respaldo publicado.

Cada ejecución usa un prefijo de snapshot único y por repositorio, por ejemplo mirror/AAAAMMDDThhmmssZ-hex12/pl0n3r_Factory/. Es versionado por **claves inmutables distintas**, sin reemplazar ni borrar instantáneas anteriores. No depende de que el proveedor implemente la API de versionado de objetos de AWS; antes del uso real se debe validar retención, lifecycle, costos y política de protección del bucket. La aplicación no configura un bucket ni presupone una retención ya contratada.

## Contrato de secretos

Solo se admiten archivos privados con permisos 0600 (no symlinks, sin salto de línea interior), mediante variables de entorno con sufijo FILE:

| Variable | Significado | Valor en este documento |
| --- | --- | --- |
| GITHUB_TOKEN_FILE | Archivo con token GitHub de mínimo alcance, usado solo para GET a api.github.com | No definido |
| B2_KEY_ID_FILE | Archivo con Application Key ID del destino compatible con S3 | No definido |
| B2_APP_KEY_FILE | Archivo con Application Key privada del destino compatible con S3 | No definido |
| B2_S3_ENDPOINT | URL HTTPS de la región S3 de Backblaze B2, sin usuario ni ruta | No definido |
| B2_S3_REGION | Región S3 del bucket | No definido |
| B2_S3_BUCKET | Nombre del bucket de respaldo fuera de GitHub | No definido |

La URL HTTPS para leer la API GitHub se limita a api.github.com; no se siguen redirecciones con credenciales. Las credenciales de almacenamiento solo se envían como cabeceras firmadas HTTPS al endpoint configurado. Nunca se pasan secretos como argumentos de línea de comandos ni se imprimen. No crear ni subir archivos de secretos al repositorio. Configurar claves con derechos mínimos y almacenamiento cifrado según el proveedor, una vez autorizado.

## Procedimiento futuro de exportación (sin ejecutar en esta tarea)

Requiere Python 3.11+, git en PATH, cuenta B2 autorizada, conectividad, el bucket ya provisionado y las seis variables anteriores. No requiere paquetes pip. Después de confirmar los controles de live y credenciales privadas en el entorno seguro:

    python3 scripts/espejo_repos.py export --prefix mirror

Se imprime JSON por repositorio con cuatro campos: repo, key, sha256, snapshot. Guardar este registro en un lugar distinto de GitHub y del mismo bucket. Un éxito parcial entre siete repositorios exige gestionar los repos faltantes, sin considerar completa la tanda. El bundle solo cubre refs que GitHub publicó: ramas borradas, recursos GitHub privados no autorizados, configuraciones de protección, webhooks, secretos y acciones de GitHub no se recuperan automáticamente.

## Procedimiento futuro de restauración offline

No sobrescribe el destino y no recrea automáticamente issues/PRs en GitHub.

1. Recuperar fuera de banda el par manifiesto (key, sha256) correspondiente al repo deseado.
2. Preparar un directorio padre existente y una ruta destino **que todavía no exista**.
3. Con credenciales S3 en archivos privados, ejecutar:

    python3 scripts/espejo_repos.py restore --manifest-key RUTA_DEL_MANIFIESTO --manifest-sha256 HUELLA_SHA256_ANCLADA --destination /ruta/nueva/restauracion

4. El script contrasta SHA-256 del manifiesto y de los tres objetos, identidad del repo/snapshot y estructura JSON **antes** de crear el destino. Git verifica la legibilidad del bundle al clonar un repositorio bare en destino/repository.git. En el mismo directorio deja issues.json, pulls.json y manifest.json, para lectura o importación manual futura.
5. Inspeccionar sin ejecutar contenido no confiable: git --git-dir=/ruta/nueva/restauracion/repository.git fsck --full y git --git-dir=... show-ref. Comprobar SHAs de ramas/tags contra la referencia previa; para un nuevo hosting crear el repositorio remoto bajo control del dueño y migrar refs tras autorización explícita. Importar issues/PRs es una operación aparte que exige plan de mapeo de IDs, participantes y permisos; **este script no modifica GitHub ni el destino original**.

Restaurar sin SHA del manifiesto conocido fuera del almacén no constituye verificación de autenticidad. Las huellas detectan corrupción o manipulación de objetos respecto del manifiesto anclado, no sustituyen control de acceso, backups múltiples ni pruebas operativas.

## Pruebas y reversibilidad

    python3 -m unittest tests.test_espejo_repos -v

La prueba obligatoria exacta es tests/test_espejo_repos.py::EspejoReposTests::test_criterio_principal. Crea un repositorio git **local**, agrega un commit/tag falsos, exporta a un almacén simulado y recupera refs, issues y PRs sin llamadas reales. Cubre SHA corrupto, hash de manifiesto alterado, directorio ya existente, lista canónica, path traversal, secretos con permisos excesivos, claves versionadas y subida parcial. La reversión del PR elimina estos tres archivos; no se ha modificado la infraestructura externa.

## Inventario de accesos alternos (sin datos ni valores)

**Pendiente de registrar exclusivamente por el dueño antes de live.** Las columnas son deliberadamente vacías, no son afirmaciones de que exista acceso ni de que haya ocurrido una revisión. No incluir usuarios, claves, direcciones privadas, URLs de recuperación ni códigos MFA aquí.

| Acceso/servicio que deberá verificarse | Existe (sí/no) | Dónde se custodia, sin revelar el valor | Última revisión UTC |
| --- | --- | --- | --- |
| Cuenta GitHub del propietario y códigos de recuperación | | | |
| Segundo factor de GitHub y dispositivo alterno | | | |
| Propiedad de organización/repositorios y administrador alterno | | | |
| Cuenta y panel de Backblaze B2 | | | |
| Identidad/clave de aplicación B2 y procedimiento de rotación | | | |
| Custodia externa de manifiestos y SHA-256 anclados | | | |
| DNS/registrador de los dominios y su MFA | | | |
| Hosting y panel de producción, con vía de acceso alterna | | | |
| Gestor de contraseñas y acceso de recuperación | | | |
| Canal de incidentes fuera de GitHub | | | |

Los valores deben permanecer en la custodia definida por el dueño, no en este archivo. Una marca de «existe» no autoriza operaciones de dinero, de recuperación en producción ni go-live.

## Riesgos y puertas duras

El espejo no es un backup de bases de datos productivas, volúmenes, secretos, endpoints de salud ni sistemas de identidad. No incluye configuraciones privadas de GitHub (webhooks, reglas de protección o Actions secrets). Los recursos de exportación pueden ser voluminosos; el programa usa límites de tamaño y paginación y falla cerrado. No programar ejecuciones periódicas de esta tarea; el plan live, su frecuencia y retención exigen autorización ulterior del propietario. No se usa un servicio externo durante pruebas.
