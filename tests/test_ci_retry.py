import unittest

from scripts.ci_retry import OPERATIONS, operation_command, transient


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
