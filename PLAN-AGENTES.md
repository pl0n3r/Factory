# Plan de agentes de la fábrica

> Instrucciones del dueño (@pl0n3r) para todos los agentes de pl0n3r/Condor, pl0n3r/GrindFlow, pl0n3r/brvtal y pl0n3r/factory.
> El agente lee este archivo, **determina solo su tanda** con las reglas de abajo y ejecuta la sección de su repositorio.

## 0. Cómo determinar tu tanda

Revisa estas condiciones en GitHub, en orden, y toma la **primera** que no esté cumplida:

| Tanda | Condición de "terminada" |
| --- | --- |
| **1** | Los Issues de Roadmap pl0n3r/Condor#1, pl0n3r/GrindFlow#2 y pl0n3r/brvtal#533 tienen un comentario "🟢 PRODUCCIÓN EN VERDE" / "🟢 PRODUCTION GREEN" con evidencia **y** pl0n3r/factory tiene el tag `v1.0.0` |
| **2** | Los épicos pl0n3r/Condor#192, pl0n3r/GrindFlow#129 y pl0n3r/brvtal#630 están cerrados como completados |
| **3** | Continua: desarrollo normal |

Particularidades:
- Si **tu repo** ya cumplió su parte de la tanda actual, pero otro repo no, **no avances**: comenta en tu épico que esperas la tanda y detente.
- `factory` solo trabaja en la tanda 1; después solo mantiene el kit.
- Si producción de tu repo deja de estar en VERDE en cualquier momento, **vuelves a la sección de tanda 1 de tu repo** antes que cualquier otra cosa.

## Reglas comunes (todas las tandas)

- Lee primero AGENTES.md / AGENTS.md de tu repositorio.
- Actúa como **el profesional que exige cada tarea** (SRE, DBA, ingeniería de software, seguridad, QA, UX, diseño, marketing, SEO…) y **declara el rol en cada PR**.
- **Un solo agente por repo** (factory admite un segundo agente, ver la sección de factory).
- Máximo **10 commits por PR** (agrupa localmente antes de hacer push) y **3 rondas** de revisión automática; si se agotan, `estado: bloqueado` / `status: blocked` con un resumen, y sigues con otra cosa.
- **Sin polling**: revisa el CI una vez al terminar, no en bucle.
- Todo Issue o PR se etiqueta al crearlo con tipo, prioridad y estado (BRVTAL en inglés: `type:`, `priority:`, `status:`).
- **Decisiones del dueño vigentes (no se revierten):**
  - migraciones aditivas automáticas con backup en post-deploy (Condor D-054);
  - escrituras autónomas en producción durante la fase de desarrollo (Condor #185, GrindFlow #126, brvtal #628), con backup previo; SQL destructivo o borrado irreversible siguen requiriendo autorización;
  - sistema de releases de Condor en los 3 proyectos (en BRVTAL reemplaza a `update-release-metadata.yml`);
  - etiquetas obligatorias (tipo + prioridad + estado) en todo Issue y PR;
  - roles profesionales por tarea (factory#2);
  - factory no genera trabajo para el dueño.
- **Solo escala al dueño:** dirección de producto, dinero, legal, datos reales de clientes o pasar a live. Todo lo demás lo decides tú según AGENTES.md.

## Definición de VERDE

1. `/health` (o equivalente) responde 200 con la versión y el SHA exactos de main y, si aplica, el esquema al día (`schema_up_to_date: true`).
2. Home, login del admin y el panel principal del admin responden sin 5xx.
3. El smoke/observador de producción del repo pasa en su última corrida.
4. No queda ningún Issue abierto de incidente (`tipo: incidente` / `type: incident`) ni ningún `[AUTO]` de fallo de producción.
5. El último CI de main pasa.

---

## TANDA 1

### Condor: producción en verde
- Crítico conocido: PR #186 (Closes #185 y #187). Las migraciones pendientes causan `TableNotFoundException` y 500 en `/`, `/health`, `/marcela-arias-tienda` y el centro de control. Termínalo e intégralo; no abras un PR paralelo (recupera la reserva con `/tomar` si está inactiva).
- Verifica los 5 puntos de VERDE, incluyendo `/marcela-arias-tienda` y el centro de control.
- Busca otros problemas críticos no reportados; repórtalos como incidente crítico y arréglalos.
- Al terminar: comenta "🟢 PRODUCCIÓN EN VERDE" en Condor#1 con la evidencia de los 5 puntos (URL, HTTP, versión, SHA, run) y detente.

### GrindFlow: producción en verde
- Crítico conocido: #121 y #73. Ningún código aprovisiona `e2e-admin@grindflow.test` en producción (`E2eSeeder` solo corre en local/testing y crea `e2e-browser@…`). Implementa un comando artisan idempotente que cree o actualice el usuario sintético desde el `.env` de producción (mínimo privilegio, sin loguear secretos), ejecutado automáticamente en el post-deploy. Si falta una variable en el `.env` de producción, documéntala en el PR y en #121.
- Verifica los 5 puntos de VERDE (Production Smoke en verde; cierra #73).
- Busca otros problemas críticos no reportados; repórtalos y arréglalos.
- Al terminar: comenta "🟢 PRODUCCIÓN EN VERDE" en GrindFlow#2 con la evidencia y detente.

### BRVTAL: production green (English)
- Known critical: #623 / PR #626, the slow DISCADMIN. Release the PHP session lock on read-only requests (`session_write_close` / `read_and_close`); use one shared `/auth` call instead of about 9 per module; memoize `information_schema` checks (at most 1 per request) and aggregate the dashboard counts; paginate the admin listings. Measure dashboard load time before and after and record it in the PR.
- Verify the 5 GREEN points (`/api/health.php` with the exact version, SHA and database; `/discadmin/` and the dashboard without 5xx).
- Look for unreported critical problems; report them as critical incidents and fix them.
- When done: comment "🟢 PRODUCTION GREEN" on brvtal#533 with the evidence and stop.

### factory: construir el kit
- Orden: #14 arranque → #1 kit v1 completo (ci, deploy con rollback, release, observar, coordinación, etiquetas es/en, política con `decisiones.yml` y tope de 3 rondas) → #2 roles → #3 orquestador → #4 especificaciones ejecutables → #5 evaluación de agentes → #7 costos → #8 memoria → #9 puertas humanas → #6, #10, #11, #12 → `template/`.
- Extrae de lo que ya funciona en pl0n3r/Condor en vez de inventar. Todo configurable por inputs: stack (Symfony, Laravel, PHP plano), dominio, fuente de versión, idioma de etiquetas y fase `construccion|live`.
- Acciones fijadas a SHA, mínimo privilegio, `concurrency` y filtros `if:` para no cargar GitHub.
- Publica el tag `v1.0.0` cuando #1 a #14 estén cerrados y el template pase su propio CI.
- **Segundo agente opcional:** si ya hay otro agente trabajando en factory, tú solo tomas #5, #6, #7, #8, #9, #10, #11 y #12, con archivos exclusivos `metricas/`, `seguridad/`, `docs/` y `.github/workflows/{metricas,costos,seguridad}.yml`. No tocas archivos del otro agente (si necesitas algo ahí, abre un Issue) y haces rebase sobre main antes de cada push.
- Al terminar: comenta la guía de adopción del kit v1.0.0 en Condor#192, GrindFlow#129 y brvtal#630, y detente.

---

## TANDA 2: adoptar el kit (Condor, GrindFlow y BRVTAL)

Guía: el comentario de adopción en tu épico (Condor#192, GrindFlow#129, brvtal#630).

1. Reemplaza CI, coordinación, etiquetas, release, observador/smoke y deploy locales por los reusable workflows del kit (`uses: pl0n3r/factory/...@v1`). Elimina las copias locales divergentes.
2. Crea `decisiones.yml` con todas las decisiones vigentes del dueño (lista en "Reglas comunes").
3. Adopta el núcleo común de AGENTES.md del kit y conserva solo la capa propia del proyecto.
4. Activa el deploy con rollback, la merge queue con auto-merge, las métricas y el monitoreo del kit.
5. Cierra como resueltos por el kit: Condor #188 y #190; GrindFlow #123, #124 y #125; brvtal #624, #625 y #627.
6. Valida con un PR de prueba que pase el CI del kit, se integre solo y termine en producción validada o en rollback automático.

Solo terminas si después del último deploy se siguen cumpliendo los 5 puntos de VERDE; publica la evidencia en tu Roadmap. Luego cierra tu épico como completado y detente.

---

## TANDA 3: desarrollo normal

Retoma el desarrollo desde tu Roadmap (Condor#1, GrindFlow#2, brvtal#533), en el punto en que estaba antes de la auditoría, más los Issues abiertos críticos y altos:
- Condor: #183/#184 (pedidos, e-commerce y stock) y #191 (recuperación de cuenta y cambio de contraseña).
- GrindFlow: #127 (recuperación de cuenta y cambio de contraseña).
- BRVTAL: #629 (account recovery and password change) y #623 si sigue abierto.

Trabaja con las reglas del kit: `/tomar`, rol profesional declarado, criterios de aceptación ejecutables y reglas comunes. Si producción deja de estar en VERDE, eso va antes que cualquier otra cosa.
