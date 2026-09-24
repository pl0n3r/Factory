#!/usr/bin/env python3
"""Lectura confinada de archivos pertenecientes al checkout actual."""
from __future__ import annotations
from pathlib import Path

DEFAULT_MAX_BYTES = 2_000_000

class SafeIOError(ValueError):
    pass

def resolve_repo_file(path: Path, *, root: Path | None = None, max_bytes: int = DEFAULT_MAX_BYTES) -> Path:
    base = (root or Path.cwd()).resolve()
    candidate_input = Path(path)
    if candidate_input.is_absolute() or ".." in candidate_input.parts:
        raise SafeIOError("La ruta debe ser relativa y no puede contener '..'.")
    if max_bytes < 1:
        raise SafeIOError("max_bytes debe ser positivo.")
    current = base
    for part in candidate_input.parts:
        current = current / part
        if current.is_symlink():
            raise SafeIOError("No se permiten enlaces simbólicos.")
    try:
        candidate = current.resolve(strict=True)
        candidate.relative_to(base)
    except (OSError, ValueError) as exc:
        raise SafeIOError("La ruta no pertenece al checkout permitido.") from exc
    if not candidate.is_file():
        raise SafeIOError("La ruta debe apuntar a un archivo regular.")
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise SafeIOError("No se pudo inspeccionar el archivo.") from exc
    if size > max_bytes:
        raise SafeIOError(f"El archivo supera el máximo de {max_bytes} bytes.")
    return candidate

def read_repo_text(path: Path, *, root: Path | None = None, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    resolved = resolve_repo_file(path, root=root, max_bytes=max_bytes)
    try:
        return resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SafeIOError("El archivo no es UTF-8 legible.") from exc
