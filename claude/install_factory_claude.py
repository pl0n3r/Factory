#!/usr/bin/env python3
"""Instala/actualiza factory-claude en un repo consumidor, de forma idempotente.

Uso: install_factory_claude.py <ruta-repo> [--profile laravel|php|node-web|kit] [--check]

Escribe `.claude/settings.json` (marketplace `factory` + plugins del perfil,
fusionando lo que ya exista) y asegura `CLAUDE.md` con la importación de
AGENTES.md/AGENTS.md. `--check` no escribe y sale 1 si faltan cambios.
"""
import json
import os
import sys

MARKETPLACES = {
    "factory": {"source": {"source": "github", "repo": "pl0n3r/factory"}},
    "claude-plugins-official": {"source": {"source": "github", "repo": "anthropics/claude-plugins-official"}},
}
BASE = ["factory-claude@factory"]
PROFILES = {
    "kit": [],
    "php": ["php-lsp@claude-plugins-official"],
    "laravel": ["php-lsp@claude-plugins-official", "laravel-boost@claude-plugins-official"],
    "node-web": ["playwright@claude-plugins-official", "frontend-design@claude-plugins-official"],
}
REPO_PROFILE = {
    "factory": "kit", "autofactory": "kit", "factoryrunner": "kit",
    "controlbot": "php", "condor": "php", "grindflow": "laravel", "brvtal": "node-web",
}
CLAUDE_MD = "@{agents}\n\nOperativa multiagente: https://github.com/pl0n3r/factory/blob/main/PLAN-AGENTES.md (manda sobre este archivo).\nSkills y hooks: plugin `factory-claude` (marketplace `factory`), ver docs/factory-claude.md en pl0n3r/factory.\n"


def desired_settings(existing, profile):
    out = json.loads(json.dumps(existing))
    out.setdefault("extraKnownMarketplaces", {})
    for name, cfg in MARKETPLACES.items():
        out["extraKnownMarketplaces"].setdefault(name, cfg)
    enabled = out.setdefault("enabledPlugins", {})
    for plugin in BASE + PROFILES[profile]:
        enabled.setdefault(plugin, True)
    return out


def install(root, profile=None, check=False):
    """Devuelve la lista de archivos cambiados (o por cambiar con check=True)."""
    profile = profile or REPO_PROFILE.get(os.path.basename(os.path.abspath(root)).lower(), "kit")
    changed = []
    sp = os.path.join(root, ".claude", "settings.json")
    existing = {}
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as fh:
            existing = json.load(fh)
    new = desired_settings(existing, profile)
    if new != existing:
        changed.append(sp)
        if not check:
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            with open(sp, "w", encoding="utf-8") as fh:
                json.dump(new, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
    cp = os.path.join(root, "CLAUDE.md")
    agents = next((n for n in ("AGENTES.md", "AGENTS.md") if os.path.exists(os.path.join(root, n))), None)
    if agents:
        text = open(cp, encoding="utf-8").read() if os.path.exists(cp) else ""
        if f"@{agents}" not in text:
            changed.append(cp)
            if not check:
                with open(cp, "w", encoding="utf-8") as fh:
                    fh.write((text.rstrip() + "\n\n" if text.strip() else "") + CLAUDE_MD.format(agents=agents))
    return changed


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    profile = next((a.split("=", 1)[1] for a in argv if a.startswith("--profile=")), None)
    if not args or (profile and profile not in PROFILES):
        print(__doc__)
        return 2
    changed = install(args[0], profile, check="--check" in argv)
    print(json.dumps({"changed": changed}))
    return 1 if (changed and "--check" in argv) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
