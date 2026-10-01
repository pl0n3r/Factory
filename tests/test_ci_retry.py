import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.ci_retry import OPERATIONS, operation_command, run, transient


class T(unittest.TestCase):
    def test_closed_operations_return_only_constant_argv(self):
        self.assertEqual(operation_command("npm-ci"), OPERATIONS["npm-ci"])
        self.assertEqual(operation_command("composer-install")[0], "composer")
        for malicious in (
            "bash",
            "../bash",
            "npm;bash",
            "npm-ci --ignore-scripts=false",
            "$(id)",
            "composer-install\nwhoami",
        ):
            with self.subTest(malicious=malicious):
                with self.assertRaises(ValueError):
                    operation_command(malicious)

    def test_operation_argv_is_immutable(self):
        command = operation_command("npm-ci")
        self.assertIsInstance(command, tuple)
        with self.assertRaises(TypeError):
            command[0] = "bash"  # type: ignore[index]

    def test_transient(self):
        self.assertTrue(transient(1, "HTTP 503"))
        self.assertFalse(transient(1, "certificate verify failed"))

    def test_run_covers_retry_exhaustion_and_non_transient_exit(self):
        with (
            patch(
                "scripts.ci_retry.subprocess.run",
                side_effect=[
                    SimpleNamespace(returncode=1, stdout="HTTP 503\n"),
                    SimpleNamespace(returncode=0, stdout="ok\n"),
                ],
            ) as process,
            patch("scripts.ci_retry.time.sleep") as sleep,
            patch.dict(
                "scripts.ci_retry.os.environ",
                {"ACTIONS_RUNTIME_TOKEN": "secret", "KEEP_ME": "yes"},
                clear=True,
            ),
        ):
            self.assertEqual(run("npm-ci", attempts=3, base_delay=0.25), 0)
        self.assertEqual(process.call_count, 2)
        self.assertEqual(sleep.call_args_list[0].args, (0.25,))
        self.assertNotIn("ACTIONS_RUNTIME_TOKEN", process.call_args.kwargs["env"])
        self.assertEqual(process.call_args.kwargs["env"]["KEEP_ME"], "yes")

        with (
            patch(
                "scripts.ci_retry.subprocess.run",
                side_effect=[
                    SimpleNamespace(returncode=75, stdout="timeout"),
                    SimpleNamespace(returncode=75, stdout="timeout"),
                ],
            ) as process,
            patch("scripts.ci_retry.time.sleep") as sleep,
        ):
            self.assertEqual(run("composer-audit", attempts=2, base_delay=1), 75)
        self.assertEqual(process.call_count, 2)
        sleep.assert_called_once_with(1)

        with (
            patch(
                "scripts.ci_retry.subprocess.run",
                return_value=SimpleNamespace(
                    returncode=2,
                    stdout="certificate verify failed",
                ),
            ) as process,
            patch("scripts.ci_retry.time.sleep") as sleep,
        ):
            self.assertEqual(run("npm-audit", attempts=5, base_delay=1), 2)
        process.assert_called_once()
        sleep.assert_not_called()

        for attempts, delay in ((0, 1), (6, 1), (1, -1), (1, 31)):
            with self.subTest(attempts=attempts, delay=delay):
                with self.assertRaises(ValueError):
                    run("npm-ci", attempts=attempts, base_delay=delay)
