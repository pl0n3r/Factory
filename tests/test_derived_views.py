"""Pruebas del contrato común de vistas derivadas."""

import json
import unittest
from pathlib import Path

from intelligence.derived_views import (
    DerivedViewDriftError,
    DerivedViewSpec,
    check_drift,
    render_markdown_table,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "derived_views.json"


class DerivedViewsTests(unittest.TestCase):
    def test_manifest_declares_canonical_source_and_views(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertTrue(payload["views"])

        spec = DerivedViewSpec(**payload["views"][0])
        spec.validate()
        self.assertEqual(spec.view_id, "factory.readme.tandas")
        self.assertIn("PLAN-AGENTES.md", spec.source)
        self.assertEqual(spec.view, "README.md#estado-de-las-tandas")
        self.assertEqual(spec.mode, "regression")

    def test_generation_is_deterministic(self):
        rows_a = [
            {"id": "b", "state": "blocked"},
            {"id": "a", "state": "complete"},
        ]
        rows_b = list(reversed(rows_a))
        expected = render_markdown_table(rows_a, ("id", "state"), sort_by="id")
        self.assertEqual(
            expected,
            render_markdown_table(rows_b, ("id", "state"), sort_by="id"),
        )

    def test_drift_fails_closed(self):
        expected = render_markdown_table(
            [{"id": "a", "state": "complete"}],
            ("id", "state"),
            sort_by="id",
        )
        with self.assertRaises(DerivedViewDriftError):
            check_drift(expected, expected + "drift")

    def test_manifest_rejects_self_referential_source(self):
        with self.assertRaises(ValueError):
            DerivedViewSpec(
                view_id="bad",
                source="README.md",
                view="README.md",
                mode="regression",
                generator=None,
                drift_check="tests/test_derived_views.py",
            ).validate()


if __name__ == "__main__":
    unittest.main()
