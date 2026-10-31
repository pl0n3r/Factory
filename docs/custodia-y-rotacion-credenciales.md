# Custodia y rotación de credenciales — preparación sin secretos

**Estado:** procedimiento preparado en `construccion`; inventario **pendiente de verificación por el dueño en live**. Este documento no acredita que una cuenta, un factor o una clave estén configurados ni que se haya efectuado una rotación real. No guardar aquí contraseñas, códigos de respaldo, tokens, valores de llaves, identificadores sensibles ni capturas de configuraciones privadas.

## Inventario de custodia

Cada fila inventaría una **clase de acceso a verificar**, no confirma su existencia. Las columnas son la plantilla de custodia; las ubicaciones concretas, inventario verdadero y fecha de revisión los acredita exclusivamente el dueño en un registro privado durante el live. Se registra **solo la referencia del repositorio/sistema**, nunca la ruta del secreto ni su contenido.

| Clase de acceso o cuenta a verificar | Autoridad / custodio | Custodia (sin valores) | Última revisión | Comprobación pendiente |
| --- | --- | --- | --- | --- |
| Cuenta titular y permisos GitHub | Dueño | Registro privado del dueño; ubicación por confirmar | Pendiente: dueño / live | Verificar titular, recuperación y accesos delegados |
| Instalación GitHub App y sus permisos | Dueño | Registro privado del dueño; ubicación por confirmar | Pendiente: dueño / live | Verificar repositorios autorizados, alcance y permisos mínimos |
| Credenciales de automatización y GitHub Actions | Dueño | Almacén privado administrado por el dueño; ubicación por confirmar | Pendiente: dueño / live | Revisar vigencia, alcance, revocación y cuentas de servicio |
| Llaves de acceso a hosting y despliegue | Dueño | Almacén privado administrado por el dueño; ubicación por confirmar | Pendiente: dueño / live | Verificar propietario, acceso por servicio y mecanismo de rotación |
| Segundo factor (2FA) y códigos de recuperación | Dueño | Custodia privada del dueño; ubicación por confirmar | Pendiente: dueño / live | Comprobar métodos activos y capacidad de recuperación sin publicar detalles |
| Credenciales de DNS/TLS, proveedores y servicios externos | Dueño | Registro privado del dueño; ubicación por confirmar | Pendiente: dueño / live | Confirmar proveedores utilizados y accesos autorizados |

**Campos del recibo privado de revisión:** fecha UTC, sistema, identificador **no secreto**, responsable de revisión, resultado, siguiente revisión y referencia privada del recibo. La revisión del dueño se registra fuera del repositorio; aquí solo puede consignarse que sigue pendiente o que existe una referencia pública no sensible autorizada por el dueño.

## Procedimiento ante credencial comprometida

1. **Contener:** abrir incidente con hora UTC, sistema afectado, responsables y alcance estimado, sin copiar la credencial ni sus trazas. Suspender temporalmente la automatización que la use si es necesario y permitido.
2. **Revocar primero:** desde la consola oficial del proveedor, invalidar la credencial expuesta y sesiones derivadas cuando el proveedor lo permita. Verificar que la credencial antigua deja de autenticar. Si el orden revocar/emitir requiere continuidad, obtener autorización operativa y preservar el corte seguro; nunca permitir que la antigua siga vigente por comodidad.
3. **Generar nueva:** mediante la función oficial del proveedor, crear una credencial con permisos mínimos y caducidad apropiada. **No imprimir, copiar al Issue ni confirmar su valor**; restringir quién puede verla.
4. **Actualizar custodia privada:** registrar el cambio en el almacén autorizado del dueño. En consumidores que usan archivos privados (`NAME_FILE`), actualizar **solo el archivo privado autorizado y fuera del repositorio**; comprobar permisos de archivo y no volcar su contenido en logs. Este documento no ordena acceder ni modificar ningún secreto real.
5. **Verificar funcionamiento y revocación:** con prueba mínima autorizada, confirmar que la nueva credencial cumple exclusivamente el permiso requerido y que la antigua falla; inspeccionar ejecuciones y registros **redactados** sin valores. Ante fallo, deshabilitar la integración afectada y escalar, no restaurar una clave comprometida.
6. **Cerrar con evidencia:** registrar en el inventario privado el activo, responsable, hora UTC, evidencia de revocación/verificación, impacto, revisión de sesiones y siguiente fecha de revisión. Actualizar acciones preventivas (permisos, 2FA y monitoreo) sin introducir secretos al repositorio.

La rotación de una clave comprometida **no admite rollback a la clave anterior**. El rollback seguro es deshabilitar temporalmente la integración y emitir otra credencial limpia bajo autoridad del dueño. Se requiere autorización y backup según D-059 antes de mutaciones reales en hosting/DNS/despliegue; el gasto, go-live y cambios irreversibles no se delegan.

## Ensayo offline con credenciales ficticias

El caso `tests/test_custodia_rotacion.py::CustodiaRotacionTests::test_rotacion_ficticia_revoca_primero` ejecuta un simulacro sin GitHub, red ni proveedores. Usa los identificadores inventados `CLAVE_SIMULADA_ANTIGUA` y `CLAVE_SIMULADA_NUEVA` en un directorio temporal: primero marca la antigua como revocada, después escribe la nueva en un archivo privado **temporal**, comprueba que la anterior no autentica y que la nueva sí, y destruye el entorno temporal. Ninguno de esos identificadores es una credencial real ni permite acceso.

Comando local para repetir el ensayo:

```sh
python3 -m unittest discover -s tests -p 'test_custodia_rotacion.py' -v
```

**Resultado del ensayo:** el test constituye únicamente evidencia de la secuencia simulada; no valida el proveedor real, la custodia del dueño, 2FA, la revocación remota ni el estado `live`.

## Revisión pendiente del dueño antes de live

- Confirmar el inventario real, sin publicar valores ni nombres privados de cuentas, y firmar el recibo de revisión fuera de GitHub.
- Confirmar propietarios, factores 2FA, ubicaciones de custodia, responsables suplentes, periodos de revisión y la ruta de emergencia de cada proveedor.
- Ensayar el procedimiento autorizado contra cada proveedor en un entorno seguro; conservar la evidencia de verificación y sus accesos bajo custodia privada.
- No registrar un estado «revisado», «rotado» o «validado en producción» sin recibo auténtico del dueño.
