#!/usr/bin/env python3
"""Detecta el stack real de un repo y propone la matriz de pruebas.

Uso: detect_stack.py [ruta]  → JSON {stack:[...], commands:[{kind, cmd}]}.
Solo lee archivos del repo; no ejecuta nada. Los comandos salen de los
scripts/herramientas que el repo declara, nunca se inventan.
"""
import json
import os
import sys


def _json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def detect(root):
    has = lambda *p: os.path.exists(os.path.join(root, *p))
    stack, cmds = [], []
    pkg = _json(os.path.join(root, "package.json"))
    scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts"), dict) else {}
    comp = _json(os.path.join(root, "composer.json"))
    cscripts = comp.get("scripts", {}) if isinstance(comp.get("scripts"), dict) else {}
    deps = {**comp.get("require", {}), **comp.get("require-dev", {})}
    if has("artisan") or "laravel/framework" in deps:
        stack.append("laravel")
        cmds.append({"kind": "unit+integration", "cmd": "php artisan test"})
        if has("pint.json"):
            cmds.append({"kind": "format", "cmd": "vendor/bin/pint --test"})
    elif "symfony/framework-bundle" in deps or has("bin", "console"):
        stack.append("symfony")
    elif comp:
        stack.append("php")
    if comp:
        if has("phpunit.xml") or has("phpunit.xml.dist"):
            if "laravel" not in stack:
                cmds.append({"kind": "unit+integration", "cmd": "vendor/bin/phpunit"})
        if has("phpstan.neon") or has("phpstan.neon.dist"):
            cmds.append({"kind": "static", "cmd": "vendor/bin/phpstan analyse --no-progress"})
        if has("rector.php"):
            cmds.append({"kind": "static", "cmd": "vendor/bin/rector process --dry-run"})
        for name in ("test", "lint", "analyse", "stan", "check"):
            if name in cscripts:
                cmds.append({"kind": "composer-script", "cmd": f"composer run {name}"})
    if pkg:
        stack.append("node")
        for name, kind in (("test", "unit"), ("lint", "static"), ("typecheck", "static"),
                           ("build", "build"), ("test:e2e", "e2e"), ("e2e", "e2e")):
            if name in scripts:
                cmds.append({"kind": kind, "cmd": f"npm run {name}" if name != "test" else "npm test"})
    if has("playwright.config.mjs") or has("playwright.config.ts") or has("playwright.config.js"):
        cmds.append({"kind": "e2e", "cmd": "npx playwright test"})
    if has("tests") and any(f.startswith("test_") and f.endswith(".py") for f in os.listdir(os.path.join(root, "tests"))):
        stack.append("python")
        cmds.append({"kind": "unit", "cmd": "python3 -m unittest discover -s tests"})
    elif has("pyproject.toml") or has("requirements.txt"):
        stack.append("python")
    if has(".github", "workflows"):
        cmds.append({"kind": "ci", "cmd": "gh pr checks --watch=false"})
    # ordenar: rápido → lento y sin duplicados
    order = {"format": 0, "static": 1, "unit": 2, "unit+integration": 2, "composer-script": 2, "build": 3, "e2e": 4, "ci": 5}
    seen, out = set(), []
    for c in sorted(cmds, key=lambda c: order.get(c["kind"], 9)):
        if c["cmd"] not in seen:
            seen.add(c["cmd"])
            out.append(c)
    return {"stack": sorted(set(stack)), "commands": out}


def main(argv):
    print(json.dumps(detect(argv[1] if len(argv) > 1 else "."), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
