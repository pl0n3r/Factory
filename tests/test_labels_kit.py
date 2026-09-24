#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.labels_kit import (
    LabelError,
    catalog_for_language,
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
        self.assertEqual(upsert_plan(self.catalog, existing), [])
        existing[0]["color"] = "FFFFFF"
        plan = upsert_plan(self.catalog, existing)
        self.assertEqual(plan[0]["action"], "update")
        self.assertEqual(plan[0]["name"], self.catalog[0]["name"])

    def test_sweep_reports_only_invalid_issues(self):
        valid = {
            "number": 1,
            "labels": [
                {"name": "tipo: mejora"},
                {"name": "prioridad: normal"},
                {"name": "estado: disponible"},
            ],
        }
        invalid = {"number": 2, "labels": [{"name": "tipo: mejora"}]}
        self.assertEqual(sweep(self.catalog, [json.dumps(valid), json.dumps(invalid)]), [2])

    def test_low_level_loader_still_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(LabelError):
                load_catalog(Path("../bad.json"), root=root)

if __name__ == "__main__":
    unittest.main()
