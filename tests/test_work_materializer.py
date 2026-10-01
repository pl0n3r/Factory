#!/usr/bin/env python3
import unittest
from scripts.aceptacion_kit import parse_contract
from scripts.work_inventory import detect_unmaterialized_executable_work, remaining_work_summary
from scripts.work_materializer import MaterializationError, materialize_detected_work, materialize_leaf


def item(classification="leaf_ready", key="roadmap-item"):
    return {
        "source_key": key, "classification": classification, "title": "Leaf verificable",
        "objective": "Entregar una unidad ejecutable.", "scope": "Solo contrato puro.",
        "out_of_scope": "Live, gasto y datos reales.", "evidence_ref": "roadmap:1",
        "parent_ref": "Factory#701", "priority": "alta",
        "roles": ["ingenieria-software", "qa"], "dependencies": [],
        "acceptance": [{"kind": "test",
                        "target": "tests/test_work_materializer.py::WorkMaterializerTests::test_leaf_requires_complete_executable_contract",
                        "description": "El leaf conserva contrato ejecutable."}],
    }


class WorkMaterializerTests(unittest.TestCase):
    def test_leaf_requires_complete_executable_contract(self):
        result = materialize_leaf(item())
        self.assertEqual(result["action"], "created")
        self.assertEqual(result["leaf"]["status"], "available")
        self.assertEqual(len(parse_contract(result["leaf"]["body"])), 1)
        broken = item(); broken["roles"] = []
        with self.assertRaises(MaterializationError):
            materialize_leaf(broken)

    def test_materialization_is_idempotent(self):
        first = materialize_leaf(item())
        second = materialize_leaf(item(), [first["leaf"]])
        self.assertEqual(second["action"], "reused")
        self.assertEqual(second["leaf"]["source_key"], "roadmap-item")

    def test_future_decision_and_live_gated_work_stays_fail_closed(self):
        for classification in ("future_idea", "decision_required", "live_only"):
            with self.subTest(classification=classification):
                result = materialize_leaf(item(classification=classification))
                self.assertEqual(result["action"], "deferred")
                self.assertNotIn("leaf", result)

    def test_e2e_hidden_roadmap_work_becomes_valid_ready_leaf(self):
        hidden_item = item(key="hidden-roadmap-work")
        hidden = detect_unmaterialized_executable_work(
            [{"source_key": hidden_item["source_key"], "classification": "leaf_ready",
              "evidence_ref": hidden_item["evidence_ref"]}], []
        )
        self.assertEqual(len(hidden), 1)
        created = materialize_detected_work([hidden_item])[0]["leaf"]
        summary = remaining_work_summary("pl0n3r/Factory", [created], [])
        self.assertEqual(summary["state"], "READY")
        self.assertEqual(summary["next_work"], "hidden-roadmap-work")


if __name__ == "__main__":
    unittest.main()
