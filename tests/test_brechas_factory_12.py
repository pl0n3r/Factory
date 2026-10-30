#!/usr/bin/env python3
"""Factory #1630: pruebas locales sintéticas; ningún dictamen jurídico ni live."""
from __future__ import annotations

import ast
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from seguridad.cumplimiento import (
    ComplianceError, inspect_composer, inspect_npm, main as compliance_main,
    validate_inventory, validate_privacy,
)
from intelligence.derived_views import (
    DerivedViewError, DerivedViewSpec, check_drift, render_markdown_table,
)

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
LOCAL = "LOCAL_SYNTHETIC_ONLY"
GAP = "BRECHA_DOCUMENTADA"
NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
TICK = chr(96)
FILES = {
    "matrix": "docs/matriz-cobertura.md",
    "privacy_doc": "docs/cumplimiento-datos-licencias.md",
    "views_doc": "docs/derived-views.md",
    "privacy_code": "seguridad/cumplimiento.py",
    "privacy_tests": "seguridad/test_cumplimiento.py",
    "security_ci": ".github/workflows/seguridad.yml",
    "views_code": "intelligence/derived_views.py",
    "views_manifest": "config/derived_views.json",
    "views_tests": "tests/test_derived_views.py",
}
CLAUSES = {
    "docs/cumplimiento-datos-licencias.md:L7-U1":
        "El script `seguridad/cumplimiento.py` comprueba que un producto tenga",
    "docs/cumplimiento-datos-licencias.md:L15-U2":
        "El validador rechaza campos adicionales y revisiones con más de 365 días",
    "docs/cumplimiento-datos-licencias.md:L17-U1":
        "`exception_for_legal_review` solo deja constancia",
    "docs/cumplimiento-datos-licencias.md:L17-U2":
        "El responsable debe contrastar evidencias y hechos del producto",
    "docs/cumplimiento-datos-licencias.md:L21-U1":
        "El CLI no acepta rutas arbitrarias.",
    "docs/cumplimiento-datos-licencias.md:L21-U2":
        "La evidencia de privacidad entra por `stdin`",
    "docs/cumplimiento-datos-licencias.md:L36-U1":
        "PYTHONPATH=seguridad python3 -m unittest discover -s seguridad",
    "docs/cumplimiento-datos-licencias.md:L37-U1":
        "`seguridad.yml` ya ejecuta `unittest discover -s seguridad",
    "docs/cumplimiento-datos-licencias.md:L37-U2":
        "al integrar este slice, las regresiones de cumplimiento quedan dentro",
    "docs/cumplimiento-datos-licencias.md:L38-U1":
        "Cada proyecto debe aportar al menos una evidencia documentada y verificada",
    "docs/cumplimiento-datos-licencias.md:L38-U2":
        "Un fixture de tests **no** es prueba de cumplimiento",
    "docs/cumplimiento-datos-licencias.md:L39-U1":
        "Cierre de #12 requiere CI y evidencia de la revisión material",
    "docs/derived-views.md:L10-U1": "`source`: fuente canónica",
    "docs/derived-views.md:L11-U1": "`view`: superficie derivada.",
    "docs/derived-views.md:L12-U1": "`mode`: `generated` si existe un generador seguro",
    "docs/derived-views.md:L13-U1":
        "`generator`: función determinista obligatoria para `generated`.",
}
GAPS = {
    "docs/cumplimiento-datos-licencias.md:L17-U1":
        "excepción documental no autoriza tratamiento",
    "docs/cumplimiento-datos-licencias.md:L17-U2":
        "revisión humana de hechos del producto no acreditada",
    "docs/cumplimiento-datos-licencias.md:L37-U2":
        "CI de seguridad usa filtro de paths; esta prueba aislada no lo dispara",
    "docs/cumplimiento-datos-licencias.md:L38-U1":
        "evidencia real por tratamiento y lockfiles del producto no observada",
    "docs/cumplimiento-datos-licencias.md:L38-U2":
        "fixtures no prueban cumplimiento legal",
    "docs/cumplimiento-datos-licencias.md:L39-U1":
        "revisión jurídica material y CI de cierre no observados",
}


def sources():
    return {k: (ROOT / path).read_text(encoding="utf-8")
            for k, path in FILES.items()}


def rows(raw):
    if type(raw) is not str or not raw:
        raise ValueError("UNKNOWN: matriz ausente")
    found = {}
    for line in raw.splitlines():
        if not line.startswith("| " + TICK + "docs/"):
            continue
        cols = tuple(p.strip() for p in line.strip().strip("|").split("|"))
        if not cols:
            continue
        key = cols[0].strip(TICK)
        if key not in CLAUSES:
            continue
        if (key in found or len(cols) != 5 or cols[0] != TICK + key + TICK
                or CLAUSES[key] not in cols[1] or cols[2] != "NO_VERIFICABLE"
                or "No se confirmó test + PR fusionado" not in cols[3]
                or "contraste #1570" not in cols[4]):
            raise ValueError("UNKNOWN: fila duplicada, incompleta o promovida " + key)
        found[key] = cols
    if set(found) != set(CLAUSES):
        raise ValueError("UNKNOWN: faltan filas")
    return found


def fixture():
    return {
        "version": 1, "project": "pl0n3r/Condor",
        "scope": "synthetic_scope", "purpose": "test_only",
        "data_categories": ["none"], "consent_or_exception": "no_personal_data",
        "evidence": {key: "audit:synthetic-" + key for key in (
            "privacy_policy", "terms", "processing_register", "rights_channel",
            "retention_schedule", "vendor_review", "legal_review")},
        "reviewed_at": "2026-09-23T10:00:00Z",
    }


def rejects(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except (ComplianceError, DerivedViewError, ValueError, TypeError):
        return True
    return False


def cli_probe():
    output = StringIO()
    with (patch.object(sys, "argv", ["cumplimiento.py", "--stdlib-only"]),
          patch.object(sys, "stdin", StringIO(json.dumps(fixture()))),
          redirect_stdout(output)):
        code = compliance_main()
    payload = json.loads(output.getvalue())
    stdin_ok = (
        code == 0
        and payload == {
            "project": "pl0n3r/Condor",
            "evidence_status": "documented_not_legally_approved",
            "license_status": "identifiers_present_review_required",
            "packages_observed": 0,
        }
        and "audit:synthetic" not in output.getvalue()
    )
    with (patch.object(sys, "argv", [
            "cumplimiento.py", "--arbitrary-path", "/tmp/synthetic.json"
          ]), redirect_stderr(StringIO())):
        try:
            compliance_main()
            path_rejected = False
        except SystemExit as exc:
            path_rejected = exc.code == 2
    return path_rejected, stdin_ok


def witnesses():
    item = fixture()
    valid = validate_privacy(item, now=NOW) == item["project"]
    extra = {**item, "extra": "invalid"}
    old = {**item, "reviewed_at": (NOW - timedelta(days=366)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")}
    edge = {**item, "reviewed_at": (NOW - timedelta(days=365)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")}
    dates = (rejects(validate_privacy, extra, now=NOW)
             and rejects(validate_privacy, old, now=NOW)
             and validate_privacy(edge, now=NOW) == item["project"])
    exception = deepcopy(item)
    exception["data_categories"] = ["synthetic_category"]
    exception["consent_or_exception"] = "exception_for_legal_review"
    described = validate_privacy(exception, now=NOW) == item["project"]
    composer = {"packages": [{
        "name": "synthetic/pkg", "version": "1.0", "license": ["MIT"]
    }], "packages-dev": []}
    npm = {"packages": {"": {}, "node_modules/synthetic-pkg": {
        "version": "1.0", "license": "MIT"
    }}}
    locks = (validate_inventory(inspect_composer(composer))["license_status"]
             == "identifiers_present_review_required"
             and validate_inventory(inspect_npm(npm))["packages_observed"] == 1)
    no_path, from_stdin = cli_probe()

    manifest = json.loads((ROOT / FILES["views_manifest"]).read_text(
        encoding="utf-8"))
    if (manifest.get("version") != 1
            or type(manifest.get("views")) is not list
            or not manifest["views"]):
        raise ValueError("UNKNOWN: manifiesto ausente")
    specs = [DerivedViewSpec(**entry) for entry in manifest["views"]]
    for spec in specs:
        spec.validate()
    derived_source = (
        all(s.source and s.source != s.view for s in specs)
        and rejects(DerivedViewSpec(
            "x", "", "derived.md", "regression", None, "test.py").validate))
    derived_view = (
        all(s.view for s in specs)
        and rejects(DerivedViewSpec(
            "x", "source.md", "", "regression", None, "test.py").validate)
        and rejects(DerivedViewSpec(
            "x", "same.md", "same.md", "regression", None, "test.py").validate))
    modes = (
        {s.mode for s in specs} == {"generated", "regression"}
        and rejects(DerivedViewSpec(
            "x", "a", "b", "automatic", None, "test.py").validate)
        and rejects(DerivedViewSpec(
            "x", "a", "b", "regression", "fake", "test.py").validate)
        and rejects(DerivedViewSpec(
            "x", "a", "b", "generated", None, "test.py").validate))
    synthetic = [{"id": "b", "value": "queued"}, {
        "id": "a", "value": "done"}]
    expected = render_markdown_table(synthetic, ("id", "value"), sort_by="id")
    observed = render_markdown_table(
        list(reversed(synthetic)), ("id", "value"), sort_by="id")
    check_drift(expected, observed)
    generator = (
        expected == observed
        and all(s.generator for s in specs if s.mode == "generated")
        and rejects(check_drift, expected, expected + "drift")
        and rejects(render_markdown_table, synthetic, (), sort_by="id"))
    p = "docs/cumplimiento-datos-licencias.md:L"
    d = "docs/derived-views.md:L"
    result = {
        p+"7-U1": LOCAL if valid and locks else UNKNOWN,
        p+"15-U2": LOCAL if dates else UNKNOWN,
        p+"17-U1": GAP if described else UNKNOWN,
        p+"17-U2": GAP,
        p+"21-U1": LOCAL if no_path else UNKNOWN,
        p+"21-U2": LOCAL if from_stdin else UNKNOWN,
        p+"36-U1": LOCAL,
        p+"37-U1": LOCAL,
        p+"37-U2": GAP,
        p+"38-U1": GAP, p+"38-U2": GAP, p+"39-U1": GAP,
        d+"10-U1": LOCAL if derived_source else UNKNOWN,
        d+"11-U1": LOCAL if derived_view else UNKNOWN,
        d+"12-U1": LOCAL if modes else UNKNOWN,
        d+"13-U1": LOCAL if generator else UNKNOWN,
    }
    return result


def evidence(key, data, observation):
    if (type(key) is not str or key not in CLAUSES
            or type(data) is not dict or set(data) != set(FILES)
            or any(type(v) is not str or not v for v in data.values())
            or type(observation) is not dict
            or set(observation) != set(CLAUSES)
            or any(v not in (LOCAL, GAP, UNKNOWN) for v in observation.values())):
        return UNKNOWN
    try:
        rows(data["matrix"])
    except ValueError:
        return UNKNOWN
    doc = data["views_doc"] if key.startswith("docs/derived") else data["privacy_doc"]
    if CLAUSES[key] not in doc:
        return UNKNOWN
    if key.endswith(":L36-U1") and not (
        "class PrivacyTests" in data["privacy_tests"]
        and "test_valid_record" in data["privacy_tests"]
    ):
        return UNKNOWN
    if key.endswith(":L37-U1") and not (
        "Validar puertas del candidato" in data["security_ci"]
        and "unittest discover -s seguridad -p 'test_*.py'"
        in data["security_ci"]
    ):
        return UNKNOWN
    if key.startswith("docs/derived") and (
        "class DerivedViewSpec" not in data["views_code"]
    ):
        return UNKNOWN
    return observation[key]


def operational(_key, _claimed=None):
    return UNKNOWN


class BrechasFactory12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = sources()
        cls.proof = witnesses()

    def test_contrato_principal(self):
        self.assertEqual(16, len(CLAUSES))
        self.assertEqual(set(CLAUSES), set(rows(self.data["matrix"])))
        self.assertEqual(set(CLAUSES), set(self.proof))
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertEqual(
                    GAP if key in GAPS else LOCAL,
                    evidence(key, self.data, self.proof))
                self.assertEqual(UNKNOWN, operational(key))

    def test_falla_cerrado(self):
        raw = self.data["matrix"]
        for key in CLAUSES:
            line = next(x for x in raw.splitlines()
                        if x.startswith("| " + TICK + key + TICK))
            for changed in (
                raw.replace(line, "", 1),
                raw + "\n" + line,
                raw.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            ):
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, UNKNOWN):
                        rows(changed)
                    self.assertEqual(UNKNOWN, evidence(
                        key, {**self.data, "matrix": changed}, self.proof))
            doc = "views_doc" if key.startswith("docs/derived") else "privacy_doc"
            self.assertEqual(UNKNOWN, evidence(
                key, {**self.data, doc: "unknown"}, self.proof))
        for name in FILES:
            incomplete = dict(self.data)
            incomplete.pop(name)
            self.assertEqual(UNKNOWN, evidence(
                next(iter(CLAUSES)), incomplete, self.proof))
        self.assertEqual(UNKNOWN, evidence(
            "unknown", self.data, self.proof))
        self.assertEqual(UNKNOWN, evidence(
            next(iter(CLAUSES)), self.data, {"ci": "success"}))

    def test_sin_datos_reales(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        names = {a.name.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in ast.walk(tree)
                  if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(names & {
            "socket", "requests", "httpx", "urllib", "subprocess",
            "pymysql", "playwright", "selenium",
        })
        self.assertEqual(["none"], fixture()["data_categories"])
        self.assertTrue(all(s.startswith("audit:synthetic")
                            for s in fixture()["evidence"].values()))

    def test_estados_unknown_explicitos(self):
        for key in CLAUSES:
            with self.subTest(key=key):
                self.assertEqual("NO_VERIFICABLE", rows(self.data["matrix"])[key][2])
                for forged in (None, True, "approved", {"ci": "success"},
                               {"production": "GREEN"}, {"legal": "approved"}):
                    self.assertEqual(UNKNOWN, operational(key, forged))
                if key in GAPS:
                    self.assertEqual(GAP, evidence(key, self.data, self.proof))
                    self.assertTrue(GAPS[key])


if __name__ == "__main__":
    unittest.main()
