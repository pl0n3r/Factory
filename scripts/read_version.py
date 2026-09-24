#!/usr/bin/env python3
"""Lee una versión SemVer desde un archivo confinado al checkout."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
if __package__:
    from scripts.safe_io import SafeIOError, read_repo_text
else:
    from safe_io import SafeIOError, read_repo_text

SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,79}$")
FORMATS = {"auto", "json", "php-array", "text"}
MAX_VERSION_FILE_BYTES = 64 * 1024

class VersionError(ValueError):
    pass

def read_version(path: Path, fmt: str, key: str, *, root: Path | None = None) -> str:
    if fmt not in FORMATS:
        raise VersionError("Formato de versión no soportado.")
    if not KEY.fullmatch(key):
        raise VersionError("Clave de versión inválida.")
    try:
        text = read_repo_text(path, root=root, max_bytes=MAX_VERSION_FILE_BYTES)
    except SafeIOError as exc:
        raise VersionError(str(exc)) from exc
    effective = fmt
    if effective == "auto":
        effective = {".php": "php-array", ".json": "json"}.get(path.suffix.lower(), "text")
    if effective == "json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VersionError("JSON de versión inválido.") from exc
        value = raw.get(key, "") if isinstance(raw, dict) else ""
    elif effective == "php-array":
        pattern = re.compile(r"""['"]""" + re.escape(key) + r"""['"]\s*=>\s*['"]([^'"]+)['"]""")
        match = pattern.search(text)
        value = match.group(1) if match else ""
    else:
        lines = text.splitlines()
        value = lines[0].strip() if lines else ""
    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise VersionError("Versión SemVer inválida.")
    return value

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--format", default="auto", choices=sorted(FORMATS))
    parser.add_argument("--key", default="version")
    args = parser.parse_args()
    try:
        print(read_version(args.source, args.format, args.key))
        return 0
    except VersionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
