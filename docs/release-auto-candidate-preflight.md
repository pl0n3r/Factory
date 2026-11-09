# Preflight de candidato de publicación automática — solo lectura

Hoja [#2084](https://github.com/pl0n3r/Factory/issues/2084), del épico #1080, autorizada para **desarrollo y pruebas** por la decisión OWNER [#2075/A](https://github.com/pl0n3r/Factory/issues/2075) (voto #6713206181, journal bot v2/A #6713215649). **No autoriza publicar v1.0.51, cambiar permisos ni mover Factory@v1.**

## Fuentes y límites

El módulo `scripts/release_auto_candidate_preflight.py` construye solo consultas `gh api -X GET` acotadas: `main` con SHA y protección, ref/tag `v1`, ruleset protegido, kill switch #767 y freeze #921, puertas `factory-release` abiertas, presupuesto `/rate_limit`, versiones de `config/version.json` leídas por SHA y v1, comparación `v1...SHA`, y checks exactos `Validar`, `SonarCloud Code Analysis` y `CodeQL` con identidad de GitHub App fijada.

El clasificador bloquea evidencia incompleta o ambigua, SHA distinto, reglas de protección desconocidas, cambio de maquinaria de release o seguridad, `phase=live`, versiones que no avanzan, checks no terminales/verdes, cuota baja y cualquier veto global. El presupuesto exige al menos 20 % disponible y 1.200 solicitudes si el límite es 5.000.

**Limitación deliberada:** el parámetro `phase=construccion` es una afirmación del caller, no un hecho autenticado por el módulo. Las verificaciones de compatibilidad de los seis consumidores y watchdog requieren recibos independientes exact-SHA. El colector mantiene esas señales `UNKNOWN` y su resultado ordinario es `BLOCKED` hasta integrar esas fuentes. Los fakes de las pruebas jamás acreditan datos reales.

## Autoridad, integración futura y reversión

Incluso con todos los datos de prueba en verde, el resultado máximo es `REVIEW_ONLY`, **siempre** `authorizes_release=false`, `mutations=0`, `tag_writes=0`, `release_writes=0`. Esta herramienta no crea workflow programado, no solicita nuevas credenciales, no incluye operaciones mutantes sobre GitHub y no modifica el canal distribuido.

Una siguiente hoja aprobada necesitará identidad de fase, compatibilidad auténtica de consumidores, watchdog, permisos de agente mínimos, rollback probado en repositorio de prueba y CI/seguridad exact-HEAD. El flujo vigente de `Factory Release Window`, la decisión humana `factory-release` por versión y el movimiento manual de `v1` por el propietario permanecen obligatorios hasta que una política nueva supere todas sus puertas.

Pruebas: `python3 -m unittest -v tests.test_release_auto_candidate_preflight`. La reversión consiste en revertir el squash de #2084, sin manipular tags, releases ni consumidores.
