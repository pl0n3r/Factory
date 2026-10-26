# Puertas humanas en lenguaje fácil

Las decisiones nuevas deben entenderse sin conocer GitHub, programación ni
seguridad informática. El mensaje breve debe explicar **qué se decide y qué cambia**.

## Guía para escribir una decisión

1. **Pregunta**: una frase corta en `title_simple`, preferiblemente una pregunta.
2. **Resumen**: dos o tres frases cortas en `summary_simple`. No más de 25 palabras por oración.
3. **Opciones**: `label` es un título corto; `effect` y `explain_simple`
   explican en una frase lo que pasa al elegirla, sin jerga.
4. **Impacto**: indicar claramente si afecta datos de personas, dinero, redes,
   cuentas o producción, o si se limita a pruebas con datos inventados.
5. **Recomendación**: usar `why_recommended` para explicar una opción en una frase.
6. **Detalles técnicos separados**: referencias a issues, versiones, hashes,
   reservas, normas y pruebas quedan en `context` o en la documentación
   técnica. No ponerlos al principio de la pregunta ni del resumen.

Evitar palabras como `exact-main`, `fail-closed`, `exact-HEAD`,
`V3`, `D-063`, `journal`, `SHA` e `idempotencia`. Tampoco incluir
identificadores como `#1516` en los textos explicativos.

## Ejemplo comprensible

**Pregunta:** ¿Preparamos una prueba?

**Resumen:** Podemos comprobar el cambio con datos inventados.
Todavía no se conectarán cuentas ni personas reales.

**A: Preparar prueba.** Solo se crea una prueba con datos inventados.
No afecta dinero, cuentas, datos de personas ni servicios reales.

**B: No preparar todavía.** Dejamos todo como está por ahora.

**Recomendación:** Preparar la prueba permite revisar el resultado sin riesgos.

## Regla automática y compatibilidad

`seguridad/puertas_humanas.py` comprueba el texto del **formato completo de
puerta nueva**: `explain_simple` presente tanto en raíz como en todas las
opciones. Rechaza una oración con más de 25 palabras y la jerga anterior en
`title_simple`, `summary_simple`, `explain_simple`, `why_recommended`,
`label`, `effect`, `cost`, `pros` y `cons`.
Los errores nombran el campo, pero jamás copian el contenido de la puerta.

Las puertas ya publicadas que no usan el formato completo conservan la
validación histórica: no se alteran sus opciones, autoridad, identificadores
o decisiones. Los campos técnicos `context`, `blocks`, los identificadores
de opciones y las huellas de autorización tampoco se reescriben. **Esto no
autoriza un cambio real**: siguen vigentes todas las aprobaciones humanas
y las comprobaciones de seguridad del flujo.

Para comprobarlo localmente:

```bash
python3 -m unittest discover -s tests -p 'test_puertas_lenguaje_simple.py' -v
python3 -m unittest discover -s seguridad -p 'test_puertas_humanas.py' -v
```

Al revertir, usar un nuevo PR que revierta el commit sin cambiar las
decisiones que ya haya registrado el dueño.
