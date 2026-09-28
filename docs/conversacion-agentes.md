# Conversación de agentes: progreso visible y estado compacto

Contrato operativo de [#290](https://github.com/pl0n3r/Factory/issues/290). La regla corta vive en [`agentes/NUCLEO.md`](../agentes/NUCLEO.md); este documento fija ejemplos y el formato canónico.

## 1. Actualizaciones de progreso

Solo en transiciones significativas. Cada una dice **qué se confirmó** y **qué sigue**.

Válidas:

- `Encontré que el fallo viene del wiring de test, no del transporte productivo. Ahora valido el contenedor en APP_ENV=test.`
- `Backend y Validar ya están verdes; solo falta Playwright. Mientras corre, reviso el flujo nuevo para detectar fallos lógicos.`
- `El enfoque A falló por X. Cambio al enfoque B porque evita Y.`

Prohibidas: `Sigo revisando.`, `Déjame pensar.`, `Estoy trabajando en eso.` y repetir `voy a revisar...` sin hallazgo nuevo.

## 2. Nota de estado compacta

Sustituye la relectura del historial. Se escribe por **hitos** (merge, cambio de enfoque, fallo relevante, cambio de Issue/PR, contexto ruidoso), no por mensaje.

```md
STATE
objetivo: ...
repo: ...
issue: #...
pr: #...
head: <branch>@<sha>
decisiones:
- ...
confirmado:
- ...
no repetir:
- ...
pendiente:
- ...
siguiente: ...
```

Debe conservar: objetivo, repo/Issue/PR, branch y SHA, decisiones tomadas, hallazgos confirmados, intentos fallidos que no deben repetirse, checks pendientes y la siguiente acción exacta. Nada más: sin transcripciones ni razonamiento interno.

## 3. Eficiencia

- No reexplicar lo ya presente en Issue/PR/`lecciones/`.
- Buscar primero; abrir solo fragmentos relevantes.
- Agrupar lecturas independientes en paralelo.
- Sin polling: una lectura terminal de CI y más solo ante fallo o transición real.
- Resultado primero, detalle después; hitos en 3–7 líneas salvo petición.
- No duplicar en el chat lo registrado en GitHub.

## 4. Prompt vs. integración

| Capa | Responsabilidad |
|---|---|
| Prompt/contrato del agente | cadencia y contenido de actualizaciones, concisión, no repetir, compactar estado |
| Integración/API/UI (Factory, ControlBot, FactoryRunner) | streaming, persistencia de estado, truncado/resumen de contexto, caché, límites de tokens, visualización en tiempo real |

Lo de la segunda fila no se resuelve solo con instrucciones: si la integración es nuestra, se evalúa allí.

## Fixture de continuidad

[`tests/fixtures/estado_compacto.md`](../tests/fixtures/estado_compacto.md) es una nota `STATE` de ejemplo; `tests/test_conversacion_agentes.py` comprueba que trae todos los campos y que un agente puede reanudar solo con ella (objetivo, SHA, fallos a no repetir y siguiente acción).
