# Auditoría técnica pre-v1.0.0 de Factory

**Fecha:** 2026-09-24  
**Repositorio:** `pl0n3r/factory`  
**SHA auditado:** `4b2be9fcf827278631caa3e3e68603b6e2a680d7`  
**Objetivo:** determinar con evidencia qué impide publicar `v1.0.0` de forma estable, segura, reproducible y operable.

## Resumen ejecutivo

Factory tiene una base técnica madura para un repositorio de automatización: reusable workflows centralizados, acciones externas de GitHub fijadas a SHA, permisos por job, `concurrency`, timeouts, aceptación ejecutable, coordinación con reservas, deploy con backup/rollback, health exacto por versión/SHA, auditoría de workflows, privacidad como código, memoria, métricas y control de costos.

La auditoría no encontró un defecto **CRÍTICO** confirmado en el SHA revisado. Sí encontró **2 hallazgos ALTOS que bloquean la publicación inicial de v1.0.0**, **3 MEDIOS** y **1 BAJO**. Además, Factory ya tiene un bloqueo canónico independiente: #13 continúa abierto porque #54 todavía exige la revalidación de privacidad de los tres productos contra seis documentos y la primera ejecución real del auditor semanal.

**Conclusión pre-v1:** no publicar `v1` / `v1.0.0` todavía. Antes deben cerrarse #54 → #13, #82 y #83, resolverse la puerta humana `release-1.0.0` y revalidarse el SHA exacto final.

## Roles aplicados

- Arquitectura de software
- Ingeniería de software
- Seguridad / supply chain
- Infraestructura / GitHub Actions
- SRE / resiliencia
- QA
- Release Engineering
- Performance / costo de CI
- Producto
- Technical Writing / DX
- Legal-privacidad cuando el alcance lo requirió

DBA no produjo un hallazgo propio: Factory no mantiene una base de datos de aplicación; su superficie DBA relevante está en el contrato de migración/backup/rollback del kit y fue revisada desde SRE/infraestructura.

## Metodología

1. Se congeló la revisión contra el SHA indicado.
2. Se revisaron Issues #1–#14, #35, #41, #54 y trabajo activo para evitar duplicados.
3. Se inventariaron workflows raíz y del template, scripts, tests, seguridad, privacidad, métricas, memoria y documentación de release.
4. Se contrastó implementación con contratos ejecutables y con el estado real de GitHub Actions.
5. Cada candidato fue sometido a una segunda pasada: evidencia, duplicado existente, severidad, probabilidad y frontera pre/post-v1.
6. Los hallazgos ALTOS se materializaron como Issues separados; MEDIOS/BAJOS quedan en este informe.

## Hallazgos

### AUD-REL-001 · Camino inicial de v1.0.0 no ejecutable de extremo a extremo

**Roles:** Release Engineering + Arquitectura + Infraestructura + Seguridad + QA  
**Evidencia:** CONFIRMADO  
**Severidad:** ALTO  
**Probabilidad:** ALTA al intentar el primer release  
**Bloquea v1.0.0:** SÍ  
**Issue:** #82

**Evidencia exacta**

- `docs/release-bootstrap.md:20-28` define las puertas previas.
- `docs/release-bootstrap.md:38` indica ejecutar “el caller normal de release”.
- `docs/release-bootstrap.md:44` confirma que Factory no añade ese caller.
- `.github/workflows/release.yml` solo expone `workflow_call`.
- #41 registró explícitamente que no añadió caller de publicación ni archivo de versión raíz.

**Escenario de fallo:** se llega al SHA aprobado, se crea manualmente `v1`, pero el paso siguiente documentado no existe como operación ejecutable en Factory. Esto empuja a improvisar un release manual o a crear un caller justo en la frontera de publicación, fuera de la evidencia previamente auditada.

**Solución:** #82 define un caller manual/fail-closed con SHA esperado, fuente de versión canónica, verificación de #1–#14, puerta humana, coincidencia de `v1` y self-test posterior.

---

### AUD-SEC-002 · El futuro tag v1 no tiene una protección de trust-root demostrada

**Roles:** Seguridad + Infraestructura + SRE + Arquitectura  
**Evidencia:** RIESGO DEMOSTRABLE  
**Severidad:** ALTO  
**Probabilidad:** BAJA/MEDIA; impacto alto si ocurre  
**Bloquea v1.0.0:** SÍ hasta demostrar control equivalente  
**Issue:** #83

**Evidencia exacta**

- Los consumidores llaman Factory por `@v1`.
- Workflows privilegiados vuelven a cargar componentes desde `ref: v1`.
- `docs/release-bootstrap.md:42` dice que solo el proceso humano/autorizado debe actualizar el canal mayor.
- La API de Rulesets del repositorio devuelve una lista vacía en la auditoría. No existe un ruleset moderno que haga cumplir esa restricción.
- La integración actual no puede certificar una eventual protección legacy administrativa, así que esa protección no está demostrada.

**Escenario de fallo:** si `v1` se mueve o elimina fuera del proceso autorizado, múltiples consumidores pueden ejecutar otro código sin modificar sus propios workflows, incluyendo rutas de deploy/release con secretos.

**Solución:** #83 exige proteger el tag antes de crearlo y demostrar que actores/tokens no autorizados no pueden moverlo o borrarlo.

---

### AUD-SC-003 · Dependencias ejecutables externas no tienen integridad criptográfica completa

**Roles:** Seguridad + Infraestructura  
**Evidencia:** CONFIRMADO  
**Severidad:** MEDIO  
**Probabilidad:** BAJA  
**Bloquea v1.0.0:** NO por sí solo  
**Esfuerzo:** S

**Evidencia**

- `.github/workflows/factory-ci.yml:24-27` descarga `actionlint 1.7.7` por HTTPS y lo ejecuta, pero no valida SHA256/firma del artefacto.
- `.github/workflows/cabina.yml:31-34` instala `sentry-sdk==2.70.0` en runtime desde PyPI. La versión directa está fijada, pero no existe lock/hash de artefactos/transitivas para esa instalación.

**Riesgo:** una alteración de origen/artefacto o una resolución transitoria inesperada puede cambiar el código ejecutado en CI sin cambio en el repositorio. En cabina, el paquete instalado se importa después en una ejecución que recibe `GH_TOKEN` y `SENTRY_DSN`.

**Antes**

```bash
curl ... actionlint_1.7.7_linux_amd64.tar.gz | tar -xz actionlint
python3 -m pip install 'sentry-sdk==2.70.0'
```

**Después recomendado**

```bash
curl ... -o actionlint.tar.gz
echo "$ACTIONLINT_SHA256  actionlint.tar.gz" | sha256sum -c -
tar -xzf actionlint.tar.gz actionlint

python3 -m pip install --require-hashes -r tooling/sentry-requirements.txt
```

Mantener además el paso de instalación sin secretos y entregar secretos únicamente al proceso que realmente los necesita.

---

### AUD-DX-004 · El template no documenta su contrato operativo de variables y secretos

**Roles:** Technical Writing + DX + Infraestructura + SRE  
**Evidencia:** CONFIRMADO  
**Severidad:** MEDIO  
**Probabilidad:** ALTA para un proyecto nuevo  
**Bloquea v1.0.0:** NO, pero reduce la promesa “proyecto nuevo ya listo”  
**Esfuerzo:** XS/S

**Evidencia**

- `template/README.md:5` solo indica que deploy/observación se habilitan “cuando el proyecto configura su entorno”.
- `template/.github/workflows/deploy.yml:8-21` consume `DEPLOY_ENABLED`, `DOMAIN`, `HEALTH_PATH`, `PRODUCTION_STAGE`, `MIGRATION_MODE`, `LIVE_MIGRATION_APPROVED` y tres secrets.
- `template/.github/workflows/observar.yml:14-22` depende de `DOMAIN` y opciones de health.

**Riesgo:** un consumidor puede copiar el template correctamente pero no saber qué variables son obligatorias, cuáles son opcionales, qué formato aceptan y qué habilita producción. Eso convierte parte del onboarding en conocimiento implícito.

**Solución:** documentar una tabla cerrada de variables/secrets, defaults, fase en que aplican y comportamiento fail-closed; enlazarla desde `template/README.md`.

---

### AUD-REL-005 · El caller de release implica un bump de versión por cada push a main, pero la política es implícita

**Roles:** Release Engineering + QA + DX  
**Evidencia:** CONFIRMADO  
**Severidad:** MEDIO  
**Probabilidad:** MEDIA  
**Bloquea v1.0.0:** NO si se define la política antes de adopción  
**Esfuerzo:** S

**Evidencia**

- `template/.github/workflows/release.yml:3-4` se dispara en todo `push` a `main`.
- El reusable `.github/workflows/release.yml` falla si el tag de la versión ya existe y apunta a un SHA distinto del push actual.
- `agentes/NUCLEO.md:54-56` define el canal major, pero no establece que todo merge a main deba incrementar versión.
- `template/README.md` tampoco documenta el requisito.

**Escenario:** después de crear `v0.1.0`, un merge documental o técnico que no cambie `config/version.json` dispara Release; el reusable encuentra `v0.1.0` apuntando al SHA anterior y falla.

**Solución:** hacer explícita una de dos políticas y probarla:
1. **cada merge releasable incrementa versión** → añadir gate pre-merge que exija el bump; o
2. **no todo merge crea release** → limitar el caller a cambios de versión / un evento explícito.

No cambiar el chequeo del reusable que impide reutilizar un tag para otro SHA.

---

### AUD-COST-006 · Eventos de coordinación generan fan-out visible de runs descartados

**Roles:** Performance/FinOps + Infraestructura  
**Evidencia:** CONFIRMADO  
**Severidad:** BAJO  
**Probabilidad:** ALTA  
**Bloquea v1.0.0:** NO  
**Esfuerzo:** S/M

**Evidencia**

Durante la propia creación/reserva de #81 se observaron múltiples ejecuciones de `coordinacion-trabajo.yml` y `orquestador.yml` sobre eventos de Issue/comentario, muchas terminadas como `skipped` o `cancelled` (por ejemplo runs `36038051785`, `36038050932`, `36038050207`, `36038049381`, `36038048364`).

`coordinacion-trabajo.yml:9-12` escucha varios eventos amplios y filtra después por job; `orquestador.yml:4-5` escucha cada comentario y filtra `/planificar` en el job.

**Impacto:** principalmente ruido operacional y volumen de runs, no un defecto funcional ni un costo grande demostrado.

**Solución:** medir primero el costo real. Si es material, reducir eventos, consolidar mutaciones de labels/comentarios o separar routers ultraligeros de los jobs con runner. No sacrificar la coordinación fail-closed por ahorrar runs mínimos.

## Áreas revisadas

### Seguridad y supply chain

**Fortalezas**
- Auditor `seguridad/resiliencia.py` prohíbe acciones no pinneadas, `pull_request_target`, `write-all` y permisos globales de escritura.
- `seguridad/test_resiliencia.py` audita todos los workflows del repositorio.
- `factory-ci.yml` ejecuta la suite de seguridad en cada PR.
- Checkouts usan `persist-credentials: false`.
- Runtime health fija DNS a IP pública validada, mantiene TLS sobre hostname original, limita tamaño y no sigue redirects.

**Deuda:** AUD-SC-003 y AUD-SEC-002.

### Arquitectura

La separación entre reusable workflows, scripts cerrados y callers del template es coherente. Los adapters de deploy tienen tabla cerrada, rechazan symlinks y escapes del checkout. No se encontró una dependencia circular nueva; #41 documenta conscientemente el bootstrap del canal major.

Riesgo principal: el trust-root `v1` necesita enforcement externo (#83).

### Calidad de código y deuda

No se abrió hallazgo por tamaño de scripts: aunque `coordinar_trabajo.py` es grande, existe una suite de regresión extensa y no se obtuvo evidencia de defecto por complejidad. La auditoría evita usar métricas de tamaño como sustituto de riesgo.

### Testing / QA

La suite cubre contratos de CI, coordinación, aceptación, deploy, preview, privacidad, seguridad, métricas, memoria y producto.

El candidato “el template nunca se ejecuta” fue descartado: `.github/workflows/reusable-selftest.yml:14-22` sí invoca el reusable CI con `working_directory: template` y SHA del candidato. El self-test post-publicación por `@v1` sigue correctamente pendiente para el bootstrap.

No se usa porcentaje de cobertura como criterio de calidad porque no hay evidencia de que una cifra arbitraria mejore el contrato actual.

### Performance

Factory no es un runtime de aplicación con queries o endpoints propios. No se encontró evidencia de cuello de botella algorítmico relevante. El frente medible es costo/ruido de Actions, reflejado en AUD-COST-006.

### CI/CD

- Main exacto `4b2be9fc...`: `CI factory` run `36035673042` = success.
- Actionlint cubre workflows raíz y template.
- `concurrency` y timeouts están presentes en los workflows principales.
- El deploy limita contexto a default branch y usa pipeline reversible.
- Preview no recibe credenciales productivas.

Hallazgos: AUD-SC-003 y AUD-COST-006.

### Release Engineering

Es el área con mayor brecha pre-v1: AUD-REL-001. El reusable es conservador e idempotente respecto a tags existentes, pero Factory todavía no tiene el camino ejecutable del primer release.

AUD-REL-005 debe aclararse antes de escalar adopción del template.

### Observabilidad / SRE / resiliencia

`observe_kit.py` exige health 200 JSON, versión/SHA exactos y opcionalmente schema actualizado. El observer abre/cierra incidentes automáticos. El deploy revierte artefacto si deploy/health falla y evita restaurar DB a ciegas tras migración aditiva parcial.

No se encontró un falso “deploy=producción sana”: el núcleo distingue implementado, validado, desplegado y validado en producción.

### Privacidad y datos

Factory genera seis documentos canónicos, mantiene placeholders del responsable y separa revisión jurídica de evidencia técnica. #54 sigue abierto por dos condiciones canónicas: revalidación de Condor/GrindFlow/BRVTAL contra seis documentos y primera ejecución real del auditor semanal con el contrato vigente.

Esto ya está rastreado; no se abrió un Issue duplicado.

### Documentación / DX

El README raíz estaba desalineado con cierres recientes, pero #79 / PR #80 ya posee ese trabajo. Se descartó como nuevo hallazgo. AUD-DX-004 sí es independiente y afecta al consumidor del template.

### Costos

Existe presupuesto por tamaño/tipo, límites de 10 commits y 3 rondas, y reporte de tendencia. AUD-COST-006 es optimización de ruido, no señal de gasto grave demostrado.

### Mantenibilidad / operación

La memoria institucional, decisiones como código, roles y coordinación reducen dependencia del chat. Los contratos de aceptación están fingerprinted en reservas v2 y las ediciones posteriores pueden invalidar evidencia stale.

## Readiness v1.0.0

| Requisito | Estado | Evidencia / bloqueo |
|---|---|---|
| Core Factory #1–#12 y #14 | DEMOSTRADO | Issues cerrados; suites integradas |
| CI exacto de main | DEMOSTRADO | `36035673042` success en `4b2be9fc...` |
| Candidate reusable CI sobre template | DEMOSTRADO | `reusable-selftest.yml` usa `working_directory: template`; runs previos de “Probar CI reusable” verdes |
| Acciones GitHub externas pinneadas | DEMOSTRADO | auditor de resiliencia + tests en Factory CI |
| Deploy/rollback/health exacto | DEMOSTRADO | scripts + regresiones contractuales |
| Privacidad core de seis documentos | DEMOSTRADO | #71/#78 integrado |
| Adopción privacidad seis docs en 3 productos | BLOQUEADO | #54 |
| Primera ejecución real auditor semanal | BLOQUEADO | #54 |
| Épico TANDA 1 #13 | BLOQUEADO | depende del cierre de #54 |
| Camino ejecutable primer `v1.0.0` | AUSENTE | #82 |
| Protección demostrada del trust-root `v1` | AUSENTE | #83 / rulesets vacíos |
| Puerta humana `release-1.0.0` | BLOQUEADO | solo debe resolverse al final |
| `v1` y `v1.0.0` publicados | BLOQUEADO | correcto mientras lo anterior siga abierto |
| Self-test consumidor real por `@v1` | BLOQUEADO | paso post-publicación documentado |
| README/handoff canónicos | PARCIAL | #79 / PR #80 activo |

## Priorización impacto vs esfuerzo

| ID | Área | Severidad | Probabilidad | Bloquea v1 | Esfuerzo | Prioridad |
|---|---|---:|---:|---:|---:|---:|
| AUD-SEC-002 | Seguridad / supply chain | ALTO | Baja/Media | Sí | S/M | 1 |
| AUD-REL-001 | Release Engineering | ALTO | Alta | Sí | M | 2 |
| AUD-SC-003 | Supply chain CI | MEDIO | Baja | No | S | 3 |
| AUD-REL-005 | Release / DX | MEDIO | Media | No | S | 4 |
| AUD-DX-004 | DX / documentación | MEDIO | Alta | No | XS/S | 5 |
| AUD-COST-006 | CI / costos | BAJO | Alta | No | S/M | 6 |

La prioridad pone primero la protección de la raíz de confianza por impacto transversal, aunque #82 sea más probable de manifestarse inmediatamente.

## Quick wins

1. Documentar variables/secrets del template (AUD-DX-004).
2. Añadir checksum de actionlint y requirements con hashes para la dependencia runtime de cabina (AUD-SC-003).
3. Declarar y probar la política de bump de versión del template (AUD-REL-005).
4. Medir cuántos runner-minutes reales consume el fan-out antes de optimizarlo (AUD-COST-006).

## Puede esperar después de v1.0

- Optimización del fan-out de eventos si los runner-minutes demuestran costo bajo.
- Refactors por tamaño de scripts sin evidencia de defecto.
- Mejoras cosméticas de documentación que no afecten onboarding, seguridad o operación.

AUD-SC-003, AUD-DX-004 y AUD-REL-005 son recomendables antes de la adopción amplia del kit, aunque no bloquean por sí solos el primer tag.

## Falsos positivos / candidatos descartados

### DESCARTADO · “seguridad.yml no audita cambios a otros workflows”

Aunque `seguridad.yml` tiene filtros de paths, `factory-ci.yml` ejecuta toda la suite `seguridad/test_*.py` en cada PR y `test_current_repository_workflows_are_auditable` recorre todos los workflows. No existe el bypass inicialmente sospechado.

### DESCARTADO · “GitHub Pages publica la cabina sin autorización”

`cabina.yml` exige `FACTORY_CABINA_PUBLICA == 'true'` para configure/upload/deploy Pages. #35 conserva el default B. Que Pages esté habilitado a nivel de repositorio no demuestra que la cabina esté expuesta.

### DESCARTADO · “usar @v1 es por sí mismo una vulnerabilidad”

El canal major mutable es una decisión explícita de arquitectura (#41). El problema real no es usarlo, sino demostrar que su mutación está protegida (#83).

### CORREGIDO · “el template solo se valida estáticamente”

`validar_template.py` sí es estático, pero existe `reusable-selftest.yml` que ejecuta el reusable CI con `working_directory: template`. Por tanto no se registra como ALTO. El test externo post-publicación `@v1` sigue pendiente por diseño.

### DESCARTADO · README raíz desactualizado como hallazgo nuevo

#79 / PR #80 ya posee esa sincronización. Abrir otro Issue duplicaría trabajo.

## Siguientes pasos de mayor impacto

1. Resolver #83 antes de crear el tag `v1`.
2. Resolver #82 y probar el bootstrap del primer release sin publicar hasta la puerta humana final.
3. Completar #54 y cerrar #13 con evidencia.
4. Integrar #80 para que la documentación refleje el estado canónico.
5. Aplicar los quick wins MEDIOS y ejecutar la auditoría final de release sobre el SHA que vaya a recibir `v1`.

## Criterio de cierre de esta auditoría

El trabajo de auditoría se considera entregado cuando los hallazgos ALTOS estén rastreados, este informe pase sus regresiones y su PR quede validado. **Eso no significa que Factory esté listo para v1.0.0**: readiness depende de cerrar los bloqueadores identificados y realizar una revalidación final sobre el SHA de release.
