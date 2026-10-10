# AGENTES.md

Este proyecto consume el núcleo operativo de Factory v1:

https://github.com/pl0n3r/factory/blob/v1/agentes/NUCLEO.md

## Capa local

- Stack inicial: PHP plano.
- Fuente de versión: `config/version.json`.
- Fase inicial: `construccion`.
- Idioma de etiquetas: español.
- Añade aquí solo reglas técnicas o de producto propias de este proyecto; no copies el núcleo.

## Principios de construcción de la fábrica

> Guía declarativa derivada de Factory #1082. Prevalecen el núcleo v1, `PLAN-AGENTES.md`, las reglas locales más estrictas y las puertas de autoridad vigentes. Esta plantilla no otorga permisos de ejecución ni certifica su propagación a consumidores.

### Regla 0 — paralelismo seguro y demostrable

Maximizar paralelismo seguro: descomponer en hojas con dependencias reales y claims de archivos concretos. La Coordinación debe comprobar reservas V3, rutas disjuntas, dependencias y SHA; una lease ajena mantiene exclusividad. Un diff momentáneo, una promesa de editar otro hunk o un snapshot incompleto no autorizan claims solapados.

### Principio 1 — cola saludable sin fabricar trabajo

Si la cola de los siete repositorios no tiene hojas `estado: disponible`, inventariar bloqueos y aplicar la escalera de despacho: nunca crear readiness ficticio, reservas ficticias ni `NO_WORK` sin evidencia global. Mantener distintos `disponible`, `reservado`, `bloqueado`, `planificado`, `en revisión` y `requiere recuperación`, y conservar causas y condiciones de salida verificables.

### Principio 2 — hojas pequeñas, acotadas y reversibles

Dividir los épicos en hojas por archivo con AC ejecutables, bajo riesgo y reversión explícita. Preparar módulos puros build-ahead y fakes deterministas cuando un gate real impida avanzar; un fake no demuestra producción, accesos, cifrado real ni operación de un proveedor.

### Principio 3 — arbitraje por archivo y colisiones verdaderas

Declarar claims exactos por archivo, nunca dar por libre un directorio o un archivo por observar solo parte del diff. `README.md`, `config/version.php`, `package.json`, `package-lock.json` y demás lockfiles son colisiones reales hasta demostrar una integración serializada con autorización. Ante diff incompleto, SHA cambiado, leases desconocidas o conflicto: UNKNOWN y fallar cerrado; ni los hunks disjuntos habilitan escrituras paralelas en un mismo archivo.

### Principio 4 — estados, gates y evidencia terminal

`planificado` no equivale a `bloqueado`, una puerta humana no es un bloqueo técnico y `available` no equivale automáticamente a ready. `UNKNOWN` nunca es `GREEN`; un PR abierto o un workflow `success` no demuestran agentes activos ni disponibilidad de producción. Verificar CI exact-HEAD y la evidencia terminal de gates operativos, incluida `VALIDATED_IN_PRODUCTION` cuando el protocolo D-043 la exige.

### Principio 5 — autonomía de construcción, no autoridad de producción

En fase `construccion` preparar cambios reversibles build-ahead sin solicitar permiso del dueño para cada edición offline; esto no autoriza merges, activación, go-live ni publicación automática. Las puertas humanas para gasto/dinero, nuevas credenciales o secretos, datos reales de clientes, proveedores/condiciones legales, privacidad, borrados irreversibles y salida a live permanecen vigentes. Las propuestas de automatización de release no alteran por sí solas las reglas actuales ni el freeze exact-SHA.

### Principio 6 — contrato canónico antes de reservar

Antes de `/tomar`, definir `### Contexto`, `### Alcance`, `### Fuera de alcance`, `### Criterios de aceptación` y `### Contrato ejecutable`, con `[AC-NN]`, pruebas o checks ejecutables y marcador `factory-acceptance` coherente. Un `factory-plan-task` declara owner, roles, paths exactos y `depends_on`; no se escribe código antes de recibir UUID V3 y rama canónica de Coordinación.

### Principio 7 — presupuesto de API compartido

Los agentes comparten presupuesto GitHub y deben usar lecturas acotadas, snapshots frescos y evitar polling de CI. Consultar `rate_limit`: con menos del 20 % disponible, aplazar sondeos prescindibles y no suponer que las 5.000 solicitudes/hora siguen libres. El presupuesto desconocido nunca se interpreta como permiso de gasto o lectura ilimitada.

### Principio 8 — verificar código y evidencia antes de declarar brechas

Antes de reabrir, duplicar, liberar o cerrar trabajo, leer `main` exacto, criterios, paths, PRs integrados y carreras; si el contrato ya está satisfecho, reconciliarlo sin fabricar tareas. No inventar `APPROVED`, HEALTH, porcentajes de utilización, backup restaurado, READY ni go-live: ante prueba ausente o contradictoria, UNKNOWN y fail-closed.

### Límite explícito del template

Este texto no sincroniza ni modifica consumidores, no constituye aprobación humana o revisión independiente y no activa el orquestador. Ningún cambio queda listo para merge, release, `Factory@v1`, despliegue o live sin CI, revisión independiente, protección de rama y autoridad comprobadas. Se prohíben acceso a datos reales, gasto, compra, credenciales, permisos nuevos y borrados irreversibles sin su puerta legítima.
