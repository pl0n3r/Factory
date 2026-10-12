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


    def test_unexpected_staging_entry_fails_closed_without_recursive_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            original_mkdtemp = tempfile.mkdtemp
            stages = []

            def unexpected_file(*args, **kwargs):
                stage = Path(original_mkdtemp(*args, **kwargs))
                (stage / "unknown.txt").write_text("do-not-delete", encoding="utf-8")
                stages.append(stage)
                return str(stage)

            with patch("metricas.evaluar_agentes.tempfile.mkdtemp",
                       side_effect=unexpected_file):
                with self.assertRaises(OSError):
                    _write_artifact_pair(report(), directory)
            self.assertEqual(len(stages), 1)
            self.assertEqual(
                (stages[0] / "unknown.txt").read_text(encoding="utf-8"),
                "do-not-delete",
            )
            self.assertTrue(
                (directory / ".metricas-generation-incomplete").exists()
            )
            with self.assertRaises(OSError):
                _write_artifact_pair(report(), directory)

    def test_dangling_symlink_marker_does_not_escape_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "artifacts"
            directory.mkdir()
            outside = Path(tmp) / "untrusted_destination"
            (directory / ".metricas-generation-incomplete").symlink_to(outside)
            with self.assertRaises(OSError):
                _write_artifact_pair(report(), directory)
            self.assertFalse(outside.exists())
            self.assertTrue((directory / ".metricas-generation-incomplete").is_symlink())

    def test_simultaneous_writers_cannot_mix_output_generations(self):
        from threading import Event, Thread

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            started, resume = Event(), Event()
            failures = []
            original = os.replace
            first = report()
            first["period"] = "writer-one"
            second = report()
            second["period"] = "writer-two"

            def blocked_replace(source, destination):
                outcome = original(source, destination)
                if str(source).endswith("recomendaciones.json.next"):
                    started.set()
                    if not resume.wait(timeout=10):
                        raise OSError("timeout de fixture")
                return outcome

            def writer_one():
                try:
                    _write_artifact_pair(first, directory)
                except Exception as exc:
                    failures.append(exc)

            with patch("metricas.evaluar_agentes.os.replace",
                       side_effect=blocked_replace):
                thread = Thread(target=writer_one)
                thread.start()
                try:
                    self.assertTrue(started.wait(timeout=10))
                    with self.assertRaises(OSError):
                        _write_artifact_pair(second, directory)
                finally:
                    resume.set()
                    thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(json.loads((directory / "recomendaciones.json").read_text()),
                             first)
            self.assertEqual((directory / "dashboard.md").read_text(),
                             render_markdown(first) + "\n")
            self.assertFalse((directory / ".metricas-generation-incomplete").exists())


    def test_private_permissions_survive_success_and_rollback(self):
        import stat

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            names = ("recomendaciones.json", "dashboard.md")
            for name in names:
                target = output / name
                target.write_text("previous\n")
                target.chmod(0o600)
            old_umask = os.umask(0o022)
            try:
                _write_artifact_pair(report(), output)
                prior = {name: (output / name).read_bytes() for name in names}
                for name in names:
                    self.assertEqual(stat.S_IMODE((output / name).stat().st_mode),
                                     0o600)
                original = os.replace

                def fail_dashboard(source, destination):
                    if str(source).endswith("dashboard.md.next"):
                        raise OSError("fallo artificial")
                    return original(source, destination)

                with patch("metricas.evaluar_agentes.os.replace",
                           side_effect=fail_dashboard):
                    with self.assertRaises(OSError):
                        _write_artifact_pair(report(), output)
                for name in names:
                    self.assertEqual((output / name).read_bytes(), prior[name])
                    self.assertEqual(stat.S_IMODE((output / name).stat().st_mode),
                                     0o600)
            finally:
                os.umask(old_umask)

    def test_new_outputs_are_private_even_with_umask_022(self):
        import stat

        with tempfile.TemporaryDirectory() as tmp:
            old_umask = os.umask(0o022)
            try:
                output = Path(tmp)
                _write_artifact_pair(report(), output)
                for name in ("recomendaciones.json", "dashboard.md"):
                    self.assertEqual(stat.S_IMODE((output / name).stat().st_mode),
                                     0o600)
            finally:
                os.umask(old_umask)


    def test_report_paths_never_escape_named_artifacts(self):
        """Los valores del reporte no se convierten en nombres de archivo."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "artifacts"
            suspicious = report()
            suspicious["period"] = "../../escape"
            suspicious["../escape"] = {"../../other": "untrusted"}
            _write_artifact_pair(suspicious, destination)
            self.assertEqual(
                sorted(item.name for item in destination.iterdir()),
                ["dashboard.md", "recomendaciones.json"],
            )
            self.assertFalse((root / "escape").exists())
            self.assertFalse((root / "other").exists())
            self.assertEqual(
                json.loads((destination / "recomendaciones.json").read_text()),
                suspicious,
            )
