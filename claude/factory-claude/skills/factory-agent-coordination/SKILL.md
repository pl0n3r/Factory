---
name: factory-agent-coordination
description: Coordina varios agentes en la fábrica pl0n3r sin crear otro orquestador - reservas `/tomar` `/liberar` `/transferir`, TTL, dependencias entre Issues, worktrees, paralelismo controlado (máximo cuatro) y merges serializados. Úsala al repartir trabajo, detectar colisiones o preparar varios PRs.
---

# Coordinación de agentes

El orquestador **ya existe** en Factory (`docs/orquestador.md`, `scripts/orquestador_kit.py`, `scripts/coordinar_trabajo.py`, workflow `coordinacion-trabajo.yml`), con ControlBot como panel y FactoryRunner como execution plane. Esta skill solo lo usa; no inventes colas, locks ni otro dispatcher.

- **Reservas:** `/tomar` (espera UUID), `/liberar <UUID>`, `/transferir`. Una lease ajena vigente excluye ese candidato (no se invade ni se libera). La lease inactiva se recupera por el mecanismo de recuperación de Factory, no editando su código. TTL por defecto: 30 min de inactividad; trabaja con la reserva releída antes de cada escritura (el hook `reservation_guard.py` lo comprueba).
- **Dependencias y claims:** lee `factory-plan-task` (`depends_on`, `paths`). Dos Issues que tocan la misma ruta se serializan por `depends_on`; si no, falla cerrado y pasa al siguiente.
- **Paralelismo:** uno por repo por defecto; para tareas planificadas, tantos como nodos listos con claims disjuntos, **tope cuatro agentes**. Cada agente en su propio worktree/clon y rama `trabajo/issue-N`; nunca compartas working tree con edición simultánea.
- **Merges serializados:** de uno en uno; tras cada merge, `git fetch`, reconcilia el siguiente PR con `main`, espera `Validar` verde en su nuevo HEAD y solo entonces fusiona. Respeta el freeze de release #921.
- **Handoff:** al transferir o terminar, deja bloque `STATE` mínimo (sin secretos) y, con reserva canónica, el marker `factory-state` (`docs/conversacion-agentes.md`).
- **Equidad:** tras 3 despachos seguidos en un repo se prefiere otro de la misma clase (Factory#942). El ranking lo decide el plan §0, no esta skill.
