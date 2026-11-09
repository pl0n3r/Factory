---
name: factory-epic-splitter
description: Parte un roadmap o épica de la fábrica pl0n3r en hojas ejecutables con archivos propios, para que siempre haya cola de trabajo y los chats no choquen. Úsala al planificar una épica, cuando haya chats ociosos porque faltan issues asignables, o al convertir un roadmap en issues canónicos.
---

# Divisor de épicas en hojas

El cuello de botella de la fábrica es la cola, no los chats: el 2-nov-2026 había 15 chats y solo 9 issues asignables; casi todo lo demás estaba bloqueado, planificado o chocaba por archivos. Esta skill reparte una épica en hojas que se pueden trabajar en paralelo.

## Cómo partir

1. **Lee la épica y su criterio de salida.** Lista qué entrega observable falta (código, prueba, documento, evidencia). Lo que requiere live, claves o decisión del dueño no es una hoja: va a la lista del dueño.
2. **Una hoja = un resultado verificable y archivos propios.** Máximo unos pocos archivos. Si dos hojas tocan el mismo archivo, una depende de la otra (`depends_on`) o se fusionan.
3. **Cada hoja es un issue canónico** (`factory-issue-author`): contexto con enlace a la épica, alcance, fuera de alcance, criterios `AC-NN`, contrato y `epic` = número de la épica.
4. **Orden y dependencias.** `order` creciente; `depends_on` solo con issues del mismo repo y solo lo imprescindible (cada dependencia abierta bloquea la hoja).
5. **Choques.** Comprueba con `orquestador_kit.tasks_overlap` que las rutas de hojas paralelas no se solapan.
6. **Tamaño.** ControlBot limita PRs a 400 líneas; en los demás repos mantén la hoja revisable de una sola vez.
7. **Cola nunca vacía.** Deja al menos tantas hojas `disponible` como chats libres, sin romper las dependencias.

## Después de crear las hojas
- Valida cada cuerpo con `parse_contract` y `parse_task_marker`.
- Corre `factory-state-reconciler` para que las etiquetas queden coherentes.
- No marques `disponible` una hoja cuyo contrato no pase el validador.

## Evita
- Hojas que dicen «completar todo el roadmap».
- Criterios que solo se cumplen en producción o con datos reales.
- Cerrar la épica: se cierra al final, con evidencia, y por decisión del dueño.
