# Contrato común de administración de staff

D-060 separa dos dominios: **ControlBot administra staff/administración** y cada producto administra a sus clientes finales. Este contrato es un límite de arquitectura; no concede a ControlBot acceso a compradores, tenants, usuarios públicos ni credenciales humanas.

## Superficie permitida

| Método | Ruta | Efecto |
| --- | --- | --- |
| GET | `/ops/staff?q=&cursor=&limit=` | Busca staff; devuelve nombre, correo enmascarado, rol, estado y último acceso. |
| POST | `/ops/staff` | Crea una invitación con nombre, email y rol permitido. El producto envía el enlace. |
| POST | `/ops/staff/{id}/suspend` | Suspende sin borrar físicamente. |
| POST | `/ops/staff/{id}/reactivate` | Reactiva una cuenta suspendida. |
| POST | `/ops/staff/{id}/role` | Cambia solo a un rol de staff admitido por el producto. |
| POST | `/ops/staff/{id}/password-reset` | Pide al producto que envíe su flujo de recuperación. |
| GET | `/ops/summary` | Devuelve conteos agregados: activas, suspendidas y fallos recientes. |

No existen operaciones de clientes finales, exportación masiva ni `DELETE /ops/staff`. ControlBot nunca define, recibe ni devuelve contraseñas, hashes, tokens de invitación, tokens de reset, cookies o códigos 2FA.

La búsqueda exige `q` de 2–120 caracteres, usa cursor; `limit` por defecto es 25 y nunca supera 100. El producto puede aplicar límites más bajos.

## Autenticación y anti-replay

Cada producto usa una clave revocable distinta, almacenada fuera del repositorio. Si no hay clave o allowlist configuradas, la superficie `/ops` permanece deshabilitada.

Cada petición incluye:

- `X-Factory-Key-Id`
- `X-Factory-Timestamp` (Unix UTC; desviación máxima 300 s)
- `X-Factory-Nonce` (aleatorio, al menos 128 bits)
- `X-Factory-Signature`

Firma: HMAC-SHA256 sobre:

```text
KEY_ID
METHOD
PATH_WITH_SORTED_QUERY
TIMESTAMP
NONCE
SHA256(BODY)
```

La comparación de firma es constante. El producto conserva por clave el nonce (o su hash) al menos 600 s y rechaza su reutilización. La allowlist de origen es un control adicional; nunca se reemplaza por `*` para “hacer funcionar” la integración. Rate limiting debe cubrir como mínimo `key_id` y origen.

## Autorización y auditoría

El producto conserva la decisión final: valida roles permitidos y puede rechazar cualquier acción. Toda acción registra `action`, identificador de clave, staff objetivo, resultado, timestamp y request id. Nunca registra secretos, firma, body crudo, password ni token.

Errores mínimos:

- `401`: clave/firma/timestamp inválidos o integración deshabilitada.
- `403`: origen o rol no permitido.
- `409`: nonce reutilizado o conflicto de estado.
- `422`: payload/cursor inválido.
- `429`: límite excedido.

Las respuestas de error no revelan existencia de cuentas fuera del scope autorizado ni material criptográfico.

## Privacidad

La especificación portable vive en `template/ops/admin-staff-api.json`. Al activar la integración, el producto copia los tratamientos declarados allí a su `datos.yml`, ajustándolos solo a datos que realmente procese. Durante `construccion`, base, consentimiento y responsable permanecen en revisión/placeholder según el contrato de privacidad de Factory.

Un cambio de finalidad, una categoría sensible o un proveedor nuevo sigue requiriendo la puerta legal vigente antes de salir a `live`. Esta especificación no inventa base legal, consentimiento, plazo legal ni proveedor.

## Implementación

El template entrega **contrato + test**, no un endpoint funcional genérico. Cada producto implementa el adapter en su stack, conserva sus reglas de roles y auditoría, y prueba casos negativos: firma alterada, timestamp vencido, nonce repetido, origen no permitido, rol inválido, ausencia de clave y payload sobredimensionado.
