# Procedimiento de vuelta atrás de Factory@v1 — ensayo seguro

## Alcance y autoridad

La etiqueta mayor **v1** del repositorio pl0n3r/Factory es una ref protegida; no confundirla con tags semánticos inmutables como **v1.0.44**. **NO ejecutar sobre el repositorio real** los comandos de mutación de esta guía. La única autoridad para mover Factory@v1, aprobar el release o revertirlo es el dueño (OWNER), mediante su mecanismo administrativo autorizado, ruleset intacto y evidencia de las puertas de release. No se automatiza ningún cambio remoto ni se modifica main, DNS o live. El resultado del ensayo offline nunca equivale a un release.

Los comandos de cambio de refs siguientes usan exclusivamente una instancia Git creada con git init en un directorio temporal, sin remotos ni secretos. No usar git push --force, modificar permisos ni alterar tags semánticos.

## Inventario del SHA antes de mover

Para un movimiento real, el OWNER debe recopilar y aprobar en recibo privado fecha UTC, versión, puerta exacta del release, aprobación A correspondiente, main@SHA exacto, el **SHA del objeto de tag** y el **SHA pelado del commit** actual. En un tag anotado son diferentes. Son consultas solamente de lectura:

~~~sh
gh api repos/pl0n3r/Factory/commits/main --jq '.sha'
gh api repos/pl0n3r/Factory/git/ref/tags/v1 --jq '.object.sha'
git ls-remote --tags https://github.com/pl0n3r/Factory.git 'refs/tags/v1' 'refs/tags/v1^{}'
~~~

La revisión también exige el commit destino autorizado, CI factory, Sonar, CodeQL, compatibilidad de consumidores, ventana freeze y contratos del canal. Si falta una identidad, el SHA cambió, hay ventana vencida o la puerta no corresponde a ese commit/versión, detener la operación. La aprobación antigua de otra release no sirve.

## Procedimiento reservado al dueño

1. Fijar estado inicial OLD_TAG_OBJECT_SHA y OLD_PEELED_COMMIT_SHA, versión y SHA objetivo autorizado; comprobar que la referencia exacta sigue igual y que existe un recibo humano válido.
2. Obtener el objeto del tag candidato anotado y su commit pelado. No confundir el objeto Git con su commit, ni reutilizar un SHA sin cotejar identidad y procedencia.
3. Solicitar el movimiento exclusivamente mediante el mecanismo **administrativo autorizado** de GitHub y ruleset protegido, con compare-and-swap (CAS): solo aceptar el objeto original esperado. No hay ruta de escritura remota en esta guía; si el ruleset rechaza el movimiento, no forzar ni hacer bypass.
4. Verificar después objeto exacto y SHA pelado de refs/tags/v1, y validar channel-ready, self-test de ci.yml@v1, CI del candidato y compatibilidad de consumidores contra el SHA correspondiente. Los checks sin evidencia terminal no autorizan declarar publicación.
5. Si el cambio falla o hay regresión, detener la propagación. Devolver al objeto OLD_TAG_OBJECT_SHA **solo** con nueva autorización explícita del dueño y nueva CAS sobre el objeto realmente vigente; si cambió desde la última lectura, no sobrescribir. Verificar OLD_PEELED_COMMIT_SHA.
6. Conservar recibo con los SHA, aprobación, hora, evidencia terminal y estado. No cambiar main ni los tags semánticos. La restitución no debe declararse completa sin verificación real.

## Ensayo en repositorio falso

El único ensayo ejecutable es el unittest del repositorio. Usa git init en TemporaryDirectory, sin origin, sin credenciales y sin red. Crea dos commits falsos y dos objetos anotados. Ejecuta git update-ref sobre refs/tags/v1 **localmente**, proporcionando viejo y nuevo SHA (CAS). Registra los tres pasos como SIMULACRO LOCAL: 01-antes, 02-movido y 03-restaurado, con SHA completos de objeto y commit. Además prueba un CAS obsoleto que falla cerrado sin modificar el ref.

~~~sh
python3 -m unittest discover -s tests -p 'test_rollback_factory_v1.py' -v
~~~

Ejemplo explicativo **solo sobre el repositorio falso** ya creado por el test; nunca sustituir LAB_REPO por una ruta real:

~~~sh
LAB_REPO="<directorio-temporal-sin-remotos>"
OLD_TAG_OBJECT_SHA="$(git -C "$LAB_REPO" rev-parse refs/tags/v1)"
OLD_PEELED_COMMIT_SHA="$(git -C "$LAB_REPO" rev-parse 'refs/tags/v1^{commit}')"
TARGET_TAG_OBJECT_SHA="$(git -C "$LAB_REPO" rev-parse refs/tags/v1-lab-candidate)"
git -C "$LAB_REPO" update-ref refs/tags/v1 "$TARGET_TAG_OBJECT_SHA" "$OLD_TAG_OBJECT_SHA"
git -C "$LAB_REPO" rev-parse 'refs/tags/v1^{commit}'
git -C "$LAB_REPO" update-ref refs/tags/v1 "$OLD_TAG_OBJECT_SHA" "$TARGET_TAG_OBJECT_SHA"
test "$(git -C "$LAB_REPO" rev-parse 'refs/tags/v1^{commit}')" = "$OLD_PEELED_COMMIT_SHA"
~~~

El test valida además que no existe ningún remoto y que las operaciones Git apuntan siempre al directorio temporal. No tocar el ref real ni usar permisos o tokens productivos.

## Restauración y verificación

Una vuelta atrás es completa solo cuando el objeto anotado y el SHA pelado en refs/tags/v1 coinciden exactamente con el snapshot inicial, y el OWNER ha confirmado evidencia terminal de los consumidores. Si la CAS niega el movimiento o la verificación es incompleta, conservar NO_VERIFICADO y el contexto para diagnóstico; nunca reintentar forzadamente.

## Aviso a consumidores

Tras cada movimiento o devolución **real y autorizada**, avisar a Condor, GrindFlow, brvtal, ControlBot, AutoFactory y FactoryRunner: motivo, UTC, OLD_TAG_OBJECT_SHA, OLD_PEELED_COMMIT_SHA, SHA destino de objeto y commit, enlace a puerta y recibo, versión afectada, y resultados de workflows que consumen ci.yml@v1, health y smoke si aplica. Revalidar cada consumidor, sin asumir que un cambio de tag dispara CI automáticamente. El ensayo local no envía avisos.
