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

def _php_tokens(text: str) -> list[tuple[str, str]]:
    """Tokeniza el subconjunto de PHP usado por los manifests, sin ejecutarlo."""
    tokens: list[tuple[str, str]] = []
    position = 0
    length = len(text)
    # Fragmentos sin etiqueta siguen admitidos por compatibilidad.
    embedded = text.lstrip().startswith("<?")
    active = not embedded
    while position < length:
        if not active:
            start = text.find("<?", position)
            if start < 0:
                break
            if text[start:start + 5].lower() == "<?xml":
                position = start + 5
                continue
            position = start + (5 if text[start:start + 5].lower() == "<?php" else 2)
            active = True
            continue
        if text.startswith("?>", position):
            active = False
            position += 2
            continue
        char = text[position]
        if char.isspace():
            position += 1
            continue
        if text.startswith("//", position) or char == "#":
            next_line = text.find("\n", position)
            position = length if next_line == -1 else next_line + 1
            continue
        if text.startswith("/*", position):
            end = text.find("*/", position + 2)
            if end < 0:
                raise VersionError("Comentario PHP sin cerrar.")
            position = end + 2
            continue
        if text.startswith("<<<", position):
            raise VersionError("Heredoc PHP no soportado en versión.")
        if char in "'\"":
            quote = char
            cursor = position + 1
            while cursor < length:
                if text[cursor] == "\\":
                    cursor += 2
                elif text[cursor] == quote:
                    break
                else:
                    cursor += 1
            if cursor >= length:
                raise VersionError("Cadena PHP sin cerrar.")
            tokens.append(("string", text[position + 1:cursor]))
            position = cursor + 1
            continue
        if re.match(r"[A-Za-z_]", char):
            match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", text[position:])
            assert match is not None
            tokens.append(("word", match.group()))
            position += len(match.group())
            continue
        if text.startswith("=>", position):
            tokens.append(("symbol", "=>"))
            position += 2
            continue
        tokens.append(("symbol", char))
        position += 1
    return tokens


def _php_array_candidates(tokens: list[tuple[str, str]], key: str) -> list[str]:
    found: list[str] = []
    for i in range(len(tokens) - 1):
        if tokens[i] != ("word", "return") or tokens[i + 1] != ("symbol", "["):
            continue
        depth = 1
        j = i + 2
        while j < len(tokens) and depth:
            token = tokens[j]
            if token == ("symbol", "["):
                depth += 1
            elif token == ("symbol", "]"):
                depth -= 1
            elif depth == 1 and token == ("string", key) and j + 2 < len(tokens):
                if tokens[j + 1] == ("symbol", "=>"):
                    if tokens[j + 2][0] != "string":
                        raise VersionError("Valor PHP de versión no es literal.")
                    found.append(tokens[j + 2][1])
            j += 1
        if depth:
            raise VersionError("Array PHP sin cerrar.")
    return found


def _php_const_candidates(tokens: list[tuple[str, str]], key: str) -> list[str]:
    found: list[str] = []
    for i in range(len(tokens) - 2):
        if tokens[i] != ("word", "const") or tokens[i + 1] != ("word", key):
            continue
        if (tokens[i + 2] != ("symbol", "=") or i + 4 >= len(tokens)
                or tokens[i + 3][0] != "string"
                or tokens[i + 4] != ("symbol", ";")):
            raise VersionError("Constante PHP de versión no literal.")
        found.append(tokens[i + 3][1])
    return found


def _unique_php_version(values: list[str]) -> str:
    if len(set(values)) > 1:
        raise VersionError("Definiciones PHP de versión contradictorias.")
    return values[0] if values else ""


def php_array_value(text: str, key: str) -> str:
    return _unique_php_version(_php_array_candidates(_php_tokens(text), key))


def php_const_value(text: str, key: str) -> str:
    return _unique_php_version(_php_const_candidates(_php_tokens(text), key))


def php_auto_value(text: str, key: str) -> str:
    tokens = _php_tokens(text)
    return _unique_php_version(
        _php_array_candidates(tokens, key) + _php_const_candidates(tokens, key)
    )

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
        value = php_auto_value(text, key)

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
