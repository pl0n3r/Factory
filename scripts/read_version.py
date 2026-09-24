#!/usr/bin/env python3
"""Lee SemVer desde fuentes canónicas sin ejecutar código."""
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
FORMATS = {"auto", "json", "php-array", "php-const"}
VERSION_SOURCES = {
    "config/version.php": Path("config/version.php"),
    "config/version.json": Path("config/version.json"),
}
MAX_VERSION_FILE_BYTES = 64 * 1024

class VersionError(ValueError):
    pass

def canonical_source(source: str) -> Path:
    try:
        return VERSION_SOURCES[source]
    except KeyError as exc:
        raise VersionError(
            "Fuente de versión no permitida; use config/version.php o config/version.json."
        ) from exc

def php_array_value(text: str, key: str) -> str:
    pattern = re.compile(
        r"""['"]""" + re.escape(key) + r"""['"]\s*=>\s*['"]([^'"]+)['"]"""
    )
    match = pattern.search(text)
    return match.group(1) if match else ""

def php_const_value(text: str, key: str) -> str:
    pattern = re.compile(
        r"""\bconst\s+""" + re.escape(key) + r"""\s*=\s*['"]([^'"]+)['"]\s*;"""
    )
    match = pattern.search(text)
    return match.group(1) if match else ""

def read_version(
    source: str,
    fmt: str,
    key: str,
    *,
    root: Path | None = None,
) -> str:
    if fmt not in FORMATS:
        raise VersionError("Formato de versión no soportado.")
    if not KEY.fullmatch(key):
        raise VersionError("Clave de versión inválida.")
    path = canonical_source(source)
    try:
        text = read_repo_text(path, root=root, max_bytes=MAX_VERSION_FILE_BYTES)
    except SafeIOError as exc:
        raise VersionError(str(exc)) from exc

    effective = fmt
    if effective == "auto":
        effective = "json" if path.suffix == ".json" else "php-auto"

    if effective == "json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VersionError("JSON de versión inválido.") from exc
        value = raw.get(key, "") if isinstance(raw, dict) else ""
    elif effective == "php-array":
        value = php_array_value(text, key)
    elif effective == "php-const":
        value = php_const_value(text, key)
    else:
        value = php_array_value(text, key) or php_const_value(text, key)

    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise VersionError("Versión SemVer inválida.")
    return value

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, choices=sorted(VERSION_SOURCES))
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
