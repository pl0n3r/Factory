#!/usr/bin/env python3
"""Fail-closed, serial version-only merge of main into coordinated PR branches.

Run only from a trusted push-to-main caller (or an authorized manual dispatch).
Never executes code checked out from a PR, uses a force push, merges a PR, or
modifies main. Consumers must opt in after Factory@v1 is released.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from scripts.coordinar_trabajo import CoordinationError, is_version_only_patch, shared_version_paths
except ImportError:
    from coordinar_trabajo import CoordinationError, is_version_only_patch, shared_version_paths


class RebaseError(RuntimeError):
    """A safety or input precondition failed closed."""


BRANCH_RE = re.compile(r"(?:trabajo|work)/issue-([1-9][0-9]*)\Z")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
VERSION_LINE = re.compile(
    r"(?m)^(?P<prefix>\s*(?:const\s+[A-Z][A-Z0-9_]*_VERSION\s*=\s*|"
    r'"version"\s*:\s*))(?P<quote>["\x27])(?P<version>[0-9]+\.[0-9]+\.[0-9]+)'
    r"(?P=quote)(?P<suffix>\s*[,;]?\s*)$"
)
KILL_RE = re.compile(r"<!-- factory-unattended-kill-switch (\{[^\r\n{}]*\}) -->")
BOT = "github-actions[bot]"
MAX_PAGES = 10


def git(worktree: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=worktree, text=True, capture_output=True,
        timeout=120, check=False,
    )
    if check and result.returncode:
        raise RebaseError("git command failed: " + args[0] + " (exit "
                          + str(result.returncode) + ")")
    return result


def version(text: str) -> tuple[int, int, int]:
    values = [tuple(int(x) for x in match.group("version").split("."))
              for match in VERSION_LINE.finditer(text)]
    if len(values) != 1:
        raise RebaseError("Version file must contain exactly one canonical version line.")
    return values[0]


def replace_version(text: str, target: tuple[int, int, int]) -> str:
    version(text)  # A missing or ambiguous line is not silently created.
    formatted = ".".join(map(str, target))
    return VERSION_LINE.sub(
        lambda m: m.group("prefix") + m.group("quote") + formatted
        + m.group("quote") + m.group("suffix"),
        text, count=1,
    )


def version_only_git_diff(worktree: Path, base: str, tip: str, path: str) -> bool:
    diff = git(worktree, "diff", "--no-ext-diff", "--no-renames", "--unified=0",
               base, tip, "--", path).stdout
    # The coordinator's exact-head version-line parser expects hunks without
    # git diff metadata, which must itself be structurally ordinary.
    if not diff.startswith("diff --git ") or "GIT binary patch" in diff:
        return False
    lines = diff.splitlines()
    if not any(line.startswith("@@ ") for line in lines):
        return False
    hunks = []
    in_hunk = False
    for line in lines:
        if line.startswith("@@ "):
            in_hunk = True
        elif not in_hunk:
            if line.startswith(("rename ", "copy ", "new file", "deleted file", "Binary files")):
                return False
            continue
        hunks.append(line)
    return is_version_only_patch("\n".join(hunks))


def readable_file(worktree: Path, commit: str, path: str) -> str:
    if not SHA_RE.fullmatch(commit):
        raise RebaseError("Invalid exact commit SHA.")
    return git(worktree, "show", commit + ":" + path).stdout


def issue_for_branch(branch: str) -> int | None:
    match = BRANCH_RE.fullmatch(branch)
    return int(match.group(1)) if match else None


def comment_marker(kind: str, pr: int, head: str, main: str,
                   conflicts: list[str]) -> str:
    record = {"version": 1, "pr": pr, "head": head, "main": main,
              "paths": sorted(conflicts)}
    return "<!-- factory-version-autorebase-" + kind + " " + json.dumps(
        record, separators=(",", ":"), sort_keys=True, ensure_ascii=True
    ) + " -->"


class GitHub:
    def __init__(self, repo: str, token: str) -> None:
        if not REPO_RE.fullmatch(repo) or not token:
            raise RebaseError("Repository or authenticated token missing.")
        self.repo = repo
        self.token = token

    def request(self, method: str, path: str, payload: Any = None) -> Any:
        if not path.startswith("/") or "//" in path:
            raise RebaseError("Invalid GitHub API path.")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = Request(
            "https://api.github.com" + path, data=data, method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + self.token,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "factory-version-autorebase",
            },
        )
        try:
            with urlopen(req, timeout=20) as response:
                return json.load(response)
        except (HTTPError, URLError, ValueError) as exc:
            raise RebaseError("GitHub API request failed (" + method + " "
                              + path.split("?")[0] + ")") from exc

    def get_ref(self, branch: str = "main") -> str:
        value = self.request("GET", "/repos/" + self.repo
                             + "/git/ref/heads/" + branch)
        sha = (value.get("object") or {}).get("sha")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise RebaseError("GitHub branch ref is missing or invalid.")
        return sha

    def running(self) -> bool:
        issue = self.request("GET", "/repos/pl0n3r/Factory/issues/767")
        body = issue.get("body") if isinstance(issue, dict) else None
        markers = KILL_RE.findall(body) if isinstance(body, str) else []
        if (not isinstance(issue, dict) or issue.get("state") != "closed"
            or (issue.get("user") or {}).get("login") != "pl0n3r"
            or len(markers) != 1
            or len(re.findall(r"<!--\s*factory-unattended-kill-switch", body)) != 1):
            return False
        try:
            return json.loads(markers[0]) == {
                "version": 1, "state": "RUNNING", "owner": "pl0n3r"
            }
        except ValueError:
            return False

    def pulls(self) -> list[dict[str, Any]]:
        all_rows: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            rows = self.request(
                "GET", f"/repos/{self.repo}/pulls?state=open&base=main"
                f"&sort=created&direction=asc&per_page=100&page={page}")
            if not isinstance(rows, list):
                raise RebaseError("Incomplete GitHub PR inventory.")
            all_rows.extend(rows)
            if len(rows) < 100:
                if len({row.get("number") for row in all_rows}) != len(all_rows):
                    raise RebaseError("Duplicate PR numbers in inventory.")
                return sorted(all_rows, key=lambda row: (row["created_at"], row["number"]))
        raise RebaseError("PR inventory exceeded bounded pagination; no writes.")

    def pull(self, number: int) -> dict[str, Any]:
        value = self.request("GET", f"/repos/{self.repo}/pulls/{number}")
        if not isinstance(value, dict):
            raise RebaseError("PR detail unavailable.")
        return value

    def comments(self, number: int) -> list[dict[str, Any]]:
        found = []
        for page in range(1, MAX_PAGES + 1):
            rows = self.request(
                "GET", f"/repos/{self.repo}/issues/{number}/comments"
                       f"?per_page=100&page={page}")
            if not isinstance(rows, list):
                raise RebaseError("PR comment inventory incomplete.")
            found.extend(rows)
            if len(rows) < 100:
                return found
        raise RebaseError("PR comments unbounded; fail closed.")

    def comment_once(self, number: int, marker: str, body: str) -> None:
        if any(marker in str(row.get("body") or "")
               and (row.get("user") or {}).get("login") == BOT
               for row in self.comments(number)):
            return
        self.request("POST", f"/repos/{self.repo}/issues/{number}/comments",
                     {"body": marker + "\n\n" + body})


def candidate(pr: dict[str, Any], repo: str) -> bool:
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    return bool(
        pr.get("state") == "open"
        and pr.get("draft") is False
        and pr.get("mergeable_state") == "dirty"
        and pr.get("mergeable") is False
        and base.get("ref") == "main"
        and (base.get("repo") or {}).get("full_name", "").casefold() == repo.casefold()
        and (head.get("repo") or {}).get("full_name", "").casefold() == repo.casefold()
        and isinstance(head.get("ref"), str)
        and issue_for_branch(head["ref"]) is not None
        and isinstance(head.get("sha"), str)
        and SHA_RE.fullmatch(head["sha"])
    )


def git_patch(worktree: Path, patch: str) -> None:
    """Apply only a verified version-line patch; no whole-file data writes."""
    if not isinstance(patch, str) or not patch.startswith("diff --git "):
        raise RebaseError("Missing canonical version patch.")
    proc = subprocess.run(
        ["git", "apply", "--unidiff-zero", "--no-add", "-"],
        input=patch, cwd=worktree, text=True, capture_output=True,
        timeout=30, check=False,
    )
    if proc.returncode:
        raise RebaseError("Strict version patch could not apply to main file.")


def make_version_patch(path: str, before: str,
                       target: tuple[int, int, int]) -> str:
    """Only the version line, not arbitrary contents from a caller, is written."""
    after = replace_version(before, target)
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="a/" + path, tofile="b/" + path, n=0,
    ))
    if not diff:
        raise RebaseError("No version change to apply.")
    patch = "diff --git a/" + path + " b/" + path + "\n" + diff
    hunks = patch[patch.index("@@ "):]
    if not is_version_only_patch(hunks):
        raise RebaseError("Generated patch changes non-version lines.")
    return patch


def trusted_bump(
    worktree: Path, main: str, paths: list[str],
    target: tuple[int, int, int], command: str,
) -> dict[str, str]:
    """Return narrow patches; never return or write entire sensitive files."""
    if not command:
        return {path: make_version_patch(
            path, readable_file(worktree, main, path), target
        ) for path in paths}
    argv = shlex.split(command)
    if not argv or any("\x00" in part for part in argv):
        raise RebaseError("Invalid trusted bump command.")
    with tempfile.TemporaryDirectory(prefix="factory-bump-main-") as directory:
        trusted = Path(directory)
        git(worktree, "worktree", "add", "--detach", str(trusted), main)
        try:
            # The callable runs in a worktree created from verified MAIN only.
            # No PR-sourced code or workflow token may reach the command.
            env = {k: v for k, v in os.environ.items()
                   if k not in {"GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN",
                                "ACTIONS_ID_TOKEN_REQUEST_TOKEN"}}
            env["FACTORY_TARGET_VERSION"] = ".".join(map(str, target))
            result = subprocess.run(
                argv, cwd=trusted, env=env, text=True, capture_output=True,
                timeout=90, check=False,
            )
            if result.returncode:
                raise RebaseError("Trusted bump command failed.")
            status = git(trusted, "status", "--porcelain", "--untracked-files=all").stdout
            rows = status.splitlines()
            if not rows or any(
                len(row) < 4
                or row[:2] not in {" M", "M ", "MM"}
                or row[3:] not in paths
                for row in rows
            ):
                raise RebaseError("Trusted bump touched unexpected or untracked files.")
            patches: dict[str, str] = {}
            for path in paths:
                text = (trusted / path).read_text(encoding="utf-8")
                if version(text) != target:
                    raise RebaseError("Trusted bump did not produce the exact target.")
                patch = git(
                    trusted, "diff", "--no-ext-diff", "--unified=0",
                    "HEAD", "--", path
                ).stdout
                if "@@ " not in patch or not is_version_only_patch(
                    patch[patch.index("@@ "):]
                ):
                    raise RebaseError("Trusted bump changed non-version data.")
                patches[path] = patch
            return patches
        finally:
            git(worktree, "worktree", "remove", "--force",
                str(trusted), check=False)


def prepare_rebase(
    worktree: Path, main: str, head: str, branch: str,
    allowed: frozenset[str], allocated: tuple[int, int, int] | None,
    bump_command: str,
) -> tuple[list[str], tuple[int, int, int] | None]:
    # Must fetch both refs from the same authenticated repo. A final push uses
    # Git fast-forward protection against any concurrent actor.
    git(worktree, "fetch", "--no-tags", "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        "+refs/heads/" + branch + ":refs/remotes/origin/" + branch)
    if (git(worktree, "rev-parse", "refs/remotes/origin/main").stdout.strip() != main
        or git(worktree, "rev-parse", "refs/remotes/origin/" + branch).stdout.strip() != head):
        raise RebaseError("Main/PR ref moved during exact-SHA preflight.")

    base = git(worktree, "merge-base", main, head).stdout.strip()
    if not SHA_RE.fullmatch(base):
        raise RebaseError("Common ancestor missing.")
    git(worktree, "checkout", "--detach", "-f", head)
    merged = git(worktree, "merge", "--no-commit", "--no-ff", main, check=False)
    conflicts = sorted(git(worktree, "diff", "--name-only", "--diff-filter=U").stdout.splitlines())
    if merged.returncode == 0 or not conflicts:
        git(worktree, "merge", "--abort", check=False)
        raise RebaseError("Dirty PR without a verifiable version-only merge conflict.")
    if not set(conflicts).issubset(allowed):
        git(worktree, "merge", "--abort", check=False)
        return conflicts, None

    try:
        main_versions = []
        original_versions = []
        for path in conflicts:
            if not (version_only_git_diff(worktree, base, main, path)
                    and version_only_git_diff(worktree, base, head, path)):
                return conflicts, None
            main_versions.append(version(readable_file(worktree, main, path)))
            original_versions.append(version(readable_file(worktree, head, path)))
        if len(set(main_versions)) != 1 or len(set(original_versions)) != 1:
            return conflicts, None
        main_version, original = main_versions[0], original_versions[0]
        target = max(
            (main_version[0], main_version[1], main_version[2] + 1),
            original,
            (allocated[0], allocated[1], allocated[2] + 1) if allocated else (0, 0, 0),
        )
        # Never run the caller's command from the untrusted PR worktree.
        patches = trusted_bump(worktree, main, conflicts, target, bump_command)
        for path, patch in patches.items():
            git(worktree, "checkout", "--theirs", "--", path)
            git_patch(worktree, patch)
            git(worktree, "add", "--", path)
        if git(worktree, "diff", "--name-only", "--diff-filter=U").stdout.strip():
            raise RebaseError("Unresolved index entries after strict resolution.")
        git(worktree, "config", "user.name", BOT)
        git(worktree, "config", "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com")
        git(worktree, "commit", "-m", "chore(version): rebase automático sobre main "
            + "(v" + ".".join(map(str, target)) + ")")
        return [], target
    finally:
        # Callers that did not create a merge commit must not carry conflicts
        # into the next PR. A committed merge has no MERGE_HEAD to abort.
        git(worktree, "merge", "--abort", check=False)


def reconcile(
    api: GitHub, worktree: Path, allowed: frozenset[str],
    run_url: str, bump_command: str = "",
) -> dict[str, int]:
    if not allowed:
        return {"updated": 0, "skipped": 0, "unresolved": 0}
    if not api.running():
        raise RebaseError("Factory#767 is not RUNNING: no mutation.")
    main = api.get_ref("main")
    prs = api.pulls()
    allocated = None
    counters = {"updated": 0, "skipped": 0, "unresolved": 0}
    for row in prs:
        number = row.get("number")
        if type(number) is not int or number < 1:
            raise RebaseError("PR inventory contains invalid identifier.")
        pr = api.pull(number)
        if not candidate(pr, api.repo):
            counters["skipped"] += 1
            continue
        branch = pr["head"]["ref"]
        head = pr["head"]["sha"]
        if api.get_ref("main") != main or not api.running():
            raise RebaseError("Main or Factory#767 changed; stop before push.")
        try:
            conflicts, target = prepare_rebase(
                worktree, main, head, branch, allowed, allocated, bump_command
            )
        except RebaseError:
            # Unexpected source or unverified diff is never auto-corrected.
            git(worktree, "merge", "--abort", check=False)
            raise
        if target is None:
            git(worktree, "merge", "--abort", check=False)
            marker = comment_marker("conflict", number, head, main, conflicts)
            api.comment_once(number, marker,
                "Autorebase de versión omitido: conflictos fuera de las líneas "
                "de versión verificadas: " + ", ".join(conflicts) + ". "
                "No se empujaron cambios. " + run_url)
            counters["unresolved"] += 1
            continue
        current = api.pull(number)
        if (current["head"]["sha"] != head
            or current.get("state") != "open" or current.get("draft") is not False
            or current["base"]["sha"] != main
            or api.get_ref("main") != main
            or not api.running()):
            raise RebaseError("PR, main or kill switch changed before push.")
        # NO --force, no git push -f, no --admin and no PR merge.
        git(worktree, "push", "origin", "HEAD:refs/heads/" + branch)
        allocated = target
        new_head = git(worktree, "rev-parse", "HEAD").stdout.strip()
        marker = comment_marker("result", number, head, main, conflicts)
        api.comment_once(number, marker,
            "Reconciliación de versión: merge normal de main " + main
            + " a la rama coordinada; versión v" + ".".join(map(str, target))
            + "; push sin force, sin fusionar PR, sin saltar CI. "
            + "HEAD: " + new_head + ". Ejecución: " + run_url)
        counters["updated"] += 1
    return counters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--shared-version-paths", default="")
    parser.add_argument("--bump-command", default="")
    parser.add_argument("--run-url", default="")
    args = parser.parse_args()
    try:
        allowed = shared_version_paths(args.shared_version_paths)
        if not REPO_RE.fullmatch(args.repo):
            raise RebaseError("Invalid target repository.")
        worktree = args.repo_path.resolve(strict=True)
        if not (worktree / ".git").exists():
            raise RebaseError("Consumer checkout is not a Git working directory.")
        if not allowed:
            print("VERSION AUTOREBASE: no shared paths declared; no-op.")
            return 0
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        api = GitHub(args.repo, token)
        result = reconcile(api, worktree, allowed, args.run_url, args.bump_command)
        print("VERSION AUTOREBASE: " + json.dumps(result, sort_keys=True))
        return 0
    except (RebaseError, CoordinationError, OSError, subprocess.TimeoutExpired,
            ValueError) as exc:
        print("VERSION AUTOREBASE FAIL-CLOSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
