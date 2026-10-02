#!/usr/bin/env python3
"""Regresiones del contrato de despacho documentado por Factory."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTES.md").read_text(encoding="utf-8")
DECISIONS = json.loads((ROOT / "decisiones.yml").read_text(encoding="utf-8"))


class PlanContractTests(unittest.TestCase):
    def test_plan_defines_directed_and_dispatch_modes(self):
        required = (
            "## 0. Dónde trabajar: modo dirigido o modo despachador",
            "**Modo dirigido:**",
            "trabajas **solo ahí**",
            "**Modo despachador:**",
            "HEALTH degradado",
            "Issue abierto de incidente",
            "reparación activa válida",
            "decisión del dueño ya respondida",
            "prioridad: crítica",
            "prioridad: alta",
            "media",
            "Solo pueden coexistir líneas cuando el candidato y cada línea activa relevante",
            "claims de paths son disjuntos",
            "Despacho: elegí <repo>#<n> porque <regla N>",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

        ordered = (
            "HEALTH degradado",
            "Issue abierto de incidente",
            "reparación activa válida",
            "decisión del dueño ya respondida",
            "prioridad: crítica",
            "prioridad: alta",
            "media",
        )
        positions = [PLAN.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_canonical_product_queue_is_exact(self):
        queue = (
            "Cola automática canónica:** Factory, Condor, GrindFlow, BRVTAL, "
            "ControlBot, AutoFactory y FactoryRunner"
        )
        self.assertIn(queue, PLAN)
        self.assertIn("pl0n3r/ControlBot", AGENTS)
        self.assertIn("pl0n3r/AutoFactory", AGENTS)
        self.assertNotIn(
            "ControlBot y AutoFactory quedan fuera del despacho automático de producto",
            PLAN,
        )
        self.assertIn(
            "Condor#192, GrindFlow#129, brvtal#630 y **FactoryRunner#1**",
            PLAN,
        )
        self.assertIn(
            "Condor#1, GrindFlow#2, brvtal#533 y FactoryRunner#1",
            PLAN,
        )

        d061 = [d for d in DECISIONS["decisions"] if d["id"] == "D-061"]
        self.assertEqual(len(d061), 1)
        self.assertEqual(d061[0]["status"], "active")

    def test_priority_tiebreaks_precede_age(self):
        self.assertIn(
            "prioridad: crítica` / `priority: critical` mejor posicionado por el desempate de la regla 7",
            PLAN,
        )
        self.assertIn(
            "prioridad: alta` y después `media`, aplicando el mismo desempate",
            PLAN,
        )
        self.assertIn(
            "desbloqueo → impacto transversal → continuidad → menor riesgo/esfuerzo → antigüedad",
            PLAN,
        )

    def test_blocked_incident_is_watch_only_and_dispatch_continues(self):
        for value in (
            "solo preempta si es ejecutable",
            "estado: bloqueado",
            "queda en vigilancia",
            "no detiene el despacho de otros repos",
            "Preempción ejecutable",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_lost_reservation_or_overlap_must_continue_global_ranking(self):
        for value in (
            "lease ajena",
            "claim overlap",
            "carrera de reserva perdida",
            "continúa inmediatamente con el siguiente candidato del ranking entre los siete repos",
            "No publica `overlap` ni `NO_WORK` hasta agotar los candidatos ejecutables del ciclo",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_no_work_requires_live_seven_repo_inventory_and_final_recheck(self):
        self.assertIn("NO_WORK válido solo tras inventario global vivo", PLAN)
        self.assertIn("en **ese mismo ciclo**", PLAN)
        for repo in (
            "Factory",
            "Condor",
            "GrindFlow",
            "BRVTAL",
            "ControlBot",
            "AutoFactory",
            "FactoryRunner",
        ):
            with self.subTest(repo=repo):
                self.assertIn(repo, PLAN)
        self.assertIn("registrar para cada repositorio el motivo", PLAN)
        self.assertIn("recomprobación final", PLAN)
        self.assertIn("available", PLAN)
        self.assertIn("estado: disponible", PLAN)

    def test_inventory_change_invalidates_prior_no_work_snapshot(self):
        for value in (
            "Cualquier cambio de inventario invalida el snapshot previo",
            "descartar esa fotografía y reevaluar",
            "snapshot parcial o stale",
            "falla cerrado respecto a `NO_WORK`",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_d043_requires_validated_in_production_not_workflow_success(self):
        for value in (
            "Puertas D-043/release: evidencia terminal, no color del workflow",
            "`workflow conclusion=success` por sí solo **no satisface D-043**",
            "`VALIDATED_IN_PRODUCTION`",
            "identidad/SHA coincidentes",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_deploy_observed_keeps_dependent_leaf_blocked_even_when_workflow_succeeds(self):
        for value in (
            "`DEPLOY_OBSERVED`",
            "`NO_OBSERVADO`",
            "`pending` no vacío",
            "mantienen el leaf bloqueado",
            "aunque GitHub Actions muestre `success`",
            "lease creada por inferir readiness desde `success` no amplía autoridad",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_tranche_gate_precedes_ready_reservation_and_cannot_be_overridden(self):
        gate = "**Gate de tanda antes de prioridades:**"
        priority = "5. El Issue ready de"
        self.assertIn(gate, PLAN)
        self.assertLess(PLAN.index(gate), PLAN.index(priority))
        for value in (
            "etiqueta `available` / `estado: disponible`",
            "`/tomar`",
            "reserva activa",
            "no sobreescriben este gate",
            "antes de aplicar las reglas 5–7",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_factory_is_not_blocked_by_phase_wait_rule(self):
        self.assertIn(
            "Esta regla de espera por tanda **no bloquea a Factory**",
            PLAN,
        )


    def test_three_lane_policy_and_owner_decisions_are_recorded(self):
        for value in (
            "Carril 1 — auto-alimentado",
            "Carril 2 — dirección de producto",
            "Carril 3 — preparación del live",
            "Factory#683",
            "Backblaze B2",
            "AutoFactory#79",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)
        active = {
            d["id"]: d
            for d in DECISIONS["decisions"]
            if d["status"] == "active"
        }
        for decision_id in ("D-064", "D-065", "D-066", "D-067"):
            self.assertIn(decision_id, active)
            self.assertIn("Factory#683", active[decision_id]["text"])

    def test_product_direction_policy_matches_early_threshold(self):
        self.assertIn("como máximo 1 leaf elegible", PLAN.replace("**", ""))
        self.assertIn("2 o más leaves elegibles", PLAN.replace("**", ""))
        self.assertNotIn(
            "cuando Condor, GrindFlow o BRVTAL no tengan ningún leaf elegible",
            PLAN,
        )
        self.assertNotIn("o reaparece un leaf elegible", PLAN)
        self.assertIn(
            "mientras no exista aprobación explícita, no se materializa ningún leaf",
            PLAN,
        )

    def test_product_direction_policy_covers_all_automatic_projects(self):
        lane = next(
            line
            for line in PLAN.splitlines()
            if "**Carril 2 — dirección de producto:**" in line
        )
        for project in (
            "Factory",
            "Condor",
            "GrindFlow",
            "BRVTAL",
            "ControlBot",
            "AutoFactory",
            "FactoryRunner",
        ):
            with self.subTest(project=project):
                self.assertIn(project, lane)

        self.assertIn(
            "la puerta no salta bloqueos de autoridad, live, gasto ni proveedores",
            PLAN,
        )
        self.assertIn("ControlBot#45", PLAN)
        self.assertIn("ControlBot#182", PLAN)
        self.assertIn("AutoFactory#70", PLAN)
        self.assertIn("Backblaze B2 no se provisiona antes de live", PLAN)

    def test_direction_gate_creation_requires_post_create_reconciliation(self):
        for value in (
            "reconciliar post-create",
            "created_at",
            "número de Issue",
            "cierra las posteriores como duplicadas",
            "mientras no exista aprobación explícita, no se materializa ningún leaf",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_product_direction_requires_reservable_leaf_contract(self):
        for value in (
            "mismo preflight de aceptación",
            "usado por `/tomar`",
            "no puede etiquetarse `available`",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_intentional_blocks_keep_documented_conditions(self):
        for reference in (
            "ControlBot#45",
            "ControlBot#182",
            "Factory#305",
            "AutoFactory#70",
            "Condor#389",
        ):
            with self.subTest(reference=reference):
                self.assertIn(reference, PLAN)
        self.assertIn("Condición de desbloqueo", PLAN)
        self.assertIn("nueva evidencia SonarCloud directa/canónica", PLAN)
        self.assertIn("orden explícita del dueño de salir a live", PLAN.lower())


    def test_readme_explains_launch_modes(self):
        required = (
            "### Los dos modos de lanzar un agente",
            "**Modo dirigido**",
            "**Modo despachador:**",
            "Trabajas en el repositorio pl0n3r/Condor.",
            "en modo despachador.",
            "**Cola automática de Factory:**",
            "reparación activa válida",
            "readiness, reservas, dependencias, PR equivalente y claims de paths",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, README)

        self.assertNotIn(
            "Abrir un agente en cada repositorio",
            README,
        )


if __name__ == "__main__":
    unittest.main()
