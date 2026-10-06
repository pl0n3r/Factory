# Sonar CE superseded reports

Factory trata un `ce_task.status=FAILED` como fallo por defecto. Hay una excepción cerrada para un caso que Sonar declara explícitamente como obsoleto: un reporte de un commit viejo no puede procesarse porque ya se procesó un reporte más nuevo.

## Cuándo deja de bloquear

La excepción solo aplica si el mensaje completo coincide con la forma canónica observada por Sonar:

- identifica el commit del reporte rechazado con un SHA hexadecimal de 40 caracteres;
- afirma que un reporte más nuevo ya fue procesado;
- afirma que procesar reportes antiguos no está soportado;
- identifica el último commit procesado con otro SHA hexadecimal de 40 caracteres;
- no contiene texto extra fuera de esa forma.

En ese caso `quality/sonar.py` conserva el mensaje saneado como evidencia, devuelve `PASS` para la señal `ce_task` y usa la razón auditable `ce_task_superseded_by_newer_report`. Esto permite que `sonar-watch.py` cierre el Issue automático anterior únicamente cuando la señal está fresca y el resto de observables vigentes también se evalúan normalmente.

## Fail-closed

Cualquier otro `FAILED` conserva `FAIL/ce_task_failed`. También se mantiene el fallo si el texto es parecido pero ambiguo, falta alguno de los SHA canónicos, cambia la estructura del mensaje, o aparecen datos extra que impiden demostrar que el fallo fue solamente un reporte superseded.

La reconciliación no cambia Quality Gate, umbrales, TTL, cobertura ni deuda. Tampoco reintenta análisis, escribe en Sonar, modifica el repositorio observado ni cierra manualmente Issues sin una nueva evaluación fresca.
