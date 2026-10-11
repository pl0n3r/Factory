#!/usr/bin/env python3
"""Lint puro de claims propuestos; NO verifica el árbol ni concede reservas.

Los directorios legacy continúan gestionados por el coordinador existente:
esta biblioteca se usa solo en la preparación de nuevas hojas.
"""
from __future__ import annotations

import re
import unicodedata

MAX_PATHS_PER_LEAF = 6
MAX_INPUT_PATHS = 64
MAX_PATH_LENGTH = 240
_CANONICAL_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
_GLOBS = frozenset("*?[]{}")
_SHARED_NAMES = frozenset({
    "readme.md", "package.json", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "composer.lock", "poetry.lock", "cargo.lock",
    "gemfile.lock", "uv.lock", "pipfile.lock", "bun.lock", "bun.lockb",
    "npm-shrinkwrap.json",
})


def _report(
    *, valid: bool, reason_codes: list[str],
    needs_partition: bool = False,
    proposed_groups: list[list[str]] | None = None,
    shared_integration_paths: list[str] | None = None,
) -> dict[str, object]:
    """Salida cerrada: nunca devuelve permiso para /tomar."""
    return {
        "valid": valid,
        "reason_codes": reason_codes,
        "needs_partition": needs_partition,
        "proposed_groups": proposed_groups if proposed_groups is not None else [],
        "shared_integration_paths": (
            shared_integration_paths if shared_integration_paths is not None else []
        ),
        "can_reserve": False,
    }


def _path_problem(path: object) -> str | None:
    if type(path) is not str or not 1 <= len(path) <= MAX_PATH_LENGTH:
        return "invalid_path"
    if path.endswith("/"):
        return "directory_claim"
    if any(char in _GLOBS for char in path):
        return "glob_claim"
    if _CANONICAL_PATH.fullmatch(path) is None:
        return "invalid_path"
    # Win32 silently aliases trailing dots and reserves device basenames,
    # including names with extensions, in every directory component.
    devices = {"con", "prn", "aux", "nul"} | {
        prefix + str(number)
        for prefix in ("com", "lpt") for number in range(1, 10)
    }
    for part in path.split("/"):
        if part in ("", ".", "..") or part.endswith("."):
            return "invalid_path"
        if part.split(".", 1)[0].casefold() in devices:
            return "invalid_path"
    return None


def _shared(path: str) -> bool:
    lower = path.lower()
    return lower.rsplit("/", 1)[-1] in _SHARED_NAMES or any(
        lower == version_path or lower.endswith("/" + version_path)
        for version_path in ("config/version.php", "config/version.json")
    )


def inspect_claim_paths(paths: object) -> dict[str, object]:
    """Preflight sintáctico fail-closed sobre rutas; no consulta GitHub ni FS.

    'valid' solamente describe un conjunto pequeño con sintaxis de archivo.
    Aun con valid=True, el caller DEBE probar archivo real, SHA, ausencia de
    solapamientos, dependencias y reserva canónica antes de escribir código.
    'proposed_groups' son recomendaciones NO AUTORIZADAS, nunca hojas ready.
    """
    if type(paths) is not list or not 1 <= len(paths) <= MAX_INPUT_PATHS:
        return _report(valid=False, reason_codes=["invalid_input_size"])

    errors: set[str] = set()
    seen: set[str] = set()
    accepted: list[str] = []
    for path in paths:
        problem = _path_problem(path)
        if problem is not None:
            errors.add(problem)
            continue
        # Cross-platform aliases must never appear as independent claims.
        key = unicodedata.normalize("NFC", path).casefold()
        if key in seen:
            errors.add("duplicate_path")
        seen.add(key)
        accepted.append(path)

    if errors:
        # La entrada no confiable no reaparece en ningún error ni en propuestas.
        return _report(valid=False, reason_codes=sorted(errors))

    ordered = sorted(accepted)
    shared = [path for path in ordered if _shared(path)]
    if len(ordered) > MAX_PATHS_PER_LEAF:
        groups = [
            ordered[i:i + MAX_PATHS_PER_LEAF]
            for i in range(0, len(ordered), MAX_PATHS_PER_LEAF)
        ]
        return _report(
            valid=False, reason_codes=["too_many_paths"], needs_partition=True,
            proposed_groups=groups, shared_integration_paths=shared,
        )
    return _report(valid=True, reason_codes=[], shared_integration_paths=shared)
