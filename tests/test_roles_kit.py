#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from scripts.roles_kit import (
    MAX_CONTEXT,
    REQUIRED_ROLES,
    RoleError,
    classify,
    declared_roles,
    load_catalog,
    parse_context,
    validate_pr,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "agentes" / "roles" / "catalogo.json"
ROLES_DIR = ROOT / "agentes" / "roles"


def context(*, body="", labels=None, files=None, title=""):
    return {
        "body": body,
        "labels": labels or [],
        "files": files or [],
        "title": title,
    }


def complete_body(roles, primary=None, reviewer=None):
    declared = list(dict.fromkeys(roles))
    primary = primary or declared[0]
    if primary not in declared:
        raise ValueError("primary debe estar declarado")
    if reviewer is not None and reviewer not in declared:
        raise ValueError("reviewer debe estar declarado")
    lines = [f"Rol(es): {', '.join(declared)}", f"Rol primario: {primary}"]
    if reviewer:
        lines.append(f"Revisión cruzada: {reviewer}")
    for role in declared:
        content = (ROLES_DIR / f"{role}.md").read_text(encoding="utf-8")
        section = content.split("## Checklist", 1)[1].split(
            "## Evidencia exigida", 1
        )[0]
        for line in section.splitlines():
            if line.startswith("- [ ] "):
                lines.append("- [x] " + line[6:])
    return "\n".join(lines)


class RolesKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(CATALOG, ROLES_DIR)

    def test_catalog_has_exactly_sixteen_complete_roles(self):
        self.assertEqual(set(self.catalog), REQUIRED_ROLES)
        self.assertEqual(len(self.catalog), 16)

    def test_schema_change_requires_dba_and_cross_review(self):
        roles, risks = classify(context(files=["migrations/2026_add_index.sql"]))
        self.assertIn("dba", roles)
        self.assertIn("qa", roles)
        self.assertIn("schema", risks)

    def test_workflow_change_requires_infra_sre_security(self):
        roles, risks = classify(context(files=[".github/workflows/deploy.yml"]))
        self.assertTrue({"infraestructura", "sre", "seguridad"} <= set(roles))
        self.assertIn("deploy", risks)

    def test_public_frontend_change_requires_ux(self):
        roles, risks = classify(context(files=["public/app.css"]))
        self.assertTrue({"frontend", "ux", "qa"} <= set(roles))
        self.assertIn("public-ux", risks)

    def test_issue_type_can_assign_role_without_files(self):
        roles, _ = classify(context(labels=["tipo: producto"]))
        self.assertEqual(roles, ["producto"])

    def test_validate_pr_accepts_complete_multi_role_evidence(self):
        required, _ = classify(context(files=[".github/workflows/roles.yml"]))
        declared = sorted(set(required) | {"ingenieria-software", "qa"})
        body = complete_body(
            declared,
            primary="ingenieria-software",
            reviewer="seguridad",
        )
        labels = [self.catalog[role]["label_es"] for role in declared]
        result = validate_pr(
            context(
                body=body,
                labels=labels,
                files=[".github/workflows/roles.yml"],
            ),
            self.catalog,
            ROLES_DIR,
            "es",
        )
        self.assertEqual(set(result["declared"]), set(declared))
        self.assertTrue(set(required) <= set(result["declared"]))

    def test_missing_checklist_fails_closed(self):
        required, _ = classify(context(files=["scripts/roles_kit.py"]))
        body = (
            f"Rol(es): {', '.join(required)}\n"
            "Rol primario: ingenieria-software"
        )
        labels = [self.catalog[role]["label_es"] for role in required]
        with self.assertRaisesRegex(RoleError, "Checklist incompleto"):
            validate_pr(
                context(
                    body=body,
                    labels=labels,
                    files=["scripts/roles_kit.py"],
                ),
                self.catalog,
                ROLES_DIR,
                "es",
            )

    def test_risk_without_cross_review_fails(self):
        required, _ = classify(context(files=[".github/workflows/roles.yml"]))
        declared = sorted(set(required) | {"ingenieria-software"})
        body = complete_body(declared, primary="ingenieria-software")
        labels = [self.catalog[role]["label_es"] for role in declared]
        with self.assertRaisesRegex(RoleError, "Revisión cruzada"):
            validate_pr(
                context(
                    body=body,
                    labels=labels,
                    files=[".github/workflows/roles.yml"],
                ),
                self.catalog,
                ROLES_DIR,
                "es",
            )

    def test_english_labels_are_enforced(self):
        required, _ = classify(context(files=["scripts/roles_kit.py"]))
        body = complete_body(required)
        labels = [self.catalog[role]["label_en"] for role in required]
        validate_pr(
            context(
                body=body,
                labels=labels,
                files=["scripts/roles_kit.py"],
            ),
            self.catalog,
            ROLES_DIR,
            "en",
        )

    def test_unknown_declared_role_fails(self):
        self.assertEqual(declared_roles("Rol(es): qa, sre"), ["qa", "sre"])
        bad = "Rol(es): qa, mago\nRol primario: qa"
        with self.assertRaisesRegex(RoleError, "desconocidos"):
            validate_pr(
                context(body=bad, labels=["rol: qa"], files=[]),
                self.catalog,
                ROLES_DIR,
                "es",
            )

    def test_path_classification_uses_segments_not_ambiguous_regex(self):
        roles, risks = classify(
            context(
                files=[
                    "migrations/2026_add.sql",
                    "public/app.css",
                    ".github/workflows/deploy.yml",
                ]
            )
        )
        self.assertTrue({"dba", "frontend", "ux", "infraestructura", "sre", "seguridad"} <= set(roles))
        self.assertEqual({"schema", "public-ux", "deploy"}, risks)

    def test_role_declarations_handle_large_body_without_multiline_regex(self):
        prefix = "x" * 100_000
        body = prefix + "\nRol(es): qa, sre\nRol primario: qa\n"
        self.assertEqual(declared_roles(body), ["qa", "sre"])

    def test_declaration_parser_does_not_accept_trailing_content_as_slug(self):
        required, _ = classify(context())
        body = complete_body(required)
        body = body.replace(
            f"Rol primario: {required[0]}",
            "Rol primario: qa extra",
            1,
        )
        labels = [self.catalog[role]["label_es"] for role in required]
        with self.assertRaisesRegex(RoleError, "Rol primario"):
            validate_pr(
                context(body=body, labels=labels, files=[]),
                self.catalog,
                ROLES_DIR,
                "es",
            )

    def test_context_is_bounded_and_closed(self):
        payload = json.dumps(
            {
                "body": "",
                "title": "",
                "labels": ["tipo: producto"],
                "files": [],
            }
        )
        parsed = parse_context(payload)
        self.assertEqual(parsed["labels"], ["tipo: producto"])
        with self.assertRaisesRegex(RoleError, "demasiado grande"):
            parse_context("x" * (MAX_CONTEXT + 1))


if __name__ == "__main__":
    unittest.main()
