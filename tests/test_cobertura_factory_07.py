#!/usr/bin/env python3
"""Factory #1798: nota STATE real; límites del contrato conversacional.

Solo L39-U1 dispone de una función local ejecutable: parse_state, en la
suite de continuidad ya versionada. Las demás cláusulas describen conducta
de agentes, políticas de prompts o estados reales de la plataforma. Esta
prueba NO simula observación de chats, revisión de plataforma ni seguridad.
No lee ninguna matriz, no realiza I/O remoto y usa datos sintéticos.
"""
from __future__ import annotations

from functools import lru_cache
import importlib.util
from pathlib import Path
import re
import socket
import unittest
import urllib.request
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIELDS = frozenset({
    "objetivo", "repo", "issue", "pr", "head", "decisiones",
    "confirmado", "no repetir", "pendiente", "siguiente",
})
A = frozenset({"L39-U1"})
B = {
    "L65-U1": "aviso real de revisión ChatGPT web requiere UI y sesión externa",
    "L65-U2": "espera única y continuación tras aviso requieren interacción real",
}
C = {
    "L12-U3": "ejemplo de un mensaje, no ejecución de una sesión real",
    "L13-U1": "ejemplo textual de diagnóstico A, no motor de decisiones",
    "L13-U2": "ejemplo textual de cambio de estrategia, no política programática",
    "L15-U1": "prohibición discursiva de progreso vacío en el prompt",
    "L43-U1": "instrucción a agentes de no reexplicar lo documentado",
    "L44-U1": "orden normativo de consultas, sin runtime de búsquedas aquí",
    "L44-U2": "instrucción de lectura selectiva, no mecanismo ejecutable",
    "L45-U1": "recomendación de agrupar lecturas; depende del agente",
    "L46-U1": "política de evitar polling de CI; depende del agente",
    "L47-U1": "criterio editorial de presentación del resultado",
    "L47-U2": "extensión de hitos de chat, no validador de salidas",
    "L48-U1": "no duplicar mensajes de GitHub es una conducta del agente",
    "L57-U1": "atribución de responsabilidad a integración, no implementación",
    "L66-U1": "recomendación de una tarea acotada por turno",
    "L66-U2": "prohibición de pegar secretos/logs; no prueba todas las sesiones",
    "L66-U3": "restricción a ejecuciones innecesarias; política de prompt",
    "L66-U4": "recomendación de describir finalidad de comandos de seguridad",
}


@lru_cache(maxsize=1)
def real_parser():
    """Importa el código existente, sin copiar ni reimplementar parse_state."""
    file = ROOT / "tests" / "test_conversacion_agentes.py"
    if not file.is_file():
        raise AssertionError("UNKNOWN: parser real de continuidad ausente")
    spec = importlib.util.spec_from_file_location(
        "factory_1798_real_conversation_parser", file
    )
    if spec is None or spec.loader is None:
        raise AssertionError("UNKNOWN: loader de parser no disponible")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "parse_state", None)):
        raise AssertionError("UNKNOWN: parse_state no es callable")
    return module.parse_state


def sample_state() -> str:
    """Todas las referencias son ficticias; ningún ID ni SHA de trabajo real."""
    return "\n".join((
        "STATE",
        "objetivo: comprobar recuperación de una nota sintética",
        "repo: pl0n3r/Factory",
        "issue: #42",
        "pr: #43",
        "head: trabajo/issue-42@" + "a" * 40,
        "decisiones:",
        "- probar exclusivamente un contrato local",
        "- no usar sesiones externas",
        "confirmado:",
        "- el parser mantiene los campos y listas",
        "no repetir:",
        "- volver a ejecutar un intento inválido",
        "pendiente:",
        "- comprobación sintética de CI",
        "siguiente: validar la nota sin historial",
    ))


class CoberturaFactory07Tests(unittest.TestCase):
    def test_contrato_principal(self):
        """AC-01: L39-U1 invoca parse_state, no compara texto de la matriz."""
        self.assertEqual((len(A), len(B), len(C)), (1, 2, 17))
        self.assertEqual(len(A | B.keys() | C.keys()), 20)
        self.assertFalse(A & B.keys())
        self.assertFalse(A & C.keys())
        self.assertFalse(B.keys() & C.keys())

        result = real_parser()(sample_state())
        self.assertEqual(set(result), FIELDS)
        self.assertEqual(result["objetivo"],
                         ["comprobar recuperación de una nota sintética"])
        self.assertEqual(result["repo"], ["pl0n3r/Factory"])
        self.assertEqual(result["issue"], ["#42"])
        self.assertEqual(result["pr"], ["#43"])
        self.assertRegex(result["head"][0],
                         r"^trabajo/issue-42@[a-f0-9]{40}$")
        self.assertEqual(result["decisiones"], [
            "probar exclusivamente un contrato local",
            "no usar sesiones externas",
        ])
        self.assertEqual(result["confirmado"],
                         ["el parser mantiene los campos y listas"])
        self.assertEqual(result["no repetir"],
                         ["volver a ejecutar un intento inválido"])
        self.assertEqual(result["pendiente"],
                         ["comprobación sintética de CI"])
        self.assertEqual(result["siguiente"],
                         ["validar la nota sin historial"])

        # También procesa la fixture canónica sin exigir un chat anterior.
        fixture = (ROOT / "tests" / "fixtures" /
                   "estado_compacto.md").read_text(encoding="utf-8")
        from_repo = real_parser()(fixture)
        self.assertEqual(set(from_repo), FIELDS)
        self.assertTrue(re.fullmatch(r"\S+@[a-f0-9]{40}",
                                     from_repo["head"][0]))
        self.assertTrue(from_repo["no repetir"])
        self.assertTrue(from_repo["siguiente"])

    def test_falla_cerrado(self):
        """AC-02: un encabezado/no lista ilegibles no generan estado válido."""
        parser = real_parser()
        with self.assertRaises(ValueError):
            parser("objetivo: sin cabecera STATE")
        with self.assertRaises(IndexError):
            parser("")
        with self.assertRaises(KeyError):
            parser("STATE\n- lista huérfana")
        # El parser es un helper, NO valida obligatoriedad de todos los
        # campos. El consumidor debe negar una nota incompleta. No presentar
        # este contraejemplo como una garantía de runtime inexistente.
        incomplete = parser("STATE\nrepo: pl0n3r/Factory")
        self.assertNotEqual(set(incomplete), FIELDS)
        self.assertFalse(FIELDS.issubset(incomplete))
        self.assertEqual(real_parser()(sample_state())["head"][0].split("@")[0],
                         "trabajo/issue-42")

    def test_sin_datos_reales(self):
        """AC-03: el parser y los escenarios no necesitan red ni credenciales."""
        with (
            mock.patch.object(socket, "create_connection",
                              side_effect=AssertionError("red no autorizada")),
            mock.patch.object(urllib.request, "urlopen",
                              side_effect=AssertionError("red no autorizada")),
        ):
            parsed = real_parser()(sample_state())
            parsed_again = real_parser()(sample_state())
        self.assertEqual(parsed, parsed_again)
        self.assertEqual(parsed["head"],
                         ["trabajo/issue-42@" + "a" * 40])
        self.assertEqual(parsed["repo"], ["pl0n3r/Factory"])
        self.assertEqual(parsed["issue"], ["#42"])
        serialized = sample_state().lower()
        for forbidden in ("access_token", "api_key", "password",
                          "client_secret", "private_key",
                          "authorization: bearer", "cookie:"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
