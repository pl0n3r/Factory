#!/usr/bin/env python3
"""Contrato documental ejecutable: persistencia de agentes ante límites (#1334).

Sin red, secretos, temporizadores ni repositorios externos: solo verifica el
protocolo versionado y prueba mutaciones adversariales representativas.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

PLAN = Path(__file__).resolve().parents[1] / "PLAN-AGENTES.md"
HEADING = "### Persistencia ante límites — Factory#1334"
TERMINATOR = "- Tras cerrar/liberar un frente, volver a ejecutar el árbol de despacho."


def persistence_contract(source: str) -> str:
    """Extrae únicamente la política entregable, sin apoyarse en otros párrafos."""
    if source.count(HEADING) != 1:
        raise AssertionError("missing_or_duplicate_persistence_policy")
    segment = source.split(HEADING, 1)[1]
    if TERMINATOR not in segment:
        raise AssertionError("missing_policy_terminator")
    segment = segment.split(TERMINATOR, 1)[0]
    if len(segment.strip()) < 600:
        raise AssertionError("incomplete_persistence_policy")
    return segment


class AgentPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.full = PLAN.read_text(encoding="utf-8")
        cls.contract = persistence_contract(cls.full)

    def test_active_reservation_continues_before_taking_new_work(self) -> None:
        rule = self.contract
        for fragment in (
            "reserva V3 propia, vigente y verificable",
            "continúa el mismo Issue hasta fusionar su PR",
            "antes de tomar otro Issue",
            "HEALTH, incidentes, producto, QA y gobernanza",
            "nunca se invade una lease ajena",
            "la reserva, HEAD y checks",
            "reserva V3 propia activa con trabajo ejecutable",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, rule)
        ranking = re.search(r"(?m)^3\. Una reparación activa válida.*$", self.full)
        self.assertIsNotNone(ranking)
        self.assertIn("la misma continuidad rige cualquier frente propio", ranking.group().lower())
        self.assertIn("lease ajena", ranking.group())
        self.assertIn("ranking global", ranking.group())
        self.assertNotIn("excluye ese candidato y continúa el ranking global",
                         ranking.group().split("Si la línea pertenece", 1)[0])

    def test_limit_hit_waits_and_retries_instead_of_abandoning(self) -> None:
        rule = self.contract
        for fragment in (
            "GitHub API 403/429",
            "CodeRabbit",
            "conservar la reserva V3",
            "reintentar ese **mismo Issue**",
            "CI rojo/cancelado",
            "diagnosticar el error, corregir su causa",
            "dos intentos del mismo enfoque",
            "cambiar de enfoque **dentro del mismo Issue**",
            "más commits nunca constituye por sí sola una condición de parada",
            "revalidar todas las puertas",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, rule)
        rejected = rule.replace("cambiar de enfoque **dentro del mismo Issue**",
                                "cambiar al siguiente Issue")
        with self.assertRaises(AssertionError):
            self.assertIn("cambiar de enfoque **dentro del mismo Issue**",
                          persistence_contract(self.full.replace(rule, rejected)))

    def test_only_hard_gates_justify_stopping(self) -> None:
        rule = self.contract
        for fragment in (
            "**Únicas condiciones de parada:**",
            "dinero o gasto",
            "datos reales",
            "borrado irreversible",
            "despliegue",
            "go-live",
            "kill switch Factory#767",
            "freeze de release",
            "falta de autoridad del dueño",
            "dependencia real abierta",
            "reserva V3 perdida, revocada, caducada o colisión real de claims",
            "preparación offline autorizada",
            "nunca se amplían los claims",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, rule)
        for unsafe in ("ignorar el kill switch", "saltar el freeze",
                       "autoriza deploy automático", "auto-merge en live"):
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, rule)

    def test_blocked_comment_requires_a_stop_condition(self) -> None:
        rule = self.contract
        for fragment in (
            "**Comentario de bloqueo con plan:**",
            "solo se permite declarar «bloqueo real»",
            "cita una de las condiciones de parada anteriores",
            "evidencia verificable",
            "plan de reintento/desbloqueo del mismo Issue",
            "no justifican abandonar",
            "el agente continúa y corrige",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, rule)
        broken = rule.replace("con evidencia verificable", "sin evidencia")
        with self.assertRaises(AssertionError):
            self.assertIn("evidencia verificable",
                          persistence_contract(self.full.replace(rule, broken)))

    def test_retry_is_scheduled_not_a_polling_loop(self) -> None:
        rule = self.contract
        for fragment in (
            "programar el reintento para la hora de reinicio",
            "X-RateLimit-Reset",
            "Retry-After",
            "Si no existe hora de reinicio verificable",
            "UNKNOWN",
            "**Prohibido el polling en bucle**",
            "nunca inventar un reloj",
            "programación real solo cuando esté disponible",
            "sin un programador disponible",
            "no es permiso de escritura",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, rule)
        for mutation in (
            rule.replace("programar el reintento para la hora de reinicio",
                         "reintentar inmediatamente"),
            rule.replace("**Prohibido el polling en bucle**",
                         "Permitir polling continuo"),
        ):
            with self.subTest(variant=mutation[:80]):
                self.assertTrue(
                    "programar el reintento para la hora de reinicio" not in mutation
                    or "**Prohibido el polling en bucle**" not in mutation
                )


if __name__ == "__main__":
    unittest.main()
