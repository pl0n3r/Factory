"""Factory #1669: 16 brechas de provisión y lenguaje simple, sin red ni PII.

Un test sintético demuestra comportamiento local, NO una ejecución real o
una cobertura histórica fusionada. Lo que no se puede acreditar queda UNKNOWN.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import provision_project as provision

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "seguridad"
if str(SECURITY) not in sys.path:
    sys.path.insert(0, str(SECURITY))
from puertas_humanas import (  # noqa: E402
    GateValidationError, gate_authority_contract, validate_gate,
)

SHA = "a" * 40
UNKNOWN = "UNKNOWN"
UNITS = (
    "docs/provisioning.md:L9-U3",
    "docs/puertas-humanas-lenguaje-simple.md:L10-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L10-U2",
    "docs/puertas-humanas-lenguaje-simple.md:L12-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L14-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L15-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L19-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L28-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L3-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L30-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L35-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L4-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L47-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L8-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L9-U1",
    "docs/puertas-humanas-lenguaje-simple.md:L9-U2",
)


def synthetic_request():
    return {
        "project_id": "project-example", "project_slug": "example",
        "target_repository": "pl0n3r/Example", "governance_ref": provision.GOVERNANCE_REF,
        "idempotency_key": "b" * 64,
    }


def synthetic_gate():
    return {
        "category": "product-direction",
        "context": "Prueba de una decisión ficticia, sin sistemas externos.",
        "title_simple": "¿Preparamos una prueba?",
        "summary_simple": ("Podemos comprobar el cambio con datos inventados. "
                           "Todavía no se conectarán cuentas ni personas reales."),
        "explain_simple": "Se decide preparar una prueba sin tocar servicios reales.",
        "why_recommended": "La prueba permite revisar el resultado sin riesgos.",
        "blocks": "Solo pruebas sintéticas, sin publicar.",
        "options": [
            {"id": "A", "label": "Preparar prueba",
             "effect": "Solo se crea una prueba con datos inventados.",
             "explain_simple": "No afecta dinero, cuentas ni servicios reales."},
            {"id": "B", "label": "No preparar todavía",
             "effect": "Dejamos todo como está por ahora.",
             "explain_simple": "No se prepara ninguna prueba."},
        ],
        "recommendation": "A", "safe_default": "B",
    }


def matrix_rows():
    rows = {}
    for line in (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) >= 6:
            key = cells[1].strip("` ")
            if key in UNITS:
                rows.setdefault(key, []).append(cells)
    return rows


def unknown(reason):
    """La ausencia de evidencia no se transforma en un aprobado."""
    return {"status": UNKNOWN, "reason": reason, "sha": None}


class BrechasFactory51Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: los 16 IDs tienen evidencia funcional o brecha explícita."""
        raw = synthetic_gate()
        gate = validate_gate(raw)
        marker = provision.marker_for(synthetic_request(), SHA)
        changed_sha = provision.marker_for(synthetic_request(), "c" * 40)
        docs = (ROOT / "docs/puertas-humanas-lenguaje-simple.md").read_text(encoding="utf-8")
        # Algunos predicados son recomendaciones editoriales, NO gates automáticos.
        # Verificamos su ejemplo sin declarar que el validador los garantiza.
        weak_question = copy.deepcopy(raw)
        weak_question["title_simple"] = "Preparar prueba"
        weak_summary = copy.deepcopy(raw)
        weak_summary["summary_simple"] = "Resumen breve."
        weak_impact = copy.deepcopy(raw)
        weak_impact["explain_simple"] = "Preparamos una prueba."
        weak_impact["options"][0]["explain_simple"] = "Seguimos con la prueba."
        results = {
            UNITS[0]: (provision.MARKER_PATH == ".factory/provisioning.json"
                       and marker["governance_sha"] == SHA
                       and marker["request_identity"] == provision.identity(synthetic_request(), SHA)
                       and marker["request_identity"] != changed_sha["request_identity"]),
            UNITS[1]: (gate["options"][0]["label"] == "Preparar prueba"
                       and len(gate["options"][0]["label"]) < 80),
            UNITS[2]: (gate["options"][0]["effect"] == raw["options"][0]["effect"]
                       and gate["options"][0]["explain_simple"] == raw["options"][0]["explain_simple"]),
            UNITS[3]: ("dinero" in gate["options"][0]["explain_simple"]
                       and validate_gate(weak_impact)["options"][0]["id"] == "A"
                       and unknown("impact_not_semantically_enforced")["status"] == UNKNOWN),
            UNITS[4]: (gate["why_recommended"] == raw["why_recommended"]
                       and gate["recommendation"] == "A"),
            UNITS[5]: ("context" in gate and "summary_simple" in gate
                       and "SHA" not in gate["summary_simple"]),
            UNITS[6]: ("exact-main" in docs and "fail-closed" in docs
                       and "exact-HEAD" in docs),
            UNITS[7]: ("Todavía no se conectarán cuentas ni personas reales." in gate["summary_simple"]
                       and unknown("actual_connections_not_observed")["status"] == UNKNOWN),
            UNITS[8]: ("Las decisiones nuevas deben entenderse" in docs
                       and unknown("comprehension_not_measured")["status"] == UNKNOWN),
            UNITS[9]: (gate["options"][0]["effect"] == "Solo se crea una prueba con datos inventados."
                       and unknown("real_effect_not_observed")["status"] == UNKNOWN),
            UNITS[10]: (gate["why_recommended"] == "La prueba permite revisar el resultado sin riesgos."
                        and unknown("risk_not_observed")["status"] == UNKNOWN),
            UNITS[11]: ("preparar una prueba" in gate["explain_simple"]
                        and "sin tocar servicios reales" in gate["explain_simple"]),
            UNITS[12]: ("validación histórica" in docs
                        and "explain_simple" not in self._legacy_gate()
                        and gate_authority_contract(self._legacy_gate(), historical=True)
                        == gate_authority_contract(copy.deepcopy(self._legacy_gate()), historical=True)),
            UNITS[13]: (gate["title_simple"].endswith("?")
                        and validate_gate(weak_question)["title_simple"] == "Preparar prueba"
                        and unknown("question_is_recommendation")["status"] == UNKNOWN),
            UNITS[14]: (len(re.findall(r"[.!?](?:\s|$)", gate["summary_simple"])) == 2
                        and validate_gate(weak_summary)["summary_simple"] == "Resumen breve."
                        and unknown("two_or_three_sentences_not_enforced")["status"] == UNKNOWN),
            UNITS[15]: (len(gate["summary_simple"].split()) <= 25),
        }
        self.assertEqual(len(UNITS), 16)
        self.assertEqual(len(set(UNITS)), 16)
        self.assertEqual(set(results), set(UNITS))
        self.assertEqual(set(matrix_rows()), set(UNITS))
        for identifier, holds in results.items():
            with self.subTest(unit=identifier):
                self.assertTrue(holds, identifier + ": UNKNOWN")
                self.assertEqual(len(matrix_rows()[identifier]), 1)

    @staticmethod
    def _legacy_gate():
        return {"category": "product-direction", "context": "Caso histórico sintético.",
                "title_simple": "Publicar V3", "summary_simple": "Necesita exact-HEAD.",
                "options": [{"id": "A", "label": "Aceptar SHA", "effect": "Paso A"},
                            {"id": "B", "label": "No aceptar", "effect": "Paso B"}],
                "recommendation": "B", "safe_default": "B"}

    def test_falla_cerrado(self):
        """AC-02: SHA ambiguo, lenguaje inválido y entradas incompletas no son éxito."""
        with self.assertRaises(provision.ProvisionError):
            provision.marker_for(synthetic_request(), "unknown")
        for forbidden in ("exact-main", "fail-closed", "exact-HEAD", "V3", "SHA", "#1516"):
            with self.subTest(jargon=forbidden):
                candidate = synthetic_gate()
                candidate["summary_simple"] = "Requiere " + forbidden + " para continuar."
                with self.assertRaises(GateValidationError):
                    validate_gate(candidate)
        for field in ("summary_simple", "why_recommended", "explain_simple"):
            with self.subTest(field=field):
                candidate = synthetic_gate()
                candidate[field] = " ".join(["palabra"] * 26) + "."
                with self.assertRaises(GateValidationError):
                    validate_gate(candidate)
        for index, field in ((0, "effect"), (1, "label"), (1, "explain_simple")):
            candidate = synthetic_gate()
            candidate["options"][index][field] = "Requiere idempotencia para continuar."
            with self.assertRaises(GateValidationError):
                validate_gate(candidate)
        incomplete = synthetic_gate()
        del incomplete["summary_simple"]  # Opcional en compatibilidad; no certifica redacción.
        self.assertNotIn("summary_simple", validate_gate(incomplete))
        self.assertEqual(unknown("summary_missing")["status"], UNKNOWN)
        self.assertIsNone(unknown("summary_missing")["sha"])

    def test_sin_datos_reales(self):
        """AC-03: fixtures falsas, sin transporte y sin credenciales."""
        raw = synthetic_gate()
        with patch.object(provision, "urlopen", side_effect=AssertionError("network")) as outbound:
            marker = provision.marker_for(synthetic_request(), SHA)
            validated = validate_gate(raw)
            outbound.assert_not_called()
        self.assertEqual(marker["governance_sha"], SHA)
        self.assertEqual(validated["safe_default"], "B")
        payload = json.dumps({"request": synthetic_request(), "gate": raw}, ensure_ascii=False).lower()
        for secret in ("@gmail", "@outlook", "access_token", "secret_key", "https://", "http://"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, payload)

    def test_estados_unknown_explicitos(self):
        """AC-04: no promover evidencia de fixtures a estado CUBIERTO/live."""
        rows = matrix_rows()
        self.assertEqual(set(rows), set(UNITS))
        for identifier in UNITS:
            with self.subTest(unit=identifier):
                self.assertEqual(len(rows[identifier]), 1)
                self.assertEqual(rows[identifier][0][3], "NO_VERIFICABLE")
                self.assertIn("Contraste #1573", rows[identifier][0][4])
        reasons = (
            "provisioning_remote_sha_not_observed",
            "impact_not_semantically_enforced",
            "question_is_recommendation",
            "two_or_three_sentences_not_enforced",
            "actual_connections_not_observed",
            "risk_not_observed",
            "comprehension_not_measured",
            "legacy_real_decisions_not_observed",
        )
        for reason in reasons:
            evidence = unknown(reason)
            self.assertEqual(evidence["status"], UNKNOWN)
            self.assertTrue(evidence["reason"])
            self.assertIsNone(evidence["sha"])
            self.assertNotIn("success", evidence.values())


if __name__ == "__main__":
    unittest.main()
