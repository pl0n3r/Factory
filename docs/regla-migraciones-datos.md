# Regla común para migraciones de datos — Factory #1955

**Productos:** Condor, GrindFlow, brvtal y ControlBot. La regla es una puerta **pre-live**: no autoriza migrar datos, consultar bases reales, descargar copias, habilitar servicios, gastar ni desplegar. Los ejemplos y las pruebas son sintéticos; revertir el squash no modifica datos.

## Secuencia por cada migración

1. **Copia verificada previa.** Antes de modificar datos, conservar un recibo autenticado del respaldo del ambiente de origen con identificador único, fecha UTC, SHA-256 del artefacto, verificación efectiva de integridad y procedimiento de recuperación. Un archivo ZIP o un campo `verified` no prueba por sí solo la existencia ni autenticidad del backup. Evidencia ausente: **NO_GO**.
2. **Ensayo en copia local aislada.** Restaurar exclusivamente una copia autorizada y minimizada en entorno local aislado, sin conexión a producción. Registrar identificador de copia, `rows_before`, `rows_after` y resultado. Comprobar integridad, esquema, índices y restricciones; justificar cualquier variación de conteos.
3. **Plan de reversión por migración.** Fijar de antemano disparadores, forma de detener escrituras, método de recuperación, pasos ordenados, recibo de respaldo referenciado y comprobación posterior del conteo y de integridad. Considerar datos intermedios y ventanas autorizadas; si la vuelta atrás segura no está disponible, **NO_GO**.
4. **Puerta humana para live.** El contrato offline no concede autoridad de migrar datos reales: se requieren aprobación del propietario, revisión de privacidad/legal, respaldo real auténtico, ensayo aislado, restore probado y recibos del cambio. `CONTRATO_OFFLINE_COMPLETO` **NO ACREDITA** backup, restore, RPO/RTO, producción VERDE ni go-live. D-059 y D-066 siguen aplicando.

## Formato declarativo y verificador

La descripción JSON declara `schema_version: 1`, `project`, `migration_id` y tres componentes críticos. El verificador no ejecuta SQL ni backups:

- `verified_backup`: `receipt_id` no vacío, `sha256` de 64 hexadecimales minúsculos, `verified: true` y `verified_at_utc` no vacío.
- `local_rehearsal`: `environment: isolated_local_copy`, `copy_id` no vacío, `rows_before` y `rows_after` enteros no negativos, `passed: true`.
- `rollback_plan`: `backup_receipt_id` igual al recibo, `trigger` y `restore_method` no vacíos, lista no vacía `steps`, `verification.expected_rows` igual a `rows_before` y `verification.method` no vacío.

Ejemplo **ficticio**, no apto como evidencia de recuperación real:

```json
{
  "schema_version": 1,
  "project": "Condor",
  "migration_id": "fixture-1955",
  "verified_backup": {
    "receipt_id": "fixture-backup-001",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "verified": true,
    "verified_at_utc": "2026-10-30T00:00:00Z"
  },
  "local_rehearsal": {
    "environment": "isolated_local_copy",
    "copy_id": "fixture-copy-001",
    "rows_before": 12,
    "rows_after": 14,
    "passed": true
  },
  "rollback_plan": {
    "backup_receipt_id": "fixture-backup-001",
    "trigger": "fallo de integridad o error de migración",
    "restore_method": "restaurar copia verificada en entorno aislado",
    "steps": ["detener escrituras", "restaurar respaldo", "verificar integridad"],
    "verification": {"expected_rows": 12, "method": "conteo e integridad"}
  }
}
```

Desde el checkout de Factory, con descripción JSON en un directorio autorizado:

```bash
python3 tests/test_regla_migraciones.py --check-json /ruta/a/descripcion.json
python3 -m unittest -v tests.test_regla_migraciones
```

El primer comando devuelve estado 0 con `CONTRATO_OFFLINE_COMPLETO` si pasa el contrato estructural, o estado 1 con `RECHAZADO` si falta algo. **No** verifica firma del proveedor, calcula checksum real, lee bases, copias, tokens, secretos, perfiles ni red. El SHA-256 es un formato declarado, no una atestación. AC-01 apunta al método ejecutable `tests.test_regla_migraciones.ReglaMigracionesTests.test_criterio_principal` que ejercita las cuatro variantes y las ausencias.

## Reversibilidad

Solo se cambian `docs/regla-migraciones-datos.md` y `tests/test_regla_migraciones.py`. Revertir el squash elimina la regla y su comprobación sin alterar datos de productos; cualquier nueva operación live necesita autorización independiente.
