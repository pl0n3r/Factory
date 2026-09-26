#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.labels_kit import (
    LabelError,
    aliases_for_language,
    catalog_for_language,
    linked_issue_names,
    sweep_issue_plan,
    validation_document_plan,
    validation_plan,
    warning_plan,
    load_catalog,
    selected_names,
    sweep,
    upsert_plan,
    validate_selection,
)

ROOT = Path(__file__).resolve().parents[1]


class LabelsKitTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog_for_language("es")

    def test_catalog_language_is_closed(self):
        self.assertTrue(catalog_for_language("en"))
        with self.assertRaises(LabelError):
            catalog_for_language("../es")
        with self.assertRaises(LabelError):
            aliases_for_language("../es")

    def test_catalog_uses_medium_low_and_shared_extra_types(self):
        es = {item["key"]: item["name"] for item in catalog_for_language("es")}
        en = {item["key"]: item["name"] for item in catalog_for_language("en")}
        self.assertEqual(es["priority_medium"], "prioridad: media")
        self.assertEqual(es["priority_low"], "prioridad: baja")
        self.assertEqual(en["priority_medium"], "priority: medium")
        self.assertEqual(en["priority_low"], "priority: low")
        self.assertNotIn("priority_normal", es)
        self.assertNotIn("priority_normal", en)
        self.assertEqual(es["type_security"], "tipo: seguridad")
        self.assertEqual(es["type_quality"], "tipo: calidad")
        self.assertEqual(es["type_technical_debt"], "tipo: deuda técnica")
        self.assertEqual(es["type_accessibility"], "tipo: accesibilidad")
        self.assertEqual(en["type_security"], "type: security")
        self.assertEqual(en["type_quality"], "type: quality")
        self.assertEqual(en["type_technical_debt"], "type: technical debt")
        self.assertEqual(en["type_accessibility"], "type: accessibility")

    def test_valid_selection_requires_exactly_one_per_dimension(self):
        validate_selection(
            self.catalog,
            {"tipo: infraestructura", "prioridad: crítica", "estado: reservado"},
        )
        with self.assertRaises(LabelError):
            validate_selection(self.catalog, {"tipo: infraestructura", "estado: reservado"})
        with self.assertRaises(LabelError):
            validate_selection(
                self.catalog,
                {
                    "tipo: infraestructura",
                    "tipo: mejora",
                    "prioridad: crítica",
                    "estado: reservado",
                },
            )

    def test_upsert_plan_is_idempotent_and_updates_drift(self):
        existing = [
            {
                "name": item["name"],
                "color": item["color"],
                "description": item["description"],
            }
            for item in self.catalog
        ]
        aliases = aliases_for_language("es")
        self.assertEqual(upsert_plan(self.catalog, existing, aliases=aliases), [])
        existing[0]["color"] = "FFFFFF"
        plan = upsert_plan(self.catalog, existing, aliases=aliases)
        self.assertEqual(plan[0]["action"], "update")
        self.assertEqual(plan[0]["name"], self.catalog[0]["name"])

    def test_alias_renames_when_canonical_is_absent(self):
        aliases = aliases_for_language("es")
        existing = [
            {"name": "prioridad: normal", "color": "C5DEF5", "description": "legacy"},
            {"name": "calidad", "color": "FFFFFF", "description": "legacy"},
        ]
        plan = upsert_plan(self.catalog, existing, aliases=aliases)
        renames = {item["old_name"]: item for item in plan if item["action"] == "rename"}
        self.assertEqual(renames["prioridad: normal"]["name"], "prioridad: media")
        self.assertEqual(renames["calidad"]["name"], "tipo: calidad")
        self.assertFalse(
            any(
                item["action"] == "create"
                and item["name"] in {"prioridad: media", "tipo: calidad"}
                for item in plan
            )
        )

    def test_alias_and_canonical_can_coexist_idempotently(self):
        existing = [
            {
                "name": item["name"],
                "color": item["color"],
                "description": item["description"],
            }
            for item in self.catalog
        ]
        existing.append(
            {"name": "prioridad: normal", "color": "C5DEF5", "description": "legacy"}
        )

        plan = upsert_plan(
            self.catalog,
            existing,
            aliases=aliases_for_language("es"),
        )

        self.assertEqual(plan, [])

    def test_alias_and_canonical_updates_canonical_metadata(self):
        existing = [
            {
                "name": item["name"],
                "color": item["color"],
                "description": item["description"],
            }
            for item in self.catalog
        ]
        canonical = next(
            item for item in existing if item["name"] == "prioridad: media"
        )
        canonical["color"] = "FFFFFF"
        canonical["description"] = "drift"
        existing.append(
            {"name": "prioridad: normal", "color": "C5DEF5", "description": "legacy"}
        )

        plan = upsert_plan(
            self.catalog,
            existing,
            aliases=aliases_for_language("es"),
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action"], "update")
        self.assertEqual(plan[0]["name"], "prioridad: media")

    def test_english_aliases_cover_real_repo_legacy_names(self):
        aliases = aliases_for_language("en")
        self.assertEqual(aliases["priority: normal"], "priority: medium")
        self.assertEqual(aliases["quality"], "type: quality")
        self.assertEqual(aliases["security"], "type: security")
        self.assertEqual(aliases["technical debt"], "type: technical debt")
        self.assertEqual(aliases["accessibility"], "type: accessibility")

    def test_sweep_reports_only_invalid_issues(self):
        valid = {
            "number": 1,
            "labels": [
                {"name": "tipo: mejora"},
                {"name": "prioridad: media"},
                {"name": "estado: disponible"},
            ],
        }
        invalid = {"number": 2, "labels": [{"name": "tipo: mejora"}]}
        self.assertEqual(sweep(self.catalog, [json.dumps(valid), json.dumps(invalid)]), [2])

    def test_validation_plan_defaults_state_and_inherits_unique_closing_issue(self):
        catalog = catalog_for_language("en")
        linked_issue = {
            "state": "closed",
            "labels": [
                {"name": "type: infrastructure"},
                {"name": "priority: high"},
                {"name": "status: available"},
            ],
        }
        linked = linked_issue_names(linked_issue)
        plan = validation_plan(
            catalog,
            set(),
            is_pull_request=True,
            body="Closes #42",
            linked_names=linked,
        )
        self.assertTrue(plan["valid"])
        self.assertEqual(plan["closing_issue"], 42)
        self.assertEqual(
            set(plan["add"]),
            {"type: infrastructure", "priority: high", "status: in review"},
        )

        self.assertEqual(
            linked_issue_names({**linked_issue, "state": "open"}),
            linked,
        )
        self.assertIsNone(linked_issue_names({**linked_issue, "pull_request": {}}))

        ambiguous = validation_plan(
            catalog,
            set(),
            is_pull_request=True,
            body="Closes #42\nFixes #43",
            linked_names=linked,
        )
        self.assertIsNone(ambiguous["closing_issue"])
        self.assertEqual(set(ambiguous["add"]), {"status: in review"})
        self.assertEqual(ambiguous["missing"], ["type", "priority"])

        issue = validation_plan(catalog, set(), is_pull_request=False)
        self.assertIn("status: available", issue["add"])
        self.assertEqual(issue["missing"], ["type", "priority"])

        with self.assertRaises(LabelError):
            validation_plan(catalog, set(), is_pull_request=1)

        document = {
            "labels": [],
            "is_pull_request": True,
            "body": "Closes #42",
            "linked_issue": linked_issue,
        }
        self.assertTrue(validation_document_plan(catalog, document, "en")["valid"])

    def test_open_linked_issue_inherits_type_and_priority(self):
        for language, type_name, priority_name, review_name in (
            ("es", "tipo: error", "prioridad: alta", "estado: en revisión"),
            ("en", "type: bug", "priority: high", "status: in review"),
        ):
            catalog = catalog_for_language(language)
            linked = linked_issue_names(
                {
                    "state": "open",
                    "labels": [
                        {"name": type_name},
                        {"name": priority_name},
                        {"name": "estado: reservado" if language == "es" else "status: reserved"},
                    ],
                }
            )
            plan = validation_plan(
                catalog,
                set(),
                is_pull_request=True,
                body="Closes #194",
                linked_names=linked,
            )
            self.assertTrue(plan["valid"])
            self.assertEqual(plan["closing_issue"], 194)
            self.assertEqual(set(plan["add"]), {type_name, priority_name, review_name})

    def test_closed_linked_issue_keeps_inheritance_and_pr_review_state(self):
        catalog = catalog_for_language("es")
        linked = linked_issue_names(
            {
                "state": "closed",
                "labels": [
                    {"name": "tipo: mejora"},
                    {"name": "prioridad: media"},
                    {"name": "estado: cerrado"},
                ],
            }
        )
        plan = validation_plan(
            catalog,
            set(),
            is_pull_request=True,
            body="Fixes #41",
            linked_names=linked,
        )
        self.assertTrue(plan["valid"])
        self.assertEqual(
            set(plan["add"]),
            {"tipo: mejora", "prioridad: media", "estado: en revisión"},
        )
        self.assertNotIn("estado: cerrado", plan["add"])

    def test_ambiguous_or_pull_request_link_does_not_inherit(self):
        catalog = catalog_for_language("en")
        linked_issue = {
            "state": "open",
            "labels": [
                {"name": "type: infrastructure"},
                {"name": "priority: high"},
            ],
        }
        self.assertIsNone(
            linked_issue_names({**linked_issue, "pull_request": {"url": "ignored"}})
        )
        self.assertIsNone(linked_issue_names({**linked_issue, "state": "draft"}))

        ambiguous = validation_plan(
            catalog,
            set(),
            is_pull_request=True,
            body="Closes #42\nResolves #43",
            linked_names=linked_issue_names(linked_issue),
        )
        self.assertIsNone(ambiguous["closing_issue"])
        self.assertFalse(ambiguous["valid"])
        self.assertEqual(set(ambiguous["add"]), {"status: in review"})
        self.assertEqual(ambiguous["missing"], ["type", "priority"])

    def test_incomplete_open_linked_issue_keeps_pr_invalid(self):
        catalog = catalog_for_language("es")

        missing_priority = validation_plan(
            catalog,
            set(),
            is_pull_request=True,
            body="Resolves #7",
            linked_names=linked_issue_names(
                {
                    "state": "open",
                    "labels": [{"name": "tipo: error"}],
                }
            ),
        )
        self.assertFalse(missing_priority["valid"])
        self.assertEqual(missing_priority["missing"], ["priority"])

        duplicate_type = validation_plan(
            catalog,
            set(),
            is_pull_request=True,
            body="Resolves #8",
            linked_names=linked_issue_names(
                {
                    "state": "open",
                    "labels": [
                        {"name": "tipo: error"},
                        {"name": "tipo: mejora"},
                        {"name": "prioridad: alta"},
                    ],
                }
            ),
        )
        self.assertFalse(duplicate_type["valid"])
        self.assertEqual(duplicate_type["missing"], ["type"])
        self.assertNotIn("tipo: error", duplicate_type["add"])
        self.assertNotIn("tipo: mejora", duplicate_type["add"])

    def test_warning_plan_is_idempotent_and_clears_when_valid(self):
        invalid = {"valid": False, "missing": ["priority"], "multiple": []}
        first = warning_plan(invalid, "en")
        second = warning_plan(invalid, "en")
        self.assertEqual(first, second)
        self.assertEqual(first["action"], "warn")
        self.assertTrue(first["body"].startswith("<!-- factory-label-validation -->"))
        self.assertIn("Incomplete classification", first["body"])

        cleared = warning_plan({"valid": True, "missing": [], "multiple": []}, "en")
        self.assertEqual(cleared["action"], "clear")
        self.assertNotIn("Incomplete", cleared["body"])

    def test_sweep_issue_plan_is_singleton_and_closes_at_zero(self):
        catalog = catalog_for_language("en")
        plan = sweep_issue_plan(catalog, [7, 3, 7], "en")
        self.assertEqual(plan["action"], "upsert")
        self.assertEqual(plan["title"], "[AUTO] Unlabeled items")
        self.assertEqual(
            set(plan["labels"]),
            {"type: infrastructure", "priority: medium", "status: available"},
        )
        self.assertLess(plan["body"].index("#3"), plan["body"].index("#7"))
        self.assertEqual(sweep_issue_plan(catalog, [], "en")["action"], "close")

        with self.assertRaises(LabelError):
            sweep_issue_plan(catalog, [True], "en")

    def test_low_level_loader_still_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(LabelError):
                load_catalog(Path("../bad.json"), root=root)


if __name__ == "__main__":
    unittest.main()
