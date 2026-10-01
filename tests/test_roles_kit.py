#!/usr/bin/env python3
import io
import json
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts import roles_kit as rk
from scripts.roles_kit import (
    MAX_CONTEXT,
    REQUIRED_ROLES,
    RoleError,
    classify,
    compile_team,
    declared_roles,
    labels_for,
    load_catalog,
    main,
    parse_context,
    propose_role_candidate,
    register_role_candidate,
    validate_pr,
    validate_role_candidate,
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

    def test_catalog_has_all_required_complete_roles(self):
        self.assertTrue(REQUIRED_ROLES <= set(self.catalog))
        self.assertGreaterEqual(len(self.catalog), len(REQUIRED_ROLES))

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

    def test_negated_role_keywords_do_not_force_roles(self):
        roles, _ = classify(
            context(
                title="Cambio de documentación",
                body="Sin migraciones y sin cambios de schema.",
                labels=["tipo: documentación"],
            )
        )
        self.assertNotIn("dba", roles)
        self.assertEqual(roles, ["contenido"])

        roles, _ = classify(
            context(
                title="Cambio de documentación",
                body="Sin migraciones de schema.",
                labels=["tipo: documentación"],
            )
        )
        self.assertNotIn("dba", roles)
        self.assertEqual(roles, ["contenido"])

    def test_exact_word_does_not_trigger_marketing_roles(self):
        roles, _ = classify(
            context(
                title="Validar SHA exacto",
                body="La base exacta se conserva sin cambios de producto.",
            )
        )
        self.assertNotIn("marketing", roles)
        self.assertNotIn("contenido", roles)

    def test_non_database_migration_does_not_trigger_dba(self):
        roles, _ = classify(
            context(
                title="Migración de Sonar a CI-based",
                body="Migración reversible de Automatic Analysis a CI-based.",
                files=[".github/workflows/sonar.yml"],
            )
        )
        self.assertNotIn("dba", roles)

    def test_real_marketing_signals_still_trigger_marketing_and_content(self):
        roles, _ = classify(context(body="CTA de campaña y campaign tracking."))
        self.assertLessEqual({"marketing", "contenido"}, set(roles))

    def test_database_migration_signals_still_trigger_dba(self):
        for body in (
            "Migración de schema para pedidos.",
            "Database migration for orders.",
            "DB migration for orders.",
        ):
            with self.subTest(body=body):
                roles, _ = classify(context(body=body))
                self.assertIn("dba", roles)

        roles, risks = classify(context(files=["migrations/2026_add_index.sql"]))
        self.assertIn("dba", roles)
        self.assertIn("schema", risks)

    def test_text_role_false_positive_regression_matrix(self):
        cases = (
            ("SHA exacto y base exacta", {"marketing", "contenido"}, False),
            ("Migración de Sonar a CI-based", {"dba"}, False),
            ("CTA de campaña", {"marketing", "contenido"}, True),
            ("Migración de schema", {"dba"}, True),
        )
        for body, expected, present in cases:
            with self.subTest(body=body):
                roles, _ = classify(context(body=body))
                if present:
                    self.assertLessEqual(expected, set(roles))
                else:
                    self.assertTrue(expected.isdisjoint(roles))

    def test_catalog_accepts_additional_valid_role(self):
        original = json.loads(CATALOG.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            roles_dir = base / "roles"
            roles_dir.mkdir()
            for source in ROLES_DIR.glob("*.md"):
                shutil.copyfile(source, roles_dir / source.name)
            extra = roles_dir / "mobile-engineering.md"
            template = (ROLES_DIR / "ingenieria-software.md").read_text(encoding="utf-8")
            extra.write_text(
                template.replace("# Ingeniería de software", "# Mobile Engineering")
                .replace("Slug: `ingenieria-software`", "Slug: `mobile-engineering`")
                .replace("rol: ingenieria-software", "rol: mobile-engineering")
                .replace("role: software-engineering", "role: mobile-engineering"),
                encoding="utf-8",
            )
            rel_roles = roles_dir.relative_to(ROOT)
            catalog = []
            for item in original:
                copy = dict(item)
                copy["file"] = str(rel_roles / f"{copy['slug']}.md")
                catalog.append(copy)
            catalog.append(
                {
                    "slug": "mobile-engineering",
                    "label_es": "rol: mobile-engineering",
                    "label_en": "role: mobile-engineering",
                    "file": str(rel_roles / "mobile-engineering.md"),
                }
            )
            catalog_path = base / "catalogo.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            loaded = load_catalog(catalog_path, roles_dir)
            self.assertIn("mobile-engineering", loaded)
            self.assertTrue(REQUIRED_ROLES <= set(loaded))

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


    def test_validation_and_cli_boundaries_are_covered(self):
        with self.assertRaises(RoleError):
            rk._repo_relative(Path("/tmp/outside-factory"))
        with self.assertRaisesRegex(RoleError, "Checklist"):
            rk.parse_checklist("sin checklist")
        for payload in (
            "{",
            "[]",
            json.dumps({"body": 1, "title": "", "labels": [], "files": []}),
            json.dumps({"body": "", "title": "", "labels": "bad", "files": []}),
            json.dumps({"body": "", "title": "", "labels": [], "files": "bad"}),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(RoleError):
                    rk.parse_context(payload)

        roles, risks = rk._classify_file("security/auth.py")
        self.assertTrue({"seguridad", "qa", "ingenieria-software"} <= roles)
        self.assertIn("security", risks)
        roles, _ = rk._classify_file("analytics/report.py")
        self.assertIn("datos-analitica", roles)
        roles, _ = rk._classify_file("seo/robots.txt")
        self.assertIn("seo", roles)
        roles, _ = rk._classify_file("legal/privacy.md")
        self.assertIn("legal-privacidad", roles)
        roles, _ = rk._classify_file("architecture/adr.md")
        self.assertIn("arquitectura", roles)

        self.assertEqual(rk.declared_roles(""), [])
        self.assertIsNone(rk.single_role("Rol primario: QA EXTRA", "Rol primario"))
        self.assertEqual(rk.checked_items("- [x] Uno\n- [X] Dos"), {"Uno", "Dos"})
        self.assertTrue({"qa", "seguridad"} <= rk.cross_review_allowed({"deploy", "security"}))

        bad_candidates = [
            {},
            {
                "slug": "X",
                "title": "x",
                "seniority": "x",
                "domains": ["x"],
                "stacks": ["x"],
                "heuristics": ["x"],
                "checklist": ["x"],
                "evidence": ["x"],
                "trigger": "x",
            },
        ]
        for candidate in bad_candidates:
            with self.subTest(candidate=candidate):
                with self.assertRaises(RoleError):
                    rk.validate_role_candidate(candidate)

        mobile = rk.propose_role_candidate(
            context(body="Android Kotlin mobile app"),
            self.catalog,
        )
        self.assertIsNotNone(mobile)
        registry = rk.register_role_candidate({}, mobile)
        self.assertIn("mobile-engineering", registry)
        with self.assertRaisesRegex(RoleError, "ya existe"):
            rk.register_role_candidate(registry, mobile)

        team = rk.compile_team(
            context(
                body="Hostinger MariaDB deployment security",
                files=[".github/workflows/deploy.yml", "migrations/x.sql"],
            ),
            self.catalog,
        )
        self.assertIn(team["primary"], team["roles"])
        self.assertIn("github-actions", team["stacks"])
        self.assertTrue(team["contextual_profiles"])

        self.assertEqual(len(rk.labels_for(self.catalog, "es")), len(self.catalog))
        self.assertEqual(len(rk.labels_for(self.catalog, "en")), len(self.catalog))

        commands = [
            ("validate-catalog", "", 0),
            ("labels", "", 0),
            (
                "suggest",
                json.dumps(
                    {
                        "body": "Android mobile",
                        "title": "",
                        "labels": [],
                        "files": [],
                    }
                ),
                0,
            ),
        ]
        for command, stdin, expected in commands:
            with (
                self.subTest(command=command),
                patch.object(sys, "argv", ["roles_kit.py", command, "--language", "es"]),
                patch("sys.stdin", io.StringIO(stdin)),
                patch("sys.stdout", new_callable=io.StringIO),
            ):
                self.assertEqual(rk.main(), expected)

        with (
            patch.object(sys, "argv", ["roles_kit.py", "suggest"]),
            patch("sys.stdin", io.StringIO("{")),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.assertEqual(rk.main(), 1)


if __name__ == "__main__":
    unittest.main()
