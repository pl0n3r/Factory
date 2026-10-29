"""Evidencia sintética, fail-closed, para 16 brechas Factory (#1688).

VERIFIED_SYNTHETIC no certifica fusión ni promociona la matriz de cobertura.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import roles_kit as roles
from tests import test_sonar_superseded_ce as sonar_examples

ROOT = Path(__file__).resolve().parents[1]
VERIFIED = "VERIFIED_SYNTHETIC"
UNKNOWN = "UNKNOWN"
ROLE_PATH = "docs/roles-profesionales.md:"
SONAR_PATH = "docs/sonar-superseded-ce.md:"
ROLE_IDS = tuple(ROLE_PATH + item for item in (
    "L28-U1", "L29-U1", "L29-U2", "L3-U1",
    "L30-U1", "L30-U2", "L9-U1",
))
SONAR_IDS = tuple(SONAR_PATH + item for item in (
    "L10-U1", "L11-U1", "L12-U1", "L13-U1", "L15-U1",
    "L21-U1", "L3-U1", "L7-U1", "L9-U1",
))
IDS = ROLE_IDS + SONAR_IDS


def role_fixture():
    """PR sintético construido con el catálogo y checklists canónicos."""
    catalog = roles.load_catalog()
    ctx = {
        "title": "Prueba sintética del catálogo",
        "body": "",
        "labels": ["tipo: pruebas"],
        "files": ["tests/test_brechas_factory_70.py"],
    }
    assigned, risks = roles.classify(ctx, catalog)
    if risks:
        raise ValueError("Una prueba aislada no debe reclamar riesgo profesional.")
    primary = "ingenieria-software" if "ingenieria-software" in assigned else assigned[0]
    lines = ["Rol(es): " + ", ".join(assigned), "Rol primario: " + primary]
    for name in assigned:
        profile = (ROOT / "agentes" / "roles" / (name + ".md")).read_text(
            encoding="utf-8"
        )
        lines.extend("- [x] " + item for item in roles.parse_checklist(profile))
    ctx["body"] = "\n".join(lines)
    ctx["labels"].extend(catalog[name]["label_es"] for name in assigned)
    return ctx, catalog, assigned


def sonar_fixture():
    raw = sonar_examples.snapshot()
    raw["ce_task"] = {
        "status": "FAILED",
        "error_message": sonar_examples.SUPERSEDED,
    }
    return raw


def ce_is_fail(message):
    raw = sonar_fixture()
    raw["ce_task"]["error_message"] = message
    signal = sonar_examples.ce_signal(raw)
    return signal["status"] == "FAIL" and signal["reason"] == "ce_task_failed"


def role_evidence(row, ctx, catalog, assigned, workflow):
    if row == ROLE_PATH + "L3-U1":
        es = json.loads((ROOT / "labels/es.json").read_text(encoding="utf-8"))
        en = json.loads((ROOT / "labels/en.json").read_text(encoding="utf-8"))
        names = [item["name"] for item in es + en]
        return (
            set(roles.REQUIRED_ROLES) <= set(catalog)
            and len(roles.labels_for(catalog, "es")) == len(catalog)
            and len(roles.labels_for(catalog, "en")) == len(catalog)
            and not any(value.startswith(("rol: ", "role: ")) for value in names)
            and "python3 .factory/scripts/roles_kit.py labels" in workflow
        )
    if row == ROLE_PATH + "L9-U1":
        declared = roles.declared_roles(ctx["body"])
        result = roles.validate_pr(ctx, catalog, roles.ROLES_DIR, "es")
        return (set(declared) == set(assigned)
                and set(result["declared"]) == set(assigned)
                and len(declared) >= 2)
    if row == ROLE_PATH + "L28-U1":
        write = workflow.split("\n  mutate:\n", 1)[-1]
        return all(fragment in write for fragment in (
            'case "$EVENT_NAME" in',
            'issues) [[ "$EVENT_ISSUE" == "$NUMBER" && "$NUMBER" != "0" ]]',
            'pull_request) [[ "$EVENT_PR" == "$NUMBER" && "$NUMBER" != "0" ]]',
            'workflow_dispatch) [[ "$REF_NAME" == "refs/heads/$DEFAULT_BRANCH"'
            ' && "$NUMBER" != "0" ]]',
            '*) false ;;',
            'suggest requiere la entidad del evento o dispatch en main',
        )) and "if: inputs.mode == 'sync' || inputs.mode == 'suggest'" in write
    if row == ROLE_PATH + "L29-U1":
        payload = json.dumps(ctx, sort_keys=True)
        with patch.object(sys, "stdin", io.StringIO(payload)), \
             patch.object(sys, "argv", ["roles_kit.py", "validate-pr"]), \
             contextlib.redirect_stdout(io.StringIO()) as output, \
             contextlib.redirect_stderr(io.StringIO()):
            rc = roles.main()
        return (rc == 0 and "declared" in json.loads(output.getvalue())
                and len(payload) < roles.MAX_CONTEXT)
    if row == ROLE_PATH + "L29-U2":
        with patch.object(sys, "argv", [
            "roles_kit.py", "suggest", "--catalog", "/tmp/foreign.json",
        ]), contextlib.redirect_stderr(io.StringIO()):
            try:
                roles.main()
            except SystemExit as exc:
                return exc.code != 0
        return False
    if row == ROLE_PATH + "L30-U1":
        a = roles.classify(ctx, catalog)
        b = roles.classify(copy.deepcopy(ctx), catalog)
        return a == b and a[0] == sorted(set(a[0])) and a[0] == assigned
    if row == ROLE_PATH + "L30-U2":
        malicious = dict(ctx, title="$(echo FORBIDDEN) ; $(id)")
        with patch("os.system", side_effect=AssertionError("shell forbidden")) as sh, \
             patch("subprocess.run", side_effect=AssertionError("exec forbidden")) as exe:
            derived = roles.classify(malicious, catalog)
        return bool(derived[0]) and not sh.called and not exe.called
    return False


def sonar_evidence(row, raw):
    canonical = sonar_examples.SUPERSEDED
    old = sonar_examples.OLD_SHA
    newer = sonar_examples.NEW_SHA
    if row == SONAR_PATH + "L3-U1":
        signal = sonar_examples.ce_signal(raw)
        return (signal["status"] == "PASS"
                and signal["reason"] == "ce_task_superseded_by_newer_report"
                and ce_is_fail("Compute Engine failure unrelated to superseded report"))
    if row == SONAR_PATH + "L7-U1":
        return (sonar_examples.ce_signal(raw)["status"] == "PASS"
                and ce_is_fail(canonical + " extra information"))
    invalid_reports = {
        SONAR_PATH + "L9-U1": canonical.replace(old, "bad-old-sha", 1),
        SONAR_PATH + "L10-U1": canonical.replace(
            "a newer report has already been processed",
            "a newer report may exist", 1,
        ),
        SONAR_PATH + "L11-U1": canonical.replace(
            "processing older reports is not supported",
            "older reports were deferred", 1,
        ),
        SONAR_PATH + "L12-U1": canonical.replace(newer, "not-hex", 1),
    }
    if row in invalid_reports:
        return (old in canonical and newer in canonical
                and len(old) == 40 and len(newer) == 40
                and ce_is_fail(invalid_reports[row]))
    if row == SONAR_PATH + "L13-U1":
        return ce_is_fail("prefix " + canonical) and ce_is_fail(canonical + " suffix")
    if row == SONAR_PATH + "L15-U1":
        issues = sonar_examples.FakeIssues()
        operations = sonar_examples.sonar_watch.sync_project(
            contract=sonar_examples.contract(), snapshot=copy.deepcopy(raw),
            observed_at=sonar_examples.NOW, project_ref="pl0n3r/Condor",
            origin_ref="sonar:condor",
            origin_url="https://sonarcloud.io/project/overview?id=pl0n3r_Condor",
            issues=issues,
        )
        return ({"action": "closed", "signal": "ce_task"} in operations
                and issues.rows[0]["state"] == "closed"
                and all(call[0] == "update" for call in issues.calls)
                and sonar_examples.ce_signal(raw)["freshness"]["state"] == "CURRENT")
    if row == SONAR_PATH + "L21-U1":
        issues = sonar_examples.FakeIssues()
        with patch("socket.socket", side_effect=AssertionError("no network")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("no Sonar writes")):
            ops = sonar_examples.sonar_watch.sync_project(
                contract=sonar_examples.contract(), snapshot=copy.deepcopy(raw),
                observed_at=sonar_examples.NOW, project_ref="pl0n3r/Condor",
                origin_ref="sonar:condor",
                origin_url="https://sonarcloud.io/project/overview?id=pl0n3r_Condor",
                issues=issues,
            )
        return (len(ops) == 1 and ops[0]["action"] == "closed"
                and issues.calls == [("update", 1039, "closed")])
    return False


def evidence(row, fixtures):
    """No inferir éxito para ID fuera de alcance ni datos ausentes/ambiguos."""
    if row not in IDS or not isinstance(fixtures, dict):
        return UNKNOWN
    try:
        if row in ROLE_IDS:
            ctx, catalog, assigned = fixtures["roles"]
            ok = role_evidence(row, ctx, catalog, assigned, fixtures["workflow"])
        else:
            snapshot = fixtures["sonar"]
            if not isinstance(snapshot, dict) or not isinstance(
                snapshot.get("ce_task"), dict
            ):
                return UNKNOWN
            ok = sonar_evidence(row, snapshot)
    except (KeyError, ValueError, TypeError, AttributeError, IndexError):
        return UNKNOWN
    return VERIFIED if ok is True else UNKNOWN


class BrechasFactory70Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = {
            "roles": role_fixture(),
            "workflow": (ROOT / ".github/workflows/roles.yml").read_text(
                encoding="utf-8"
            ),
            "sonar": sonar_fixture(),
        }

    def test_contrato_principal(self):
        self.assertEqual(len(ROLE_IDS), 7)
        self.assertEqual(len(SONAR_IDS), 9)
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        for row in IDS:
            with self.subTest(row=row):
                self.assertEqual(evidence(row, self.fixtures), VERIFIED)

    def test_falla_cerrado(self):
        with self.assertRaises(roles.RoleError):
            roles.parse_context("x" * (roles.MAX_CONTEXT + 1))
        with self.assertRaises(roles.RoleError):
            roles.parse_context(json.dumps({"body": None, "files": [42]}))
        ctx, catalog, _ = self.fixtures["roles"]
        with self.assertRaises(roles.RoleError):
            roles.validate_pr(
                {**ctx, "body": "Rol(es): unknown\nRol primario: unknown"},
                catalog, roles.ROLES_DIR, "es",
            )
        original = sonar_examples.SUPERSEDED
        self.assertTrue(ce_is_fail(original.replace(
            sonar_examples.NEW_SHA, "not-sha", 1)))
        self.assertTrue(ce_is_fail(original + " warning"))
        self.assertEqual(evidence(SONAR_IDS[0], {"sonar": None}), UNKNOWN)
        self.assertEqual(evidence(ROLE_IDS[0], {"roles": None}), UNKNOWN)
        self.assertEqual(evidence("not-a-row", self.fixtures), UNKNOWN)

    def test_sin_datos_reales(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("remote forbidden")):
            role = evidence(ROLE_PATH + "L30-U1", self.fixtures)
            sonar = evidence(SONAR_PATH + "L21-U1", self.fixtures)
        self.assertEqual(role, VERIFIED)
        self.assertEqual(sonar, VERIFIED)
        self.assertEqual(sonar_examples.snapshot()["project"], "condor")
        self.assertTrue(all(row.startswith("docs/") for row in IDS))
        self.assertNotIn("password", str(self.fixtures).lower())
        self.assertEqual(roles.MAX_CONTEXT, 500_000)

    def test_estados_unknown_explicitos(self):
        matrix = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        found = {}
        for line in matrix.splitlines():
            if not line.startswith("|"):
                continue
            cells = [part.strip() for part in re.split(
                r"(?<!\\)\|", line.strip().strip("|")
            )]
            key = cells[0].strip(chr(96))
            if key in IDS:
                self.assertNotIn(key, found, "ID duplicado")
                self.assertEqual(len(cells), 5)
                self.assertEqual(cells[2], "NO_VERIFICABLE")
                self.assertEqual(cells[4], "—")
                found[key] = cells
        self.assertEqual(set(found), set(IDS))
        for row in IDS:
            with self.subTest(row=row):
                self.assertTrue(
                    "No se confirmó" in found[row][3]
                    or "acreditación individual pendiente" in found[row][3],
                    "No afirmar cumplimiento previo sin PR fusionado",
                )
        partial = dict(self.fixtures)
        partial.pop("sonar")
        self.assertTrue(all(evidence(row, partial) == UNKNOWN for row in SONAR_IDS))
        self.assertEqual(evidence("docs/roles-profesionales.md:L999-U1",
                                  self.fixtures), UNKNOWN)


if __name__ == "__main__":
    unittest.main()
