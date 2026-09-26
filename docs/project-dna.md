# Project DNA v1

Project DNA describe **lo que el repositorio demuestra**, no lo que Factory
supone. Su objetivo es dar a los agentes una huella mínima y determinista antes
de elegir roles, controles o estrategias.

## Fuentes admitidas

El descubridor recibe señales explícitas y no secretas:

- rutas relativas del repositorio;
- presencia de manifests conocidos;
- estructura declarada de esos manifests;
- capacidades declaradas por un caller confiable.

No abre archivos arbitrarios, no escanea secretos, no lee datos reales y no
infiere infraestructura por similitud de nombres fuera de sus señales
versionadas.

## Campos base

Project DNA v1 contiene:

- `version`;
- `stack`;
- `frameworks`;
- `data`;
- `ci`;
- `hosting`;
- `integrations`;
- `capabilities`;
- `signals`;
- `extensions`;
- `fingerprint`.

Cuando una superficie carece de evidencia, su valor es exactamente
`"unknown"`. No se sustituye por una conjetura.

## Determinismo

Las rutas, capabilities y resultados detectados se normalizan y ordenan. El
fingerprint es SHA-256 del documento canónico sin el propio campo
`fingerprint`, por lo que el mismo conjunto de señales produce la misma huella
aunque el orden de entrada cambie.

## Extensibilidad

Los campos base permanecen cerrados. Las capacidades futuras deben añadirse
bajo `extensions`, cuyo contenido puede evolucionar sin reinterpretar los
campos v1. Un cambio incompatible de los campos base requiere una nueva versión
de Project DNA.

## Señales v1

La versión inicial reconoce, cuando están presentes explícitamente, manifests
de PHP/Composer, Node/npm, Python, Go y Rust; GitHub Actions/GitLab/Jenkins;
rutas de datos SQL/Prisma; algunos manifests de hosting; y frameworks conocidos
por dependencias declaradas. Ausencia de señal significa `unknown`.
