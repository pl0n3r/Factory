#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

from scripts.labels_kit import (
    catalog_for_language,
    planned_state_decision,
    planned_state_migration_plan,
)

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

    def test_raw_planning_issue_without_execution_evidence_fails_closed(self):
        raw_issue = {
            "number": 42,
            "title": "Roadmap: siguiente tramo",
            "body": "<!-- factory-plan-epic {\"version\":1} -->",
            "labels": [
                {"name": "tipo: mejora"},
                {"name": "prioridad: media"},
                {"name": "estado: bloqueado"},
            ],
        }

        decision = planned_state_decision(raw_issue)
        self.assertFalse(decision["planned"])
        self.assertEqual(decision["reason"], "execution_evidence_incomplete")
        self.assertEqual(
            planned_state_migration_plan(catalog_for_language("es"), [raw_issue]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
