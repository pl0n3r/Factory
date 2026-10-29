#!/usr/bin/env python3
"""Regresiones del pack consumer-neutral del handoff desatendido Factory#799."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "unattended_handoff_v1"
DOC_PATH = ROOT / "docs" / "unattended-handoff-consumer-pack.md"

EXPECTED_PERMISSIONS = {
    "reserve": False,
    "merge": False,
    "deploy": False,
    "spend": False,
    "live": False,
}


def _load(name: str) -> dict[str, object]:
    with (FIXTURE_DIR / f"{name}.json").open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AssertionError(f"fixture {name} must be an object")
    return payload


def _consumer_state(payload: dict[str, object]) -> str:
    """Proyección mínima: no recalcula ranking, 4B, 4C ni autoridad."""

    if payload.get("freshness") == "unknown":
        return "UNKNOWN"
    action = payload.get("action")
    if action in {"ALLOW", "PAUSE", "BLOCKED"}:
        return str(action)
    raise AssertionError("canonical fixture contains unsupported action")



# Factory#1690: contratos locales de 16 filas de la matriz.
# Las seis filas de consumidores externos continúan UNKNOWN:
# la prueba sintética no acredita un E2E ni una reserva/merge.
import copy

MATRIX = ROOT / "docs/matriz-cobertura.md"
SCHEMA = ROOT / "config/unattended-handoff-v1.schema.json"
IDS = tuple(
    "docs/unattended-handoff-consumer-pack.md:" + suffix for suffix in (
        "L29-U1", "L30-U1", "L33-U1", "L43-U1",
        "L49-U1", "L5-U1", "L51-U1", "L52-U1",
        "L53-U1", "L54-U1", "L55-U1", "L56-U1",
        "L58-U1", "L63-U1", "L64-U1", "L67-U1",
    )
)
EXTERNAL_UNKNOWN = frozenset(
    "docs/unattended-handoff-consumer-pack.md:" + suffix for suffix in (
        "L5-U1", "L33-U1", "L43-U1",
        "L63-U1", "L64-U1", "L67-U1",
    )
)
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_CONTRACT"


def _rows(raw):
    """Falla cerrado ante IDs omitidos, duplicados o filas ambiguas."""
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| "):
            continue
        parts = tuple(x.strip() for x in line.strip("|").split("|"))
        if not parts:
            continue
        key = parts[0].strip(chr(96))
        if key not in IDS:
            continue
        if (key in found or len(parts) != 5 or
                parts[0] != chr(96) + key + chr(96) or
                not line.rstrip().endswith("|")):
            raise ValueError("UNKNOWN: matriz ambigua")
        found[key] = parts
    if set(found) != set(IDS):
        raise ValueError("UNKNOWN: matriz incompleta")
    return found


def _schema_is_denial(schema):
    """Comprueba invariantes locales, no sustituye un validador JSON Schema."""
    if type(schema) is not dict:
        return False
    try:
        properties = schema["properties"]
        rights = schema["$defs"]["permissions"]
        return (
            schema["type"] == "object"
            and schema["additionalProperties"] is False
            and set(schema["required"]) == set(properties)
            and properties["version"]["const"] == 1
            and properties["authority"]["const"] == "unchanged"
            and set(properties["action"]["enum"]) == {"ALLOW", "PAUSE", "BLOCKED"}
            and set(properties["next_transition"]["enum"]) == {"ALLOW", "PAUSE", "BLOCKED"}
            and set(properties["freshness"]["enum"]) == {"fresh", "stale", "unknown"}
            and rights["additionalProperties"] is False
            and set(rights["required"]) == set(EXPECTED_PERMISSIONS)
            and set(rights["properties"]) == set(EXPECTED_PERMISSIONS)
            and all(rights["properties"][key]["const"] is False
                    for key in EXPECTED_PERMISSIONS)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _safe_projection(payload, schema):
    """Simulación aislada; nunca deriva permiso operativo del handoff."""
    if type(payload) is not dict or not _schema_is_denial(schema):
        return UNKNOWN
    if set(payload) != set(schema["required"]):
        return UNKNOWN
    if (type(payload["version"]) is not int or payload["version"] != 1
            or payload["authority"] != "unchanged"
            or type(payload["permissions"]) is not dict
            or payload["permissions"] != EXPECTED_PERMISSIONS
            or any(type(x) is not bool
                   for x in payload["permissions"].values())):
        return UNKNOWN
    action, transition = payload["action"], payload["next_transition"]
    freshness = payload["freshness"]
    if (type(action) is not str
            or action not in {"ALLOW", "PAUSE", "BLOCKED"}
            or transition != action
            or freshness not in {"fresh", "stale", "unknown"}):
        return UNKNOWN
    if (type(payload["reasons"]) is not list
            or type(payload["incidents"]) is not list
            or any(type(x) is not str or not x
                   for x in payload["reasons"] + payload["incidents"])):
        return UNKNOWN
    provenance = payload["provenance"]
    if provenance is not None and (
        type(provenance) is not dict
        or set(provenance) != {
            "head_sha", "dispatch_ref", "guard_ref", "watchdog_ref", "freshness"
        }
        or provenance["freshness"] != freshness
    ):
        return UNKNOWN
    if freshness != "fresh" or provenance is None:
        return UNKNOWN
    if action != "ALLOW" and (
        payload["work_identity"] is not None or payload["work_class"] is not None
    ):
        return UNKNOWN
    try:
        return _consumer_state(payload)
    except (TypeError, ValueError, KeyError, AssertionError):
        return UNKNOWN


def _report(rows, fixtures, schema, document):
    outcome = dict.fromkeys(IDS, UNKNOWN)
    if not _schema_is_denial(schema):
        return outcome
    if set(fixtures) != {"allow", "pause", "blocked", "unknown"}:
        return outcome
    visible = {name: _safe_projection(p, schema)
               for name, p in fixtures.items()}
    if visible != {"allow": "ALLOW", "pause": "PAUSE",
                   "blocked": "BLOCKED", "unknown": UNKNOWN}:
        return outcome
    if ("no se deriva una transición nueva" not in document or
            "no un capability token" not in document or
            "`UNKNOWN` **no** amplía el enum de `action`" not in document):
        return outcome
    if not all(row[2] == "NO_VERIFICABLE" and row[1] and row[3]
               for row in rows.values()):
        return outcome
    for key in IDS:
        if key in EXTERNAL_UNKNOWN:
            continue
        suffix = key.rsplit(":", 1)[1]
        if suffix in {"L29-U1", "L30-U1"}:
            passed = all(p["action"] == p["next_transition"]
                         for p in fixtures.values())
        elif suffix in {"L49-U1", "L51-U1"}:
            passed = all(p["authority"] == "unchanged"
                         for p in fixtures.values())
        elif suffix in {"L52-U1", "L53-U1", "L54-U1", "L55-U1", "L56-U1"}:
            permission = {"L52-U1": "reserve", "L53-U1": "merge",
                          "L54-U1": "deploy", "L55-U1": "spend",
                          "L56-U1": "live"}[suffix]
            passed = (
                f"`permissions.{permission}=false`" in document and
                all(p["permissions"][permission] is False
                    for p in fixtures.values())
            )
        elif suffix == "L58-U1":
            passed = (
                "incluso un documento `ALLOW` **no autoriza**" in document
                and all(p["permissions"] == EXPECTED_PERMISSIONS
                        for p in fixtures.values())
            )
        else:
            passed = False
        if passed:
            outcome[key] = LOCAL
    return outcome


class BrechasFactory72Tests(TestCase):
    def _sources(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        fixtures = {n: _load(n) for n in ("allow", "pause", "blocked", "unknown")}
        rows = _rows(MATRIX.read_text(encoding="utf-8"))
        doc = DOC_PATH.read_text(encoding="utf-8")
        return schema, fixtures, rows, doc

    def test_contrato_principal(self):
        schema, fixtures, rows, doc = self._sources()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        self.assertEqual(set(rows), set(IDS))
        result = _report(rows, fixtures, schema, doc)
        for key in IDS:
            with self.subTest(id=key):
                self.assertEqual(
                    result[key], UNKNOWN if key in EXTERNAL_UNKNOWN else LOCAL
                )
        for name, expected in (
            ("allow", "ALLOW"), ("pause", "PAUSE"),
            ("blocked", "BLOCKED"), ("unknown", UNKNOWN)
        ):
            with self.subTest(name=name):
                self.assertEqual(_safe_projection(fixtures[name], schema), expected)

    def test_falla_cerrado(self):
        schema, fixtures, rows, doc = self._sources()
        seed = fixtures["allow"]
        for field, value in (
            ("version", True), ("version", 2),
            ("action", "UNKNOWN"), ("next_transition", "PAUSE"),
            ("authority", "approved"), ("freshness", "stale"),
            ("freshness", "unknown"), ("provenance", None),
            ("reasons", "invalid"), ("incidents", [False]),
            ("permissions", {"reserve": True, "merge": False,
                             "deploy": False, "spend": False, "live": False}),
        ):
            with self.subTest(field=field, value=value):
                payload = copy.deepcopy(seed)
                payload[field] = value
                self.assertEqual(_safe_projection(payload, schema), UNKNOWN)
        for raw in (None, [], "ALLOW", 17):
            self.assertEqual(_safe_projection(raw, schema), UNKNOWN)
        altered = copy.deepcopy(schema)
        altered["$defs"]["permissions"]["properties"]["merge"]["const"] = True
        self.assertEqual(_report(rows, fixtures, altered, doc),
                         dict.fromkeys(IDS, UNKNOWN))
        missing = copy.deepcopy(seed)
        del missing["permissions"]
        self.assertEqual(_safe_projection(missing, schema), UNKNOWN)
        extra = copy.deepcopy(seed)
        extra["unexpected"] = True
        self.assertEqual(_safe_projection(extra, schema), UNKNOWN)

    def test_sin_datos_reales(self):
        schema, fixtures, _, doc = self._sources()
        self.assertTrue(_schema_is_denial(schema))
        self.assertIn("No hay llamadas a GitHub", doc)
        forbidden = {"email", "password", "cookie", "token",
                     "conversation", "phone", "api_key", "ip_address"}
        for name, payload in fixtures.items():
            with self.subTest(fixture=name):
                self.assertEqual(set(payload), set(schema["required"]))
                self.assertFalse(set(payload) & forbidden)
                self.assertEqual(payload["permissions"], EXPECTED_PERMISSIONS)
                self.assertEqual(payload["authority"], "unchanged")
        self.assertFalse(any(EXPECTED_PERMISSIONS.values()))

    def test_estados_unknown_explicitos(self):
        schema, fixtures, rows, doc = self._sources()
        result = _report(rows, fixtures, schema, doc)
        self.assertEqual(
            {key for key in result if result[key] == UNKNOWN},
            EXTERNAL_UNKNOWN,
        )
        stale = copy.deepcopy(fixtures["blocked"])
        stale["freshness"] = "stale"
        self.assertEqual(_safe_projection(stale, schema), UNKNOWN)
        bad = copy.deepcopy(fixtures["unknown"])
        bad["action"] = "ALLOW"
        bad["next_transition"] = "ALLOW"
        self.assertEqual(_safe_projection(bad, schema), UNKNOWN)
        self.assertFalse(any(p["permissions"]["reserve"]
                             or p["permissions"]["merge"]
                             for p in fixtures.values()))
