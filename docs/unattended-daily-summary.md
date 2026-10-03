# Resumen diario unattended para el dueño

Estado: **entrega GitHub-native, idempotente y fail-closed**.

## Canal y horario

La decisión humana A de Factory#768 fija el canal y la hora:

- destino: un comentario en Factory#768;
- hora: **08:00 America/Bogota**, equivalente a **13:00 UTC**;
- cron: `0 13 * * *`;
- no usa correo, mensajería externa, credenciales nuevas ni servicios de pago.

El workflow `.github/workflows/unattended-watchdog.yml` conserva además el watchdog cada 15 minutos. El evento diario tiene un job separado; el evento `*/15` sigue ejecutando únicamente el watchdog.

## Fuente y semántica

`scripts/unattended_daily_summary.py` reutiliza las primitives ya integradas de #769:

1. carga la configuración versionada del watchdog;
2. recoge evidencia GitHub mediante `collect_github_input()`;
3. evalúa 4C mediante `evaluate_runtime()`;
4. añade contexto read-only de Issues abiertos/cerrados para decisiones, bloqueos y avances;
5. renderiza un resumen corto en español.

Cada hecho muestra `source`, edad y freshness cuando existe evidencia temporal. Si un dato no puede demostrarse, queda como **UNKNOWN**; si la evidencia excede su vigencia, queda **STALE**. No se usan timestamps de GitHub como heartbeat de agente.

Las cuotas de CI, GitHub API y cuentas de ChatGPT se muestran como `UNKNOWN` mientras Factory#584 no entregue una medición canónica al runtime. El resumen no inventa capacidad.

## Puerta pública D-043 de Condor

Antes de renderizar “Decisiones pendientes”, el resumen consulta únicamente la API
pública de comentarios de `pl0n3r/Condor#1`:

- método `GET`, sin header `Authorization`;
- `User-Agent` explícito y timeout de 3 segundos;
- máximo 3 páginas de 100 comentarios y cero retries internos;
- solo se confían comentarios de `github-actions[bot]` con el marker exacto
  `condor-d043-validation-card`;
- la versión visible, SHA de 40 hex y el comando
  `gh workflow run observar-release.yml` deben describir la misma identidad;
- una evidencia automática `VALIDATED_IN_PRODUCTION` elimina únicamente la
  tarjeta con la misma versión **y** SHA; una release posterior nunca cubre otra
  por inferencia;
- si quedan varias tarjetas pendientes, se muestra la versión más reciente y el
  número de anteriores aún pendientes.

La Fact resultante usa `source=Condor#1 public GitHub`, edad y freshness. Si la
API pública falla, el JSON es inválido, se agota el límite de páginas o un marker
canónico es ambiguo/inconsistente, el resumen muestra una Fact
`UNKNOWN`/`STALE` y continúa entregando las demás secciones.

Esta lectura no reutiliza `GH_TOKEN`, PAT, GitHub App ni ninguna credencial de
Factory. Tampoco ejecuta `observar-release.yml`, marca flags D-043, escribe en
Condor ni declara producción validada.

## Orden del resumen

El comentario prioriza, en este orden:

1. decisiones pendientes;
2. bloqueos;
3. avances;
4. alertas;
5. próximas acciones;
6. cuotas;
7. fuente principal.

Solo incidentes **S1/S2** califican como interrupción inmediata aparte. S3 y UNKNOWN permanecen en el resumen/flujo normal del watchdog y no se promocionan.

## Idempotencia

Cada comentario lleva un marker cerrado:

`<!-- factory-unattended-daily-summary {"local_date":"YYYY-MM-DD","version":1} -->`

Antes de escribir, el publicador recorre los comentarios existentes de Factory#768. Si ya existe un marker confiable de `github-actions[bot]` para la fecha local, no crea otro comentario.

Markers propios ambiguos o malformados fallan cerrado. Un comentario de otro autor no puede simular una entrega canónica.

## Kill switch y autoridad

Inmediatamente antes del `POST`, el publicador relee Factory#767 con el parser canónico. Cualquier estado que implique pausa produce **cero mutaciones**.

La entrega diaria:

- no reserva trabajo;
- no abre/cierra PRs;
- no despliega;
- no publica releases;
- no gasta;
- no cambia severidades;
- no concede autoridad nueva.

## Reversión

Revertir el cron/job diario y los tres artefactos de #768 retira la entrega. El watchdog de 15 minutos y 4B/4C siguen intactos. Los comentarios históricos se conservan como evidencia.
