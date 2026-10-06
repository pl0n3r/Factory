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

    def test_planned_state_exists_in_both_catalogs_with_same_semantic_key_and_color(self):
        es = {item["key"]: item for item in self.load("es")}
        en = {item["key"]: item for item in self.load("en")}

        self.assertIn("state_planned", es)
        self.assertIn("state_planned", en)
        self.assertEqual(es["state_planned"]["color"], en["state_planned"]["color"])
        self.assertEqual(es["state_planned"]["name"], "estado: planificado")
        self.assertEqual(en["state_planned"]["name"], "status: planned")
        self.assertIn("no cuenta como bloqueo", es["state_planned"]["description"])
        self.assertIn("does not count as blocked", en["state_planned"]["description"])

if __name__ == "__main__":
    unittest.main()
