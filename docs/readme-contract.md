# README Contract v1

README Contract v1 convierte el README en una **portada operativa**, no en una segunda base de datos. Define una anatomía común para los repos gobernados por Factory y reserva la generación automática a bloques delimitados cuya fuente real vive en otra parte.

## Límite del sistema

El contrato separa dos clases de contenido:

1. **Contenido humano estable:** propósito, arquitectura, stack, delivery, calidad, desarrollo y contexto.
2. **Contenido derivado:** señales operativas que pueden comprobarse contra una fuente canónica.

El generador de la fase ENGINE solo podrá modificar bloques declarados en `readme/contract.json`. Todo byte fuera de esos markers pertenece a la narrativa humana y debe preservarse.

## Anatomía común

Todo consumidor conserva estas once superficies informativas:

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

La anatomía es común; el branding, el tono y la profundidad siguen perteneciendo a cada proyecto.

## Metadata mínima

La metadata estable del proyecto declara:

- `name`: identidad visible;
- `role`: papel arquitectónico dentro de la fábrica;
- `phase`: `construccion` o `live`;
- `roadmap`: referencia al Roadmap canónico;
- `stack`: descripción estructurada del stack estable.

No se versionan manualmente como metadata de proyecto SHA, versión activa, CI, release, health, smoke, quality, Issue/PR activo ni último release. Esas señales son operativas y deben llegar como evidencia derivada.

## Bloques derivados

Contract v1 declara inicialmente un bloque:

```text
<!-- factory:status:start -->
...estado derivado...
<!-- factory:status:end -->
```

Los markers son frontera de escritura. Una implementación que no encuentre exactamente el bloque esperado debe fallar cerrado; nunca debe ampliar el área editable para “arreglar” un README.

## Estados y evidencia

Las señales derivadas admiten:

- `GREEN`: existe evidencia suficiente y verificable de estado sano;
- `DEGRADED`: existe evidencia suficiente y verificable de degradación;
- `PENDING`: la evidencia está en proceso o todavía no es terminal;
- `UNKNOWN`: no existe evidencia utilizable.

GREEN y DEGRADED requieren evidencia. Ausencia de datos **nunca** equivale a GREEN ni debe ocultar una degradación conocida. El README tampoco convierte un merge o deploy en producción validada sin la evidencia que exija el proyecto.

## Work Queue sin duplicar Roadmap

La cola visible usa únicamente NOW / NEXT / LATER / BLOCKED como resumen y enlaza las fuentes canónicas. No conserva una copia completa del Roadmap ni un historial de releases.

El detalle temporal pertenece a:

- GitHub Issues/Roadmap para planificación;
- Pull Requests para el cambio en revisión;
- GitHub Releases para entregas;
- `docs/` para documentación profunda.

## Compatibilidad y evolución

`contract.json.version` versiona el contrato de información. Cambios incompatibles en secciones, metadata obligatoria o semántica de markers requieren una evolución explícita del contrato.

Los consumidores no deben reinterpretar silenciosamente un contrato nuevo como si fuera v1.

## Reversión

La reversión segura es retirar generación/validación y conservar el Markdown resultante como contenido humano normal. Nunca se promueve el README a fuente canónica para poder revertir el mecanismo.

## Seguridad y privacidad

La metadata estable no debe contener secretos, tokens, cookies, credenciales, payloads sensibles ni datos operativos que pertenezcan a otra fuente. El cockpit solo presenta evidencia sanitizada y apta para la portada del repositorio.

## Próximas fases

- **ENGINE (#262):** funciones deterministas de generación y drift validation, reutilizando `intelligence/derived_views.py`.
- **ENFORCEMENT (#263):** reusable check y bootstrap del template.
- **FACTORY_ADOPTION (#264):** adopción de referencia en el README de Factory.
- Rollout a otros repos: trabajo posterior y dirigido en cada repositorio; no forma parte de este slice.
