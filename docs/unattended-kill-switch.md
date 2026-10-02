# Kill switch global del modo desatendido

Este interruptor detiene **nuevo trabajo y nuevas mutaciones** de todos los agentes que siguen Factory. No mata procesos remotos que ya estuvieran ejecutándose.

Fuente pública canónica:

`https://api.github.com/repos/pl0n3r/Factory/issues/767`

## Estado

El Issue debe contener exactamente un marker:

`<!-- factory-unattended-kill-switch {"version":1,"state":"RUNNING","owner":"pl0n3r"} -->`

Estados válidos:

- `RUNNING`: no añade pausa; el resto de guardas 4B sigue aplicando.
- `PAUSED`: `global_pause=true`; no se inicia trabajo ni se muta GitHub.
- `UNKNOWN`: estado derivado localmente ante lectura fallida, fuente inesperada o marker inválido. Siempre pausa fail-closed.

## Pausar

Solo el dueño puede ordenar el cambio operativo. Con una instrucción explícita del dueño, edita **el único marker** del body de Factory#767 y cambia `state` de `RUNNING` a `PAUSED`. No cambies `version` ni `owner`.

Después del cambio, cualquier ciclo nuevo debe leer la URL exacta antes de comentar, reservar, crear branch/PR o escribir código. Si observa `PAUSED`, no muta nada.

## Reanudar

Solo el dueño puede ordenar la reanudación. Cambia el mismo marker de `PAUSED` a `RUNNING`. Un agente no reanuda por inferencia, timeout ni porque la causa original parezca resuelta.

`RUNNING` solo quita esta pausa global; no sobreescribe breakers, techos, fencing, gates humanos ni otras guardas.

## Lectura fallida o inválida

Si la URL no puede leerse, apunta a otro Issue/repositorio/autor, el marker falta o aparece más de una vez, o el JSON/version/owner/state no es válido:

1. deriva `UNKNOWN`;
2. trata `global_pause=true`;
3. realiza cero mutaciones;
4. informa una única línea al dueño con la razón auditable.

No intentes “reparar” el marker automáticamente.

La API del Issue expone `user.login` del **creador** del Issue. Esa señal ayuda a rechazar una fuente inesperada, pero **no demuestra quién hizo la última edición** del body. La regla “solo el dueño cambia el marker” sigue siendo una frontera de gobernanza y no debe presentarse como provenance técnica del último editor.

## Límite real

El kill switch es una puerta de admisión para cada ciclo. No cancela una llamada remota o proceso que ya comenzó antes de observar la pausa. Por eso cada ciclo debe comprobarlo **antes de la primera mutación** y volver a comprobarlo al iniciar el siguiente ciclo.
