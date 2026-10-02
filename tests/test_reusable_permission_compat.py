import ast
import inspect
import unittest

from scripts import reusable_permission_compat as compat


class ReusablePermissionCompatTests(unittest.TestCase):
    def test_permission_lattice_is_closed_and_ordered(self):
        self.assertEqual(
            compat.LEVEL_RANK,
            {"none": 0, "read": 1, "write": 2},
        )
        self.assertTrue(
            compat.compare_permissions(
                {"contents": "read"},
                {"contents": "write"},
            )["compatible"]
        )
        self.assertFalse(
            compat.compare_permissions(
                {"contents": "write"},
                {"contents": "read"},
            )["compatible"]
        )
        unknown_scope = compat.compare_permissions(
            {"not-a-github-scope": "read"},
            {"contents": "write"},
        )
        invalid_level = compat.compare_permissions(
            {"contents": "admin"},
            {"contents": "write"},
        )
        self.assertEqual(unknown_scope["reason"], "invalid_contract")
        self.assertEqual(invalid_level["reason"], "invalid_contract")
        self.assertFalse(unknown_scope["compatible"])
        self.assertFalse(invalid_level["compatible"])

    def test_reusable_envelope_must_fit_inside_caller_envelope(self):
        result = compat.compare_permissions(
            {"actions": "read", "pull-requests": "write"},
            {"pull-requests": "read", "contents": "read"},
        )
        self.assertFalse(result["compatible"])
        self.assertEqual(result["reason"], "insufficient_permissions")
        self.assertEqual(
            result["missing"],
            [
                {"scope": "actions", "required": "read", "granted": "none"},
                {
                    "scope": "pull-requests",
                    "required": "write",
                    "granted": "read",
                },
            ],
        )

    def test_incident_860_permission_regressions_are_detected(self):
        actions_gap = compat.compare_permissions(
            {"actions": "read"},
            {"contents": "write", "issues": "write", "pull-requests": "write"},
        )
        pr_gap = compat.compare_permissions(
            {"pull-requests": "write"},
            {"pull-requests": "read"},
        )
        self.assertEqual(
            actions_gap["missing"],
            [{"scope": "actions", "required": "read", "granted": "none"}],
        )
        self.assertEqual(
            pr_gap["missing"],
            [
                {
                    "scope": "pull-requests",
                    "required": "write",
                    "granted": "read",
                }
            ],
        )

    def test_all_callers_must_be_compatible_without_majority_shortcut(self):
        result = compat.compare_callers(
            {"contents": "read", "pull-requests": "write"},
            {
                "condor": {"contents": "read", "pull-requests": "write"},
                "controlbot": {"contents": "write", "pull-requests": "write"},
                "legacy": {"contents": "read", "pull-requests": "read"},
            },
        )
        self.assertFalse(result["compatible"])
        self.assertEqual(result["reason"], "caller_incompatible")
        failures = [entry for entry in result["callers"] if not entry["compatible"]]
        self.assertEqual([entry["caller"] for entry in failures], ["legacy"])

    def test_contract_is_pure_deterministic_and_fail_closed(self):
        required = {"issues": "write", "contents": "read"}
        callers = {
            "b": {"issues": "write", "contents": "read"},
            "a": {"issues": "read", "contents": "read"},
        }
        first = compat.compare_callers(required, callers)
        second = compat.compare_callers(required, callers)
        self.assertEqual(first, second)
        self.assertFalse(
            compat.compare_callers(required, {})["compatible"]
        )

        tree = ast.parse(inspect.getsource(compat))
        imported_roots = set()
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)

        self.assertTrue({"collections", "typing"}.issubset(imported_roots))
        self.assertTrue(
            imported_roots.isdisjoint(
                {"requests", "urllib", "socket", "subprocess", "os", "pathlib"}
            )
        )
        self.assertNotIn("open", calls)


if __name__ == "__main__":
    unittest.main()
