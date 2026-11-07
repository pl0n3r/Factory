# Factory — preflight de recuperación local sintética (FSP-02 / FSP-04)

Hoja hija Factory #2077 del contrato Factory #305. **Evidencia local, no evidencia operativa.** El propietario autorizó un ensayo local aislado con huellas SHA-256 y cronometraje (Factory #305, comentario `6528213736`). Este ensayo no utiliza Backblaze B2, terceros, cuentas, credenciales, datos personales ni respaldos de productos.

## Procedimiento reproducible

Ejecutar desde la raíz de Factory:

```bash
python3 -m unittest -v tests.test_factory_backup_preflight
```

`tests/test_factory_backup_preflight.py` efectúa realmente este recorrido con una fixture binaria fija y `tempfile.TemporaryDirectory`:

1. Escribe bytes **inventados** en un archivo temporal original y calcula su SHA-256.
2. Copia los bytes a **otro directorio local temporal**, verifica su SHA-256 y elimina el archivo original.
3. Comprueba que el original no existe y restaura desde la copia en un tercer directorio temporal aislado, **no desde el original**.
4. Valida el SHA-256 y los bytes del archivo restaurado contra los datos sintéticos. Mide la duración con reloj monotónico en nanosegundos.
5. Prueba adulteración de la copia: un hash diferente impide empezar la restauración y no deja archivo de destino.
6. El directorio completo desaparece al terminar. No persiste copias fuera del entorno de prueba.

## Recibo de ejecución local previa al PR

Ejecutado con Python 3, cuatro pruebas: **4/4 PASS**. Una ejecución adicional de la rutina produjo:

```text
scope=SYNTHETIC_LOCAL_ONLY
sha256=9c1fde1271134f24d9edf494a86c72f90ee41375ceb7079caa7ac1c4bad825f2
duration_ns=1632808
source_absent_before_restore=true
bytes_match=true
```

El valor `duration_ns` es una **medición local ilustrativa**, no un RTO certificado ni un objetivo de servicio. Cada ejecución mide su propia duración y el número puede variar según hardware y carga. No es válido deducir RPO real ni disponibilidad productiva de esta fixture.

## Límites y puertas pendientes

- **No se certifica 3-2-1-1-0**: la copia del ensayo no abandona el equipo, no usa medios diferentes, retención ni Object Lock.
- **No hay backup productivo**: no se consultan DB/media de productos, no se verifica cifrado externo ni existe prueba de recuperación de una copia real offsite.
- **No hay RPO/RTO operativo**: los objetivos no están aprobados y los tiempos aquí son locales y sintéticos.
- Factory `decisiones.yml` **D-066** permanece activa: Backblaze B2, backup/restore real y pasar a `live` exigen orden **separada, expresa y específica** del propietario; FSP-18 impide gasto automático.
- Los **13 criterios de recuperación real de Factory #305 permanecen sin acreditar**. Recovery se mantiene `UNKNOWN`, jamás `HEALTHY` ni `VALIDATED_IN_PRODUCTION` por esta prueba.
- El ensayo y este documento son reversibles con el squash revert de su hoja. No modifican `decisiones.yml`, `PLAN-AGENTES.md`, `docs/matriz-cobertura.md`, releases, tags o infraestructura.
