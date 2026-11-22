#!/usr/bin/env python3
"""Synthetic Git-only regression tests for Factory #2178."""
from __future__ import annotations

import io
import json
import sys
from urllib.error import HTTPError
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import version_autorebase as mod
from scripts.coordinar_trabajo import CoordinationError, shared_version_paths

ROOT = Path(__file__).resolve().parents[1]
SHARED = frozenset({"config/version.php", "package.json"})


def git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, text=True,
                       capture_output=True, timeout=30, check=False)
    if r.returncode:
        raise AssertionError("git " + " ".join(args) + ": " + r.stderr)
    return r.stdout.strip()


def write_files(repo, value, app="base", extra_php=False):
    (repo / "config").mkdir(exist_ok=True)
    (repo / "config/version.php").write_text(
        "<?php\nconst APP_VERSION = '" + value + "';\n"
        + ("require_once 'new-code.php';\n" if extra_php else ""), encoding="utf-8")
    (repo / "package.json").write_text(
        '{\n  "name": "test",\n  "version": "' + value + '"\n}\n', encoding="utf-8")
    (repo / "app.txt").write_text(app + "\n", encoding="utf-8")


class FakeGitHub:
    repo = "pl0n3r/brvtal"

    def __init__(self, remote, branches):
        self.remote = remote
        self.branches = branches
        self.comments_seen = {}

    def get_ref(self, branch="main"):
        return git(self.remote, "rev-parse", "refs/heads/" + branch)

    def running(self):
        return True

    def pulls(self):
        return [{"number": number, "created_at": "2026-11-22T%02d:00:00Z" % number}
                for number in self.branches]

    def pull(self, number):
        name = self.branches[number]
        head, main = self.get_ref(name), self.get_ref("main")
        dirty = subprocess.run(["git", "merge-base", "--is-ancestor", main, head],
                               cwd=self.remote, capture_output=True).returncode != 0
        return {
            "state": "open", "draft": False,
            "mergeable_state": "dirty" if dirty else "clean",
            "mergeable": not dirty,
            "head": {"sha": head, "ref": name, "repo": {"full_name": self.repo}},
            "base": {"sha": main, "ref": "main", "repo": {"full_name": self.repo}},
        }

    def comments(self, number):
        return self.comments_seen.get(number, [])

    def comment_once(self, number, marker, body):
        existing = self.comments(number)
        if not any(marker in item["body"] for item in existing):
            self.comments_seen.setdefault(number, []).append({
                "body": marker + "\n\n" + body,
                "user": {"login": "github-actions[bot]"},
            })


class VersionAutorebaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory-2178-git-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote, self.repo = root / "origin.git", root / "work"
        subprocess.run(["git", "init", "--bare", "--initial-branch=main",
                        str(self.remote)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(self.remote), str(self.repo)],
                       check=True, capture_output=True)
        git(self.repo, "config", "user.name", "QA Synthetic")
        git(self.repo, "config", "user.email", "qa@example.test")
        write_files(self.repo, "0.1.1")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "push", "origin", "HEAD:refs/heads/main")

    def make_pr(self, branch, app="base", extra_php=False):
        git(self.repo, "checkout", "-B", branch, self.base)
        write_files(self.repo, "0.1.3", app, extra_php)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "PR candidate")
        git(self.repo, "push", "origin", "HEAD:refs/heads/" + branch)

    def move_main(self, app="base"):
        git(self.repo, "checkout", "-B", "main", self.base)
        write_files(self.repo, "0.1.2", app)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "other PR merged")
        git(self.repo, "push", "origin", "HEAD:refs/heads/main")

    def show(self, branch, path):
        return git(self.remote, "show", "refs/heads/" + branch + ":" + path)

    def test_version_only_conflict_resolved_serially(self):
        self.make_pr("trabajo/issue-41", app="first")
        self.make_pr("work/issue-42", app="second")
        self.move_main()
        api = FakeGitHub(self.remote,
                         {41: "trabajo/issue-41", 42: "work/issue-42"})
        calls = []
        original_git = mod.git

        def capture(repo, *args, **kwargs):
            calls.append(args)
            return original_git(repo, *args, **kwargs)

        with patch.object(mod, "git", side_effect=capture):
            result = mod.reconcile(api, self.repo, SHARED, "synthetic-run")
        self.assertEqual(result, {"updated": 2, "skipped": 0, "unresolved": 0})
        for number, branch, ver in (
            (41, "trabajo/issue-41", (0, 1, 3)),
            (42, "work/issue-42", (0, 1, 4)),
        ):
            self.assertEqual(mod.version(self.show(branch, "package.json")), ver)
            self.assertEqual(mod.version(self.show(branch, "config/version.php")), ver)
            self.assertEqual(len(api.comments(number)), 1)
            self.assertIn("push sin force", api.comments(number)[0]["body"])
        self.assertEqual(self.show("trabajo/issue-41", "app.txt"), "first")
        self.assertEqual(self.show("work/issue-42", "app.txt"), "second")
        self.assertFalse(any(args[0] == "push" and
                             set(args).intersection({"-f", "--force", "--force-with-lease"})
                             for args in calls))
        # The same HEAD/main must be a complete idempotent no-op.
        second = mod.reconcile(api, self.repo, SHARED, "synthetic-run")
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unresolved"], 0)
        self.assertEqual(len(api.comments(41)), 1)
        self.assertEqual(len(api.comments(42)), 1)

    def test_conflict_same_file_other_line_is_not_touched(self):
        self.make_pr("trabajo/issue-41", extra_php=True)
        self.move_main()
        api = FakeGitHub(self.remote, {41: "trabajo/issue-41"})
        original = api.get_ref("trabajo/issue-41")
        result = mod.reconcile(api, self.repo, SHARED, "synthetic-run")
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(api.get_ref("trabajo/issue-41"), original)
        self.assertIn("config/version.php", api.comments(41)[0]["body"])
        mod.reconcile(api, self.repo, SHARED, "synthetic-run")
        self.assertEqual(len(api.comments(41)), 1)

    def test_conflict_elsewhere_is_not_touched(self):
        self.make_pr("trabajo/issue-41", app="branch")
        self.move_main(app="main")
        api = FakeGitHub(self.remote, {41: "trabajo/issue-41"})
        original = api.get_ref("trabajo/issue-41")
        result = mod.reconcile(api, self.repo, SHARED, "synthetic-run")
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(api.get_ref("trabajo/issue-41"), original)
        self.assertIn("app.txt", api.comments(41)[0]["body"])

    def test_drafts_and_noncoordinated_branches_ignored(self):
        self.make_pr("work/issue-41")
        self.move_main()
        api = FakeGitHub(self.remote, {41: "work/issue-41"})
        real = api.pull
        for changed in ({"draft": True},
                        {"head": {"sha": "a" * 40, "ref": "feature/abc",
                                  "repo": {"full_name": api.repo}}},
                        {"head": {"sha": "a" * 40, "ref": "work/issue-41",
                                  "repo": {"full_name": "foreign/fork"}}}):
            with patch.object(api, "pull", side_effect=lambda n, ch=changed:
                              {**real(n), **ch}):
                self.assertEqual(mod.reconcile(api, self.repo, SHARED,
                                                "synthetic-run")["updated"], 0)

    def test_markdown_derived_version_line_and_hook(self):
        from scripts.coordinar_trabajo import is_version_only_patch

        old_line = "- Proyecto `pl0n3r/brvtal`, versión declarada `0.1.1`."
        new_line = "- Proyecto `pl0n3r/brvtal`, versión declarada `0.1.3`."
        patch_text = "@@ -1 +1 @@\n-" + old_line + "\n+" + new_line + "\n"
        self.assertTrue(is_version_only_patch(patch_text))
        self.assertFalse(is_version_only_patch(
            patch_text + "+texto sin vínculo con versión\n"))
        self.assertFalse(is_version_only_patch(
            "@@ -1 +1 @@\n- Proyecto `otro`, versión declarada `0.1.1`.\n"
            "+ Proyecto `otro`, versión declarada `0.1.3`.\n"))
        self.assertEqual(mod.version(old_line), (0, 1, 1))
        self.assertEqual(mod.replace_version(old_line, (0, 1, 300)),
                         old_line.replace("0.1.1", "0.1.300"))

        # Only trusted main may define the post-bump script.  It deliberately
        # rewrites just the derived version line, never legal source documents.
        git(self.repo, "checkout", "-B", "main", self.base)
        index = self.repo / "revision-juridica" / "00-LEEME.md"
        index.parent.mkdir(exist_ok=True)
        index.write_text(old_line + "\n", encoding="utf-8")
        scripts = self.repo / "scripts"
        scripts.mkdir(exist_ok=True)
        hook = scripts / "regenerate_index.py"
        hook.write_text(
            "import os, re\n"
            "from pathlib import Path\n"
            "path = Path('revision-juridica/00-LEEME.md')\n"
            "body = path.read_text(encoding='utf-8')\n"
            "v = os.environ['FACTORY_TARGET_VERSION']\n"
            "body = re.sub(r'versión declarada `[0-9]+\\.[0-9]+\\.[0-9]+`', "
            "lambda _: 'versión declarada `' + v + '`', body)\n"
            "path.write_text(body, encoding='utf-8')\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "trust minimal index regeneration")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "push", "origin", "HEAD:refs/heads/main")
        self.make_pr("trabajo/issue-41")
        self.move_main()
        api = FakeGitHub(self.remote, {41: "trabajo/issue-41"})
        allowed = SHARED | frozenset({"revision-juridica/00-LEEME.md"})
        outcome = mod.reconcile(
            api, self.repo, allowed, "synthetic-run",
            post_bump_command="python3 scripts/regenerate_index.py",
        )
        self.assertEqual(outcome["updated"], 1)
        self.assertEqual(
            self.show("trabajo/issue-41", "revision-juridica/00-LEEME.md").strip(),
            new_line,
        )
        self.assertEqual(
            mod.version(self.show("trabajo/issue-41", "package.json")),
            (0, 1, 3),
        )
        self.assertEqual(len(api.comments(41)), 1)
        with self.assertRaises(mod.RebaseError):
            mod._safe_script("python3 -c 'print(1)'", self.repo)
        with self.assertRaises(mod.RebaseError):
            mod._safe_script("bash scripts/regenerate_index.py", self.repo)

    def test_api_transport_live_guards_and_idempotent_comment(self):
        """A fake GitHub API covers malformed identity and safe POST behavior."""
        marker = ('<!-- factory-unattended-kill-switch '
                  '{"version":1,"state":"RUNNING","owner":"pl0n3r"} -->')
        tracked = {"posts": 0, "kill": marker}

        def urlopen_stub(request, timeout):
            path = request.full_url.split("https://api.github.com", 1)[1]
            if path.startswith("/repos/pl0n3r/Factory/issues/767"):
                result = {
                    "state": "closed", "user": {"login": "pl0n3r"},
                    "body": tracked["kill"],
                }
            elif "/git/ref/heads/" in path:
                result = {"object": {"sha": "f" * 40}}
            elif "/pulls?" in path:
                result = [
                    {"number": 7, "created_at": "2026-11-22T10:00:00Z"},
                    {"number": 6, "created_at": "2026-11-22T09:00:00Z"},
                ]
            elif "/pulls/7" in path:
                result = {"number": 7, "head": {"ref": "work/issue-7"}}
            elif "/issues/7/comments?" in path:
                result = [{
                    "body": "<!-- known-result -->",
                    "user": {"login": "github-actions[bot]"},
                }]
            elif "/issues/7/comments" in path and request.get_method() == "POST":
                tracked["posts"] += 1
                result = {"id": tracked["posts"]}
            else:
                raise AssertionError("Unexpected mock path: " + path)
            return io.BytesIO(json.dumps(result).encode("utf-8"))

        with self.assertRaises(mod.RebaseError):
            mod.GitHub("invalid /repo", "token")
        with self.assertRaises(mod.RebaseError):
            mod.GitHub("owner/repo", "")
        api = mod.GitHub("pl0n3r/brvtal", "fake")
        with self.assertRaises(mod.RebaseError):
            api.request("GET", "//other")
        with patch.object(mod, "urlopen", side_effect=urlopen_stub):
            self.assertTrue(api.running())
            self.assertEqual(api.get_ref(), "f" * 40)
            self.assertEqual([pr["number"] for pr in api.pulls()], [6, 7])
            self.assertEqual(api.pull(7)["number"], 7)
            self.assertEqual(len(api.comments(7)), 1)
            api.comment_once(7, "<!-- known-result -->", "Already posted")
            self.assertEqual(tracked["posts"], 0)
            api.comment_once(7, "<!-- new-result -->", "Version reconciled")
            self.assertEqual(tracked["posts"], 1)
            tracked["kill"] = marker.replace('"RUNNING"', '"PAUSED"')
            self.assertFalse(api.running())
            tracked["kill"] = marker + "\n" + marker
            self.assertFalse(api.running())
        with patch.object(mod, "urlopen", side_effect=HTTPError(
                "https://api.github.com", 403, "Forbidden", {}, None)):
            with self.assertRaises(mod.RebaseError):
                api.get_ref()
        first = mod.comment_marker(
            "result", 7, "a" * 40, "b" * 40,
            ["package.json", "config/version.php"],
        )
        reordered = mod.comment_marker(
            "result", 7, "a" * 40, "b" * 40,
            ["config/version.php", "package.json"],
        )
        self.assertEqual(first, reordered)
        self.assertIn('"paths":["config/version.php","package.json"]', first)
        candidate = {
            "state": "open", "draft": False,
            "mergeable_state": "dirty", "mergeable": False,
            "head": {
                "ref": "work/issue-7", "sha": "a" * 40,
                "repo": {"full_name": "pl0n3r/brvtal"},
            },
            "base": {
                "ref": "main", "repo": {"full_name": "pl0n3r/brvtal"},
            },
        }
        self.assertTrue(mod.candidate(candidate, "pl0n3r/brvtal"))
        self.assertFalse(mod.candidate({**candidate, "draft": True}, "pl0n3r/brvtal"))
        self.assertFalse(mod.candidate(
            {**candidate, "mergeable_state": "clean"}, "pl0n3r/brvtal"))

    def test_trusted_main_bump_command_and_rejection(self):
        git(self.repo, "checkout", "-B", "main", self.base)
        scripts = self.repo / "scripts"
        scripts.mkdir(exist_ok=True)
        valid = scripts / "bump_versions.py"
        valid.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "target = os.environ['FACTORY_TARGET_VERSION']\n"
            "for path in ['config/version.php', 'package.json']:\n"
            "    file = Path(path)\n"
            "    text = file.read_text(encoding='utf-8')\n"
            "    file.write_text(text.replace('0.1.1', target), encoding='utf-8')\n",
            encoding="utf-8",
        )
        invalid = scripts / "alter_app.py"
        invalid.write_text(
            "from pathlib import Path\n"
            "Path('app.txt').write_text('unallowed', encoding='utf-8')\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "trusted script fixtures")
        main = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "push", "origin", "HEAD:refs/heads/main")
        good = mod.trusted_bump(
            self.repo, main, sorted(SHARED), (0, 1, 5),
            "python3 scripts/bump_versions.py",
        )
        self.assertEqual(set(good), set(SHARED))
        self.assertTrue(all(mod.is_version_only_patch(p[p.index("@@ "):])
                            for p in good.values()))
        with self.assertRaises(mod.RebaseError):
            mod.trusted_bump(
                self.repo, main, sorted(SHARED), (0, 1, 5),
                "", "python3 scripts/alter_app.py",
            )
        with self.assertRaises(mod.RebaseError):
            mod._safe_script("python3 scripts/../escape.py", self.repo)

    def test_cli_dispatch_and_fail_closed_inputs(self):
        def argv(*items):
            return ["version_autorebase.py", *items]

        with patch.object(sys, "argv", argv(
                "--repo", "pl0n3r/brvtal", "--repo-path", str(self.repo))):
            self.assertEqual(mod.main(), 0)  # No opt-in is a no-op.
        with patch.object(sys, "argv", argv(
                "--repo", "../../bad", "--repo-path", str(self.repo),
                "--shared-version-paths", '["package.json"]')):
            self.assertEqual(mod.main(), 1)
        with patch.object(sys, "argv", argv(
                "--repo", "pl0n3r/brvtal", "--repo-path", str(self.repo),
                "--shared-version-paths", '["package.json"]')):
            with patch.dict("os.environ", {"GH_TOKEN": "fake"}):
                with patch.object(mod, "reconcile", return_value={
                    "updated": 0, "skipped": 0, "unresolved": 0,
                }) as runner:
                    self.assertEqual(mod.main(), 0)
                    runner.assert_called_once()

    def test_ref_and_inventory_fail_closed_on_invalid_responses(self):
        api = mod.GitHub("pl0n3r/brvtal", "fake")
        with patch.object(api, "request", return_value={"object": {"sha": "bad"}}):
            with self.assertRaises(mod.RebaseError):
                api.get_ref()
        with patch.object(api, "request", return_value={"unexpected": True}):
            with self.assertRaises(mod.RebaseError):
                api.pulls()
            with self.assertRaises(mod.RebaseError):
                api.comments(8)
            # A broken detail response must never be treated as an open PR.
            self.assertEqual(api.pull(8), {"unexpected": True})
        with patch.object(api, "request", return_value=[
            {"number": 1, "created_at": "2026-11-22T10:00:00Z"},
            {"number": 1, "created_at": "2026-11-22T10:00:00Z"},
        ]):
            with self.assertRaises(mod.RebaseError):
                api.pulls()
        with patch.object(api, "request", return_value=None):
            with self.assertRaises(mod.RebaseError):
                api.pull(8)
        with patch.object(api, "request", return_value=[]):
            self.assertEqual(api.comments(8), [])
            self.assertEqual(api.pulls(), [])

    def test_patch_write_confined_to_version_and_rejects_invalid(self):
        original = (self.repo / "config/version.php").read_text()
        patch_text = mod.make_version_patch(
            "config/version.php", original, (0, 1, 9))
        self.assertIn("@@ ", patch_text)
        mod.git_patch(self.repo, patch_text)
        self.assertEqual(
            mod.version((self.repo / "config/version.php").read_text()),
            (0, 1, 9))
        with self.assertRaises(mod.RebaseError):
            mod.git_patch(self.repo, "this is not a git patch")
        with self.assertRaises(mod.RebaseError):
            mod.git_patch(self.repo, patch_text)  # Not idempotent if base differs.
        with self.assertRaises(mod.RebaseError):
            mod.make_version_patch(
                "config/version.php", original, (0, 1, 1))
        with self.assertRaises(mod.RebaseError):
            mod.version("no version here")
        with self.assertRaises(mod.RebaseError):
            mod.version(
                "const APP_VERSION = '0.1.1';\n"
                "const OTHER_VERSION = '0.1.2';\n")
        with self.assertRaises(mod.RebaseError):
            mod.readable_file(self.repo, "bad", "package.json")
        self.assertIsNone(mod.issue_for_branch("work/issue-0"))
        self.assertIsNone(mod.issue_for_branch("work/issue-01"))
        self.assertIsNone(mod.issue_for_branch("work/issue-1/other"))

    def test_empty_opt_in_and_stale_head_are_safe_no_ops(self):
        api = FakeGitHub(self.remote, {})
        self.assertEqual(
            mod.reconcile(api, self.repo, frozenset(), "synthetic-run"),
            {"updated": 0, "skipped": 0, "unresolved": 0},
        )
        self.make_pr("work/issue-41")
        self.move_main()
        api = FakeGitHub(self.remote, {41: "work/issue-41"})
        with patch.object(api, "running", return_value=False):
            with self.assertRaises(mod.RebaseError):
                mod.reconcile(api, self.repo, SHARED, "synthetic-run")
        before = api.get_ref("work/issue-41")
        with self.assertRaises(mod.RebaseError):
            mod.prepare_rebase(
                self.repo, api.get_ref(), "0" * 40,
                "work/issue-41", SHARED, None, "")
        self.assertEqual(api.get_ref("work/issue-41"), before)

    def test_bump_script_guard_rejects_noncanonical_paths(self):
        for command in (
            "", "sh scripts/hook.py", "python3 -c print(1)",
            "python3 scripts/../../bad.py",
            "python3 scripts/file.py extra",
            "python3 scripts/a.b.py",
        ):
            with self.assertRaises(mod.RebaseError):
                mod._safe_script(command, self.repo)
        with self.assertRaises(mod.RebaseError):
            mod.GitHub("../invalid", "secret")

    def test_workflow_inputs_permissions_and_idempotence(self):
        workflow = (ROOT / ".github/workflows/version-autorebase.yml").read_text()
        script = (ROOT / "scripts/version_autorebase.py").read_text()
        self.assertIn("workflow_call:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("shared_version_paths:", workflow)
        self.assertIn("bump_command:", workflow)
        self.assertIn("post_bump_command:", workflow)
        self.assertIn("group: version-autorebase-${{ github.repository }}", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertRegex(workflow, r"permissions:\n  contents: read")
        self.assertRegex(workflow, r"(?s)jobs:\n  version-autorebase:.*?permissions:\n"
                                      r"      contents: write\n      pull-requests: write")
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("persist-credentials: true", workflow)
        self.assertIn("ref: ${{ job.workflow_sha }}", workflow)
        self.assertIn('git(worktree, "push", "origin"', script)
        self.assertNotIn('"--no-add"', script)
        self.assertIn('Applied patch did not leave exact target version.', script)
        for invalid in ("not-json", '["../bad","package.json"]',
                        '["package.json","package.json"]', '["a","b","c","d","e"]'):
            with self.assertRaises(CoordinationError):
                shared_version_paths(invalid)
        self.assertEqual(shared_version_paths(""), frozenset())
        self.assertIsNone(mod.issue_for_branch("feature/foo"))
        self.assertEqual(mod.issue_for_branch("work/issue-42"), 42)


if __name__ == "__main__":
    unittest.main()
