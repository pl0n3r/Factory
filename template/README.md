# Proyecto Factory

Plantilla mínima para consumir `pl0n3r/factory@v1`.

Incluye CI, coordinación, etiquetas, política y release. Deploy/observación se habilitan cuando el proyecto configura su entorno. El deploy usa adapters ejecutables fijos en `ops/factory/{build,backup,migrate,deploy,rollback}`.

`public/health.php` es un stub explícito en fase `construccion`: no inventa SHA ni estado de esquema y expone `evidence=construction-stub`. En fase `live` exige un `RELEASE_SHA` real; `schema_up_to_date` solo refleja `SCHEMA_UP_TO_DATE` cuando el proyecto decide reportarlo.
