"""AC-01..04 del lint puro de claims de Issues de Factory #1107."""
from __future__ import annotations

import unittest

from scripts.validar_claims_issue import (
    MAX_INPUT_PATHS,
    MAX_PATHS_PER_LEAF,
    inspect_claim_paths,
)


class ValidarClaimsIssueTests(unittest.TestCase):
    def test_rejects_directory_globs_and_invalid_paths(self):
        samples = (
            (["src/"], "directory_claim"),
            (["docs/"], "directory_claim"),
            (["src/**"], "glob_claim"),
            (["*.py"], "glob_claim"),
            (["/root/a.py"], "invalid_path"),
            (["../secret.py"], "invalid_path"),
            (["src/../escape.py"], "invalid_path"),
            (["src//a.py"], "invalid_path"),
            (["src/./a.py"], "invalid_path"),
            (["a\\b.py"], "invalid_path"),
            (["src/a.py\n"], "invalid_path"),
            (["a.py", "a.py"], "duplicate_path"),
            (["src/Cache.php", "src/cache.php"], "duplicate_path"),
            (["README.md", "readme.md"], "duplicate_path"),
            (["src/report."], "invalid_path"),
            (["src/report", "src/report."], "invalid_path"),
            (["src/CON"], "invalid_path"),
            (["src/aux.txt"], "invalid_path"),
            (["src/COM1.log"], "invalid_path"),
            (["LPT9"], "invalid_path"),
            (["src/nul/config.json"], "invalid_path"),
        )
        for paths, code in samples:
            with self.subTest(paths=paths):
                report = inspect_claim_paths(paths)
                self.assertFalse(report["valid"])
                self.assertIn(code, report["reason_codes"])
                self.assertEqual(report["proposed_groups"], [])
                self.assertFalse(report["can_reserve"])
        self.assertTrue(inspect_claim_paths(["src/one.php", "src/two.php"])["valid"])
        both = inspect_claim_paths(["src/", "*.py"])
        self.assertEqual(both["reason_codes"], ["directory_claim", "glob_claim"])

    def test_shared_files_remain_real_collisions(self):
        paths = [
            "src/safe.py", "README.md", "config/version.php",
            "config/version.json",
            "package-lock.json", "internal/Makefile",
        ]
        report = inspect_claim_paths(paths)
        self.assertTrue(report["valid"])
        self.assertEqual(report["reason_codes"], [])
        self.assertEqual(report["shared_integration_paths"], [
            "README.md", "config/version.json", "config/version.php",
            "package-lock.json",
        ])
        self.assertFalse(report["can_reserve"])
        self.assertFalse(report["needs_partition"])
        for lock in ("bun.lock", "bun.lockb", "npm-shrinkwrap.json",
                     "apps/demo/bun.lock"):
            with self.subTest(lock=lock):
                self.assertEqual(inspect_claim_paths([lock])[
                    "shared_integration_paths"], [lock])
        self.assertIn("apps/alpha/config/version.json", inspect_claim_paths(
            ["apps/alpha/config/version.json"])["shared_integration_paths"])
        self.assertEqual(inspect_claim_paths(
            ["config/other.json"])["shared_integration_paths"], [])
        self.assertEqual(report["proposed_groups"], [])
        # A filename without an extension may be a file OR a directory;
        # this helper cannot assert reality or skip independent tree checks.
        self.assertTrue(inspect_claim_paths(["Dockerfile"])["valid"])
        self.assertFalse(inspect_claim_paths(["Dockerfile"])["can_reserve"])

    def test_excessive_claims_produce_advisory_partitions(self):
        paths = [f"src/module_{n:02d}.py" for n in range(14)]
        for sample in (paths, list(reversed(paths))):
            report = inspect_claim_paths(sample)
            self.assertFalse(report["valid"])
            self.assertEqual(report["reason_codes"], ["too_many_paths"])
            self.assertTrue(report["needs_partition"])
            self.assertFalse(report["can_reserve"])
            groups = report["proposed_groups"]
            self.assertEqual([len(group) for group in groups], [6, 6, 2])
            self.assertTrue(all(len(g) <= MAX_PATHS_PER_LEAF for g in groups))
            self.assertEqual([path for group in groups for path in group], sorted(paths))
        self.assertFalse(inspect_claim_paths(paths[:6])["needs_partition"])
        # A Win32-unsafe path can never be recommended in a new leaf.
        for unsafe in ("src/report.", "src/CON", "src/aux.txt"):
            report = inspect_claim_paths(paths[:6] + [unsafe])
            self.assertFalse(report["valid"])
            self.assertEqual(report["reason_codes"], ["invalid_path"])
            self.assertEqual(report["proposed_groups"], [])
            self.assertFalse(report["can_reserve"])
        portable = paths[:6] + ["src/report.txt"]
        self.assertEqual(inspect_claim_paths(portable)["reason_codes"],
                         ["too_many_paths"])
        # Alias in different would-be partitions must reject the entire plan.
        aliases = paths[:6] + ["src/MODULE_00.py"]
        result = inspect_claim_paths(aliases)
        self.assertEqual(result["reason_codes"], ["duplicate_path"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["proposed_groups"], [])

    def test_bounds_and_unknown_fail_closed(self):
        for payload in (None, {}, [], "src/a.py", [True], [None], [42],
                        [object()], ["x" * 241],
                        [f"src/f_{n}.py" for n in range(MAX_INPUT_PATHS + 1)]):
            with self.subTest(kind=type(payload).__name__):
                report = inspect_claim_paths(payload)
                self.assertFalse(report["valid"])
                self.assertFalse(report["can_reserve"])
                self.assertEqual(report["proposed_groups"], [])
                self.assertEqual(report["shared_integration_paths"], [])
                self.assertEqual(report["reason_codes"], ["invalid_input_size"]
                                 if type(payload) is not list or len(payload) == 0
                                 or len(payload) > MAX_INPUT_PATHS
                                 else ["invalid_path"])
        leaked = inspect_claim_paths(["private-mail@example.test", "src/"])
        self.assertFalse(leaked["valid"])
        self.assertNotIn("private-mail", repr(leaked))
        self.assertEqual(set(leaked), {
            "valid", "reason_codes", "needs_partition", "proposed_groups",
            "shared_integration_paths", "can_reserve",
        })


if __name__ == "__main__":
    unittest.main()
