# README Contract v2

README Contract v2 convierte el README en una **portada corta con enlaces y señales vivas**, no en una segunda base de datos ni en un tablero calculado por commits.

## Qué cambia

Contract v1 reservaba bloques para `Operational Cockpit` y `Progress + Readiness`. Cuando no llegaba evidencia, el generador escribía tablas completas con valores `UNKNOWN`. Como esas señales no tenían un productor vivo común, la portada terminaba mostrando ausencia de datos en lugar de información útil.

Contract v2 elimina esos bloques de los README migrados:

- no renderiza tablas de estado con placeholders;
- no renderiza `Progress + Readiness`;
- no calcula progreso ni readiness;
- no crea commits periódicos para refrescar una portada;
- conserva narrativa humana estable y enlaza las fuentes que ya son autoridad.

El motor `readme/progress_readiness.py` y sus schemas no cambian. Siguen disponibles como biblioteca para consumidores que tengan evidencia canónica, por ejemplo el Orquestador. Simplemente dejan de formar parte del README v2.

## Estado vivo

Un README v2 presenta solo señales que pueden actualizarse sin modificar `main`:

1. **GitHub Actions:** insignia del workflow principal sobre `main` y enlace a Actions.
2. **GitHub Releases:** insignia de la última release y enlace a Releases.
3. **`/health` público:** opcional. Se añade únicamente si el producto ya expone un endpoint público real. Puede presentarse con una insignia dinámica de Shields que consulte ese endpoint; nunca se inventa un valor alternativo.
4. **Orquestador de ControlBot:** enlace al detalle operativo global cuando se necesita más contexto.

Si una fuente opcional no existe, no tiene acceso público seguro o no puede demostrarse, **la señal se omite**. La ausencia de señal no significa cero progreso, mala salud, buena salud ni readiness desconocido. El README no tiene autoridad para inferir ninguna de esas cosas.

## Sin commits de refresco

Las insignias de GitHub/Shields se resuelven al visualizar la página. El README no ejecuta cron, no llama producción desde un generador y no hace commits automáticos para cambiar estado.

Esto evita que un cambio puramente visual mueva `main`, dispare de nuevo gates de release o cree ruido de historial.

## Narrativa humana

Se mantienen las once superficies del contrato durante la transición para no romper el check reutilizable:

1. Hero / Project Card.
2. Operational Cockpit.
3. Work Queue.
4. Qué hace el producto.
5. Arquitectura en 60 segundos.
6. Stack e infraestructura.
7. Ciclo de entrega.
8. Calidad y seguridad.
9. Roadmap y fuentes de verdad.
10. Desarrollo local.
11. Mapa de la fábrica.

En v2 deben ser breves. Issues, PRs, Releases, documentación profunda y el Orquestador conservan el detalle temporal.

## Transición v1 → v2

La migración es deliberadamente compatible:

- `contract.json.version` es `2`;
- el contrato conserva internamente la definición de los markers v1 como `legacy_v1_only`;
- `readme/validate_readme.py` acepta un README v1 mientras todavía contenga sus markers legados y lo valida con el generador v1 existente;
- un README sin esos markers se trata como v2 y debe usar fuentes vivas;
- no se retira la compatibilidad v1 hasta que todos los consumidores hayan migrado con sus propios PR.

Así, actualizar Factory no invalida de golpe Condor, GrindFlow, BRVTAL, FactoryRunner, ControlBot o AutoFactory.

## Reglas del validador v2

Un README v2 falla cerrado si:

- conserva markers o tablas legadas de estado/progreso;
- intenta volver a renderizar `Progress + Readiness`;
- el contrato permite commits de refresco;
- no enlaza GitHub Actions o GitHub Releases;
- no conserva el enlace al Orquestador para el detalle operativo.

El `/health` es opcional porque no todos los repos lo exponen de forma pública. Cuando exista, su URL debe ser pública, no contener secretos y representar el estado real del propio producto.

## Fuentes permitidas

Contract v2 reconoce estas clases de fuente:

- `github_actions`;
- `github_releases`;
- `public_health` (opcional);
- `controlbot_orchestrator` (opcional para detalle).

No son fuentes válidas para la portada: estimaciones inventadas, porcentajes manuales de progreso, snapshots sin provenance, secretos, credenciales, datos privados ni resultados derivados por un commit automático del README.

## Reversión

La reversión es un `revert` del cambio de contrato. Los consumidores que todavía estén en v1 siguen validados durante toda la transición. Un README nunca se convierte en fuente canónica de estado, por lo que revertir su presentación no modifica la realidad operativa.
