"""Pruebas sintéticas de 16 brechas de resiliencia y feedback (#1682)."""
from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest

from producto.feedback import FeedbackValidationError, load_catalog, validate_record
from seguridad.resiliencia import ValidationError, audit_workflow, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
UNKNOWN = "UNKNOWN"
IDS = tuple("docs/resiliencia-fabrica.md:" + item for item in (
    "L40-U1", "L41-U1", "L42-U1", "L42-U2", "L43-U1", "L44-U1",
    "L45-U1", "L62-U1", "L62-U2", "L7-U1", "L9-U1",
)) + tuple("docs/retroalimentacion-producto.md:" + item for item in (
    "L10-U1", "L11-U1", "L12-U1", "L13-U1", "L14-U1",
))
RUNBOOK = (
    ("**Contener:**", ("revoked", "suspended")),
    ("**Delimitar:**", ("permissions_scoped", "window_scoped")),
    ("**Rotar:**", ("rotated", "old_revoked")),
    ("los tokens efímeros expiran", ("ephemeral_not_stored",)),
    ("**Recuperar:**", ("offsite_verified", "isolated_restore")),
    ("**Verificar:**", ("ci_ok", "smoke_ok", "rollback_ok")),
    ("**Aprender:**", ("redacted", "lessons_recorded")),
)
REAL_WORLD_IDS = frozenset(IDS[:9])


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw):
    if not isinstance(raw, str):
        raise ValueError("matriz ausente")
    found = {}
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cols = tuple(p.strip() for p in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        key = cols[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in found or len(cols) != 5 or not all(cols[:4]):
            raise ValueError("fila incompleta o duplicada: " + key)
        if cols[2] != "NO_VERIFICABLE":
            raise ValueError("promoción sin evidencia: " + key)
        found[key] = cols
    if set(found) != set(IDS):
        raise ValueError("faltan IDs")
    return found


def incident_step(evidence, required):
    """Un fixture nunca verifica un incidente de producción."""
    if type(evidence) is not dict or set(evidence) != set(required):
        return UNKNOWN
    if not all(type(value) is bool and value is True
               for value in evidence.values()):
        return UNKNOWN
    return "SYNTHETIC_ONLY"


def manifest():
    return {
        "version": 2, "project": "sample/factory",
        "execution_mechanisms": {
            "ci": "github-token:ephemeral",
            "observer": "github-token:ephemeral", "deploy": "hostinger:git",
        },
        "cross_repo_write": {"required_mechanism": "github-app"},
        "checks": {
            name: {"verified_at": "2026-09-23T12:00:00Z",
                   "evidence_ref": "audit:synthetic-" + name}
            for name in ("repo_backup", "secrets_escrow",
                         "token_rotation", "restore_drill")
        },
    }


def accepts_manifest(value):
    try:
        validate_manifest(value, now=NOW)
    except (ValidationError, TypeError, ValueError):
        return False
    return True


def record():
    return {
        "project": "sample/factory", "epic": "sample/factory#123",
        "metric": "error_rate", "surface": "home", "phase": "baseline",
        "period_start": "2026-09-01T00:00:00Z",
        "period_end": "2026-09-08T00:00:00Z",
        "value": 0.02, "sample_size": 200,
    }


def accepts_record(value, catalog):
    try:
        validate_record(value, catalog, "synthetic")
    except (FeedbackValidationError, TypeError, ValueError):
        return False
    return True


def rejects_record(catalog, **changes):
    return not accepts_record({**record(), **changes}, catalog)


def behavior():
    """Un predicado específico por fila, sin confundir local con real."""
    doc = read("docs/resiliencia-fabrica.md")
    feedback_doc = read("docs/retroalimentacion-producto.md")
    catalog = load_catalog()
    result = {}
    for key, (phrase, required) in zip(IDS[:7], RUNBOOK):
        result[key] = (
            phrase in doc and incident_step({}, required) == UNKNOWN
            and incident_step(dict.fromkeys(required, True),
                              required) == "SYNTHETIC_ONLY"
        )
    valid = manifest()
    invalid_cross = deepcopy(valid)
    invalid_cross["cross_repo_write"]["required_mechanism"] = "github-token:ephemeral"
    invalid_ci = deepcopy(valid)
    invalid_ci["execution_mechanisms"]["ci"] = "github-token:persistent"
    try:
        audit_workflow("permissions:\n  contents: write\njobs:\n  test:\n    steps: []\n")
        auditor_rejects = False
    except ValidationError:
        auditor_rejects = True
    result[IDS[7]] = (accepts_manifest(valid)
                      and validate_manifest(valid, now=NOW) is None
                      and "La validación estructural no prueba hechos externos" in doc)
    result[IDS[8]] = (accepts_manifest(valid) and not accepts_manifest(invalid_cross)
                      and "GitHub App dedicada" in doc)
    result[IDS[9]] = (accepts_manifest(valid)
                      and set(valid["execution_mechanisms"]) ==
                      {"ci", "observer", "deploy"}
                      and "no una cantidad artificial de identidades" in doc)
    result[IDS[10]] = (accepts_manifest(valid)
                       and valid["execution_mechanisms"]["ci"] ==
                       "github-token:ephemeral"
                       and not accepts_manifest(invalid_ci)
                       and auditor_rejects
                       and "permisos mínimos por job" in doc)
    result[IDS[11]] = (accepts_record(record(), catalog)
                       and rejects_record(catalog, epic="other/factory#123")
                       and rejects_record(catalog, epic="sample/factory#0")
                       and "owner/repo#N" in feedback_doc)
    result[IDS[12]] = (accepts_record(record(), catalog)
                       and record()["metric"] in catalog
                       and rejects_record(catalog, metric="unlisted_metric")
                       and "producto/metricas.json" in feedback_doc)
    result[IDS[13]] = (accepts_record(record(), catalog)
                       and rejects_record(catalog, surface="home/user-123")
                       and rejects_record(catalog, surface="Home")
                       and "slug de taxonomía" in feedback_doc)
    result[IDS[14]] = (accepts_record(record(), catalog)
                       and rejects_record(catalog, phase="production")
                       and rejects_record(catalog, phase=None)
                       and "post-deploy" in feedback_doc)
    result[IDS[15]] = (accepts_record(record(), catalog)
                       and rejects_record(catalog, period_start="2026-09-01T00:00:00")
                       and rejects_record(catalog, period_end="2026-09-01T00:00:00Z")
                       and "ISO-8601 con zona horaria" in feedback_doc)
    return result


def project(matrix, checks, claimed_live=None):
    """Ni un mock ni una prueba estructural certifican efectos externos."""
    try:
        matrix_rows(matrix)
    except ValueError:
        return dict.fromkeys(IDS, UNKNOWN)
    if (type(checks) is not dict or set(checks) != set(IDS)
            or any(type(v) is not bool for v in checks.values())):
        return dict.fromkeys(IDS, UNKNOWN)
    return {key: ("LOCAL_CONTRACT" if checks[key] and key not in REAL_WORLD_IDS
                  else UNKNOWN) for key in IDS}


class BrechasFactory64Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = read("docs/matriz-cobertura.md")
        rows = matrix_rows(matrix)
        checks = behavior()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(checks), set(IDS))
        for key in IDS:
            with self.subTest(brecha=key):
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertTrue(checks[key], "sin aserción/UNKNOWN: " + key)

    def test_falla_cerrado(self):
        matrix = read("docs/matriz-cobertura.md")
        line = next(row for row in matrix.splitlines()
                    if chr(96) + IDS[0] + chr(96) in row)
        for bad in (
            None, "", matrix.replace(line, "", 1), matrix + "\n" + line,
            matrix.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            matrix.replace(line, "| " + chr(96) + IDS[0] + chr(96) + " |", 1),
        ):
            with self.subTest(matrix=str(bad)[:25]):
                with self.assertRaises(ValueError):
                    matrix_rows(bad)
                self.assertEqual(
                    set(project(bad, dict.fromkeys(IDS, True)).values()),
                    {UNKNOWN})
        for bad in (None, {}, {IDS[0]: True}, dict.fromkeys(IDS, 1),
                    dict.fromkeys(IDS, "success"),
                    {**dict.fromkeys(IDS, True), "extra": True}):
            self.assertEqual(set(project(matrix, bad).values()), {UNKNOWN})
        for _, required in RUNBOOK:
            self.assertEqual(incident_step(None, required), UNKNOWN)
            self.assertEqual(incident_step({}, required), UNKNOWN)
            self.assertEqual(incident_step(dict.fromkeys(required, False), required),
                             UNKNOWN)
            self.assertEqual(incident_step({**dict.fromkeys(required, True),
                                             "extra": True}, required), UNKNOWN)
        catalog = load_catalog()
        for change in (
            {"epic": "other/factory#123"}, {"metric": "absent"},
            {"surface": "checkout/123"}, {"phase": "live"},
            {"period_start": "2026-09-01T00:00:00"},
            {"period_end": "2026-08-30T00:00:00Z"},
        ):
            with self.subTest(change=change):
                self.assertTrue(rejects_record(catalog, **change))
        invalid = manifest()
        invalid["cross_repo_write"] = {"required_mechanism": "personal-pat"}
        self.assertFalse(accepts_manifest(invalid))

    def test_sin_datos_reales(self):
        fixtures = json.dumps((manifest(), record()), sort_keys=True).lower()
        for forbidden in ("password=", "access_token", "private key", "ghp_",
                          "https://", "http://", "@gmail", "person@"):
            self.assertNotIn(forbidden, fixtures)
        tree = ast.parse(read("tests/test_brechas_factory_64.py"))
        banned = {"requests", "socket", "urllib", "http", "subprocess"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse({n.name.split(".")[0] for n in node.names} & banned)
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], banned)
        self.assertEqual(len(set(IDS)), 16)

    def test_estados_unknown_explicitos(self):
        matrix = read("docs/matriz-cobertura.md")
        claims = behavior()
        statuses = project(matrix, claims)
        self.assertEqual(set(statuses), set(IDS))
        for key in IDS:
            with self.subTest(brecha=key):
                self.assertEqual(
                    statuses[key],
                    UNKNOWN if key in REAL_WORLD_IDS else "LOCAL_CONTRACT")
                self.assertNotIn(statuses[key], {"LIVE", "CUBIERTO", "VERIFIED"})
                self.assertEqual(project(matrix, {**claims, key: False})[key], UNKNOWN)
        self.assertEqual(project(matrix, claims, {"live": True})[IDS[4]], UNKNOWN)
        self.assertEqual(set(project(matrix, dict.fromkeys(IDS, False)).values()),
                         {UNKNOWN})


if __name__ == "__main__":
    unittest.main()
