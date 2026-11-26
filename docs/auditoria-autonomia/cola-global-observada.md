# Censo global observado (#2221)

El cron existente ejecuta el observador local y, separadamente, un censo global GET-only con el mismo token de Actions y permisos de lectura. No crea un scheduler, ni una publicación, ni una reserva.

- Dos barridos de Factory, Condor, GrindFlow, brvtal, ControlBot, AutoFactory y FactoryRunner, con identidad de repositorio y filas, Link real, secuencia y proyección estable de #1104.
- Límite: 24 páginas por repositorio/barrido, 120 s de ventana monotónica, respuestas de hasta 2 MiB y cuota mínima de 20 % (también 1200 solicitudes si el límite es >=5000). Se comprueba cuota antes, durante y después. Solo URLs HTTPS canónicas construidas localmente; no redirects. Si GitHub devuelve un formato Link que #1104 no admite, se declara UNKNOWN, nunca se sigue o reescribe.
- Salida JSON tipada: SHA de política del checkout, scope, timestamps, agregados, fingerprints de proyecciones verificadas, writes=0, authority=unchanged y capacity=null. Sin datos personales, cuerpos/títulos, identificadores de usuario, secretos ni payloads crudos en stdout/summary.
- OBSERVED_GLOBAL_ONLY no es una fotografía atómica, no implica READY, NO_WORK, HEALTH ni orden ejecutable. UNKNOWN/DEFERRED no contienen conteos parciales; no promueven ausencia de evidencia a cola vacía. No se infieren causas de bloqueo.
- El token de Factory puede carecer de acceso a un consumidor: UNKNOWN, sin permisos adicionales ni escalada. Las pruebas son offline con fixtures sintéticos y no ejecutan al publicador mutante.

## Evidencia de operación

Pendiente del primer run horario real de `salud-cola.yml` en main después de integrar este cambio. No se ha ejecutado publicación ni se acredita una observación global real con el CI del PR. Registrar el run, SHA y resultado sanitizado cuando exista; esto no cierra #1082.
