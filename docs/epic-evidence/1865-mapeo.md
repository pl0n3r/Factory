# Factory #1865: mapeo canónico de FSP-11 (DNS/TLS)

> Hoja documental [Factory #2226](https://github.com/pl0n3r/Factory/issues/2226), reserva V3 `7efe56d8-9e0f-4374-9c14-4d072b255a53`. Corte de evidencia de GitHub: **25-nov-2026, `Factory/main@e0d36346230690676843a5f7975fc704fda8ec4a`**. Este documento **no constituye recibo del OWNER, auditoría actual de red ni autorización de live**. Los checks de este PR deberán verificarse por separado en su HEAD exacto.

## Identidad y autoridad de la hoja matriz

- [#1865](https://github.com/pl0n3r/Factory/issues/1865) es un **pendiente del dueño FSP-11**, no una épica técnica con criterios de aceptación: sigue **OPEN**, `estado: bloqueado` y asignado a `pl0n3r`. El cuerpo prohíbe explícitamente `/tomar` y no declara `factory-plan-task`, `factory-acceptance` ni rutas reclamadas. Su cierre **no** resulta de cerrar esta hoja documental.
- En [la decisión OWNER del 30-oct-2026](https://github.com/pl0n3r/Factory/issues/1865#issuecomment-6528281097), el propietario autorizó **chequeos automáticos de DNS/TLS de solo lectura** y reservó el **recibo oficial FSP-11 al flujo live**. No autoriza cambios de zonas, certificados, credenciales ni cambio de fase.
- [`docs/lista-salida-produccion.md`](../lista-salida-produccion.md) conserva expresamente **FSP-11 = `DEL_DUEÑO`** en el blob de `main` `33f417d9b57432a5b4466934621c7080d5ef8847`. Los cuatro consumidores requieren observación por producto y acuse auténtico del OWNER.
- [PLAN-AGENTES](../../PLAN-AGENTES.md), [`decisiones.yml`](../../decisiones.yml) (D-059 y D-069) y el kill switch [#767](https://github.com/pl0n3r/Factory/issues/767) preservan la frontera entre preparación reversible y activación productiva; el interruptor se observó `CLOSED`, creador `pl0n3r`, único marker `RUNNING` al iniciar esta hoja. `RUNNING` no concede autoridad de live.

## Matriz de evidencia y pendientes FSP-11

| Condición del padre | Evidencia autenticada/código en `main` | Evaluación para esta hoja | Pendiente para aceptación real |
| --- | --- | --- | --- |
| **Auditor DNS/TLS por consumidor, read-only** | Hoja técnica [#1952](https://github.com/pl0n3r/Factory/issues/1952) **CLOSED**; [PR #1967](https://github.com/pl0n3r/Factory/pull/1967) **MERGED** por squash `853a1cc828bc4457bcf77e80eedfc1d942cd6bd9`. `scripts/check_dns_tls.py` existe en el `main` del corte con blob `2ad34ec68726ae2af9aa2846da7c61101f6e3ab7`; `tests/test_check_dns_tls.py` con blob `044430a22027dc979966135b202b5b7851bbe96f`. | **Técnica integrada**. El script usa configuración externa de dominios, informes separados y `UNKNOWN` para lectura inconclusa. Sus tests son sintéticos: no demuestran certificados actuales. | Ninguna hoja duplicada de implementación; cualquier defecto nuevo requeriría reproducción y aceptación específica. |
| **Cuatro observaciones por producto** | El [comentario de auditoría del 8-nov](https://github.com/pl0n3r/Factory/issues/1865#issuecomment-6725062179) registra una corrida **histórica**, read-only, `4/4 VALID`, con Condor `www.condorapp.com.co`, GrindFlow `www.grindflow.com.co`, BRVTAL `www.brvtal.com.co` y ControlBot `control.condorapp.com.co`. El [corte del 10-nov](https://github.com/pl0n3r/Factory/issues/1865#issuecomment-6780626075) reportó DNS saliente no disponible **desde su entorno de ejecución**, sin resultado válido nuevo. | **Evidencia temporal, no certificación vigente**. Una falla de resolución del entorno no acredita una caída del producto; tampoco permite trasladar `VALID` de 8-nov a 25-nov. Resultado *actual* sin auditoría contemporánea: **UNKNOWN**. | Obtener informes fechados, atribuibles a cada dominio y producto, desde un entorno autorizado; cotejar DNS, CA/hostname TLS y vencimiento sin deducciones. |
| **Recibo oficial y decisión de salida** | #1865 continúa **OPEN/bloqueado** y el checklist conserva `DEL_DUEÑO`. Los comentarios de observación pasiva no sustituyen el acuse reservado al propietario. | **NO ACREDITADO / gate humano pendiente**. CI verde, código fusionado, tests o cuatro snapshots no convierten el recibo en `LISTO`. | OWNER revisa evidencia contemporánea en el flujo `live` y emite el acuse canónico FSP-11; luego se concilia checklist e Issue, nunca por inferencia. |

## Resultado del splitter: cero hojas técnicas pendientes demostradas

El generador canónico [`scripts/epic_closure_leaves.py`](../../scripts/epic_closure_leaves.py) propone hojas de cierre/mapeo (`factory-epic-splitter`), **no verifica aceptación operativa** ni sustituye puertas humanas. La hoja actual [#2226](https://github.com/pl0n3r/Factory/issues/2226) ya contiene el marker de deduplicación `factory-epic-closure {"version":1,"epic":1865,"kind":"mapeo"}` y reclama solo `docs/epic-evidence/1865-mapeo.md`. No ejecutar el modo mutador `--apply` para crear otra hoja idéntica.

**Resultado contra `main`:** la necesidad técnica demostrada de FSP-11 (auditor read-only, tests y `UNKNOWN` fail-closed) tiene hoja específica #1952 y PR #1967 ya fusionados. No se acreditó brecha técnica adicional, nueva, reversible y disjunta que justifique otra Issue. El resto es **observación productiva + recibo del propietario** y no puede transformarse en hojas automáticas `estado: disponible`. El criterio de creación de Issues de [PLAN-AGENTES §0](../../PLAN-AGENTES.md) impide fabricar tareas para aparentar un DAG ejecutable.

Para cualquier **defecto nuevo comprobado** del auditor, primero contrastar el código contra un SHA nuevo de `main`, reproducir la falla sin secretos ni red privada y aplicar el presupuesto de creación de Issues. Solo entonces dividir en hoja con `factory-acceptance` concreto, owner/roles, dependencias y claims precisos, sin invadir `scripts/check_dns_tls.py` o `tests/test_check_dns_tls.py` por una reserva ajena. El Issue [#1960](https://github.com/pl0n3r/Factory/issues/1960), aunque hace referencia textual a #1865, describe **FSP-52 (espejos de repositorios)**, no es evidencia de DNS/TLS ni dependencia adicional de este mapa.

## Reentrada operativa reservada al OWNER

1. Corroborar la identidad de los cuatro FQDN desde documentación canónica vigente y el entorno autorizado; no añadir listas de dominios supuestos ni credenciales al repositorio.
2. Ejecutar, dentro del alcance autorizado de solo lectura, el auditor `scripts/check_dns_tls.py` con configuración externa; registrar fecha/UTC, producto, FQDN, resultado DNS, identidad CA/hostname, expiración y errores. `UNKNOWN` permanece `UNKNOWN`; un éxito antiguo no lo borra.
3. El propietario valida los cuatro recibos en el flujo **live**, y emite **su** acuse oficial FSP-11. Si no existe, conservar `#1865` abierto/bloqueado y `FSP-11 = DEL_DUEÑO`. No abrir un PR para simular el voto, cambiar DNS/TLS, renovar certs ni activar despliegues.
4. Solo después de esa evidencia, actualizar el estado administrativo por los canales autorizados y decidir si #1865 puede cerrarse. Una nueva evidencia parcial o ilegible exige otra reconciliación, no una conclusión positiva.

## QA, no alcance y reversión

**AC-01 de #2226:** contraste de identidad contra `main` exacto (Issue #1865, checklist, #1952, PR #1967, blobs del auditor/test y declaraciones OWNER) y separación de lo ya ejecutado frente a lo pendiente. **AC-02 de #2226:** mapeo explícito de `UNKNOWN`, deduplicación y puerta humana. Los dos AC de esta **hoja** remiten al check `Tests de scripts`; para fusionar su PR también se necesita `Validar` terminal verde sobre HEAD exacto y las guardas de D-069. Este archivo **no proclama** que hayan ocurrido esos checks o una nueva auditoría real.

Roles **ingeniería de software / QA**: un único documento, sin cambiar contratos del script; negativos conservados (`UNKNOWN`, fallo de DNS de entorno, ausencia de acuse, snapshot caducado); mapeo condición→evidencia y reversión simple por squash-revert. No aplica E2E de aplicación: no se modifica API, persistencia, UI, red ni software operativo. Sin secretos, gastos, cambios de DNS/TLS, uso de datos de clientes, releases, publicación, go-live o actos en nombre del dueño.

**Reversión:** revertir solo `docs/epic-evidence/1865-mapeo.md`. En ningún caso el merge de #2226 cierra #1865 o acredita FSP-11.
