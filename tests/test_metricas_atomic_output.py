"""Fail-closed staged JSON/Markdown publishing for Factory #1198."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from metricas.evaluar_agentes import _write_artifact_pair, render_markdown


def write_report(data, directory):
    # Inject only a trusted test directory, never a CLI path.
    with patch("metricas.evaluar_agentes.DEFAULT_OUTPUT_DIR", directory):
        _write_artifact_pair(data)


def report():
    return {
        "records": 0, "min_samples": 3, "period": "all",
        "task_types": {}, "publication_allowed": False,
    }


class MetricAtomicOutputTests(unittest.TestCase):
    def test_second_output_failure_preserves_previous_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "recomendaciones.json").write_text("old-json\n")
            (root / "dashboard.md").write_text("old-md\n")
            original = os.replace

            def fail_second(source, destination):
                if Path(source).name == ".metricas-md-next":
                    raise OSError("synthetic second-publish failure")
                return original(source, destination)

            data = report()
            with patch("metricas.evaluar_agentes.os.replace",
                       side_effect=fail_second):
                with self.assertRaises(OSError):
                    write_report(data, root)
            self.assertEqual("old-json\n",
                             (root / "recomendaciones.json").read_text())
            self.assertEqual("old-md\n",
                             (root / "dashboard.md").read_text())
            self.assertEqual(
                sorted(p.name for p in root.iterdir()),
                ["dashboard.md", "recomendaciones.json"],
            )

    def test_successful_generation_updates_both(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_report(report(), root)
            self.assertEqual(report(), json.loads(
                (root / "recomendaciones.json").read_text(),
            ))
            self.assertEqual(render_markdown(report()) + "\n",
                             (root / "dashboard.md").read_text())
            self.assertFalse(json.loads(
                (root / "recomendaciones.json").read_text(),
            )["publication_allowed"])
            self.assertEqual(
                sorted(p.name for p in root.iterdir()),
                ["dashboard.md", "recomendaciones.json"],
            )

    def test_unrecoverable_rollback_blocks_new_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "recomendaciones.json").write_text("old-json\n")
            (root / "dashboard.md").write_text("old-md\n")
            original = os.replace

            def fail_second_and_rollback(source, destination):
                if Path(source).name in (
                    ".metricas-md-next", ".metricas-json-rollback",
                ):
                    raise OSError("synthetic publish/rollback failure")
                return original(source, destination)

            data = report()
            with patch("metricas.evaluar_agentes.os.replace",
                       side_effect=fail_second_and_rollback):
                with self.assertRaises(OSError):
                    write_report(data, root)
            self.assertTrue(
                (root / ".metricas-generation-incomplete").exists()
            )
            with self.assertRaises(OSError):
                write_report(data, root)

    def test_second_staging_failure_never_changes_published_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "recomendaciones.json").write_text("old-json\n")
            (root / "dashboard.md").write_text("old-md\n")
            from metricas.evaluar_agentes import _metric_private_stage

            def reject_markdown_stage(path, content, mode):
                if path.name == ".metricas-md-next":
                    raise OSError("synthetic staging failure")
                return _metric_private_stage(path, content, mode)

            data = report()
            with patch("metricas.evaluar_agentes._metric_private_stage",
                       side_effect=reject_markdown_stage):
                with self.assertRaises(OSError):
                    write_report(data, root)
            self.assertEqual("old-json\n",
                             (root / "recomendaciones.json").read_text())
            self.assertEqual("old-md\n",
                             (root / "dashboard.md").read_text())
            self.assertEqual(
                sorted(p.name for p in root.iterdir()),
                ["dashboard.md", "recomendaciones.json"],
            )

    def test_symlink_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "artifacts"
            root.mkdir()
            outside = Path(temp) / "outside"
            (root / "recomendaciones.json").symlink_to(outside)
            data = report()
            with self.assertRaises(OSError):
                write_report(data, root)
            self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
