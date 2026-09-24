#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class LabelCatalogTests(unittest.TestCase):
    def load(self, language: str):
        return json.loads((ROOT / "labels" / f"{language}.json").read_text(encoding="utf-8"))

    def test_catalogs_have_same_semantic_keys_and_colors(self):
        es = {item["key"]: item for item in self.load("es")}
        en = {item["key"]: item for item in self.load("en")}
        self.assertEqual(set(es), set(en))
        self.assertEqual(len(es), len(self.load("es")))
        self.assertEqual(len(en), len(self.load("en")))
        for key in es:
            self.assertEqual(es[key]["color"], en[key]["color"])
            self.assertTrue(es[key]["name"])
            self.assertTrue(en[key]["name"])

    def test_required_dimensions_exist(self):
        keys = {item["key"] for item in self.load("es")}
        for prefix in ("type_", "priority_", "state_"):
            self.assertTrue(any(key.startswith(prefix) for key in keys))
        for key in ("priority_critical", "state_available", "state_reserved", "state_review", "state_completed"):
            self.assertIn(key, keys)

if __name__ == "__main__":
    unittest.main()
