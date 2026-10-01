import os
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
        self.assertTrue(transient(75, ""))
        self.assertTrue(transient(1, "connection reset by peer"))
        self.assertFalse(transient(1, "certificate verify failed"))

    def test_run_covers_retry_exhaustion_and_non_transient_exit(self):
        transient_failure = SimpleNamespace(returncode=75, stdout="timeout\n")
        success = SimpleNamespace(returncode=0, stdout="ok")
        with patch.dict(os.environ, {"ACTIONS_CACHE_URL": "secret-cache", "KEEP_ME": "yes"}):
            with patch("scripts.ci_retry.subprocess.run", side_effect=[transient_failure, success]) as execute:
                with patch("scripts.ci_retry.time.sleep") as sleep:
                    self.assertEqual(run("npm-ci", 3, 0.25), 0)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(execute.call_args.kwargs["env"].get("KEEP_ME"), "yes")
        self.assertNotIn("ACTIONS_CACHE_URL", execute.call_args.kwargs["env"])
        sleep.assert_called_once_with(0.25)

        with patch("scripts.ci_retry.subprocess.run", return_value=transient_failure):
            with patch("scripts.ci_retry.time.sleep") as sleep:
                self.assertEqual(run("composer-audit", 2, 1), 75)
        sleep.assert_called_once_with(1)

        permanent_failure = SimpleNamespace(returncode=2, stdout="certificate verify failed")
        with patch("scripts.ci_retry.subprocess.run", return_value=permanent_failure) as execute:
            with patch("scripts.ci_retry.time.sleep") as sleep:
                self.assertEqual(run("npm-audit", 5, 2), 2)
        execute.assert_called_once()
        sleep.assert_not_called()

        for attempts, delay in ((0, 1), (6, 1), (1, -1), (1, 31)):
            with self.subTest(attempts=attempts, delay=delay):
                with self.assertRaises(ValueError):
                    run("npm-ci", attempts, delay)
