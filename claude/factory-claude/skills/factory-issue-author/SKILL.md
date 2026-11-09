---
name: factory-issue-author
description: Escribe issues canónicos de la fábrica pl0n3r que pasan el validador de Factory y se pueden reservar con /tomar (o /take en brvtal). Úsala al crear, reescribir o arreglar un issue (contrato, criterios AC, rutas reclamadas, roles, etiquetas) o cuando una reserva falle por "criterios de aceptación ejecutables válidos".
---

# Autor de issues canónicos

Un issue que no pasa el validador **no se puede reservar**: el bot responde con un error y el chat se queda sin trabajo. En la auditoría de 2-nov-2026, 81 de 134 issues abiertos no lo pasaban. Escribe siempre con esta plantilla y valida antes de publicar.

## Plantilla (secciones exactas, una vez cada una)

```
### Contexto
Por qué existe y de qué roadmap viene (enlaces #N).

### Alcance
- Qué se hace, concreto y acotado.

### Fuera de alcance
Qué NO se toca (producción, datos reales, credenciales, live, otros archivos).

### Criterios de aceptación
- [ ] [AC-01] Resultado verificable.
- [ ] [AC-02] `<check>` en `success` sobre HEAD exacto.

### Contrato ejecutable
<!-- factory-acceptance {"version":1,"criteria":[{"id":"AC-01","kind":"check","target":"<check>"},{"id":"AC-02","kind":"check","target":"<check>"}]} -->

### Rutas reclamadas
- `ruta/exacta/del/archivo`
<!-- factory-plan-task {"version":1,"epic":N,"task_key":"CLAVE_UNICA","order":10,"owner":"pl0n3r","roles":["ingenieria-software","qa"],"depends_on":[],"paths":["ruta/exacta/del/archivo"]} -->

### Riesgo, pruebas y reversión
Riesgo, cómo se prueba y cómo se revierte.
```

## Reglas que fallan en la práctica

1. **Toda línea que empiece por `- [` dentro de «Criterios de aceptación» debe ser `- [ ] [AC-NN] texto`.** Una línea extra sin `[AC-NN]` (p. ej. «- [ ] Sin secretos…») rompe todo el contrato. Los puntos generales van como `- texto` sin corchetes.
2. El título de la sección es exactamente `### Criterios de aceptación` (no «Criterios»), y `### Fuera de alcance` es obligatoria.
3. Cada AC del texto tiene su par en el marker JSON (mismos ids, 1 a 20).
4. `kind:"test"` exige `ruta/test.py::Clase::metodo`. `kind:"check"` usa el nombre completo del check; `Validar` o `Criterios de aceptación` solos están prohibidos.
5. `factory-plan-task` exige todos estos campos: `version`, `epic`, `task_key`, `order`, `owner`, `roles`, `depends_on`, `paths`. **`epic` es el número del issue de roadmap padre** (Condor 1, GrindFlow 2, brvtal 975, Factory 1296, AutoFactory 1, FactoryRunner 465, ControlBot 1) y `paths` debe coincidir con «Rutas reclamadas». Sin `epic` el bot rechaza el `/tomar` con «factory-plan-task tiene esquema inválido».
6. Un solo marker `factory-acceptance` y un solo `factory-plan-task`. `task_key` único en el repo, solo mayúsculas ASCII, dígitos y `_`, máximo 32 caracteres; `depends_on` solo con números de issues del mismo repo.
7. «Rutas reclamadas» = archivos exactos, nunca directorios completos, y que no choquen con issues reservados o en revisión.

## Por repo

| Repo | Comando | Check de aceptación | Etiquetas | Rama |
|---|---|---|---|---|
| Condor | `/tomar` | `CI Factory v1 / Validar` | `tipo: …`, `prioridad: …`, `estado: disponible`, `rol: …` | `trabajo/issue-N` |
| GrindFlow | `/tomar` | `Factory CI reusable / Validar` | igual | `trabajo/issue-N` |
| Factory | `/tomar` | `Tests de scripts` | igual | `trabajo/issue-N` |
| ControlBot | `/tomar` | `CI Factory v1 / Validar` | igual | `trabajo/issue-N` |
| AutoFactory | `/tomar` | `Validate / Pruebas y smoke Chrome` | igual | `trabajo/issue-N` |
| FactoryRunner | `/tomar` | `ci / Validar` | igual | `trabajo/issue-N` |
| brvtal | `/take` | `factory-ci / Validar` | `type: …`, `priority: …`, `status: available`, `role: …` | `work/issue-N` |

Estos nombres salieron de issues recientes de cada repo. Si un check cambia, copia el de un issue canónico reciente.

## Validar antes de publicar

```bash
python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ.get("FACTORY_SCRIPTS", os.path.expanduser("~/Desktop/Factory/scripts")))
import aceptacion_kit as k
import orquestador_kit as o
cuerpo = open("cuerpo.md", encoding="utf-8").read()
k.parse_contract(cuerpo)        # criterios y contrato
o.parse_task_marker(cuerpo)     # plan: epic, task_key, order, roles, paths
print("contrato y plan válidos")
PY
```

Si lanza `AcceptanceError`, el mensaje dice qué sección o criterio falla. Después de publicar, comenta el comando de reserva y espera la respuesta del bot (la cola de GitHub puede tardar minutos).

## Nunca
Pegar secretos o datos personales, reclamar archivos ajenos, ni dar por buena una reserva sin ver el comentario `condor-reserva` con `"active":true`.
