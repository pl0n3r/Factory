"""Evidencia sintética para 16 brechas Risk Compiler/Roles Kit (#1687).

VERIFIED_SYNTHETIC nunca equivale a test + PR fusionado ni promociona la matriz.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch
from intelligence.project_dna import discover_project_dna
from intelligence import risk_compiler as risk
from scripts import roles_kit as roles

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = "UNKNOWN"
RISK_IDS = tuple(f"docs/risk-compiler.md:L{n}-U1" for n in (37, 38, 41, 52))
ROLE_IDS = tuple("docs/roles-profesionales.md:" + n for n in (
    "L10-U1", "L11-U1", "L12-U1", "L14-U1", "L14-U2", "L18-U1",
    "L19-U1", "L21-U1", "L25-U1", "L25-U2", "L26-U1", "L27-U1"))
IDS = RISK_IDS + ROLE_IDS


def dna(sparse=False):
    return discover_project_dna(
        paths=["package.json"] if sparse else [
            "package.json", ".github/workflows/ci.yml", "vercel.json",
            "database/schema.sql", ".sentryclirc"],
        manifests={"package.json": {"dependencies": {"fastify": "^5",
            **({} if sparse else {"@sentry/node": "^9"})}}},
        capabilities=["api"] if sparse else ["api", "auth"])


def task(kind, surface, **overrides):
    signals = dict.fromkeys(("production", "destructive", "migration",
                             "touches_auth", "external_integration"), False)
    signals.update(overrides)
    return {"id": "synthetic/factory#69", "title": "Synthetic fixture",
            "change_type": kind, "surfaces": [surface], "signals": signals}


def targets(result):
    return {row["target"] for row in result["controls"]}


def role_fixture(files=("scripts/roles_kit.py",), language="es"):
    catalog = roles.load_catalog()
    ctx = {"body": "", "title": "Synthetic role check",
           "labels": ["tipo: pruebas"], "files": list(files)}
    required, risks = roles.classify(ctx, catalog)
    declared = sorted(set(required) | ({"seguridad"} if risks else set()))
    primary = "ingenieria-software" if "ingenieria-software" in declared else declared[0]
    parts = ["Rol(es): " + ", ".join(declared), "Rol primario: " + primary]
    if risks:
        choices = roles.cross_review_allowed(risks)
        reviewer = next((r for r in ("seguridad", "qa", "arquitectura")
                         if r in choices and r in declared and r != primary), None)
        if reviewer:
            parts.append("Revisión cruzada: " + reviewer)
    for name in declared:
        content = (ROOT / "agentes" / "roles" / (name + ".md")).read_text(encoding="utf-8")
        parts += ["- [x] " + item for item in roles.parse_checklist(content)]
    ctx["body"] = "\n".join(parts)
    label_key = "label_en" if language == "en" else "label_es"
    ctx["labels"] = [catalog[name][label_key] for name in declared]
    return ctx, catalog, declared, primary


def validate(ctx, catalog, language="es"):
    return roles.validate_pr(ctx, catalog, roles.ROLES_DIR, language)


def evidence(row, fixtures):
    if row not in IDS:
        return UNKNOWN
    low, medium, high = fixtures["risk"]
    ctx, catalog, declared, primary = fixtures["roles"]
    workflow = fixtures["workflow"]
    if row == RISK_IDS[0]:
        ok = set(risk.BASE_CONTROLS + risk.MEDIUM_CONTROLS) <= targets(medium)
    elif row == RISK_IDS[1]:
        ok = set(risk.BASE_CONTROLS + risk.MEDIUM_CONTROLS +
                 risk.HIGH_CONTROLS) <= targets(high)
    elif row == RISK_IDS[2]:
        ok = targets(low) < targets(medium) < targets(high)
    elif row == RISK_IDS[3]:
        missing = risk.compile_risk(project_dna=dna(sparse=True),
                                    task=task("release", "api", production="unknown"))
        ok = (missing["risk"] == "high" and not missing["context_complete"]
              and "task.signals.production" in missing["unknown_critical_signals"]
              and set(risk.HIGH_CONTROLS) <= targets(missing))
    elif row == ROLE_IDS[0]:
        ok = primary in validate(ctx, catalog)["declared"]
    elif row == ROLE_IDS[1]:
        checked = roles.checked_items(ctx["body"])
        ok = all(set(roles.parse_checklist(
            (ROOT / "agentes" / "roles" / (name + ".md")).read_text(
                encoding="utf-8"))) <= checked for name in declared)
    elif row == ROLE_IDS[2]:
        risky, rcat, _, _ = role_fixture((".github/workflows/roles.yml",))
        ok = bool(validate(risky, rcat)["risks"])
        bad = dict(risky, body=re.sub(
            r"Revisión cruzada: [a-z0-9-]+", "Revisión cruzada: ingenieria-software",
            risky["body"]))
        try:
            validate(bad, rcat)
        except roles.RoleError:
            pass
        else:
            ok = False
    elif row == ROLE_IDS[3]:
        required, _ = roles.classify({
            "title": "", "body": "", "labels": ["tipo: pruebas"],
            "files": ["scripts/roles_kit.py"]}, catalog)
        ok = {"ingenieria-software", "qa"} <= set(required)
    elif row == ROLE_IDS[4]:
        bad = dict(ctx, body=ctx["body"].replace(
            "Rol primario: " + primary, "Rol primario: rol-invalido", 1))
        try:
            validate(bad, catalog)
        except roles.RoleError:
            ok = True
        else:
            ok = False
    elif row == ROLE_IDS[5]:
        ok = all(catalog[n]["label_es"] in ctx["labels"] and
                 catalog[n]["label_es"].startswith("rol: ") for n in declared)
    elif row == ROLE_IDS[6]:
        en, en_catalog, en_roles, _ = role_fixture(language="en")
        ok = (set(validate(en, en_catalog, "en")["declared"]) == set(en_roles)
              and all(label.startswith("role: ") for label in en["labels"]))
    elif row == ROLE_IDS[7]:
        mutate = workflow.split("  mutate:", 1)[-1]
        ok = ("gh label create" in mutate and
              "python3 .factory/scripts/roles_kit.py labels" in mutate and
              set(roles.labels_for(catalog, "es")) ==
              {v["label_es"] for v in catalog.values()})
    elif row == ROLE_IDS[8]:
        ok = workflow.count("ref: v1") >= 2
    elif row == ROLE_IDS[9]:
        ok = ("kit_ref" not in workflow and
              "repository: pl0n3r/factory" in workflow and
              ("ref: " + chr(36) + "{{ inputs.") not in workflow)
    elif row == ROLE_IDS[10]:
        section = workflow.split("  validate:", 1)[1].split("  mutate:", 1)[0]
        ok = ("issues: read" in section and "issues: write" not in section and
              '"$EVENT_NAME" == "pull_request"' in section and
              '"$EVENT_PR" == "$NUMBER"' in section)
    else:
        section = workflow.split("  mutate:", 1)[1]
        ok = ('case "$EVENT_NAME" in push|workflow_dispatch)' in section and
              '"$REF_NAME" == "refs/heads/$DEFAULT_BRANCH"' in section and
              "sync solo acepta rama principal" in section)
    return "VERIFIED_SYNTHETIC" if ok else UNKNOWN


class BrechasFactory69Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context = dna()
        cls.fixtures = {"risk": (
            risk.compile_risk(project_dna=context, task=task("docs", "docs")),
            risk.compile_risk(project_dna=context, task=task("code", "api")),
            risk.compile_risk(project_dna=context, task=task(
                "security", "auth", touches_auth=True))),
            "roles": role_fixture(),
            "workflow": (ROOT / ".github/workflows/roles.yml").read_text(
                encoding="utf-8")}

    def test_contrato_principal(self):
        self.assertEqual(len(IDS), 16)
        self.assertEqual(len(set(IDS)), 16)
        for row in IDS:
            with self.subTest(row=row):
                self.assertEqual(evidence(row, self.fixtures), "VERIFIED_SYNTHETIC")

    def test_falla_cerrado(self):
        with self.assertRaises(risk.RiskCompilerError):
            risk.compile_risk(project_dna=dna(), task={**task("code", "api"),
                                                       "signals": {}})
        with self.assertRaises(risk.RiskCompilerError):
            risk.compile_risk(project_dna=dna(), task={**task("code", "api"),
                                                       "surfaces": []})
        ctx, cat, _, _ = role_fixture()
        with self.assertRaises(roles.RoleError):
            validate({**ctx, "body": "Rol(es): qa\nRol primario: qa"}, cat)
        with self.assertRaises(roles.RoleError):
            validate({**ctx, "body": ctx["body"].replace("- [x] ", "- [ ] ", 1)}, cat)
        self.assertEqual(evidence("not-declared", self.fixtures), UNKNOWN)
        with patch.object(risk, "MEDIUM_CONTROLS", ()):
            broken = risk.compile_risk(project_dna=dna(), task=task("code", "api"))
            self.assertNotIn("rollback:plan", targets(broken))
            self.assertNotEqual(targets(broken), targets(self.fixtures["risk"][1]))

    def test_sin_datos_reales(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            risk_result = risk.compile_risk(project_dna=dna(), task=task("code", "api"))
            ctx, cat, _, _ = role_fixture()
            valid = validate(ctx, cat)
        self.assertEqual(risk_result["task_id"], "synthetic/factory#69")
        self.assertTrue(valid["declared"])
        self.assertTrue(all(row.startswith("docs/") for row in IDS))

    def test_estados_unknown_explicitos(self):
        raw = (ROOT / "docs/matriz-cobertura.md").read_text(encoding="utf-8")
        found = {}
        for line in raw.splitlines():
            if not line.startswith("|"):
                continue
            cells = [part.strip() for part in re.split(r"(?<!\\)\|",
                                                      line.strip().strip("|"))]
            key = cells[0].strip(chr(96))
            if key in IDS:
                self.assertNotIn(key, found)
                self.assertEqual(len(cells), 5)
                self.assertEqual(cells[2], "NO_VERIFICABLE")
                self.assertEqual(cells[4], "—")
                found[key] = cells
        self.assertEqual(set(found), set(IDS))
        for row in IDS:
            with self.subTest(row=row):
                self.assertIn("No se confirmó test + PR fusionado", found[row][3])
        self.assertEqual(evidence("docs/risk-compiler.md:L999-U1", self.fixtures),
                         UNKNOWN)


if __name__ == "__main__":
    unittest.main()
