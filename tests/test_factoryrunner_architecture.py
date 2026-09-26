#!/usr/bin/env python3
"""Regresiones del contrato arquitectónico de FactoryRunner (#167)."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCH = (ROOT / "docs" / "factoryrunner-execution-plane.md").read_text(encoding="utf-8")


class FactoryRunnerArchitectureTests(unittest.TestCase):
    def test_authority_boundaries_are_explicit(self) -> None:
        for token in (
            "**Factory gobierna**",
            "**ControlBot decide**",
            "**FactoryRunner ejecuta**",
            "**AutoFactory permanece independiente**",
            "FactoryRunner no puede crear trabajo",
            "cambiar prioridades",
            "resolver puertas humanas",
        ):
            with self.subTest(token=token):
                self.assertIn(token, ARCH)

    def test_shared_hosting_is_primary_without_os_assumptions(self) -> None:
        hosting_section = ARCH.split(
            "## 2. Target primario: Hostinger Shared/Web Hosting", 1
        )[1].split("## 3. Protocolo estable", 1)[0]
        self.assertIn("El core debe funcionar sin presuponer:", hosting_section)
        for forbidden_assumption in (
            "acceso root",
            "Docker o un daemon arbitrario",
            "Chrome/Chromium instalado localmente",
            "puertos propios",
            "WebSocket entrante",
        ):
            with self.subTest(forbidden_assumption=forbidden_assumption):
                self.assertIn(forbidden_assumption, hosting_section)
        self.assertIn("adapters/backends remotos", hosting_section)

    def test_remote_capabilities_and_mac_fallback_share_protocol(self) -> None:
        self.assertIn("browser.chrome", ARCH)
        self.assertIn("browser-as-a-service o un worker remoto", ARCH)
        self.assertIn("Fallback macOS", ARCH)
        self.assertIn("fallback de última opción", ARCH)
        self.assertIn("evidencia técnica concreta", ARCH)
        self.assertIn("exactamente el mismo protocolo ControlBot ↔ FactoryRunner", ARCH)
        self.assertIn("capabilities dinámicas", ARCH)

    def test_orders_are_secret_free_and_controlbot_owns_durable_state(self) -> None:
        for token in (
            "Las órdenes son **secret-free**",
            "passwords, tokens, cookies, API keys, claves privadas",
            "sin autoridad implícita",
            "ControlBot/MariaDB es la fuente de verdad durable",
            "vault/secret store",
        ):
            with self.subTest(token=token):
                self.assertIn(token, ARCH)

    def test_runner_loss_is_reconstructible_and_idempotent(self) -> None:
        for token in (
            "FactoryRunner es reconstructible",
            "Cada `order_id` es idempotente",
            "dispatch o requeue crea un `attempt_id` nuevo",
            "`generation` monotónica",
            "ControlBot rechaza eventos de un attempt stale",
            "`fencing_token`",
            "nunca permiten dos owners efectivos simultáneos",
            "La pérdida de heartbeat habilita requeue/handoff desde ControlBot",
            "El Runner no se autoasigna trabajo",
            "nunca son la única copia de un WorkItem",
        ):
            with self.subTest(token=token):
                self.assertIn(token, ARCH)

    def test_autofactory_remains_independent_and_factoryrunner2_is_linked(self) -> None:
        self.assertIn("Relación con FactoryRunner #2", ARCH)
        self.assertIn("FactoryRunner #2 implementa el primer runtime Node.js 24 + TypeScript", ARCH)
        self.assertIn("no duplica ese runtime", ARCH)
        self.assertIn("no reutiliza ni transforma AutoFactory", ARCH)
        self.assertIn("AutoFactory permanece local/manual e independiente", ARCH)


if __name__ == "__main__":
    unittest.main()
