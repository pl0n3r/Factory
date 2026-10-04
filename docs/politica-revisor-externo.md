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

### Dos formas válidas de demostrar el reintento

El camino histórico sigue siendo válido cuando el reviewer crea comentarios separados:

1. comentario `Review rate limited` posterior al commit HEAD;
2. Policy falla sobre ese HEAD;
3. un segundo comentario rate-limited del reviewer aparece después del fallo.

CodeRabbit también puede **reutilizar y editar el mismo comentario canónico** en vez de crear un segundo comentario. Para ese caso, la policy exige una cadena más explícita:

1. Policy falla sobre el HEAD exacto;
2. el `OWNER` del repositorio publica exactamente `@coderabbitai review` después de ese fallo;
3. el comentario del reviewer requerido se actualiza después de ese trigger y contiene una señal terminal de capacidad (`Review rate limited` o `Review limit reached`);
4. el body actualizado contiene el SHA completo del HEAD exacto;
5. `updated_at` es posterior al trigger y no puede ser anterior a `created_at`.

El simple hecho de que un comentario del bot tenga un `updated_at` reciente **no** cuenta como reintento. Sin el trigger OWNER posterior al fallo de Policy, el fallback permanece bloqueado. Un usuario no OWNER tampoco puede producir esa evidencia.

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
