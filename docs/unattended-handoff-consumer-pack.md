# Pack de conformidad del handoff desatendido v1

Estado: **read-only, consumer-neutral y offline**.

Este pack permite que ControlBot y FactoryRunner **interpreten** el handoff v1 ya
producido por Factory sin copiar ni recalcular el dispatcher, las guardas 4B o
el watchdog 4C. La única autoridad normativa sigue siendo:

- `config/unattended-handoff-v1.schema.json`;
- `tests/fixtures/unattended_handoff_v1/allow.json`;
- `tests/fixtures/unattended_handoff_v1/pause.json`;
- `tests/fixtures/unattended_handoff_v1/blocked.json`;
- `tests/fixtures/unattended_handoff_v1/unknown.json`.

El pack no añade runtime, red, persistencia, scheduler, polling ni mutaciones.

## Lectura canónica de estados

Un consumidor no vuelve a decidir nada. Solo proyecta el estado que ya viene
cerrado en el documento.

| Estado visible | Señal canónica | Interpretación permitida |
| --- | --- | --- |
| `ALLOW` | `action=ALLOW`, `freshness=fresh` | Señal read-only de que Factory no bloqueó el siguiente paso. |
| `PAUSE` | `action=PAUSE`, `freshness=fresh` | Pausa ya decidida por Factory; no crear trabajo nuevo. |
| `BLOCKED` | `action=BLOCKED`, `freshness=fresh` | Bloqueo ya decidido por Factory. |
| `UNKNOWN` | `action=BLOCKED`, `freshness=unknown` | Evidencia insuficiente/desconocida; tratar siempre como bloqueo. |

`UNKNOWN` **no** amplía el enum de `action` y nunca se convierte en `ALLOW`.
`next_transition` se consume tal como viene; no se deriva una transición nueva.

Los consumidores pueden mostrar `work_identity`, `work_class`, `reasons`,
`provenance`, `incidents` e `interrupt_owner` como evidencia. No deben usar esos
campos para recalcular ranking, prioridades 1–7, 4B, 4C, freshness ni autoridad.

## Matriz de compatibilidad

| Consumidor | Puede leer | No puede hacer |
| --- | --- | --- |
| ControlBot | Estado visible, evidencia, provenance, freshness e interrupt state. | Reservar, fusionar, desplegar, gastar, salir a live o reinterpretar Factory. |
| FactoryRunner | Estado visible y evidencia para validar compatibilidad antes de ejecutar un flujo propio autorizado. | Obtener autoridad desde el handoff, cambiar `BLOCKED→ALLOW`, reservar, fusionar, desplegar, gastar o salir a live. |

Ambos consumidores deben validar primero el documento contra el schema v1.
Versión desconocida, shape extra, contradicción o evidencia no conforme fallan
cerrado. El consumidor no intenta “arreglar” un documento inválido.

## Frontera de autoridad

El handoff conserva siempre:

- `authority=unchanged`;
- `permissions.reserve=false`;
- `permissions.merge=false`;
- `permissions.deploy=false`;
- `permissions.spend=false`;
- `permissions.live=false`.

Por tanto, incluso un documento `ALLOW` **no autoriza** reserva, merge, deploy,
gasto ni live. Es información de coordinación, no un capability token.

## Flujo de consumo

1. Leer un documento local.
2. Validarlo contra `config/unattended-handoff-v1.schema.json`.
3. Mostrar/proyectar `ALLOW|PAUSE|BLOCKED|UNKNOWN` usando únicamente
   `action` + `freshness` conforme a la tabla anterior.
4. Conservar provenance/reasons/incidents/interrupt state sin reinterpretarlos.
5. Mantener todos los permisos operativos denegados.

No hay llamadas a GitHub, ControlBot, FactoryRunner, producción ni proveedores.
La integración real de consumidores queda fuera de este leaf.
