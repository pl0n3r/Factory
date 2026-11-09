---
name: factory-state-reconciler
description: Audita y corrige las etiquetas de estado de los issues abiertos de la fábrica pl0n3r (disponible, bloqueado, reservado, en revisión, planificado) comparándolas con dependencias, PRs, reservas y contrato. Úsala al revisar el tablero, cuando haya chats ociosos con muchos issues abiertos, o al pedir "ordena los estados".
---

# Reconciliador de estados

El orquestador reparte trabajo según la etiqueta `estado:`. Una etiqueta desfasada deja chats ociosos (issue "bloqueado" con sus dependencias ya cerradas) o manda chats a trabajo imposible (issue "disponible" sin contrato válido).

## Regla (en este orden)

1. PR abierto que referencia el issue → `en revisión`.
2. Última reserva con `"active":true` → `reservado`.
3. Estaba `planificado` → se deja: lo libera el sistema, no se toca.
4. El issue es del dueño (live, legal, claves, operaciones reales) → `bloqueado`.
5. Alguna dependencia de `depends_on` sigue abierta → `bloqueado`.
6. El contrato no pasa el validador → `bloqueado` (arreglar el cuerpo con `factory-issue-author` y luego liberar).
7. Si no → `disponible`.

## Uso

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_estados.py"            # todos los repos, solo lectura
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_estados.py" Condor     # un repo
```

Usa `FACTORY_SCRIPTS` (carpeta `scripts/` de Factory, por defecto `~/Desktop/Factory/scripts`) para el validador y `DUENO_ISSUES` (JSON opcional con los issues del dueño). El script solo **propone**: imprime los cambios y los comandos `gh issue edit`. Revisa la lista antes de aplicar.

## Cuidado antes de aplicar

- Un issue con PR ya fusionado y criterios sin marcar no está listo para `disponible`: un chat repetiría trabajo hecho. Léelo antes.
- `requiere recuperación` lo gestiona el orquestador; no lo pongas a mano.
- Avisos automáticos ([AUTO]) y paneles de estado no son trabajo: no los muevas.
- Quitar `bloqueado` sin contrato válido no sirve: el bot rechaza el `/tomar`.
