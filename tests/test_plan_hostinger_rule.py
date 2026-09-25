"""Contrato durable de uso de Hostinger en Factory."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")


def _decision(path: Path, decision_id: str) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        row
        for row in payload["decisions"]
        if row.get("id") == decision_id and row.get("status") == "active"
    ]
    if len(matches) != 1:
        raise AssertionError(f"{path}: {decision_id} debe existir exactamente una vez y estar activa")
    return str(matches[0]["text"])


class PlanHostingerRuleTests(unittest.TestCase):
    """Evita drift entre la decisión D-059, el template y el plan."""

    def test_d059_is_consistent_across_factory_and_template(self):
        """AC-01: D-059 mantiene el mismo alcance y controles en las tres fuentes."""
        factory_text = _decision(ROOT / "decisiones.yml", "D-059")
        template_text = _decision(ROOT / "template" / "decisiones.yml", "D-059")

        self.assertEqual(factory_text, template_text)
        for value in (
            "cualquier agente",
            "leer y diagnosticar es libre",
            "backup previo",
            "registro en el Issue",
            "autorización explícita del dueño",
            "comprar, renovar o cambiar planes y pagos nunca lo hace un agente",
        ):
            with self.subTest(value=value):
                self.assertIn(value, factory_text)

        for value in (
            "todos los agentes conectados al MCP remoto de Hostinger",
            "incluidos Claude y GPT",
            "mirar y diagnosticar es libre",
            "backup previo",
            "dejarlo registrado en el Issue",
            "borrar sitios, bases de datos o archivos requiere autorización explícita del dueño",
            "comprar, renovar o cambiar planes y pagos nunca lo hace un agente",
        ):
            with self.subTest(value=value):
                self.assertIn(value, PLAN)


if __name__ == "__main__":
    unittest.main()
