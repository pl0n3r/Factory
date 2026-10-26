"""AC-01: redacción simple de puertas nuevas, sin cambiar autoridades legacy."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "seguridad"
if str(SECURITY) not in sys.path:
    sys.path.insert(0, str(SECURITY))

from puertas_humanas import (  # noqa: E402
    GateValidationError,
    classify_body,
    gate_identity,
    validate_gate,
)


def plain_gate():
    return {
        "category": "product-direction",
        "context": "Decidir si se preparan pruebas, sin activar nada real.",
        "title_simple": "¿Preparamos una prueba?",
        "summary_simple": (
            "Podemos comprobar el cambio con datos inventados.\n"
            "Todavía no se conectarán cuentas ni personas reales."
        ),
        "explain_simple": "Solo vamos a preparar una prueba, sin tocar sistemas reales.",
        "why_recommended": "La prueba permite revisar el resultado sin riesgos.",
        "blocks": "El trabajo de preparación queda pendiente.",
        "options": [
            {
                "id": "A",
                "label": "Preparar prueba",
                "effect": "Solo se crea una prueba con datos inventados.",
                "pros": ["No afecta personas reales"],
                "cons": ["No comprueba el servicio real"],
                "risk": "low",
                "cost": "",
                "reversible": True,
                "explain_simple": "Preparamos una prueba sin conectarnos a nadie.",
            },
            {
                "id": "B",
                "label": "No preparar todavía",
                "effect": "Se conserva el estado actual.",
                "pros": ["No hay cambios"],
                "cons": ["La prueba queda pendiente"],
                "risk": "low",
                "cost": "",
                "reversible": True,
                "explain_simple": "Dejamos todo como está por ahora.",
            },
        ],
        "recommendation": "A",
        "safe_default": "B",
    }


class PuertasLenguajeSimpleTests(unittest.TestCase):
    def test_gate_text_is_plain_language(self):
        """AC-01: acepta el texto claro y deniega jerga y frases largas."""
        good = plain_gate()
        normalized = validate_gate(good)
        self.assertEqual(normalized["title_simple"], good["title_simple"])
        self.assertEqual(
            classify_body("<!-- factory-human-gate "
                          + __import__("json").dumps(good, ensure_ascii=False)
                          + " -->")["status"], "gate"
        )

        bad_words = (
            "exact-main", "fail-closed", "exact-HEAD", "V3",
            "D-063", "journal v2", "SHA", "idempotencia", "#1516",
            "main@abcdef0123456789",
        )
        for forbidden in bad_words:
            with self.subTest(word=forbidden):
                bad = copy.deepcopy(good)
                bad["summary_simple"] = "Necesitamos " + forbidden + " para continuar."
                with self.assertRaises(GateValidationError):
                    validate_gate(bad)
                self.assertEqual(
                    classify_body("<!-- factory-human-gate "
                                  + __import__("json").dumps(bad)
                                  + " -->")["status"],
                    "invalid-gate",
                )

        for container, field in (
            ("root", "title_simple"),
            ("root", "explain_simple"),
            ("root", "why_recommended"),
            ("option", "label"),
            ("option", "effect"),
            ("option", "explain_simple"),
            ("option", "pros"),
            ("option", "cons"),
        ):
            with self.subTest(field=field):
                bad = copy.deepcopy(good)
                if container == "root":
                    bad[field] = "Este paso exige SHA para verificar la puerta."
                elif field in ("pros", "cons"):
                    bad["options"][0][field] = ["Requiere V3 para continuar"]
                else:
                    bad["options"][0][field] = "Este paso requiere exact-main."
                with self.assertRaises(GateValidationError):
                    validate_gate(bad)

        too_long = " ".join(["palabra"] * 26)
        for field in ("summary_simple", "explain_simple"):
            with self.subTest(field=field):
                bad = copy.deepcopy(good)
                bad[field] = too_long + "."
                with self.assertRaises(GateValidationError):
                    validate_gate(bad)

        boundary = copy.deepcopy(good)
        boundary["summary_simple"] = " ".join(["palabra"] * 25) + "."
        validate_gate(boundary)
        # Dos frases válidas no son una sola oración larga.
        boundary["summary_simple"] += " " + " ".join(["breve"] * 25) + "."
        validate_gate(boundary)

        # Puertas históricas incompletas no pierden validez ni identidad.
        legacy = {
            "category": "factory-release",
            "context": "Factory v1.0.42 main@" + "a" * 40,
            "title_simple": "Publicar Factory",
            "summary_simple": "Se requiere exact-HEAD y SHA para publicar.",
            "options": [
                {"id": "A", "label": "Publicar", "effect": "V3 aceptada"},
                {"id": "B", "label": "No publicar", "effect": "No cambia"},
            ],
            "recommendation": "B",
            "safe_default": "B",
        }
        self.assertEqual(validate_gate(legacy)["summary_simple"],
                         legacy["summary_simple"])
        self.assertEqual(gate_identity(legacy), gate_identity(copy.deepcopy(legacy)))


if __name__ == "__main__":
    unittest.main()
