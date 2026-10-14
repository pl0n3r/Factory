"""Tag ya publicado + versión sin cambio en el push: skip; todo lo demás sigue fallando (#1362)."""
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = (ROOT / ".github/workflows/release.yml").read_text()
ZERO = "0" * 40


def _tag_script():
    segment = W.split("      - name: Asegurar tag anotado", 1)[1].split("      - id: release", 1)[0]
    return textwrap.dedent(segment.split("        run: |\n", 1)[1])


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x",
                               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}).stdout.strip()


class ReleaseTagExistingSkipTests(unittest.TestCase):
    def _run(self, *, version_change=False, tag_on_side_branch=False, before=None,
             event="push", bootstrap="false", env_version="1.0.1"):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            _git(repo, "init", "-q", "-b", "main")
            (repo / "config").mkdir()
            (repo / "config/version.json").write_text('{"version": "1.0.1"}')
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "a")
            first = _git(repo, "rev-parse", "HEAD")
            if tag_on_side_branch:
                _git(repo, "checkout", "-q", "-b", "side")
                (repo / "side.txt").write_text("x")
                _git(repo, "add", "-A")
                _git(repo, "commit", "-q", "-m", "side")
                _git(repo, "tag", "-a", "v1.0.1", "-m", "t")
                _git(repo, "checkout", "-q", "main")
            else:
                _git(repo, "tag", "-a", "v1.0.1", "-m", "t")
            (repo / "other.txt").write_text("y")
            if version_change:
                (repo / "config/version.json").write_text('{"version": "1.0.2"}')
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "b")
            target = _git(repo, "rev-parse", "HEAD")
            (base / "factory").mkdir()
            (base / "factory/scripts").symlink_to(ROOT / "scripts")
            (repo / ".factory").symlink_to(base / "factory")
            gh = base / "gh"
            gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_LOG\"\n"
                          "case \"$*\" in */commits/*) printf '%s\\n' \"$FAKE_MAIN\"; exit 0;; esac\nexit 0\n")
            gh.chmod(0o755)
            out, summary, log = base / "out", base / "summary", base / "gh.log"
            for f in (out, summary, log):
                f.write_text("")
            (base / "tmp").mkdir()
            env = {
                **os.environ, "PATH": f"{base}:{os.environ['PATH']}", "FAKE_LOG": str(log),
                "FAKE_MAIN": target, "GH_TOKEN": "x", "TAG": "v1.0.1", "VERSION": env_version,
                "EVENT_NAME": event, "BEFORE": first if before is None else before,
                "SOURCE": "config/version.json", "FORMAT": "auto", "KEY": "version",
                "TARGET_SHA": target, "REPOSITORY": "o/r", "DEFAULT_BRANCH": "main",
                "BOOTSTRAP": bootstrap, "EXPECTED_SHA": target if bootstrap == "true" else "",
                "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary),
                "GITHUB_WORKSPACE": str(repo), "RUNNER_TEMP": str(base / "tmp"),
            }
            run = subprocess.run(["bash", "-c", _tag_script()], cwd=repo, env=env,
                                 capture_output=True, text=True)
            return run, out.read_text(), log.read_text()

    def test_unchanged_version_with_ancestor_tag_skips_without_error(self):
        run, out, log = self._run()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("skip=true", out)
        self.assertNotIn("git/tags", log)
        self.assertNotIn("git/refs", log)

    def test_changed_version_or_non_ancestor_tag_still_fails_closed(self):
        cases = {
            "version changed": {"version_change": True, "env_version": "1.0.2"},
            "tag not ancestor": {"tag_on_side_branch": True},
            "before zero": {"before": ZERO},
            "before malformed": {"before": "not-a-sha"},
            "before unknown commit": {"before": "c" * 40},
            "dispatch bootstrap": {"event": "workflow_dispatch", "bootstrap": "true"},
        }
        for label, kwargs in cases.items():
            with self.subTest(case=label):
                run, out, log = self._run(**kwargs)
                self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertNotIn("skip=true", out)
                self.assertNotIn("git/tags", log)
                self.assertIn("ya apunta a otro commit", run.stderr + run.stdout)

    def test_release_step_is_gated_by_skip_output(self):
        self.assertIn("      - id: release\n        if: steps.tag.outputs.skip != 'true'", W)


if __name__ == "__main__":
    unittest.main()
