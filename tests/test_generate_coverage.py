import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_coverage",
    ROOT / "scripts" / "generate_coverage.py",
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("No fue posible cargar generate_coverage.py")
GENERATE_COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATE_COVERAGE)


class GenerateCoverageTests(unittest.TestCase):
    def test_generator_declares_all_canonical_suites_and_python_xml(self):
        self.assertEqual(
            GENERATE_COVERAGE.SUITES,
            (
                ("tests", None),
                ("metricas", "metricas"),
                ("seguridad", "seguridad"),
                ("lecciones", "lecciones"),
                ("producto", "producto"),
            ),
        )
        self.assertEqual(
            GENERATE_COVERAGE.PYTHON_XML.relative_to(ROOT).as_posix(),
            "build/coverage/python.xml",
        )
        for directory, _ in GENERATE_COVERAGE.SUITES:
            self.assertTrue((ROOT / directory).is_dir(), directory)

    def test_generator_combines_parallel_coverage_and_omits_tests(self):
        calls = []
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            original_build = GENERATE_COVERAGE.BUILD
            original_xml = GENERATE_COVERAGE.PYTHON_XML
            GENERATE_COVERAGE.BUILD = Path(tmp)
            GENERATE_COVERAGE.PYTHON_XML = Path(tmp) / "python.xml"

            def fake_run(command, *, env=None):
                calls.append((list(command), dict(env or {})))
                if "xml" in command:
                    GENERATE_COVERAGE.PYTHON_XML.write_text(
                        "<coverage version=\"7.16.2\"/>\n",
                        encoding="utf-8",
                    )

            try:
                with mock.patch.object(GENERATE_COVERAGE, "run", side_effect=fake_run):
                    self.assertEqual(GENERATE_COVERAGE.main(), 0)
            finally:
                GENERATE_COVERAGE.BUILD = original_build
                GENERATE_COVERAGE.PYTHON_XML = original_xml

        run_calls = [command for command, _ in calls if "run" in command]
        self.assertEqual(len(run_calls), len(GENERATE_COVERAGE.SUITES))
        for command in run_calls:
            self.assertIn("--source=.", command)
            self.assertIn("--branch", command)
            self.assertIn("--parallel-mode", command)
            self.assertIn("unittest", command)

        commands = [command for command, _ in calls]
        self.assertIn(
            [GENERATE_COVERAGE.sys.executable, "-m", "coverage", "combine"],
            commands,
        )
        xml = next(command for command in commands if "xml" in command)
        self.assertIn("--omit=tests/*,*/test_*.py", xml)

        for directory, path_entry in GENERATE_COVERAGE.SUITES:
            if path_entry is None:
                continue
            matching = [
                env
                for command, env in calls
                if "run" in command and directory in command
            ]
            self.assertEqual(len(matching), 1)
            self.assertTrue(
                matching[0]["PYTHONPATH"].split(os.pathsep)[0].endswith(path_entry)
            )


if __name__ == "__main__":
    unittest.main()
