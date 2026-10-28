---
name: factory-deploy-rollback
description: Validación predeploy, migraciones seguras, health checks con versión y SHA, verificación postdeploy y rollback seguro para productos de la fábrica pl0n3r. Úsala al preparar, revisar o revertir un despliegue o release. Nunca ejecuta despliegues productivos por sí misma.
---

# Deploy y rollback

**Puertas duras (plan §0 y §7):** deploy/go-live, gasto, datos reales, SQL destructivo y borrado irreversible requieren autorización del dueño; Hostinger (D-059): backup previo registrado en el Issue antes de tocar DNS/BD/cron/despliegues. En pruebas y revisiones usa solo modo lectura/dry-run.

1. **Predeploy:** `main` en verde (`Validar` en el SHA exacto), versión/SHA a desplegar identificados, freeze #921 inactivo, kill switch `RUNNING`, backup verificado si hay migración.
2. **Migraciones:** aditivas y reversibles (expand → migrate → contract); sin `DROP`/`TRUNCATE`; probadas en base temporal; Condor D-054 permite aditivas con backup post-deploy.
3. **Health:** `/health` debe dar 200 con versión y SHA exactos (+ `schema_up_to_date: true` si aplica); home, login admin y panel sin 5xx; smoke/observador verde. Una etiqueta o tag no sustituye la observación productiva; `success` del workflow no es `VALIDATED_IN_PRODUCTION` (D-043).
4. **Rollback:** conserva el SHA/artefacto anterior; revierte con el mecanismo del repo (revert del squash o redeploy del tag previo); verifica de nuevo `/health` y smoke; no deshagas migraciones con pérdida de datos sin autorización.
5. Registra evidencia (SHA, hora, resultado) en el Issue; no hables de «listo» sin observación productiva.
