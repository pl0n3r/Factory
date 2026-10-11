"""Regresión AC-04: publicar la pareja de métricas sin mezclar generaciones."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from metricas.evaluar_agentes import _write_artifact_pair, render_markdown


def report():
    return {
        "records": 0,
        "min_samples": 3,
        "period": "all",
        "task_types": {},
        "publication_allowed": False,
    }


class MetricAtomicOutputTests(unittest.TestCase):
    def test_second_output_failure_preserves_previous_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "recomendaciones.json").write_text("old-json\n")
            (directory / "dashboard.md").write_text("old-markdown\n")
            original = os.replace

            def broken_second(source, destination):
                if str(source).endswith("dashboard.md.next"):
                    raise OSError("fallo sintetico")
                return original(source, destination)

            with patch("metricas.evaluar_agentes.os.replace", side_effect=broken_second):
                with self.assertRaises(OSError):
                    _write_artifact_pair(report(), directory)
            self.assertEqual((directory / "recomendaciones.json").read_text(),
                             "old-json\n")
            self.assertEqual((directory / "dashboard.md").read_text(),
                             "old-markdown\n")
            self.assertEqual(sorted(path.name for path in directory.iterdir()),
                             ["dashboard.md", "recomendaciones.json"])

    def test_successful_generation_updates_json_and_markdown_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_artifact_pair(report(), directory)
            json_file = directory / "recomendaciones.json"
            markdown_file = directory / "dashboard.md"
            self.assertEqual(json.loads(json_file.read_text()), report())
            self.assertEqual(markdown_file.read_text(), render_markdown(report()) + "\n")
            self.assertFalse(json.loads(json_file.read_text())["publication_allowed"])
            self.assertEqual(sorted(path.name for path in directory.iterdir()),
                             ["dashboard.md", "recomendaciones.json"])
            old_json = json_file.read_bytes()
            old_md = markdown_file.read_bytes()
            _write_artifact_pair(report(), directory)
            self.assertEqual(json_file.read_bytes(), old_json)
            self.assertEqual(markdown_file.read_bytes(), old_md)

    def test_first_write_failure_and_cleanup_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "recomendaciones.json").write_text("old-json\n")
            (directory / "dashboard.md").write_text("old-markdown\n")
            original = Path.write_text

            def broken_first(path, content, **kwargs):
                if path.name == "recomendaciones.json.next":
                    raise OSError("fallo sintetico")
                return original(path, content, **kwargs)

            with patch.object(Path, "write_text", autospec=True,
                              side_effect=broken_first):
                with self.assertRaises(OSError):
                    _write_artifact_pair(report(), directory)
            self.assertEqual(sorted(path.name for path in directory.iterdir()),
                             ["dashboard.md", "recomendaciones.json"])
            self.assertEqual((directory / "recomendaciones.json").read_text(),
                             "old-json\n")
            self.assertEqual((directory / "dashboard.md").read_text(),
                             "old-markdown\n")
            original_replace = os.replace

            def failed_rollback(source, destination):
                if str(source).endswith(("dashboard.md.next",
                                        "recomendaciones.json.bak")):
                    raise OSError("fallo sintetico")
                return original_replace(source, destination)

            with patch("metricas.evaluar_agentes.os.replace",
                       side_effect=failed_rollback):
                with self.assertRaises(OSError):
                    _write_artifact_pair(report(), directory)
            self.assertTrue((directory / ".metricas-generation-incomplete").exists())
            with self.assertRaisesRegex(OSError, "incompleta"):
                _write_artifact_pair(report(), directory)
