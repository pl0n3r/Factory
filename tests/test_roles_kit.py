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


    def _offline_health_fixture(self):
        files = list(rk.OFFLINE_HEALTH_FILES)
        declared = ["infraestructura", "ingenieria-software", "qa", "seguridad", "sre"]
        body = complete_body(declared, primary="ingenieria-software", reviewer="seguridad")
        sre = rk.parse_checklist((ROLES_DIR / "sre.md").read_text(encoding="utf-8"))
        for item in sre:
            body = body.replace("- [x] " + item, "- [ ] " + item)
        body += (
            "\nCloses #798\n## Bloqueo de roles\n"
            "Este DTO no ejecuta ninguna operación productiva.\n"
            "#### SRE — pendiente, no realizado por esta hoja\n"
        )
        labels = [self.catalog[role]["label_es"] for role in declared] + ["tipo: infraestructura"]
        scope = {
            "source": rk.OFFLINE_SCOPE_SOURCE,
            "repo": "pl0n3r/ControlBot",
            "issue": 798, "pr": 799,
            "head_sha": "bde659c30a7aaa7029fe01ad523c0c6f1a65ce28",
            "reviewed_sha": "bde659c30a7aaa7029fe01ad523c0c6f1a65ce28",
            "branch": "trabajo/issue-798",
            "reservation_id": "308c0309-3b35-4325-acac-bd946b348068",
            "paths": files,
        }
        return context(body=body, labels=labels, files=files), scope, sre

    def test_offline_health_dto_still_requires_sre_evidence_without_attestation(self):
        ctx, _scope, _items = self._offline_health_fixture()
        with self.assertRaisesRegex(RoleError, "Checklist incompleto para sre"):
            validate_pr(ctx, self.catalog, ROLES_DIR, "es")

    def test_verified_offline_scope_allows_explicit_non_applicable_operational_items(self):
        ctx, scope, items = self._offline_health_fixture()
        result = validate_pr(ctx, self.catalog, ROLES_DIR, "es", verified_scope=scope)
        self.assertIn("sre", result["declared"])
        self.assertEqual(set(result["not_applicable"]["sre"]), set(items))
        self.assertIn("sre", result["required"])

    def test_real_deploy_or_forged_applicability_fails_closed(self):
        ctx, scope, _items = self._offline_health_fixture()
        cases = [
            ({**ctx, "files": ctx["files"] + [".github/workflows/deploy.yml"]}, scope),
            (ctx, {**scope, "source": "pr-body"}),
            (ctx, {**scope, "repo": "attacker/ControlBot"}),
            (ctx, {**scope, "head_sha": "a" * 40}),
            (ctx, {**scope, "reviewed_sha": "b" * 40}),
            (ctx, {**scope, "paths": ctx["files"] + ["public/health.php"]}),
            (ctx, {**scope, "issue": 673}),
            (ctx, {**scope, "reservation_id": "not-a-uuid"}),
            ({**ctx, "body": ctx["body"].replace("Closes #798", "")}, scope),
            (ctx, {"source": rk.OFFLINE_SCOPE_SOURCE}),
        ]
        for changed_context, claimed_scope in cases:
            with self.subTest(case=claimed_scope, files=changed_context["files"]):
                with self.assertRaises(RoleError):
                    validate_pr(
                        changed_context, self.catalog, ROLES_DIR, "es",
                        verified_scope=claimed_scope,
                    )

    def test_full_roles_checklist_remains_required_without_verified_scope(self):
        ctx, scope, _items = self._offline_health_fixture()
        ctx["files"] = [".github/workflows/deploy.yml"]
        with self.assertRaises(RoleError):
            validate_pr(ctx, self.catalog, ROLES_DIR, "es", verified_scope=scope)
        with self.assertRaisesRegex(RoleError, "Checklist incompleto para sre"):
            validate_pr(self._offline_health_fixture()[0], self.catalog, ROLES_DIR, "es")

    def test_offline_scope_workflow_paginates_and_binds_exact_event_head(self):
        workflow = (ROOT / ".github" / "workflows" / "roles.yml").read_text(
            encoding="utf-8"
        )
        step = workflow.split(
            "      - name: Acreditar scope de DTO offline con GitHub autenticado", 1
        )[1].split("      - name: Validar PR", 1)[0]
        for issue in (798, 799):
            with self.subTest(issue=issue):
                self.assertIn(
                    f'gh api --paginate "repos/$REPOSITORY/issues/{issue}/comments?per_page=100"',
                    step,
                )
        self.assertIn("EVENT_HEAD_SHA: ${{ github.event.pull_request.head.sha }}", step)
        self.assertIn('event_sha = os.environ.get("EVENT_HEAD_SHA")', step)
        self.assertIn('sha != event_sha', step)
        self.assertIn('raise SystemExit("PR head differs from the triggering event head")', step)
        self.assertEqual(step.count("| jq -s '.' > /tmp/offline-"), 2)

    def _offline_legal_docs_fixture(self):
        files = list(rk.OFFLINE_LEGAL_DOC_FILES)
        declared = ["ingenieria-software", "qa", "seguridad", "sre", "legal-privacidad", "dba", "contenido"]
        body = complete_body(declared, primary="ingenieria-software", reviewer="seguridad")
        sre = rk.parse_checklist((ROLES_DIR / "sre.md").read_text(encoding="utf-8"))
        for item in sre:
            body = body.replace("- [x] " + item, "- [ ] " + item)
        body += "\nCloses #837\nSRE — **pendiente de evidencia operativa real**; ninguna casilla acredita ejecución.\n"
        labels = [self.catalog[role]["label_es"] for role in declared] + ["tipo: incidente"]
        scope = {
            "source": rk.OFFLINE_LEGAL_DOC_SOURCE,
            "repo": "pl0n3r/ControlBot", "issue": 837, "pr": 838,
            "head_sha": "2efd14b92517434044720ff3cb12d47fe18de216",
            "branch": "trabajo/issue-837",
            "reservation_id": "fd7832c7-d93a-4bf8-a960-2adb8c6449c9",
            "paths": files,
            "checks": list(rk.OFFLINE_LEGAL_DOC_CHECKS),
        }
        return context(body=body, labels=labels, files=files, title="Corrección de privacidad"), scope, sre

    def test_verified_offline_legal_doc_sync_attestation_is_narrow_and_does_not_claim_sre_performed(self):
        ctx, scope, items = self._offline_legal_docs_fixture()
        with self.assertRaisesRegex(RoleError, "Checklist incompleto para sre"):
            validate_pr(ctx, self.catalog, ROLES_DIR, "es")
        result = validate_pr(ctx, self.catalog, ROLES_DIR, "es", verified_scope=scope)
        self.assertEqual(set(result["not_applicable"]["sre"]), set(items))
        self.assertIn("sre", result["required"])
        self.assertFalse(any("- [x] " + item in ctx["body"] for item in items))

    def test_forged_legal_doc_sync_scope_wrong_paths_or_head_fails_closed(self):
        ctx, scope, _ = self._offline_legal_docs_fixture()
        mutations = [
            (ctx, {**scope, "source": "pr-body"}),
            (ctx, {**scope, "repo": "other/ControlBot"}),
            (ctx, {**scope, "issue": 798}),
            (ctx, {**scope, "pr": 799}),
            (ctx, {**scope, "head_sha": "stale"}),
            (ctx, {**scope, "branch": "trabajo/issue-798"}),
            (ctx, {**scope, "reservation_id": "not-a-uuid"}),
            (ctx, {**scope, "checks": ["Validar"]}),
            (ctx, {**scope, "checks": ["Validar", "privacidad / Privacidad como código", "bypass"]}),
            (ctx, {**scope, "paths": scope["paths"][:-1]}),
            (ctx, {**scope, "extra": True}),
            ({**ctx, "files": ctx["files"] + [".github/workflows/deploy.yml"]}, scope),
            ({**ctx, "body": ctx["body"].replace("Closes #837", "")}, scope),
        ]
        for changed, forged in mutations:
            with self.subTest(forged=forged):
                with self.assertRaises(RoleError):
                    validate_pr(changed, self.catalog, ROLES_DIR, "es", verified_scope=forged)

    def test_legal_document_scope_requires_pinned_byte_exact_artifacts(self):
        """No basta auto-consistencia: los metadatos deben ser independientes."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            canonical = {}
            for filename in rk.OFFLINE_LEGAL_DOC_FILES:
                dest = root / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                data = ("ejemplo canónico para " + filename + "\n").encode("utf-8")
                if filename == "revision-juridica/00-LEEME.md":
                    data = (
                        f"Última actualización automática (UTC): {rk.OFFLINE_LEGAL_DOC_STAMP} "
                        f"| SHA de origen: {rk.OFFLINE_LEGAL_DOC_ORIGIN_SHA}\n"
                        "# Paquete de revisión jurídica\n"
                    ).encode("utf-8")
                canonical[filename] = data
                dest.write_bytes(data)
            rk.verify_offline_legal_artifact_bytes(root, canonical)
            index = root / "revision-juridica/00-LEEME.md"
            original = index.read_bytes()
            index.write_bytes(original.replace(
                rk.OFFLINE_LEGAL_DOC_ORIGIN_SHA.encode("ascii"), b"a" * 40
            ))
            with self.assertRaisesRegex(RoleError, "origen no acreditados"):
                rk.verify_offline_legal_artifact_bytes(root, canonical)
            index.write_bytes(original.replace(b"2026-10-19", b"2026-10-20"))
            with self.assertRaises(RoleError):
                rk.verify_offline_legal_artifact_bytes(root, canonical)
            index.write_bytes(original)
            for filename in rk.OFFLINE_LEGAL_DOC_FILES:
                target = root / filename
                target.write_bytes(canonical[filename] + b"\nAlteracion")
                with self.subTest(filename=filename), self.assertRaisesRegex(
                    RoleError, "byte a byte"
                ):
                    rk.verify_offline_legal_artifact_bytes(root, canonical)
                target.write_bytes(canonical[filename])
            with self.assertRaisesRegex(RoleError, "no canónico"):
                rk.verify_offline_legal_artifact_bytes(root, {})
            # Fallos de I/O en índice y copias: fail-closed sin conceder N/A.
            with patch.object(Path, "read_bytes", side_effect=OSError("denegado")):
                with self.assertRaisesRegex(RoleError, "procedencia jurídica"):
                    rk.verify_offline_legal_artifact_bytes(root, canonical)
            original_read = Path.read_bytes

            def fail_copy_read(path):
                if path == root / rk.OFFLINE_LEGAL_DOC_FILES[1]:
                    raise OSError("documento inaccesible")
                return original_read(path)

            with patch.object(Path, "read_bytes", fail_copy_read):
                with self.assertRaisesRegex(RoleError, "No se puede leer"):
                    rk.verify_offline_legal_artifact_bytes(root, canonical)
            # Un enlace a un archivo válido sigue siendo una entrada no canónica.
            index_link = root / "revision-juridica/00-LEEME.md"
            index_backup = root / "index-original.md"
            index_link.rename(index_backup)
            index_link.symlink_to(index_backup)
            with self.assertRaisesRegex(RoleError, "índice jurídico canónico"):
                rk.verify_offline_legal_artifact_bytes(root, canonical)
            index_link.unlink()
            index_backup.rename(index_link)
            copy_link = root / rk.OFFLINE_LEGAL_DOC_FILES[3]
            copy_backup = root / "copia-original.md"
            copy_link.rename(copy_backup)
            copy_link.symlink_to(copy_backup)
            with self.assertRaisesRegex(RoleError, "no canónico"):
                rk.verify_offline_legal_artifact_bytes(root, canonical)
            copy_link.unlink()
            copy_backup.rename(copy_link)
            # Un objeto no dict o el documento ausente también deben rechazarse.
            with self.assertRaisesRegex(RoleError, "Falta render canónico"):
                rk.verify_offline_legal_artifact_bytes(root, None)
            missing = root / rk.OFFLINE_LEGAL_DOC_FILES[-1]
            missing.unlink()
            with self.assertRaises(RoleError):
                rk.verify_offline_legal_artifact_bytes(root, canonical)

    def test_legal_document_workflow_rebuilds_from_pinned_trusted_sources(self):
        workflow = (ROOT / ".github/workflows/roles.yml").read_text(
            encoding="utf-8"
        )
        checkout = workflow.split(
            "      - name: Descargar PR jurídico HEAD exacto (solo lectura)", 1
        )[1].split(
            "      - name: Acreditar N/A SRE documental desde V3 y checks exact-HEAD", 1
        )[0]
        self.assertIn("repository: pl0n3r/ControlBot", checkout)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", checkout)
        self.assertIn("persist-credentials: false", checkout)
        step = workflow.split(
            "      - name: Acreditar N/A SRE documental desde V3 y checks exact-HEAD", 1
        )[1].split("      - name: Validar PR", 1)[0]
        self.assertIn("checkout_head != head", step)
        self.assertIn('sorted(files) != paths', step)
        self.assertIn("generator.expected_files(", step)
        self.assertIn("OFFLINE_LEGAL_DOC_STAMP, OFFLINE_LEGAL_DOC_ORIGIN_SHA", step)
        self.assertIn("verify_offline_legal_artifact_bytes(root, canonical)", step)
        self.assertIn('c.get("app", {}).get("id") == 15368', step)

    def test_non_doc_incident_requires_all_sre_evidence(self):
        ctx, scope, _ = self._offline_legal_docs_fixture()
        other = {**ctx, "files": ["docs/privacidad/extra.md"]}
        with self.assertRaisesRegex(RoleError, "Checklist incompleto para sre"):
            validate_pr(other, self.catalog, ROLES_DIR, "es", verified_scope=scope)
        old_ctx, old_scope, _ = self._offline_health_fixture()
        self.assertEqual(
            validate_pr(old_ctx, self.catalog, ROLES_DIR, "es", verified_scope=old_scope)["not_applicable"]["sre"],
            sorted(rk.parse_checklist((ROLES_DIR / "sre.md").read_text(encoding="utf-8"))),
        )

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

    def test_pr_role_checklists_do_not_create_recursive_required_roles(self):
        body = complete_body(["contenido"], primary="contenido")
        result = validate_pr(
            context(
                body=body,
                labels=["tipo: documentación", self.catalog["contenido"]["label_es"]],
            ),
            self.catalog,
            ROLES_DIR,
            "es",
        )
        self.assertEqual(result["required"], ["contenido"])
        self.assertEqual(result["declared"], ["contenido"])

    def test_real_pr_prose_still_drives_text_role_classification_after_evidence_is_ignored(self):
        body = (
            complete_body(["contenido", "marketing"], primary="marketing")
            + "\n\nLa campaña requiere CTA medible para mejorar conversión."
        )
        roles, _ = classify(
            context(
                body=body,
                labels=["tipo: documentación"],
            ),
            self.catalog,
        )
        self.assertLessEqual({"contenido", "marketing"}, set(roles))
        self.assertNotIn("legal-privacidad", roles)

    def test_non_role_checkbox_prose_still_drives_text_role_classification(self):
        roles, _ = classify(
            context(body="- [x] CTA de campaña visible para conversión."),
            self.catalog,
        )
        self.assertLessEqual({"contenido", "marketing"}, set(roles))

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
        self.assertLessEqual({"seguridad", "qa", "ingenieria-software"}, roles)
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
        self.assertLessEqual(
            {"qa", "seguridad"},
            rk.cross_review_allowed({"deploy", "security"}),
        )

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
