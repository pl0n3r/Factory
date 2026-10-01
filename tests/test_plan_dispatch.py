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

    def test_direction_gate_creation_requires_post_create_reconciliation(self):
        for value in (
            "reconciliar post-create",
            "created_at",
            "número de Issue",
            "cierra las posteriores como duplicadas",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_product_direction_requires_reservable_leaf_contract(self):
        for value in (
            "roles y claims de paths exactos",
            "mismo preflight de aceptación y coordinación que `/tomar`",
            "estructuralmente no reservable",
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
