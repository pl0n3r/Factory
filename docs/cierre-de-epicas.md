# Cierre y mapeo de épicas sin hojas abiertas

## Autoridad y criterio de cierre

En fase **construccion**, un agente con reserva V3 válida puede cerrar una épica como completed solo si ha verificado *cada* criterio con evidencia enlazada del SHA vigente de main, no quedan hojas hijas abiertas y no subsisten decisiones o puertas humanas. En fase **live**, el cierre sigue reservado al dueño. Esta regla se documenta aquí sin editar PLAN-AGENTES.md mientras #2175 y #2178 reclaman ese archivo.

El workflow nunca cierra una épica por sí mismo. Solamente genera hojas *candidatas* que deben pasar por /tomar, CI, revisión y cierre evidenciado por el agente titular. Un check verde o un enlace no demuestran aceptación productiva.

## Generación y deduplicación

El comando `python3 scripts/epic_closure_leaves.py --repo pl0n3r/Factory` permite observar propuestas sin escribir. Solo `--apply` con GH_TOKEN autoriza la creación. El script pagina todos los issues (abiertos y cerrados), identifica épicas por referencia `factory-plan-task.epic` o prefijos EPIC/ÉPICA/Roadmap y no actúa cuando quedan hojas hijas abiertas. Excluye tipos/etiquetas del dueño, live, legal y gasto.

Si todos los criterios están marcados o tienen enlaces a commits, PRs, runs o comentarios de GitHub, se crea una hoja de **cierre** para que el agente *verifique realmente* esas pruebas contra main. Si faltan criterios o evidencias, se crea una hoja de **mapeo**, que pide emplear factory-epic-splitter para descomponer criterios técnicos verificables en hojas canónicas y anotar en el padre aquello que depende del dueño, sin materializar tareas humanas.

Cada nueva hoja lleva los markers factory-epic-closure, factory-plan-task y factory-acceptance, AC humanos y un claim único documental por épica. La validación utiliza la autoridad real `issue_contract_preflight.evaluate_issue_body` antes de publicar. El marcador de cierre, incluso en un issue ya cerrado, impide emitir otra hoja para la misma épica. Antes de cada mutación se revalida el interruptor global Factory #767 RUNNING, el inventario y la vigencia de ausencia de hojas abiertas. Concurrency del workflow limita carreras entre ejecuciones suyas; no sustituye una transacción contra agentes externos.

## Workflow y consumidores

.github/workflows/epic-closure.yml permite workflow_call, workflow_dispatch y schedule. Los triggers efectivos son solo en main; no acepta código desde eventos pull_request, issue_comment o forks. Requiere permisos mínimos contents:read e issues:write, checkout de Factory read-only sin credenciales persistentes, timeout y concurrency. No registra secretos, ni accede a datos de cliente.

El cron definido en el YAML aplica solamente al repositorio que guarda y habilita el workflow: **no crea tareas de ChatGPT**. Los consumidores deben activar por separado un caller a `pl0n3r/Factory/.github/workflows/epic-closure.yml@v1` tras la publicación autorizada del tag; el PR presente no publica ni mueve v1.

La entrada `acceptance_check` debe apuntar a un check **real** disponible en el consumidor. Por defecto es `Tests de scripts` para Factory. No usar `Validar` ni `Criterios de aceptación` como sustituto: ambos están prohibidos por el contrato máquina. No habilitar el flujo en un consumidor sin identificar un check apropiado. `max_leaves` limita la cantidad por ciclo (1..25, predeterminado 10); ante API incompleta o condiciones inválidas falla cerrado.

## QA y reversión

Pruebas sintéticas: `python3 -m unittest -v tests/test_epic_closure_leaves.py`. Cubren cierre, mapeo, ausencias, exclusiones humanas, idempotencia incluso con hojas cerradas, carreras y modo lectura. `Tests de scripts` exact-HEAD y `Validar` son gates de integración, no pruebas de producto. La reversión consiste en deshabilitar el workflow y reconciliar explícitamente cualquier hoja existente, sin borrar trabajo ni cerrar épicas automáticamente.
