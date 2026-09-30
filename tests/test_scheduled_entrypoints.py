#!/usr/bin/env python3
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED = {
    "scripts/coordinar_trabajo.py",
    "metricas/costos.py",
    "metricas/evaluar_agentes.py",
    "scripts/sonar-watch.py",
    "producto/feedback.py",
    "scripts/cabina.py",
}

SAFE_ARGS = {
    "scripts/coordinar_trabajo.py": ("--help",),
    "metricas/costos.py": ("--help",),
    "metricas/evaluar_agentes.py": ("--help",),
    "scripts/sonar-watch.py": (),
    "producto/feedback.py": ("--help",),
}


class ScheduledEntrypointTests(unittest.TestCase):
    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        for key in (
            "PYTHONPATH",
            "SONAR_TOKEN",
            "GH_TOKEN",
            "GITHUB_TOKEN",
            "SONAR_WATCH_CONFIG_JSON",
        ):
            env.pop(key, None)
        return env

    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, script, *args],
            cwd=ROOT,
            env=self._env(),
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )

    def _scheduled_paths(self) -> set[str]:
        discovered: set[str] = set()
        for workflow in sorted(WORKFLOWS.glob("*.yml")):
            text = workflow.read_text(encoding="utf-8")
            if not re.search(r"(?m)^\s*schedule:\s*$", text):
                continue
            discovered.update(
                match.group(1)
                for match in re.finditer(
                    r"\bpython3?\s+([A-Za-z0-9_.\-/]+\.py)(?:\s|$)",
                    text,
                )
                if not match.group(1).startswith(".factory/")
            )
        return discovered

    def test_sonar_watch_path_entrypoint_is_import_safe(self) -> None:
        result = self._run("scripts/sonar-watch.py")
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn("configuración runtime incompleta", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_feedback_path_entrypoint_is_import_safe(self) -> None:
        result = self._run("producto/feedback.py", "--help")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stdout + result.stderr)

    def test_all_scheduled_python_path_entrypoints_are_import_safe(self) -> None:
        discovered = self._scheduled_paths()
        self.assertEqual(EXPECTED, discovered)

        for script, args in SAFE_ARGS.items():
            result = self._run(script, *args)
            combined = result.stdout + result.stderr
            self.assertNotIn("ModuleNotFoundError", combined, script)
            if script == "scripts/sonar-watch.py":
                self.assertEqual(2, result.returncode, combined)
                self.assertIn("configuración runtime incompleta", result.stderr)
            else:
                self.assertEqual(0, result.returncode, combined)

        cabina = ROOT / "scripts" / "cabina.py"
        tree = ast.parse(cabina.read_text(encoding="utf-8"))
        local_roots = {p.name for p in ROOT.iterdir() if p.is_dir()}
        repo_imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                repo_imports.extend(
                    alias.name.split(".", 1)[0]
                    for alias in node.names
                    if alias.name.split(".", 1)[0] in local_roots
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in local_roots:
                    repo_imports.append(root)
        self.assertEqual([], repo_imports, "cabina.py añadió imports locales sin bootstrap")


if __name__ == "__main__":
    unittest.main()
