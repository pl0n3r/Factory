#!/usr/bin/env python3
"""Regresiones del contrato de despacho documentado por Factory."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


class PlanDispatchTests(unittest.TestCase):
    def test_plan_defines_directed_and_dispatch_modes(self):
        required = (
            "## 0. Dónde trabajar: modo dirigido o modo despachador",
            "**Modo dirigido:**",
            "trabajas **solo ahí**",
            "**Modo despachador:**",
            "producción caída o no VERDE",
            "tipo: incidente",
            "decisión del dueño ya respondida",
            "prioridad: crítica",
            "prioridad: alta",
            "media",
            "Nunca** tomes un repo donde otro agente tiene una reserva activa",
            "Despacho: elegí <repo>#<n> porque <regla N>",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

        ordered = (
            "producción caída o no VERDE",
            "Issue abierto de incidente",
            "decisión del dueño ya respondida",
            "prioridad: crítica",
            "prioridad: alta",
            "media",
        )
        positions = [PLAN.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_controlbot_and_autofactory_are_first_class_projects(self):
        required = (
            "ControlBot (privado)",
            "ControlBot, AutoFactory",
            "desde su primer despliegue, también a ControlBot",
            "AutoFactory es una extensión, no un servicio web",
            "no usa `/health` ni deploy de servidor",
            "Chrome y Safari",
            "ControlBot#2",
            "no bloquean",
            "AutoFactory#1",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, PLAN)

    def test_readme_explains_launch_modes(self):
        required = (
            "### Los dos modos de lanzar un agente",
            "**Modo dirigido**",
            "**Modo despachador:**",
            "Trabajas en el repositorio pl0n3r/Condor.",
            "en modo despachador.",
            "Nunca toma un proyecto donde otro agente está trabajando",
            "uno dirigido a `pl0n3r/factory`",
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
