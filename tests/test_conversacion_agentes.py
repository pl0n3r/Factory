"""Contrato ejecutable de progreso visible y estado compacto (Issue #290)."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAMPOS = ("objetivo", "repo", "issue", "pr", "head", "decisiones",
          "confirmado", "no repetir", "pendiente", "siguiente")


def parse_state(text):
    """Convierte una nota STATE en dict campo -> lista de valores."""
    lines = text.strip().splitlines()
    if lines[0] != "STATE":
        raise ValueError("la nota debe empezar con STATE")
    state, key = {}, None
    for line in lines[1:]:
        if line.startswith("- "):
            state[key].append(line[2:].strip())
        else:
            key, _, value = line.partition(":")
            state[key.strip()] = [value.strip()] if value.strip() else []
    return state


class ConversacionAgentesTests(unittest.TestCase):
    """Verifica el contrato en NUCLEO, la doc y la fixture de continuidad."""

    @classmethod
    def setUpClass(cls):
        cls.nucleo = (ROOT / "agentes/NUCLEO.md").read_text(encoding="utf-8")
        cls.doc = (ROOT / "docs/conversacion-agentes.md").read_text(encoding="utf-8")
        cls.state = parse_state(
            (ROOT / "tests/fixtures/estado_compacto.md").read_text(encoding="utf-8")
        )

    def test_nucleo_define_progreso_solo_en_transiciones(self):
        self.assertIn("transiciones significativas", self.nucleo)
        self.assertIn("qué se confirmó y qué sigue", self.nucleo)

    def test_nucleo_prohibe_progreso_vacio(self):
        for frase in ("sigo revisando", "déjame pensar", "estoy trabajando en eso"):
            self.assertIn(frase, self.nucleo)

    def test_estado_compacto_canonico_y_por_hitos(self):
        for campo in CAMPOS:
            self.assertRegex(self.doc, rf"(?m)^{re.escape(campo)}:")
        self.assertIn("por **hitos**", self.doc)

    def test_prompt_separado_de_integracion(self):
        self.assertIn("Prompt/contrato del agente", self.doc)
        self.assertIn("Integración/API/UI", self.doc)
        self.assertIn("pertenecen a la integración", self.nucleo)

    def test_fixture_permite_continuar_sin_historial(self):
        self.assertEqual(set(CAMPOS), set(self.state))
        self.assertTrue(re.fullmatch(r"\S+@[0-9a-f]{40}", self.state["head"][0]))
        self.assertTrue(self.state["no repetir"])
        self.assertTrue(self.state["siguiente"][0])

    def test_revision_de_plataforma_no_es_fallo(self):
        self.assertIn("procesando esta solicitud", self.doc)
        self.assertIn("no reenvíes", self.nucleo)

    def test_decision_d062_repos_publicos_en_root_y_template(self):
        import json
        for ruta in ("decisiones.yml", "template/decisiones.yml"):
            data = json.loads((ROOT / ruta).read_text(encoding="utf-8"))
            d062 = [d for d in data["decisions"] if d["id"] == "D-062"]
            self.assertEqual(len(d062), 1, ruta)
            self.assertEqual(d062[0]["status"], "active")
            self.assertIn("son públicos", d062[0]["text"])
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertNotIn("ControlBot (privado)", plan)
        self.assertIn("D-062", plan)
        arquitectura = (ROOT / "docs/arquitectura-tecnica.md").read_text(encoding="utf-8")
        self.assertIn("| `pl0n3r/AutoFactory` | Público |", arquitectura)
        self.assertNotIn("| `pl0n3r/AutoFactory` | Privado |", arquitectura)

    def test_legal_no_bloquea_en_construccion_d063(self):
        import json
        for ruta in ("decisiones.yml", "template/decisiones.yml"):
            data = json.loads((ROOT / ruta).read_text(encoding="utf-8"))
            d063 = [d for d in data["decisions"] if d["id"] == "D-063"]
            self.assertEqual(len(d063), 1, ruta)
            self.assertIn("ninguna puerta legal", d063[0]["text"])
        script = (ROOT / "scripts/auditar_privacidad.py").read_text(encoding="utf-8")
        self.assertIn('recommendation = "B"', script)
        self.assertIn('recommendation = "A"', script)
        self.assertIn('"d063_applies": d063_applies', script)
        self.assertIn('attestation.get("nothing_live") is True', script)
        self.assertIn('attestation.get("no_real_customer_data") is True', script)
        self.assertIn("no bloquea el trabajo en construcción", script)
        self.assertIn("puerta es bloqueante", script)

        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("d063_attestation.nothing_live=true", plan)
        self.assertIn("d063_attestation.no_real_customer_data=true", plan)
        puertas = (ROOT / "docs/puertas-humanas.md").read_text(encoding="utf-8")
        self.assertIn("d063_attestation.nothing_live=true", puertas)
        self.assertIn("d063_attestation.no_real_customer_data=true", puertas)
        self.assertIn("go-live", (ROOT / "decisiones.yml").read_text(encoding="utf-8"))

    def test_bloqueo_exige_causa_y_leccion_registrada(self):
        import json
        plan = (ROOT / "PLAN-AGENTES.md").read_text(encoding="utf-8")
        self.assertIn("condición de desbloqueo", plan)
        self.assertIn("en masa", plan)
        self.assertIn("comentario con la **causa**", plan)
        self.assertIn("sin ese comentario en cada uno", plan)
        self.assertIn("Quien cierra la causa desbloquea", plan)
        self.assertIn("estado: disponible", plan)
        registros = (ROOT / "lecciones/registros/factory.jsonl").read_text(encoding="utf-8")
        ids = [json.loads(x)["id"] for x in registros.splitlines() if x.strip()]
        self.assertIn("factory-20260929-bloqueos-sin-causa", ids)


if __name__ == "__main__":
    unittest.main()
