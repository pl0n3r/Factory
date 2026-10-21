"""Contrato regresivo de propagación de la decisión D-070 a los agentes.

No concede autorizaciones nuevas: documenta la excepción ya aplicada por Policy.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PlanAgentesD070Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        cls.lines = cls.plan.splitlines()
        cls.decisions = json.loads((ROOT / "decisiones.yml").read_text(encoding="utf-8"))

    @classmethod
    def rule(cls, prefix):
        matching = [line for line in cls.lines if line.startswith(prefix)]
        if len(matching) != 1:
            raise AssertionError(f"Se esperaba una sola regla {prefix}: {len(matching)}")
        return matching[0]

    def test_rate_limited_coderabbit_does_not_make_chats_wait(self):
        decision = [entry for entry in self.decisions["decisions"] if entry["id"] == "D-070"]
        self.assertEqual(len(decision), 1)
        self.assertEqual(decision[0]["status"], "active")
        rule = self.rule("- **D-070 /")
        for required in (
            "Factory#1389", "CodeRabbit", "`construccion`",
            "rate-limit", "posterior al commit del HEAD exacto",
            "`Validar`", "SonarCloud", "CodeQL", "`success`",
            "`CHANGES_REQUESTED`", "`high`", "`critical`",
            "marca el PR como listo (no borrador)",
            "sin esperar el turno de CodeRabbit",
            "CodeRabbit FINAL", "deuda", "Issue",
            "`live`", "rojos/UNKNOWN", "se mantiene el veto",
        ):
            self.assertIn(required.replace("\\", ""), rule)
        d069 = self.rule("- **D-069 /")
        self.assertIn("D-070", d069)
        self.assertIn("rate-limited = UNKNOWN y bloquea", d069)
        quota = self.rule("**Límites de cuota o tiempo:**")
        self.assertIn("CodeRabbit sin cuota", quota)
        self.assertIn("marcar el PR como listo (no borrador)", quota)
        self.assertIn("no esperar ni programar reintentos por la cuota CodeRabbit", quota)
        self.assertNotIn("`CodeRabbit` sin cuota o reinicio periódico", quota)

    def test_other_quota_security_and_release_gates_still_apply(self):
        quota = self.rule("**Límites de cuota o tiempo:**")
        for required in ("GitHub API 403/429", "X-RateLimit-Reset", "Retry-After", "reserva V3", "Prohibido el polling"):
            self.assertIn(required, quota)
        d070 = self.rule("- **D-070 /")
        for gate in ("kill switch #767", "freeze #921", "Factory@v1", "release/deploy", "datos reales", "secretos", "go-live", "V3", "protección de rama"):
            self.assertIn(gate, d070)
        self.assertIn("skip", self.rule("**Límites de cuota o tiempo:**"))
