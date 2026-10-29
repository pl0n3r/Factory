"""#1832: regresiones del código real de provisión y puertas humanas.

Datos sintéticos únicamente. No lee la matriz ni certifica ejecución live.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "seguridad"
if str(SECURITY) not in sys.path:
    sys.path.insert(0, str(SECURITY))

from scripts import provision_project as p  # noqa: E402
from puertas_humanas import (  # noqa: E402
    GateValidationError, classify_body, classify_event_text,
    gate_identity, validate_gate,
)

PROVISION = "docs/provisioning.md:"
SIMPLE = "docs/puertas-humanas-lenguaje-simple.md:"
HUMAN = "docs/puertas-humanas.md:"

OFFLINE = frozenset({
    PROVISION + "L9-U3",
    SIMPLE + "L10-U1", SIMPLE + "L10-U2", SIMPLE + "L14-U1",
    SIMPLE + "L15-U1", SIMPLE + "L19-U1", SIMPLE + "L47-U1",
    SIMPLE + "L9-U2", HUMAN + "B01", HUMAN + "B02", HUMAN + "B03",
})
EXTERNAL = {
    PROVISION + "L9-U2": "requiere verificar la descarga real independiente de Factory@v1",
}
POLICY = {
    SIMPLE + "L12-U1": "explicar impactos es editorial; el parser no comprueba su veracidad",
    SIMPLE + "L28-U1": "el ejemplo no conecta cuentas ni personas reales",
    SIMPLE + "L3-U1": "la inteligibilidad humana no es un algoritmo",
    SIMPLE + "L30-U1": "la opción A es ejemplo narrativo, no acción tipada",
    SIMPLE + "L35-U1": "recomendación ilustrativa, no regla de selección implementada",
    SIMPLE + "L4-U1": "explicar qué cambia es intención editorial",
    SIMPLE + "L8-U1": "preguntar es preferencia editorial; el schema solo valida texto",
    SIMPLE + "L9-U1": "dos o tres frases es guía; el parser limita líneas, no frases",
}


def sample_request():
    return {
        "project_id": "project-testcase", "project_slug": "testcase",
        "target_repository": "pl0n3r/TestCase",
        "governance_ref": p.GOVERNANCE_REF, "idempotency_key": "a" * 64,
    }


def sample_gate():
    return {
        "category": "product-direction",
        "context": "Probar una tarea antes de modificar un producto.",
        "title_simple": "¿Preparamos una prueba?",
        "summary_simple": (
            "Podemos revisar el cambio con datos inventados.\n"
            "No conectamos cuentas reales."
        ),
        "explain_simple": "Elegimos entre preparar una prueba y dejar todo igual.",
        "why_recommended": "Permite ver posibles errores sin activar servicios.",
        "blocks": "Esta decisión mantiene en espera el siguiente paso.",
        "options": [
            {
                "id": "A", "label": "Preparar prueba",
                "effect": "Solo creamos una prueba con datos inventados.",
                "pros": ["Podemos detectar errores"],
                "cons": ["Aún falta la revisión final"],
                "risk": "low", "cost": "", "reversible": True,
                "explain_simple": "Probamos sin usar servicios reales.",
            },
            {
                "id": "B", "label": "Mantener todo igual",
                "effect": "No creamos nada por ahora.",
                "pros": ["No hay cambios"],
                "cons": ["La revisión queda pendiente"],
                "risk": "low", "cost": "", "reversible": True,
                "explain_simple": "Dejamos la tarea sin cambios.",
            },
        ],
        "recommendation": "A", "safe_default": "B",
    }


def embedded_suite(file_name, class_name, methods):
    """Ejecuta regresiones existentes que invocan APIs reales con fakes."""
    file = SECURITY / file_name
    spec = importlib.util.spec_from_file_location("factory41_" + file.stem, file)
    if spec is None or spec.loader is None:
        raise AssertionError("No se pudo importar la regresión funcional")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(
        loader.loadTestsFromName(f"{class_name}.{method}", module)
        for method in methods
    )
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        raise AssertionError(
            f"Regresión {class_name}: {result.failures!r} {result.errors!r}"
        )
    if result.testsRun != len(methods):
        raise AssertionError("No se ejecutaron las regresiones requeridas")
    return result.testsRun


class CoberturaFactory41Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: SHA materializado, esquema, lenguaje, decisión y dedup."""
        exercised = set()
        self.assertEqual(len(OFFLINE | EXTERNAL.keys() | POLICY.keys()), 20)
        self.assertEqual((len(OFFLINE), len(EXTERNAL), len(POLICY)), (11, 1, 8))

        # La provisión escribe .factory/provisioning.json con el SHA exacto.
        req, sha = p.validate_request(sample_request()), "b" * 40
        marker = p.marker_for(req, sha)
        self.assertEqual((marker["governance_sha"], marker["version"]), (sha, 2))
        visited = []
        gateway = p.GitHubGateway("fixture-only")

        def fake_git(cwd, *argv, env=None):
            visited.append(argv)
            if argv and argv[0] == "push":
                data = json.loads(
                    (cwd / p.MARKER_PATH).read_text(encoding="utf-8")
                )
                self.assertEqual(data, marker)
                self.assertEqual(data["governance_sha"], sha)
                self.assertEqual(data["request_identity"], p.identity(req, sha))

        with mock.patch.object(gateway, "_git", side_effect=fake_git), \
             mock.patch.object(gateway, "set_default") as set_default, \
             mock.patch.object(p, "urlopen", side_effect=AssertionError("red prohibida")):
            gateway.bootstrap(
                req["target_repository"], {"AGENTES.md": "fixture"}, marker
            )
        self.assertEqual(sum(args[0] == "push" for args in visited), 1)
        set_default.assert_called_once_with(req["target_repository"])
        exercised.add(PROVISION + "L9-U3")

        gate = sample_gate()
        normalized = validate_gate(gate)
        self.assertEqual(normalized["options"][0]["label"], "Preparar prueba")
        exercised.add(SIMPLE + "L10-U1")
        self.assertEqual(normalized["options"][0]["effect"], gate["options"][0]["effect"])
        self.assertEqual(
            normalized["options"][0]["explain_simple"],
            gate["options"][0]["explain_simple"],
        )
        exercised.add(SIMPLE + "L10-U2")
        self.assertEqual(normalized["why_recommended"], gate["why_recommended"])
        exercised.add(SIMPLE + "L14-U1")

        with_context = copy.deepcopy(gate)
        with_context["context"] = "Referencia técnica main@" + "a" * 40
        self.assertEqual(
            validate_gate(with_context)["context"], with_context["context"]
        )
        exercised.add(SIMPLE + "L15-U1")
        for forbidden in (
            "exact-main", "fail-closed", "exact-HEAD", "V3", "D-063",
            "journal", "SHA", "idempotencia", "#1516",
        ):
            with self.subTest(jargon=forbidden):
                invalid = copy.deepcopy(gate)
                invalid["summary_simple"] = (
                    "Necesitamos " + forbidden + " para continuar."
                )
                with self.assertRaises(GateValidationError):
                    validate_gate(invalid)
        exercised.add(SIMPLE + "L19-U1")

        legacy = copy.deepcopy(gate)
        legacy.pop("explain_simple")
        for option in legacy["options"]:
            option.pop("explain_simple")
        legacy["summary_simple"] = "Necesitamos SHA para continuar."
        self.assertEqual(
            validate_gate(legacy)["summary_simple"], legacy["summary_simple"]
        )
        self.assertEqual(
            gate_identity(legacy), gate_identity(copy.deepcopy(legacy))
        )
        exercised.add(SIMPLE + "L47-U1")

        too_long = copy.deepcopy(gate)
        too_long["summary_simple"] = " ".join(["palabra"] * 26) + "."
        with self.assertRaises(GateValidationError):
            validate_gate(too_long)
        boundary = copy.deepcopy(gate)
        boundary["summary_simple"] = " ".join(["palabra"] * 25) + "."
        validate_gate(boundary)
        exercised.add(SIMPLE + "L9-U2")

        body = (
            "<!-- factory-human-gate "
            + json.dumps(gate, ensure_ascii=False) + " -->"
        )
        self.assertEqual(classify_body(body)["status"], "gate")
        event = json.dumps({
            "action": "opened",
            "issue": {
                "body": body, "author_association": "OWNER", "state": "open",
            },
        }, ensure_ascii=False)
        self.assertEqual(
            classify_event_text(event)["category"], "product-direction"
        )
        self.assertEqual(embedded_suite(
            "test_puertas_humanas.py", "GateTests", (
                "test_workflow_rejects_untrusted_issue_authors_and_cleans_stale_queue",
                "test_invalid_gate_reports_safe_error",
            )), 2)
        exercised.add(HUMAN + "B01")

        self.assertEqual(embedded_suite(
            "test_decision_respuesta.py", "DecisionRespuestaTests", (
                "test_authorized_exact_command_completes_valid_gate",
                "test_retry_is_idempotent",
            )), 2)
        exercised.add(HUMAN + "B02")

        self.assertEqual(embedded_suite(
            "test_puertas_humanas.py", "GateDedupTests", (
                "test_concurrent_gate_sync_exposes_only_canonical_issue",
                "test_historical_duplicates_reconcile_and_conflicts_fail_closed",
            )), 2)
        exercised.add(HUMAN + "B03")
        self.assertEqual(exercised, OFFLINE)

    def test_falla_cerrado(self):
        """AC-02: datos inválidos, autoridad insuficiente y texto inseguro."""
        for invalid in (
            {**sample_request(), "target_repository": "evil/repo"},
            {**sample_request(), "governance_ref": "factory@main"},
            {**sample_request(), "idempotency_key": "invalid"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(p.ProvisionError):
                    p.validate_request(invalid)
        with self.assertRaises(p.ProvisionError):
            p.validate_sha("invalid-sha")
        gateway = p.GitHubGateway("fixture-only")
        with mock.patch.object(
            gateway, "_request", return_value={"login": "untrusted"}
        ):
            with self.assertRaises(p.ProvisionError):
                gateway.authorize()

        for tweak in (
            {"recommendation": "D"},
            {"title_simple": ""},
            {"summary_simple": "\n".join(("a", "b", "c", "d"))},
        ):
            invalid = {**sample_gate(), **tweak}
            with self.subTest(field=tweak):
                with self.assertRaises(GateValidationError):
                    validate_gate(invalid)

        legacy = sample_gate()
        del legacy["options"][0]["explain_simple"]
        self.assertEqual(
            classify_body(
                "<!-- factory-human-gate " + json.dumps(legacy) + " -->"
            )["status"], "gate"
        )
        invalid_event = json.dumps({
            "issue": {"body": "<!-- factory-human-gate {invalid -->"}
        })
        self.assertEqual(
            classify_event_text(invalid_event)["status"], "invalid-gate"
        )
        self.assertEqual(embedded_suite(
            "test_decision_respuesta.py", "DecisionRespuestaTests", (
                "test_untrusted_bot_or_free_text_is_noop",
                "test_invalid_option_marker_or_queue_fails_closed",
            )), 2)

    def test_sin_datos_reales(self):
        """AC-03: ninguna prueba requiere datos, cuentas o tokens reales."""
        gate = sample_gate()
        original = copy.deepcopy(gate)
        normalized = validate_gate(gate)
        self.assertEqual(gate, original)
        self.assertEqual(normalized["options"][0]["cost"], "")
        self.assertTrue(all(
            option["reversible"] for option in normalized["options"]
        ))
        req = p.validate_request(sample_request())
        self.assertEqual(req["target_repository"], "pl0n3r/TestCase")
        marker = p.marker_for(req, "b" * 40)
        self.assertNotIn("token", json.dumps(marker).lower())
        self.assertEqual(marker["governance_sha"], "b" * 40)
        self.assertEqual((len(EXTERNAL), len(POLICY)), (1, 8))


if __name__ == "__main__":
    unittest.main()
