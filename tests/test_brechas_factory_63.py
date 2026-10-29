"""16 pruebas sintéticas para la resiliencia Factory, sin certificación live."""
from __future__ import annotations

import ast
from contextlib import redirect_stderr
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from seguridad.resiliencia import (
    ValidationError, audit_workflow, main as resilience_cli,
    validate_legacy_manifest, validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
UNKNOWN = "UNKNOWN"
IDS = tuple("docs/resiliencia-fabrica.md:" + suffix for suffix in (
    "L11-U1", "L11-U2", "L12-U1", "L12-U2", "L14-U1", "L16-U1",
    "L20-U1", "L24-U1", "L25-U1", "L28-U1", "L3-U1", "L30-U1",
    "L30-U2", "L34-U1", "L34-U2", "L36-U1",
))
REQUIRED_CHECKS = ("repo_backup", "secrets_escrow", "token_rotation", "restore_drill")
V2_ROOT = {"version", "project", "execution_mechanisms", "cross_repo_write", "checks"}


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def matrix_rows(raw):
    """No promocionar ni ocultar filas sin evidencia GitHub/campo."""
    if not isinstance(raw, str):
        raise ValueError("matriz ausente")
    found = {}
    for line in raw.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        fields = tuple(part.strip() for part in re.split(r"(?<!\\)\|", line.strip().strip("|")))
        key = fields[0].strip(chr(96))
        if key not in IDS:
            continue
        if key in found or len(fields) != 5 or not all(fields[:4]):
            raise ValueError("fila duplicada o incompleta: " + key)
        if fields[2] != "NO_VERIFICABLE":
            raise ValueError("promoción sin evidencia final: " + key)
        found[key] = fields
    if set(found) != set(IDS):
        raise ValueError("faltan brechas de resiliencia")
    return found


def checks_fixture():
    return {
        name: {"verified_at": "2026-09-23T12:00:00Z", "evidence_ref": "audit:synthetic-" + name}
        for name in REQUIRED_CHECKS
    }


def manifest_v2():
    return {
        "version": 2, "project": "example/factory",
        "execution_mechanisms": {
            "ci": "github-token:ephemeral", "observer": "github-token:ephemeral",
            "deploy": "hostinger:git",
        },
        "cross_repo_write": {"required_mechanism": "github-app"},
        "checks": checks_fixture(),
    }


def manifest_v1():
    return {
        "version": 1, "project": "example/factory",
        "identities": {
            "ci": "github-app:factory-ci",
            "observer": "github-app:factory-observer",
            "deploy": "github-app:factory-deploy",
        },
        "checks": checks_fixture(),
    }


def accepts(document, *, legacy=False, now=NOW):
    try:
        (validate_legacy_manifest if legacy else validate_manifest)(document, now=now)
    except (ValidationError, TypeError, ValueError):
        return False
    return True


def rejected_variant(field, key, value):
    obj = manifest_v2()
    obj[field][key] = value
    return not accepts(obj)


def rejects_workflow(yaml):
    try:
        audit_workflow(yaml)
    except ValidationError:
        return True
    return False


def legacy_cli_rejects():
    stderr = StringIO()
    with patch.object(sys, "argv", ["resiliencia.py", "--manifest-stdin"]), \
            patch.object(sys, "stdin", StringIO(json.dumps(manifest_v1()))), \
            redirect_stderr(stderr):
        try:
            resilience_cli()
        except SystemExit as exc:
            return exc.code == 1 and "migrar a v2" in stderr.getvalue()
    return False


def behavioral_evidence():
    """Cada uno de los 16 IDs tiene un predicado ejercitado por código real."""
    current = manifest_v2()
    previous = manifest_v1()
    valid = accepts(current)
    doc = read("docs/resiliencia-fabrica.md")
    audit_workflow("jobs:\n  test:\n    steps:\n      - uses: actions/checkout@" + "a" * 40 + "\n")
    wrong_roots = deepcopy(current)
    wrong_roots["identities"] = previous["identities"]
    missing_execution = deepcopy(current)
    del missing_execution["execution_mechanisms"]
    missing_cross_repo = deepcopy(current)
    del missing_cross_repo["cross_repo_write"]
    invalid_checks = deepcopy(current)
    del invalid_checks["checks"]["restore_drill"]
    nonutc = deepcopy(current)
    nonutc["checks"]["repo_backup"]["verified_at"] = "2026-09-23T13:00:00+01:00"
    past = deepcopy(current)
    past["checks"]["token_rotation"]["verified_at"] = "2026-06-25T11:59:59Z"
    future = deepcopy(current)
    future["checks"]["secrets_escrow"]["verified_at"] = "2026-09-24T12:00:01Z"
    boundary = deepcopy(current)
    boundary["checks"]["restore_drill"]["verified_at"] = (
        NOW - timedelta(days=90)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    proof = (
        valid and current["execution_mechanisms"]["deploy"] == "hostinger:git"
        and rejected_variant("execution_mechanisms", "deploy", "ssh:long-lived"),
        valid and rejected_variant("execution_mechanisms", "deploy", "github-app:factory-deploy")
        and "no usa una credencial GitHub persistente" in doc,
        valid and current["cross_repo_write"]["required_mechanism"] == "github-app"
        and rejected_variant("cross_repo_write", "required_mechanism", "github-token:ephemeral"),
        rejected_variant("cross_repo_write", "required_mechanism", "personal-pat")
        and rejected_variant("cross_repo_write", "required_mechanism", "github-token:ephemeral"),
        all(rejected_variant("execution_mechanisms", "ci", token) for token in (
            "pat:personal", "github-token:persistent", "github-token:arbitrary",
        )) and rejected_variant("execution_mechanisms", "token_alias", "github-token:ephemeral"),
        all(rejects_workflow(workflow) for workflow in (
            "on:\n  pull_request_target:\n",
            "permissions: write-all\n",
            "permissions:\n  contents: write\n",
            "steps:\n  - uses: actions/checkout@main\n",
        )),
        valid and set(current) == V2_ROOT and not accepts(wrong_roots)
        and not accepts({**current, "version": 3}),
        valid and not accepts(missing_execution)
        and rejected_variant("execution_mechanisms", "observer", "github-app:observer"),
        valid and not accepts(missing_cross_repo)
        and rejected_variant("cross_repo_write", "required_mechanism", "none"),
        all(rejected_variant("execution_mechanisms", field, "unknown:mechanism")
            for field in ("ci", "observer", "deploy"))
        and rejected_variant("cross_repo_write", "required_mechanism", "personal-pat"),
        valid and "no demuestra por sí solo" in doc and "restore real" in doc,
        valid and set(current["checks"]) == set(REQUIRED_CHECKS)
        and not accepts(invalid_checks) and not accepts(nonutc),
        valid and accepts(boundary) and not accepts(past) and not accepts(future),
        accepts(previous, legacy=True) and not accepts(previous)
        and "diagnóstico y migración" in doc,
        not accepts(previous) and legacy_cli_rejects(),
        accepts(previous, legacy=True) and not accepts(previous)
        and not accepts({**previous, "version": 2}),
    )
    return dict(zip(IDS, proof))


def evidence_status(matrix, checks):
    """La validación local no demuestra backups, restore ni credenciales reales."""
    try:
        matrix_rows(matrix)
    except ValueError:
        return dict.fromkeys(IDS, UNKNOWN)
    if type(checks) is not dict or set(checks) != set(IDS) or any(
        type(value) is not bool for value in checks.values()
    ):
        return dict.fromkeys(IDS, UNKNOWN)
    return {
        key: ("LOCAL_CONTRACT" if checks[key] and key != IDS[10] else UNKNOWN)
        for key in IDS
    }


class BrechasFactory63Tests(unittest.TestCase):
    def test_contrato_principal(self):
        matrix = read("docs/matriz-cobertura.md")
        rows = matrix_rows(matrix)
        findings = behavioral_evidence()
        self.assertEqual(len(IDS), 16)
        self.assertEqual(set(rows), set(IDS))
        self.assertEqual(set(findings), set(IDS))
        for key in IDS:
            with self.subTest(brecha=key):
                self.assertEqual(rows[key][2], "NO_VERIFICABLE")
                self.assertTrue(findings[key], "falta aserción de contrato: " + key)
        self.assertTrue(accepts(manifest_v2()))

    def test_falla_cerrado(self):
        matrix = read("docs/matriz-cobertura.md")
        line = next(row for row in matrix.splitlines() if chr(96) + IDS[0] + chr(96) in row)
        for corrupted in (
            None, "", matrix.replace(line, "", 1), matrix + "\n" + line,
            matrix.replace(line, line.replace("NO_VERIFICABLE", "CUBIERTO"), 1),
            matrix.replace(line, "| " + chr(96) + IDS[0] + chr(96) + " |", 1),
        ):
            with self.subTest(matriz=str(corrupted)[:25]):
                with self.assertRaises(ValueError):
                    matrix_rows(corrupted)
                self.assertEqual(
                    set(evidence_status(corrupted, dict.fromkeys(IDS, True)).values()), {UNKNOWN}
                )
        for invalid in (
            None, {}, {IDS[0]: True}, dict.fromkeys(IDS, 1),
            dict.fromkeys(IDS, "success"),
            {**dict.fromkeys(IDS, True), "extra": True},
        ):
            self.assertEqual(set(evidence_status(matrix, invalid).values()), {UNKNOWN})
        for field, key, bad in (
            ("execution_mechanisms", "ci", "personal-pat"),
            ("execution_mechanisms", "deploy", "ssh:personal"),
            ("cross_repo_write", "required_mechanism", "github-token:ephemeral"),
        ):
            with self.subTest(field=field, key=key):
                self.assertTrue(rejected_variant(field, key, bad))
        for invalid in (
            "2026-09-23T12:00:00+00:00", "not-a-date", "2026-09-23",
        ):
            document = manifest_v2()
            document["checks"]["repo_backup"]["verified_at"] = invalid
            self.assertFalse(accepts(document))
        leak = manifest_v2()
        leak["checks"]["secrets_escrow"]["credential"] = "synthetic-placeholder"
        with self.assertRaises(ValidationError) as caught:
            validate_manifest(leak, now=NOW)
        self.assertNotIn("synthetic-placeholder", str(caught.exception))
        legacy = manifest_v1()
        legacy["identities"]["deploy"] = legacy["identities"]["ci"]
        self.assertFalse(accepts(legacy, legacy=True))

    def test_sin_datos_reales(self):
        fixtures = json.dumps((manifest_v2(), manifest_v1()), sort_keys=True).lower()
        for forbidden in (
            "password", "access_token", "private key", "ghp_",
            "https://", "http://", "@gmail", "person@",
        ):
            self.assertNotIn(forbidden, fixtures)
        tree = ast.parse(read("tests/test_brechas_factory_63.py"))
        forbidden_modules = {"requests", "socket", "urllib", "http", "subprocess"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(
                    {part.name.split(".")[0] for part in node.names} & forbidden_modules
                )
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], forbidden_modules)
        self.assertEqual(len(set(IDS)), 16)

    def test_estados_unknown_explicitos(self):
        matrix = read("docs/matriz-cobertura.md")
        findings = behavioral_evidence()
        self.assertTrue(all(findings.values()))
        for key, status in evidence_status(matrix, findings).items():
            with self.subTest(brecha=key):
                self.assertEqual(
                    status, UNKNOWN if key == IDS[10] else "LOCAL_CONTRACT"
                )
                self.assertNotIn(
                    status, {"CUBIERTO", "LIVE", "PRODUCTION_GREEN", "VERIFIED"}
                )
                self.assertEqual(
                    evidence_status(matrix, {**findings, key: False})[key], UNKNOWN
                )
        self.assertEqual(
            set(evidence_status(matrix, dict.fromkeys(IDS, False)).values()), {UNKNOWN}
        )
        missing = manifest_v2()
        del missing["checks"]["repo_backup"]
        self.assertFalse(accepts(missing))


if __name__ == "__main__":
    unittest.main()
