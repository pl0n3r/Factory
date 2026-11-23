# Factory #305: mapeo canónico de Backup & Recovery

> Hoja de mapeo [Factory #2197](https://github.com/pl0n3r/Factory/issues/2197). **No es una certificación de recuperación, un permiso de live ni una orden de provisionamiento.**  
> Corte de lectura de fuentes: `Factory/main@0fe52fa409529700ef05a7ffaac50cef398c4a6e` (23-11-2026). La evidencia de CI del PR corresponde exclusivamente a su HEAD cuando quede terminal; este documento no la predice.

## Fuente de verdad, restricciones y límites

- [Épica #305](https://github.com/pl0n3r/Factory/issues/305): contrato 3-2-1-1-0, RPO/RTO y restauraciones verificables. Continúa **OPEN / estado: bloqueado** para recuperación real. Sus cuatro AC apuntan al check genérico `Tests de scripts`, que no acredita operación productiva por sí solo.
- [`decisiones.yml`](../../decisiones.yml), **D-066 active**, y [decisión OWNER #683](https://github.com/pl0n3r/Factory/issues/683): no provisionar Backblaze B2 ni operar backups reales hasta orden explícita, separada, del propietario para live. La aprobación de diseño/drills sintéticos está [registrada en la épica](https://github.com/pl0n3r/Factory/issues/305#issuecomment-6528213736); la prohibición de gasto autónomo figura en [FSP-18](https://github.com/pl0n3r/Factory/issues/305#issuecomment-6528281927).
- [`recovery/contract.py`](../../recovery/contract.py), [`recovery/status.py`](../../recovery/status.py) y [`docs/ops/factory-backup-preflight.md`](../ops/factory-backup-preflight.md) implementan contratos y un ensayo **local con bytes sintéticos**. Sin recibos auténticos de backup y drill por proyecto, el estado de recuperación operativa es **UNKNOWN**, nunca `HEALTHY` o `VALIDATED_IN_PRODUCTION`.
- [`scripts/epic_closure_leaves.py`](../../scripts/epic_closure_leaves.py) genera esta **hoja candidata de mapeo** y deduplica por `factory-epic-closure`. La indicación `factory-epic-splitter` del issue se aplica únicamente a **brechas técnicas autónomas nuevas y demostradas**, con aceptación verificable; no se usa para generar hojas de decisión humana.

## Matriz de aceptación de la épica

| AC de #305 | Evidencia comprobada en la fuente canónica | Resultado del mapeo | Falta para declarar aceptación |
| --- | --- | --- | --- |
| **AC-01** Contrato offline con 12 criterios | Módulos `recovery/{contract,pipeline,drill,status}.py`, tests [`test_cobertura_factory_48.py`](../../tests/test_cobertura_factory_48.py) y [preflight sintético](../ops/factory-backup-preflight.md). La [entrega #2077](https://github.com/pl0n3r/Factory/issues/2077) se integró por [PR #2078](https://github.com/pl0n3r/Factory/pull/2078), squash `29a72d767f09727952e85733171f576762932474`. La épica documenta **12 criterios offline**; no se reasigna un resultado de test histórico al HEAD de este PR. | **Código/ensayos offline presentes**, no equivalen a restore externo. | CI `Tests de scripts`/revisión de aceptación terminal en HEAD exacto y prueba de cada criterio si se pretende marcarlo. |
| **AC-02** Trece criterios de recuperación real | [Épica #305](https://github.com/pl0n3r/Factory/issues/305) y [preflight](../ops/factory-backup-preflight.md) diferencian expresamente **13 controles operativos no acreditados** de los ensayos sintéticos. No se presentó recibo auténtico por proyecto de copia externa inmutable + restore aislado ni mediciones RPO/RTO reales. | **UNKNOWN: falta evidencia operativa verificable**. Nunca inferir incumplimiento o éxito de una ausencia de observación. | Después de decisión y acceso autorizado: recibos verificables por proyecto (copias 3-2-1-1-0, retención/inmutabilidad, cifrado y checksum, restore aislado, RPO/RTO medidos, salud/smoke y fechas/SHA). |
| **AC-03** Orden explícita del propietario | [D-066](../../decisiones.yml) está `active`; [#683](https://github.com/pl0n3r/Factory/issues/683) reserva B2 real para una orden específica del OWNER; [comentario FSP](https://github.com/pl0n3r/Factory/issues/305#issuecomment-6528213736) solo autoriza ejercicios sintéticos. | **Puerta humana pendiente**, no sustituible por CI, una orden genérica al agente o el estado de esta hoja. | Decisión OWNER independiente para live/B2, alcance por proyecto, presupuesto/proveedor, custodio, privacidad, operador y procedimiento seguro. No inferir una autorización ausente de los registros inspeccionados. |
| **AC-04** `Tests de scripts` sobre HEAD exacto | Existe el contrato de check `Tests de scripts` en la épica. La presente hoja requiere además `Validar` según protección de `main`. | **Sin atribución automática a esta hoja**: los checks solo acreditan el SHA en que se ejecutaron; un resultado anterior de `main` o de otro PR no se traslada. | CI terminal verde sobre el commit definitivo y demás gates de D-069. |

## Descomposición técnica sin duplicados

El trabajo técnico *pre-live* ya tiene hojas canónicas con contratos ejecutables y rutas diferenciadas:

| Hoja | Entrega/artefacto que se verifica contra `main` | Alcance y frontera |
| --- | --- | --- |
| [#1088](https://github.com/pl0n3r/Factory/issues/1088) (CLOSED/completado) | [`recovery/manifests/`](../../recovery/manifests/), validación de esquema y objetivos declarados | Objetivos `DECLARED_NOT_MEASURED`; no RPO/RTO observado |
| [#1089](https://github.com/pl0n3r/Factory/issues/1089) (CLOSED/completado) | [`recovery/gdrive_adapter.py`](../../recovery/gdrive_adapter.py) y tests de transporte falso | Adaptador de copia fría, sin proveedor/credenciales reales |
| [#1090](https://github.com/pl0n3r/Factory/issues/1090) (CLOSED/completado) | [`recovery/media_manifest.py`](../../recovery/media_manifest.py) y [`recovery/encryption.py`](../../recovery/encryption.py) | Manifiesto y cifrado con pruebas sintéticas/llaves falsas |
| [#2077](https://github.com/pl0n3r/Factory/issues/2077) (CLOSED/completado) | [PR #2078](https://github.com/pl0n3r/Factory/pull/2078) MERGED; [ensayo de copia y restore local](../ops/factory-backup-preflight.md) | Corrupción rechazada, SHA-256 y duración local; **no** copia externa ni RTO operativo |

La hoja #2197 no crea duplicados de estas implementaciones ni inventa un nuevo trabajo técnico. Si aparece una **brecha de código independiente y reproducible** tras examinar una evidencia operativa autorizada, entonces sí procede descomponerla mediante el protocolo `factory-epic-splitter`, con aceptación ejecutable, dependencias, rutas/claims disjuntos y criterio de creación de issue de Factory #1289. Las dependencias que exijan dinero, proveedor/credenciales, tratamiento de datos reales, decisión de live o ejecución de restores reales **no** se transforman en leaves automáticas para eludir D-066.

## Pendientes del propietario y reentrada segura

1. **OWNER (no automatizable):** decidir de forma expresa y separada si autoriza fase live/backup real y el alcance de Backblaze B2, presupuesto, seguridad, custodio y operación. Mientras tanto, conservar #305 `OPEN/estado: bloqueado`.
2. **Operación autorizada, no ejecutada aquí:** establecer copias auténticas por producto y política 3-2-1-1-0, retención inmutable, cifrado y evidencia de checksums, con backup previo cuando aplique. Evitar secretos y datos personales en GitHub.
3. **QA operacional, no ejecutada aquí:** ejecutar restores aislados de copias auténticas, medir RPO y RTO contra objetivos aprobados, inspeccionar smoke/health y adjuntar recibos con identidad y tiempos verificables.
4. **Nueva reconciliación exacta:** solo con esos recibos y gates en verde revisar los 13 criterios de recuperación operativa, reabrir hojas técnicas *si existe una brecha nueva ejecutable* y evaluar cierre de #305. Evidencia ilegible o incongruente = **UNKNOWN**.

**Reversión del presente PR:** revertir únicamente el documento de mapeo. No modifica el runtime, decisiones, infraestructura, credenciales, datos, publicación, tags ni el estado de la épica.
