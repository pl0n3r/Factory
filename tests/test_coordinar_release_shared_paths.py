#!/usr/bin/env python3
"""Archivos de versión compartidos fuera de los claims exclusivos (#2163)."""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import scripts.coordinar_trabajo as coordinator
from scripts.coordinar_trabajo import CoordinationError, GitHub, reservation_marker
from tests.test_coordinar_trabajo import BOT, SESSION_A, FakeGitHub

ROOT = Path(__file__).resolve().parents[1]
SHARED = json.dumps(["config/version.php", "package.json"])
VERSION_PATCH = (
    "@@ -12,5 +12,5 @@\n"
    " declare(strict_types=1);\n"
    "-const BRVTAL_APP_VERSION = '0.1.262';\n"
    "-const BRVTAL_RELEASE_DATE = '2026-11-19';\n"
    "+const BRVTAL_APP_VERSION = '0.1.263';\n"
    "+const BRVTAL_RELEASE_DATE = '2026-11-20';\n"
)
PACKAGE_PATCH = (
    "@@ -1,4 +1,4 @@\n"
    " {\n"
    "   \"name\": \"brvtal\",\n"
    "-  \"version\": \"0.1.262\",\n"
    "+  \"version\": \"0.1.263\",\n"
)
EXTRA_LINE_PATCH = VERSION_PATCH + "+require_once __DIR__ . '/evil.php';\n"


def shared(value: str = SHARED):
    return patch.dict(os.environ, {coordinator.SHARED_VERSION_ENV: value})


def rows_api(rows_by_pr: dict[int, list[dict]]) -> GitHub:
    """GitHub real con request/pull simulados para leer el diff exact-HEAD."""
    api = GitHub("pl0n3r/brvtal", "fake-test-token")
    heads = {number: chr(ord("a") + number % 5) * 40 for number in rows_by_pr}

    def fake_pull(number):
        return {
            "state": "open",
            "changed_files": len(rows_by_pr[number]),
            "head": {"sha": heads[number], "ref": f"work/issue-{number}"},
            "base": {"sha": "f" * 40, "ref": "main"},
        }

    def fake_request(method, path, payload=None, allow=()):
        number = int(path.split("/pulls/")[1].split("/")[0])
        return rows_by_pr[number]

    patch.object(api, "pull", side_effect=fake_pull).start()
    patch.object(api, "request", side_effect=fake_request).start()
    return api


def row(name: str, patch_text: str | None, status: str = "modified") -> dict:
    entry = {"filename": name, "status": status}
    if patch_text is not None:
        entry["patch"] = patch_text
    return entry


class ReleaseSharedPathsTests(unittest.TestCase):
    def tearDown(self) -> None:
        patch.stopall()

    def claims_api(self, files, version_only):
        api = FakeGitHub()
        sha = "a" * 40
        api.branches["trabajo/issue-12"] = sha
        api.pulls[15] = {
            "number": 15, "state": "open",
            "body": f"Closes #12\n<!-- condor-reserva-id: {SESSION_A} -->",
            "head": {"ref": "trabajo/issue-12", "sha": sha,
                     "repo": {"full_name": api.repo}},
            "base": {"ref": "main", "sha": "b" * 40},
        }
        api.comments.append({
            "user": {"login": BOT},
            "body": reservation_marker(
                "pl0n3r", SESSION_A, "trabajo/issue-12", True, "tomar",
                "c" * 64, task_snapshot={
                    "task_marker_sha256": "d" * 64,
                    "task_paths": ["js/home.js"],
                    "task_depends_on": [],
                },
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        proof = {"complete": True, "head_sha": sha, "base_sha": "b" * 40,
                 "files": files}
        if version_only:
            proof["version_only_shared"] = version_only
        return api, proof

    def test_version_only_diff_passes_without_claim(self) -> None:
        with shared():
            api = rows_api({15: [
                row("js/home.js", "@@ -1 +1 @@\n-a\n+b\n"),
                row("config/version.php", VERSION_PATCH),
                row("package.json", PACKAGE_PATCH),
            ]})
            proof = api.pull_files_exact_head(15)
            self.assertEqual(proof["version_only_shared"],
                             ["config/version.php", "package.json"])
            patch.stopall()
            claims, _ = self.claims_api(proof["files"], proof["version_only_shared"])
            with patch.object(claims, "pull_files_exact_head",
                              return_value={**proof, "head_sha": "a" * 40,
                                            "base_sha": "b" * 40}, create=True):
                coordinator.validate_pr_claims(claims, 15)

    def test_non_version_change_or_missing_patch_requires_claim(self) -> None:
        self.assertFalse(coordinator.is_version_only_patch(EXTRA_LINE_PATCH))
        self.assertFalse(coordinator.is_version_only_patch(None))
        self.assertFalse(coordinator.is_version_only_patch(""))
        self.assertFalse(coordinator.is_version_only_patch(
            "@@ -1 +1,2 @@\n-const APP_VERSION = '1';\n+const APP_VERSION = '2';\n"
            "+const APP_VERSION = '3';\n"))
        with shared():
            api = rows_api({15: [
                row("config/version.php", EXTRA_LINE_PATCH),
                row("package.json", None),
                row("js/home.js", "@@ -1 +1 @@\n-a\n+b\n"),
            ]})
            proof = api.pull_files_exact_head(15)
            self.assertNotIn("version_only_shared", proof)
            patch.stopall()
            claims, _ = self.claims_api(proof["files"], [])
            with patch.object(claims, "pull_files_exact_head",
                              return_value={**proof, "head_sha": "a" * 40,
                                            "base_sha": "b" * 40}, create=True):
                with self.assertRaisesRegex(CoordinationError, "config/version.php"):
                    coordinator.validate_pr_claims(claims, 15)
        # Sin lista declarada, un diff solo de versión sigue exigiendo claim.
        claims, proof = self.claims_api(["js/home.js", "config/version.php"],
                                        ["config/version.php"])
        with patch.object(claims, "pull_files_exact_head", return_value=proof,
                          create=True):
            with self.assertRaisesRegex(CoordinationError, "config/version.php"):
                coordinator.validate_pr_claims(claims, 15)

    def collisions(self, left_patch: str, right_patch: str) -> list[str]:
        api = rows_api({
            42: [row("js/a.js", "@@ -1 +1 @@\n-a\n+b\n"),
                 row("config/version.php", left_patch)],
            43: [row("css/b.css", "@@ -1 +1 @@\n-a\n+b\n"),
                 row("config/version.php", right_patch)],
        })
        inventory = [{
            "number": n, "state": "open",
            "head": {"sha": api.pull(n)["head"]["sha"], "ref": f"work/issue-{n}"},
            "base": {"sha": "f" * 40, "ref": "main"},
        } for n in (42, 43)]
        patch.object(api, "open_pulls",
                     side_effect=[inventory, [dict(r) for r in inventory]]).start()
        return coordinator.collision_validation_errors(api, 42)

    def test_version_only_changes_do_not_collide(self) -> None:
        with shared():
            self.assertEqual(self.collisions(VERSION_PATCH, VERSION_PATCH), [])
        patch.stopall()
        with shared():
            errors = self.collisions(VERSION_PATCH, EXTRA_LINE_PATCH)
        self.assertEqual(len(errors), 1)
        self.assertIn("config/version.php", errors[0])
        patch.stopall()
        # Sin opt-in del consumidor, la colisión se mantiene.
        with patch.dict(os.environ, {coordinator.SHARED_VERSION_ENV: ""}):
            errors = self.collisions(VERSION_PATCH, VERSION_PATCH)
        self.assertEqual(len(errors), 1)
        self.assertIn("config/version.php", errors[0])

    def test_input_is_closed_and_defaults_to_current_behavior(self) -> None:
        self.assertEqual(coordinator.shared_version_paths(""), frozenset())
        self.assertEqual(coordinator.shared_version_paths("  "), frozenset())
        self.assertEqual(coordinator.shared_version_paths(SHARED),
                         frozenset({"config/version.php", "package.json"}))
        for bad in (
            "config/version.php", "{}", '["config/"]', '["config/*.php"]',
            '["./package.json"]', '["/etc/passwd"]', '["a/../b"]', '[1]',
            '["a","b","c","d","e"]', '["package.json","PACKAGE.json"]',
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(CoordinationError):
                    coordinator.shared_version_paths(bad)
        workflow = (ROOT / ".github/workflows/coordinacion.yml").read_text()
        self.assertIn("shared_version_paths:", workflow)
        self.assertIn("default: ''", workflow.split("shared_version_paths:")[1][:300])
        self.assertIn(
            "FACTORY_SHARED_VERSION_PATHS: ${{ inputs.shared_version_paths }}",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
