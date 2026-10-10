# Política de revisor externo cuando se agota la capacidad

La revisión externa sigue siendo el camino normal. Este fallback existe únicamente para evitar que una limitación de capacidad del reviewer detenga indefinidamente trabajo ya validado durante la fase `construccion`.

## Cuándo puede aplicar

La policy solo acepta el fallback cuando se cumplen **todas** estas condiciones:

1. La fase canónica leída desde `datos.yml` de la **BASE exacta** del PR es `construccion`.
2. Existe evidencia de rate limit del reviewer requerido asociada al **HEAD exacto**.
3. Sobre ese mismo HEAD existe un fallo de `Factory policy / Validar decisiones y límite de revisión`.
4. Existe un reintento posterior verificable.
5. Los demás gates obligatorios observados sobre ese HEAD están terminales y verdes: CI, pruebas/aceptación, Sonar, CodeQL, Coordinación y Privacidad.
6. No existe ningún thread abierto/no resuelto del reviewer requerido ni un `CHANGES_REQUESTED` sobre el HEAD exacto.

Un único rate limit sin reintento verificable nunca basta.

### Cómo acreditar el reintento sin aceptar causalidad supuesta

**Compatibilidad endurecida (Factory #1064 / #1072):** el camino histórico que
aceptaba dos comentarios separados `Review rate limited` alrededor de un
`Factory policy` fallido en el primer intento queda **denegado**. Aunque los
dos mensajes sean del bot real y mencionen el SHA, su orden no acredita por
sí solo un comando de reintento OWNER ni un vínculo causal entre ese comando,
la respuesta y el HEAD. El primer intento debe fallar cerrado si solo ofrece
esta secuencia. No se modifica la vía principal de revisión formal exact-HEAD.

CodeRabbit también puede **reutilizar y editar el mismo comentario canónico** en vez de crear un segundo comentario. Para ese caso, la policy exige una cadena más explícita:

1. Policy falla sobre el HEAD exacto;
2. el `OWNER` del repositorio publica exactamente `@coderabbitai review` después de ese fallo;
3. el comentario del reviewer requerido se actualiza después de ese trigger y contiene una señal terminal de capacidad (`Review rate limited` o `Review limit reached`);
4. el body actualizado contiene el SHA completo del HEAD exacto;
5. `updated_at` es posterior al trigger y no puede ser anterior a `created_at`.

El simple hecho de que un comentario del bot tenga un `updated_at` reciente **no** cuenta como reintento. Sin el trigger OWNER posterior al fallo de Policy, el fallback permanece bloqueado. Un usuario no OWNER tampoco puede producir esa evidencia.

### Respuesta CodeRabbit sin SHA: timeline autenticada no prueba causalidad

En un **rerun** (`GITHUB_RUN_ATTEMPT > 1`) durante `construccion`, CodeRabbit
puede emitir una respuesta `Review rate limited` sin el SHA en el cuerpo.
Ese texto, por sí solo, **no constituye revisión ni permite fallback**.

El reusable consulta directamente la timeline REST del **mismo PR** mediante
`github.token`, con permisos de lectura, 100 eventos por página, máximo 500
eventos y 2 MB; una sexta página solo puede estar vacía. El archivo temporal
se elimina al terminar. Ningún contenido del PR candidato determina esa
lectura. Antes de aceptar el resultado se vuelven a consultar HEAD y BASE.

El validador inspecciona estas **condiciones necesarias pero insuficientes** para descartar evidencia temporal inconsistente:

1. La timeline está completa, contiene un último evento `committed` cuyo SHA
   es el HEAD exacto y no registra force-push ni una mutación ambigua de HEAD.
   Los eventos `committed` no contienen `created_at`: se usa el **orden
   auténtico de eventos**, sin inventar timestamps.
2. Existe un primer comentario de **`coderabbitai[bot]` real**, con
   `user.type=Bot`, `actor.login` concordante, ID y cuerpo idénticos a
   `issues/{PR}/comments`, informando rate-limit después de ese HEAD.
   Se exige `updated_at == created_at`: un rate-limit inicial editado, o
   sin timestamp de integridad, no demuestra que ese texto ya existiera.
3. Más tarde, un comentario **`OWNER`** con el cuerpo literal
   `@coderabbitai review`, tipo `User` e identidad concordante solicita
   otro intento en el mismo HEAD. Tanto la ruta con SHA como la SHA-less
   exigen `updated_at == created_at` para este trigger: un comentario
   editado o sin timestamp verificable nunca acredita una petición.
4. Una **segunda respuesta distinta** del bot, posterior a ese comando y
   emitida como máximo 120 segundos después, vuelve a informar rate-limit.
   Todos los comentarios de la secuencia se cotejan por ID, actor, texto y
   timestamp con los comentarios REST autenticados del mismo PR.
5. Entre la primera respuesta rate-limited y el comando del OWNER existe
   un check `Factory policy / Validar decisiones y límite de revisión` en
   estado `completed/failure`, sobre el mismo HEAD exacto. Un rerun de Actions
   por sí solo no acredita este fallo; se exige también en el camino con SHA.
6. No hay otro comando literal `@coderabbitai review` ni
   `@coderabbitai full review` de un usuario competidor entre OWNER y la
   segunda respuesta del bot, aunque sea MEMBER. Ambos pueden disparar
   otra revisión; eventos legítimos de `mentioned` no invalidan la secuencia.
7. La segunda respuesta del bot tiene `updated_at == created_at`; un texto
   editado o sin timestamp de integridad verificable falla cerrado.
8. No hay `committed`, `head_ref_force_pushed` ni `synchronize` que
   invalide la secuencia; los demás checks exact-HEAD siguen verdes, sin
   `CHANGES_REQUESTED` ni threads abiertos.

**La timeline REST no incluye un vínculo autenticado e inequívoco entre el
comando OWNER, el comentario de respuesta del bot y el HEAD/ref durante toda
la ventana.** Dos historias (respuesta a OWNER o respuesta independiente de
otra invocación) pueden producir exactamente los mismos registros. Tampoco
la ausencia de eventos de mutación prueba una historia íntegra de ref.
Por ello, **el fallback SHA-less falla cerrado incluso cuando se cumplen
las ocho comprobaciones temporales anteriores**. La presencia de un marker
de invocación opaco del bot no constituye un enlace al comando OWNER.

Una sola respuesta, solicitud competidora, respuesta editada, ausencia de fallo
previo de Policy, actor no OWNER, bot falsificado, timeline vacía, truncada,
ambigua, reescrita, en otro HEAD o una carrera de refs también fallan cerrado.
La revisión formal exact-HEAD y el fallback con SHA explícito siguen sujetos
a sus propios criterios y checks. `live` nunca admite la excepción.
No se modifica `Factory@v1` ni se autoriza go-live, publicación o merge
por esta evidencia.

## Qué no permite

- No permite cambiar el HEAD para provocar otra ronda.
- No permite ignorar findings abiertos ni un `CHANGES_REQUESTED` del reviewer sobre el HEAD exacto.
- No permite pasar con CI, pruebas, Sonar, CodeQL, Coordinación o Privacidad en rojo.
- No permite activar el fallback cuando la fase es `live`.
- No cambia el límite de rondas de reviewers ni elimina la obligación de revisión externa antes de live.
- No permite convertir cualquier edición de comentario en evidencia: el retry OWNER, el orden temporal y el HEAD exacto siguen siendo obligatorios.

Si la fase no puede leerse de forma canónica desde la BASE, el fallback queda deshabilitado y la policy conserva el comportamiento estricto.

## Evidencia que deja

Cuando aplica, el workflow deja evidencia **read-only** en el summary y en un notice del run con:

- el SHA exacto;
- la hora del reintento rate-limited o de la actualización terminal del comentario canónico;
- el enlace al comentario del reviewer;
- una advertencia explícita de que la revisión externa sigue siendo obligatoria para `live`.

El fallback no publica, edita ni elimina comentarios del reviewer. Así el reusable conserva el mismo permission envelope de los callers históricos: `contents: read` + `pull-requests: read`.

## Modelo de seguridad

La fase se lee desde la **BASE exacta**, no desde el código candidato. Así un PR no puede habilitar su propio fallback cambiando `datos.yml`.

Los check-runs usados como evidencia se consultan por HEAD exacto mediante `gh api`, autenticado exclusivamente con el `github.token` ya disponible en el job y sin exponerlo en logs. La lectura está paginada y acotada a un máximo de **5 páginas / 500 check-runs**: `total_count` debe ser entero, permanecer idéntico en todas las páginas, la cantidad agregada observada debe coincidir exactamente con ese total y los IDs no pueden repetirse. Cada página y la evidencia agregada conservan límites de tamaño. Error de API, JSON inválido, total inconsistente, evidencia incompleta, IDs duplicados, payload excesivo o más de 500 check-runs fallan cerrado. El propio check de policy y el agregado circular `Validar` no se usan para decidir si los demás controles están verdes.

La lectura de reviews, comentarios, BASE exacta y reviewThreads continúa usando únicamente permisos read-only. El fallback no eleva el token del caller.

Cualquier ambigüedad —fase ausente, demasiados check-runs/threads para evaluar de forma acotada, evidencia malformada, HEAD distinto, trigger no OWNER, secuencia temporal incoherente o finding abierto— falla cerrado.


## Bridge inmutable exact-SHA

El reusable `politica.yml` mantiene compatibilidad histórica con `factory_ref: v1` como valor por defecto. Un consumidor build-ahead puede fijar temporalmente la implementación interna de Factory a un commit inmutable sin mover `Factory@v1`:

```yaml
with:
  pr_number: ${{ github.event.pull_request.number }}
  factory_ref: 0123456789abcdef0123456789abcdef01234567
```

El bridge acepta únicamente:

- `v1`, para conservar el canal estable histórico;
- un SHA lowercase exacto de 40 caracteres hexadecimales.

`main`, nombres de branches, tags arbitrarios, SHAs cortos, mayúsculas o refs malformados fallan cerrado **antes** del checkout interno de `pl0n3r/factory`.

El input solo selecciona el `ref` del checkout interno en `.factory`; no cambia permisos, eventos, semántica de Policy, reviewer requerido ni autoridad de publicación. El caller sigue usando el mismo `github.token` read-only. Usar un SHA exacto no publica ni mueve `Factory@v1`; únicamente permite validar un repair inmutable mientras la decisión de promoción del canal estable permanece separada.
