# Context Compiler v1

Context Compiler produce un paquete mínimo de misión para un agente. Consume un
Project DNA ya validado, la tarea actual y decisiones/lecciones previamente
seleccionadas. No vuelve a explorar el repositorio ni decide riesgo o autoridad.

## Contrato

El paquete contiene:

- `project_dna` validado;
- una `task` cerrada con id, título, objetivo y tags;
- `context` relevante con categoría, fuente, texto y tags;
- límites explícitos;
- fingerprint SHA-256 determinista.

Solo entran piezas cuyo conjunto de tags intersecta los tags de la tarea. El
resultado se ordena canónicamente y se limita a 12 elementos. Cada pieza
conserva `source` para poder auditar de dónde salió.

## Privacidad

El compilador falla cerrado ante claves sensibles como tokens, passwords,
private keys, API keys, email, teléfono, dirección o identificadores personales.
Además redacta emails y números telefónicos encontrados dentro del texto libre.

La redacción evita emitir el valor sensible; no intenta clasificar ni conservar
una versión parcial del dato.

## Límites

- máximo 12 piezas de contexto;
- máximo 1200 caracteres por texto;
- máximo 12000 caracteres para el paquete serializado;
- sin I/O, sin mutación del proyecto y sin decisión de riesgo.

Context Compiler no reemplaza Risk Compiler ni las puertas humanas. Su trabajo
termina al producir contexto pequeño, trazable y reproducible.
