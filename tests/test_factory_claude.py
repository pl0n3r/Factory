import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "claude", "factory-claude")
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "claude"))

import ci_triage  # noqa: E402
import detect_stack  # noqa: E402
import factory_guard  # noqa: E402
import install_factory_claude  # noqa: E402
import kill_switch  # noqa: E402
import log_failure  # noqa: E402
import reservation_guard  # noqa: E402

SKILLS = ["factory-issue-to-merge", "factory-ci-unblock", "factory-agent-coordination",
          "factory-test-matrix", "factory-deploy-rollback", "factory-security-audit",
          "factory-cross-repo-contracts", "factory-documentation"]
GREEN = [{"name": "Validar", "bucket": "pass"}, {"name": "lint", "bucket": "pass"}]


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(l.split(": ", 1) for l in m.group(1).splitlines()) if m else None


class PluginStructureTest(unittest.TestCase):
    def test_manifest_and_marketplace(self):
        plugin = json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))
        market = json.load(open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
        self.assertEqual(plugin["name"], "factory-claude")
        entry = market["plugins"][0]
        self.assertEqual(entry["name"], plugin["name"])
        self.assertTrue(os.path.isdir(os.path.join(ROOT, entry["source"])))
        self.assertEqual(entry["version"], plugin["version"])

    def test_eight_skills_valid(self):
        found = sorted(os.listdir(os.path.join(PLUGIN, "skills")))
        self.assertEqual(found, sorted(SKILLS))
        for name in SKILLS:
            fm = frontmatter(os.path.join(PLUGIN, "skills", name, "SKILL.md"))
            self.assertIsNotNone(fm, name)
            self.assertEqual(fm["name"], name)
            self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
            self.assertTrue(40 < len(fm["description"]) <= 1024, name)
            self.assertIn("Úsala", fm["description"], name)

    def test_skill_script_references_exist(self):
        for name in SKILLS:
            text = open(os.path.join(PLUGIN, "skills", name, "SKILL.md"), encoding="utf-8").read()
            for rel in re.findall(r"CLAUDE_PLUGIN_ROOT\}/(scripts/[\w.]+)", text):
                self.assertTrue(os.path.exists(os.path.join(PLUGIN, rel)), rel)

    def test_hooks_reference_existing_scripts(self):
        hooks = json.load(open(os.path.join(PLUGIN, "hooks", "hooks.json")))["hooks"]
        count = 0
        for groups in hooks.values():
            for group in groups:
                for hook in group["hooks"]:
                    rel = re.search(r"CLAUDE_PLUGIN_ROOT\}/(scripts/[\w.]+)", hook["command"]).group(1)
                    self.assertTrue(os.path.exists(os.path.join(PLUGIN, rel)), rel)
                    count += 1
        self.assertEqual(count, 4)


class GuardTest(unittest.TestCase):
    def state(self, checks=GREEN, comments=()):
        return lambda ref: (checks, list(comments))

    def test_admin_merge_denied(self):
        self.assertEqual(factory_guard.evaluate("gh pr merge 5 --squash --admin", self.state())[0], "deny")

    def test_merge_needs_green_validar(self):
        red = [{"name": "Validar", "bucket": "fail"}]
        self.assertEqual(factory_guard.evaluate("gh pr merge 5 --squash", self.state(red))[0], "deny")
        self.assertEqual(factory_guard.evaluate("gh pr merge 5 --squash", self.state())[0], "allow")

    def test_merge_unknown_state_fails_closed(self):
        def boom(ref):
            raise RuntimeError("sin red")
        self.assertEqual(factory_guard.evaluate("gh pr merge 5", boom)[0], "deny")

    def test_coderabbit_premature_and_duplicate(self):
        cmd = 'gh pr comment 5 --body "@coderabbitai review"'
        pending = [{"name": "Validar", "bucket": "pending"}]
        self.assertEqual(factory_guard.evaluate(cmd, self.state(pending))[0], "deny")
        self.assertEqual(factory_guard.evaluate(cmd, self.state())[0], "allow")
        prior = [{"body": "@coderabbitai review"}]
        self.assertEqual(factory_guard.evaluate(cmd, self.state(GREEN, prior))[0], "deny")

    def test_main_push_rules_and_legit_commands(self):
        self.assertEqual(factory_guard.evaluate("git push --force origin main")[0], "deny")
        self.assertEqual(factory_guard.evaluate("git push origin main")[0], "deny")
        self.assertEqual(factory_guard.evaluate("git push -u origin trabajo/issue-9")[0], "allow")
        self.assertEqual(factory_guard.evaluate("gh pr checks 5")[0], "allow")
        self.assertEqual(factory_guard.evaluate("ls -la")[0], "allow")


class ReservationAndSwitchTest(unittest.TestCase):
    def test_reservation(self):
        ev = reservation_guard.evaluate
        self.assertEqual(ev("main")[0], "warn")
        self.assertEqual(ev("feature/x")[0], "allow")
        mk = lambda state, *labels: (lambda n: {"state": state, "labels": [{"name": l} for l in labels]})
        self.assertEqual(ev("trabajo/issue-7", mk("open", "estado: reservado"))[0], "allow")
        self.assertEqual(ev("trabajo/issue-7", mk("open", "estado: disponible"))[0], "deny")
        self.assertEqual(ev("trabajo/issue-7", mk("closed"))[0], "deny")

        def boom(n):
            raise RuntimeError("x")
        self.assertEqual(ev("trabajo/issue-7", boom)[0], "warn")

    def test_kill_switch(self):
        body = lambda s: f'<!-- factory-unattended-kill-switch {{"version":1,"state":"{s}","owner":"pl0n3r"}} -->'
        issue = lambda s, login="pl0n3r": {"user": {"login": login}, "body": body(s)}
        self.assertEqual(kill_switch.parse_kill_switch(issue("RUNNING"))[0], "RUNNING")
        self.assertEqual(kill_switch.parse_kill_switch(issue("PAUSED"))[0], "PAUSED")
        self.assertEqual(kill_switch.parse_kill_switch(issue("RUNNING", "otro"))[0], "UNKNOWN")
        self.assertEqual(kill_switch.parse_kill_switch({"user": {"login": "pl0n3r"}, "body": ""})[0], "UNKNOWN")
        dup = {"user": {"login": "pl0n3r"}, "body": body("RUNNING") + body("RUNNING")}
        self.assertEqual(kill_switch.parse_kill_switch(dup)[0], "UNKNOWN")
        self.assertTrue(kill_switch.message("UNKNOWN", "x").startswith("PAUSADO:"))


class LogAndTriageTest(unittest.TestCase):
    def test_log_is_idempotent_and_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, ".claude", "factory-claude", "errores.jsonl")
            rec = log_failure.record({"tool_use_id": "t1", "tool_name": "Bash", "error": "x" * 900})
            self.assertEqual(len(rec["error"]), 300)
            self.assertTrue(log_failure.append(path, rec))
            self.assertFalse(log_failure.append(path, rec))
            self.assertEqual(len(open(path).read().splitlines()), 1)

    def test_log_dir_prefers_git(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(log_failure.log_dir(d), os.path.join(d, ".claude", "factory-claude"))
            os.mkdir(os.path.join(d, ".git"))
            path = log_failure.log_dir(d)
            self.assertEqual(path, os.path.join(d, ".git", "factory-claude"))
            rec = log_failure.record({"tool_use_id": "t9", "tool_name": "Bash", "error": "x"})
            self.assertTrue(log_failure.append(os.path.join(path, "errores.jsonl"), rec))
            self.assertFalse(log_failure.append(os.path.join(path, "errores.jsonl"), rec))
            self.assertFalse(os.path.exists(os.path.join(d, ".claude")))

    def test_hook_cli_never_blocks(self):
        for script in ("factory_guard.py", "reservation_guard.py", "log_failure.py"):
            r = subprocess.run([sys.executable, os.path.join(PLUGIN, "scripts", script)],
                               input="no es json", capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stdout), (0, ""), script)

    def test_triage_classes(self):
        c = lambda t: ci_triage.classify(t)["class"]
        self.assertEqual(c("curl: ECONNRESET while fetching"), "transient")
        self.assertEqual(c("CONFLICT (content): Merge conflict in a.py"), "conflict")
        self.assertEqual(c("npm ERR! code ERESOLVE"), "dependency")
        self.assertEqual(c("AssertionError: 1 != 2"), "test")
        self.assertEqual(c("todo bien"), "unknown")


class StackAndInstallTest(unittest.TestCase):
    def write(self, root, files):
        for rel, content in files.items():
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(content)

    def test_detect_laravel_and_node(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, {"artisan": "", "composer.json": json.dumps({"require": {"laravel/framework": "^12"}}),
                           "pint.json": "{}", "package.json": json.dumps({"scripts": {"test": "x", "lint": "y"}})})
            out = detect_stack.detect(d)
            self.assertEqual(out["stack"], ["laravel", "node"])
            cmds = [c["cmd"] for c in out["commands"]]
            self.assertIn("php artisan test", cmds)
            self.assertIn("npm run lint", cmds)
            self.assertLess(cmds.index("vendor/bin/pint --test"), cmds.index("php artisan test"))

    def test_detect_python_kit(self):
        out = detect_stack.detect(ROOT)
        self.assertIn("python", out["stack"])
        self.assertIn("python3 -m unittest discover -s tests", [c["cmd"] for c in out["commands"]])

    def test_install_idempotent_and_merging(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, "GrindFlow")
            self.write(repo, {"AGENTS.md": "# x", ".claude/settings.json": json.dumps({"permissions": {"allow": ["Bash(ls)"]}})})
            first = install_factory_claude.install(repo)
            self.assertEqual(len(first), 2)
            self.assertEqual(install_factory_claude.install(repo), [])
            self.assertEqual(install_factory_claude.install(repo, check=True), [])
            cfg = json.load(open(os.path.join(repo, ".claude", "settings.json")))
            self.assertEqual(cfg["permissions"]["allow"], ["Bash(ls)"])
            self.assertTrue(cfg["enabledPlugins"]["laravel-boost@claude-plugins-official"])
            self.assertTrue(cfg["enabledPlugins"]["factory-claude@factory"])
            self.assertIn("@AGENTS.md", open(os.path.join(repo, "CLAUDE.md")).read())

    def test_every_canonical_repo_has_profile(self):
        self.assertEqual(sorted(install_factory_claude.REPO_PROFILE),
                         ["autofactory", "brvtal", "condor", "controlbot", "factory", "factoryrunner", "grindflow"])


class IssueCycleIntegrationTest(unittest.TestCase):
    """Ciclo simulado sin red: issue reservado → CI rojo transitorio → re-run → verde → merge permitido."""

    def test_cycle(self):
        self.assertEqual(reservation_guard.evaluate(
            "trabajo/issue-1", lambda n: {"state": "open", "labels": [{"name": "estado: reservado"}]})[0], "allow")
        self.assertEqual(ci_triage.classify("Error: ETIMEDOUT")["class"], "transient")
        red = [{"name": "Validar", "bucket": "fail"}]
        merge = "gh pr merge 1 --squash"
        self.assertEqual(factory_guard.evaluate(merge, lambda r: (red, []))[0], "deny")
        self.assertEqual(factory_guard.evaluate(merge, lambda r: (GREEN, []))[0], "allow")
        self.assertEqual(factory_guard.evaluate(merge + " --admin", lambda r: (GREEN, []))[0], "deny")


if __name__ == "__main__":
    unittest.main()
