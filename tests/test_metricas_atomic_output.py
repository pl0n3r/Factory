"""Fail-closed JSON/Markdown pair publishing for Factory #1198."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from metricas.evaluar_agentes import _write_artifact_pair, render_markdown


def write_report(data, directory):
    # Explicit test-only injection of the trusted root, never a CLI argument.
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
            original = Path.write_text

            def fail_second(path, content, **kwargs):
                if path.name == "dashboard.md":
                    raise OSError("synthetic write failure")
                return original(path, content, **kwargs)

            with patch.object(Path, "write_text", autospec=True,
                              side_effect=fail_second):
                with self.assertRaises(OSError):
                    write_report(report(), root)
            self.assertEqual("old-json\n",
                             (root / "recomendaciones.json").read_text())
            self.assertEqual("old-md\n", (root / "dashboard.md").read_text())
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
            original_write = Path.write_text
            original_bytes = Path.write_bytes

            def fail_second(path, content, **kwargs):
                if path.name == "dashboard.md":
                    raise OSError("synthetic second-write failure")
                return original_write(path, content, **kwargs)

            def fail_restore(path, content):
                if path.name == "recomendaciones.json":
                    raise OSError("synthetic rollback failure")
                return original_bytes(path, content)

            with patch.object(Path, "write_text", autospec=True,
                              side_effect=fail_second), patch.object(
                Path, "write_bytes", autospec=True, side_effect=fail_restore
            ):
                with self.assertRaises(OSError):
                    write_report(report(), root)
            self.assertTrue(
                (root / ".metricas-generation-incomplete").exists()
            )
            with self.assertRaises(OSError):
                write_report(report(), root)

    def test_symlink_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "artifacts"
            root.mkdir()
            outside = Path(temp) / "outside"
            (root / "recomendaciones.json").symlink_to(outside)
            with self.assertRaises(OSError):
                write_report(report(), root)
            self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
