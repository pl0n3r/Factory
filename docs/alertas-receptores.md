# Receptores configurables de alertas · contrato offline v1

La fuente `alertas/receptores.yml` es **JSON compatible con YAML 1.2**. Esta
restricción permite validación Python 3 sin dependencias externas. El esquema
`alertas/receptores.schema.json` documenta forma, límites y campos obligatorios.
La selección es **solo lectura**: no envía avisos, no consulta GitHub, no lee
variables de entorno ni secretos, no altera la fase `construccion` y no afirma
que una alerta haya sido entregada.

Cada entrada requiere `id` (único), `nombre` público, `canal`, `secreto_ref`
(**nombre** de un secreto privado, nunca su valor), `repos`, `gravedades`,
`activo`, `desde` y `hasta`. `desde` es UTC `YYYY-MM-DDTHH:MM:SSZ` inclusivo;
`hasta` es exclusivo o `null`. `repos` admite uno o más nombres exactos de los
siete repositorios autorizados, o `"*"` **solo**, para todos los siete. La
gravedad es `info`, `warning` o `critical`. `canal` puede ser `github`, `email`,
`sms` o `webhook`; la autorización real de cada canal es independiente.

Inicialmente solo se selecciona la identidad pública `pl0n3r`; la referencia
`FACTORY_ALERT_OWNER_DESTINATION` es un **identificador**, no un secreto
configurado ni una dirección existente. Ningún otro receptor queda habilitado.

Para añadir a alguien, crear una entrada con ID único, identificador público,
canal autorizado y nombre de secreto privado `FACTORY_ALERT_*` ya gestionado
fuera del repo. Restringir repos/gravedades y vigencia temporal. Para excluirlo,
poner `activo:false` o fijar `hasta` a un instante UTC pasado. No introducir
correos, teléfonos, URLs reales, tokens, claves ni datos personales en el repo.
Un receptor que no tenga permiso real de recibir alertas debe seguir inactivo;
este contrato por sí mismo nunca concede ese permiso.

Ejemplo de validación sin envío:

```sh
python3 scripts/alertas_receptores.py
python3 scripts/alertas_receptores.py --repo pl0n3r/Factory --gravedad critical --instante 2026-10-30T12:00:00Z
python3 -m unittest tests/test_alertas_receptores.py -v
```

Toda configuración inválida, ambigua o desconocida falla cerrada. El código no
expande `secreto_ref` ni puede transmitir destinos. Un squash revert elimina
estos cinco archivos y no cambia estado operativo, permisos o releases.
