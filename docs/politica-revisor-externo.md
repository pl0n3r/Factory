# Política de revisor externo cuando se agota la capacidad

La revisión externa sigue siendo el camino normal. Este fallback existe únicamente para evitar que una limitación de capacidad del reviewer detenga indefinidamente trabajo ya validado durante la fase `construccion`.

## Cuándo puede aplicar

La policy solo acepta el fallback cuando se cumplen **todas** estas condiciones:

1. La fase canónica leída desde `datos.yml` de la **BASE exacta** del PR es `construccion`.
2. El reviewer requerido publicó una respuesta `Review rate limited` **después del timestamp del commit HEAD exacto**; respuestas anteriores al HEAD vigente no cuentan.
3. Sobre el mismo HEAD exacto existe después un fallo de `Factory policy / Validar decisiones y límite de revisión`.
4. Existe un reintento posterior y el reviewer vuelve a responder `Review rate limited`.
5. Los demás gates obligatorios observados sobre ese HEAD están terminales y verdes: CI, pruebas/aceptación, Sonar, CodeQL, Coordinación y Privacidad.
6. No existe ningún thread abierto/no resuelto del reviewer requerido.

Un único rate limit nunca basta.

## Qué no permite

- No permite cambiar el HEAD para provocar otra ronda.
- No permite ignorar findings abiertos ni un `CHANGES_REQUESTED` del reviewer sobre el HEAD exacto.
- No permite pasar con CI, pruebas, Sonar, CodeQL, Coordinación o Privacidad en rojo.
- No permite activar el fallback cuando la fase es `live`.
- No cambia el límite de rondas de reviewers ni elimina la obligación de revisión externa antes de live.

Si la fase no puede leerse de forma canónica desde la BASE, el fallback queda deshabilitado y la policy conserva el comportamiento estricto.

## Evidencia que deja

Cuando aplica, el workflow deja evidencia **read-only** en el summary y en un notice del run con:

- el SHA exacto;
- la hora del reintento rate-limited;
- el enlace al comentario del reviewer;
- una advertencia explícita de que la revisión externa sigue siendo obligatoria para `live`.

El fallback no publica, edita ni elimina comentarios del PR. Así el reusable conserva el mismo permission envelope de los callers históricos: `contents: read` + `pull-requests: read`.

## Modelo de seguridad

La fase se lee desde la **BASE exacta**, no desde el código candidato. Así un PR no puede habilitar su propio fallback cambiando `datos.yml`.

Los check-runs usados como evidencia se consultan por HEAD exacto mediante el endpoint REST público de GitHub **sin credenciales**. Este transporte se admite únicamente para repositorios públicos: error de red, HTTP distinto de 200, JSON inválido, payload excesivo o demasiados check-runs fallan cerrado. El propio check de policy y el agregado circular `Validar` no se usan para decidir si los demás controles están verdes.

La lectura de reviews, comentarios, BASE exacta y reviewThreads continúa usando únicamente permisos read-only. El fallback no eleva el token del caller.

Cualquier ambigüedad —fase ausente, demasiados check-runs/threads para evaluar de forma acotada, evidencia malformada, HEAD distinto o finding abierto— falla cerrado.
