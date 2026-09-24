#!/usr/bin/env python3
"""Valida que template/ consuma Factory sin copias divergentes."""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"template"
REQUIRED=[
    ".github/workflows/ci.yml",".github/workflows/coordinacion.yml",".github/workflows/etiquetas.yml",
    ".github/workflows/release.yml",".github/workflows/politica.yml",".github/workflows/deploy.yml",
    ".github/workflows/observar.yml",".github/dependabot.yml","config/version.json","decisiones.yml",
    "AGENTES.md","README.md","composer.lock","public/index.php","public/health.php","tests/smoke.php",
]
def validate() -> list[str]:
    errors=[]
    for path in REQUIRED:
        if not (TEMPLATE/path).is_file():
            errors.append(f"Falta template/{path}")
    for path in (TEMPLATE/".github/workflows").glob("*.yml"):
        text=path.read_text(encoding="utf-8")
        for use in re.findall(r"^\s*uses:\s*([^\s]+)",text,flags=re.MULTILINE):
            if use.startswith("pl0n3r/factory/"):
                if not use.endswith("@v1"):
                    errors.append(f"{path}: Factory debe consumirse por @v1")
            elif not re.search(r"@[0-9a-f]{40}$",use):
                errors.append(f"{path}: acción externa no fijada a SHA: {use}")
    return errors
def main() -> int:
    errors=validate()
    if errors:
        print("\n".join(errors),file=sys.stderr)
        return 1
    print("template válido")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
