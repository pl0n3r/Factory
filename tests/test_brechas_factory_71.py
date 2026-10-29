"""Regresiones offline para las 16 brechas de Factory#1689.

Las aserciones locales pueden acreditar contratos/fixtures sintéticos, pero no
convierten afirmaciones históricas ni horarios documentados en hechos observados.
"""
from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
VERIFIED = "VERIFIED_SYNTHETIC"

# Sin fuente canónica externa individual, estas afirmaciones históricas siguen
# abiertas. Cada ID conserva la afirmación concreta que debe contrastarse.
HISTORICAL = {
    "L9-U1": "clasificación de puertas, asignación y recepción móvil real quedaron verificadas",
    "L9-U2": "decisiones humanas siguen siendo explícitas y nunca se infieren",
    "L13-U1": "escritura cross-repo requiere una **GitHub App dedicada**",
    "L25-U1": "#1–#14: cerrados conforme al contrato vigente",
    "L26-U1": "#54: privacidad como código cerrada tras revalidación",
    "L27-U1": "#83: raíz de confianza del canal `v1` resuelta",
    "L28-U1": "`v1.0.0`: GitHub Release publicada y self-test consumidor en verde",
    "L29-U1": "TANDA 1 global: completada",
    "L33-U1": "cierre de TANDA 1 anterior permanece histórico y no se reescribe",
    "L35-U1": "Un cambio en `main` no modifica por sí solo el canal publicado `@v1`",
}
HISTORICAL_IDS = tuple("docs/tanda1-handoff.md:" + key for key in HISTORICAL)
DAILY_ID = "docs/unattended-daily-summary.md:B04"
FIXTURE_CONTRACTS = {
    "L10-U1": ("allow", "ALLOW", "fresh", "ALLOW"),
    "L11-U1": ("pause", "PAUSE", "fresh", "PAUSE"),
    "L12-U1": ("blocked", "BLOCKED", "fresh", "BLOCKED"),
    "L13-U1": ("unknown", "BLOCKED", "unknown", UNKNOWN),
    "L19-U1": ("allow", "ALLOW", "fresh", "ALLOW"),
}
FIXTURE_IDS = tuple("docs/unattended-handoff-consumer-pack.md:" + key
                    for key in FIXTURE_CONTRACTS)
IDS = HISTORICAL_IDS + (DAILY_ID,) + FIXTURE_IDS
PERMISSIONS = {name: False for name in ("reserve", "merge", "deploy", "spend", "live")}
REQUIRED = {"version", "action", "next_transition", "authority", "work_identity",
            "work_class", "freshness", "reasons", "provenance", "incidents",
            "interrupt_owner", "permissions"}
PROVENANCE = {"head_sha", "dispatch_ref", "guard_ref", "watchdog_ref", "freshness"}


def document(path: str) -> str:
    """Solo artefactos versionados del repositorio; nunca consulta la red."""
    return (ROOT / path).read_text(encoding="utf-8")


def load_fixture(name: str) -> dict:
    return json.loads(document("tests/fixtures/unattended_handoff_v1/" + name + ".json"))


def visible(payload: object) -> str:
    """Proyección defensiva para pruebas; rechaza autoridad y shape ambiguos."""
    if not isinstance(payload, dict) or set(payload) != REQUIRED:
        return UNKNOWN
    if type(payload["version"]) is not int or payload["version"] != 1:
        return UNKNOWN
    if payload["authority"] != "unchanged":
        return UNKNOWN
    perms = payload["permissions"]
    if not isinstance(perms, dict) or set(perms) != set(PERMISSIONS):
        return UNKNOWN
    if any(perms[key] is not False for key in PERMISSIONS):
        return UNKNOWN
    action = payload["action"]
    freshness = payload["freshness"]
    if (action not in ("ALLOW", "PAUSE", "BLOCKED")
            or payload["next_transition"] != action
            or freshness not in ("fresh", "stale", "unknown")):
        return UNKNOWN
    if not isinstance(payload["reasons"], list) or not isinstance(payload["incidents"], list):
        return UNKNOWN
    if (any(not isinstance(x, str) or not x for x in payload["reasons"] + payload["incidents"])
            or len(set(payload["reasons"])) != len(payload["reasons"])
            or len(set(payload["incidents"])) != len(payload["incidents"])):
        return UNKNOWN
    if payload["interrupt_owner"] is not None and type(payload["interrupt_owner"]) is not bool:
        return UNKNOWN
    identity, klass = payload["work_identity"], payload["work_class"]
    if (identity is None) != (klass is None):
        return UNKNOWN
    if identity is not None and (not isinstance(identity, str) or not isinstance(klass, str)
                                 or not identity or not klass):
        return UNKNOWN
    if action == "ALLOW" and (freshness != "fresh" or identity is None):
        return UNKNOWN
    if action == "PAUSE" and (freshness != "fresh" or identity is not None):
        return UNKNOWN
    if action == "BLOCKED" and identity is not None:
        return UNKNOWN
    provenance = payload["provenance"]
    if provenance is None:
        if freshness != "unknown":
            return UNKNOWN
    elif not isinstance(provenance, dict) or set(provenance) != PROVENANCE:
        return UNKNOWN
    elif (provenance["freshness"] != freshness
          or not isinstance(provenance["head_sha"], str)
          or not re.fullmatch(r"[0-9a-f]{40}", provenance["head_sha"])
          or any(not isinstance(provenance[key], str) or
                 not re.fullmatch(r"[0-9a-f]{64}", provenance[key])
                 for key in ("guard_ref", "watchdog_ref"))
          or not isinstance(provenance["dispatch_ref"], str)
          or not provenance["dispatch_ref"]):
        return UNKNOWN
    return UNKNOWN if freshness != "fresh" else action


def evidence(row: str, inputs: dict[str, object] | None = None) -> str:
    """Ningún texto o fixture sintético acredita hechos de GitHub/producción."""
    inputs = inputs or {}
    if row in HISTORICAL_IDS or row == DAILY_ID:
        return UNKNOWN  # Sin observaciones independientes, conservar la brecha.
    if row not in FIXTURE_IDS:
        return UNKNOWN
    name = FIXTURE_CONTRACTS[row.split(":", 1)[1]][0]
    payload = inputs.get(name)
    if payload is None:
        return UNKNOWN
    observed = visible(payload)
    expected = FIXTURE_CONTRACTS[row.split(":", 1)[1]][3]
    if observed != expected:
        return UNKNOWN
    return VERIFIED if expected != UNKNOWN else UNKNOWN


class BrechasFactory71Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical = document("docs/tanda1-handoff.md")
        cls.summary = document("docs/unattended-daily-summary.md")
        cls.handoff = document("docs/unattended-handoff-consumer-pack.md")
        cls.workflow = document(".github/workflows/unattended-watchdog.yml")
        cls.fixtures = {name: load_fixture(name) for name in ("allow", "pause", "blocked", "unknown")}

    def test_contrato_principal(self):
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        for key, excerpt in HISTORICAL.items():
            with self.subTest(row="docs/tanda1-handoff.md:" + key):
                self.assertIn(excerpt, self.historical)
                self.assertEqual(evidence("docs/tanda1-handoff.md:" + key), UNKNOWN)
        self.assertIn("08:00 America/Bogota", self.summary)
        self.assertIn("0 13 * * *", self.summary)
        self.assertEqual(evidence(DAILY_ID), UNKNOWN)  # cron documentado != run real
        for key, (name, action, freshness, result) in FIXTURE_CONTRACTS.items():
            row = "docs/unattended-handoff-consumer-pack.md:" + key
            with self.subTest(row=row):
                self.assertIn("`tests/fixtures/unattended_handoff_v1/" + name + ".json`", self.handoff)
                self.assertEqual(self.fixtures[name]["action"], action)
                self.assertEqual(self.fixtures[name]["freshness"], freshness)
                self.assertEqual(visible(self.fixtures[name]), result)
                self.assertEqual(evidence(row, self.fixtures),
                                 UNKNOWN if result == UNKNOWN else VERIFIED)

    def test_falla_cerrado(self):
        self.assertEqual(evidence("docs/no-existe:L1-U1", self.fixtures), UNKNOWN)
        for row in FIXTURE_IDS:
            self.assertEqual(evidence(row), UNKNOWN)
        sample = self.fixtures["allow"]
        mutations = (
            {**sample, "version": 2},
            {**sample, "authority": "grant"},
            {**sample, "freshness": "unknown"},
            {**sample, "next_transition": "PAUSE"},
            {**sample, "extra": True},
            {key: value for key, value in sample.items() if key != "provenance"},
            {**sample, "permissions": {**PERMISSIONS, "merge": True}},
            {**sample, "provenance": {**sample["provenance"], "head_sha": "not-a-sha"}},
            {**sample, "work_class": None},
        )
        for payload in mutations:
            with self.subTest(payload=repr(payload)[:90]):
                self.assertEqual(visible(payload), UNKNOWN)
        self.assertEqual(visible(None), UNKNOWN)

    def test_sin_datos_reales(self):
        # El código bajo prueba usa exclusivamente archivos y fixtures locales.
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("HTTP forbidden")):
            for name, payload in self.fixtures.items():
                with self.subTest(fixture=name):
                    self.assertEqual(payload["permissions"], PERMISSIONS)
                    self.assertEqual(payload["authority"], "unchanged")
                    self.assertIn(visible(load_fixture(name)), ("ALLOW", "PAUSE", "BLOCKED", UNKNOWN))
                    self.assertEqual(payload["work_identity"] in (None, "Factory#797"), True)
        self.assertTrue(all(row.startswith("docs/") for row in IDS))

    def test_estados_unknown_explicitos(self):
        # La retirada del cron real conserva la brecha: un texto no es un job.
        self.assertNotIn("0 13 * * *", self.workflow)
        for row in HISTORICAL_IDS + (DAILY_ID,):
            with self.subTest(row=row):
                self.assertEqual(evidence(row, self.fixtures), UNKNOWN)
        ambiguous = copy.deepcopy(self.fixtures["unknown"])
        ambiguous["action"] = "ALLOW"
        self.assertEqual(visible(ambiguous), UNKNOWN)
        self.assertEqual(visible(self.fixtures["unknown"]), UNKNOWN)
        matrix = document("docs/matriz-cobertura.md")
        for row in IDS:
            with self.subTest(matrix_row=row):
                self.assertEqual(matrix.count("| `" + row + "` |"), 1)
        self.assertIn("`UNKNOWN` **no** amplía el enum de `action`", self.handoff)


if __name__ == "__main__":
    unittest.main()
